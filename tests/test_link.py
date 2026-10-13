import json
import pytest
import httpx
from backend.app.services import url_service, redirect_service, dns_service, rdap_service, reputation_service
from backend.app.services.url_normalizer import normalize_url, validate_and_normalize_url


@pytest.mark.parametrize('url', ['', 'ftp://example.com', 'https://', 'https://bad host.com', 'https://example.com:99999', 'https://[::1%25en0]', 'https://exa\\mple.com'])
def test_malformed_url(url):
    with pytest.raises(ValueError):
        normalize_url(url)


def test_normalization_idn_credentials():
    assert validate_and_normalize_url('example.com') == 'https://example.com/'
    result = normalize_url('HTTPS://user:secret@BÜCHER.de:443/path#fragment')
    assert result['normalized_url'] == 'https://xn--bcher-kva.de/path'
    assert result['embedded_credentials']
    assert result['registered_domain'] == 'xn--bcher-kva.de'
    assert normalize_url('http://[2606:4700:4700::1111]/')['is_ip']


@pytest.mark.asyncio
@pytest.mark.parametrize('host', ['localhost', 'test.localhost', '127.0.0.1', '10.0.0.1', '172.16.0.1', '192.168.1.1', '169.254.169.254', '::1', 'fc00::1', 'fe80::1', '::ffff:8.8.8.8', '0.0.0.0'])
async def test_private_literal_blocked(host):
    assert (await dns_service.resolve_dns(host))['status'] == 'blocked'


@pytest.mark.asyncio
async def test_validate_all_dns_addresses(monkeypatch):
    async def resolve(host, kind, **kwargs):
        return ['8.8.8.8', '10.0.0.1'] if kind == 'A' else ['2606:4700:4700::1111']
    monkeypatch.setattr(dns_service.dns.asyncresolver, 'resolve', resolve)
    result = await dns_service.resolve_dns('example.com')
    assert result['status'] == 'blocked'
    assert result['blocked_addresses'] == ['10.0.0.1']


@pytest.mark.asyncio
async def test_failed_dns_not_requested(monkeypatch):
    async def resolve(host, kind, **kwargs):
        raise dns_service.dns.resolver.NXDOMAIN()
    monkeypatch.setattr(dns_service.dns.asyncresolver, 'resolve', resolve)
    result = await dns_service.resolve_dns('missing.invalid')
    assert result['status'] == 'unavailable'
    async def unavailable(host):
        return result
    async def forbidden(*args, **kwargs):
        pytest.fail('Network request after failed resolution')
    monkeypatch.setattr(redirect_service, 'resolve_dns', unavailable)
    monkeypatch.setattr(redirect_service, 'pinned_request', forbidden)
    assert (await redirect_service.inspect_redirects('https://missing.invalid'))['status'] == 'unavailable'


@pytest.mark.asyncio
async def test_redirect_to_private_blocked(monkeypatch):
    requests = []
    async def resolve(host):
        if host == '169.254.169.254':
            return {'status': 'blocked', 'addresses': [host], 'error': 'Non-public destination blocked'}
        return {'status': 'resolved', 'addresses': ['8.8.8.8']}
    async def request(client, url, resolved, method='HEAD'):
        requests.append(url)
        return 302, {'location': 'http://169.254.169.254/latest/meta-data/'}, b''
    monkeypatch.setattr(redirect_service, 'resolve_dns', resolve)
    monkeypatch.setattr(redirect_service, 'pinned_request', request)
    result = await redirect_service.inspect_redirects('https://example.com/')
    assert result['status'] == 'blocked'
    assert requests == ['https://example.com/']
    assert result['chain'][-1]['blocked']
    assert result['chain'][0]['destination'].startswith('http://169.254')


@pytest.mark.asyncio
async def test_connection_pins_ip_and_preserves_tls_identity():
    def handle(request):
        assert request.method == 'HEAD'
        assert request.url.host == '8.8.8.8'
        assert request.headers['host'] == 'example.com'
        assert request.extensions['sni_hostname'] == 'example.com'
        return httpx.Response(200)
    async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as client:
        status, _, body = await redirect_service.pinned_request(client, 'https://example.com/', {'addresses': ['8.8.8.8']})
        assert status == 200
        assert body == b''


@pytest.mark.asyncio
async def test_rebinding_revalidated(monkeypatch):
    calls = []
    async def resolve(host):
        calls.append(host)
        return {'status': 'resolved', 'addresses': ['8.8.8.8']} if len(calls) == 1 else {'status': 'blocked', 'addresses': ['127.0.0.1'], 'error': 'Blocked'}
    async def request(*args):
        return 302, {'location': '/second'}, b''
    monkeypatch.setattr(redirect_service, 'resolve_dns', resolve)
    monkeypatch.setattr(redirect_service, 'pinned_request', request)
    result = await redirect_service.inspect_redirects('https://example.com/')
    assert result['status'] == 'blocked'
    assert calls == ['example.com', 'example.com']


def test_risk_policy():
    good = {'status': 'resolved'}
    rdap = {'status': 'available'}
    rep = {'status': 'not_listed'}
    redirects = {'status': 'completed'}
    assert url_service.decide_risk(good, rdap, rep, redirects, [])[0] == 'Low Risk'
    assert url_service.decide_risk(good, rdap, {'status': 'unavailable'}, redirects, [])[0] == 'Unable to Assess'
    assert url_service.decide_risk(good, {'status': 'unavailable'}, rep, redirects, [])[0] == 'Unable to Assess'
    assert url_service.decide_risk(good, rdap, rep, {'status': 'unavailable'}, [])[0] == 'Unable to Assess'
    assert url_service.decide_risk(good, rdap, {'status': 'listed'}, redirects, [])[0] == 'High Risk'
    assert url_service.decide_risk(good, rdap, rep, redirects, [{'code': 'new_registration'}])[0] == 'Low Risk'
    for url in ['https://8.8.8.8', 'https://xn--bcher-kva.de', 'https://paypal.example.com', 'https://example.com:8080']:
        assert url_service.decide_risk(good, rdap, rep, redirects, url_service.url_indicators(normalize_url(url)))[0] == 'Caution'


@pytest.mark.asyncio
async def test_rdap_missing_not_fabricated(monkeypatch):
    monkeypatch.setattr(rdap_service, '_bootstrap', {'services': []})
    monkeypatch.setattr(rdap_service, '_bootstrap_time', __import__('time').monotonic())
    result = await rdap_service.lookup_rdap('example.invalid')
    assert result['status'] == 'unavailable'
    assert 'registration_date' not in result
    assert 'age_days' not in result


@pytest.mark.asyncio
async def test_reputation_missing_key(monkeypatch):
    monkeypatch.setattr(reputation_service.settings, 'GOOGLE_WEB_RISK_API_KEY', '')
    assert (await reputation_service.lookup_reputation('https://example.com'))['status'] == 'unavailable'


@pytest.mark.asyncio
@pytest.mark.parametrize('payload,status,expected', [({},200,'not_listed'), ({'threat': {'threatTypes': ['MALWARE']}},200,'listed'), ({},429,'unavailable'), ({},503,'unavailable'), ({'threat': {}},200,'unavailable'), ({'error': {'code': 400}},200,'unavailable')])
async def test_reputation_provider_response(monkeypatch, payload, status, expected):
    monkeypatch.setattr(reputation_service.settings, 'GOOGLE_WEB_RISK_API_KEY', 'test-only-secret')
    real_client = httpx.AsyncClient
    def handle(request):
        assert request.headers['x-goog-api-key'] == 'test-only-secret'
        assert 'test-only-secret' not in str(request.url)
        assert request.url.params['uri'] == 'http://testsafebrowsing.appspot.com/s/malware.html'
        return httpx.Response(status, stream=httpx.ByteStream(json.dumps(payload).encode()))
    monkeypatch.setattr(reputation_service.httpx, 'AsyncClient', lambda **kwargs: real_client(transport=httpx.MockTransport(handle)))
    result = await reputation_service.lookup_reputation('http://testsafebrowsing.appspot.com/s/malware.html')
    assert result['status'] == expected
    assert 'test-only-secret' not in json.dumps(result)
    if expected == 'not_listed':
        assert result['detail'] == 'Not listed by this reputation provider'


@pytest.mark.asyncio
async def test_redirect_limit(monkeypatch):
    async def resolve(host):
        return {'status': 'resolved', 'addresses': ['8.8.8.8']}
    async def request(client, url, resolved, method='HEAD'):
        return 302, {'location': url.rstrip('/') + '/next'}, b''
    monkeypatch.setattr(redirect_service, 'resolve_dns', resolve)
    monkeypatch.setattr(redirect_service, 'pinned_request', request)
    result = await redirect_service.inspect_redirects('https://example.com/')
    assert result['status'] == 'unavailable'
    assert 'limit' in result['error']
    assert len(result['chain']) == 5
