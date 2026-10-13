"""Deterministic Link Check. See docs/link-check.md for the verdict policy."""
from urllib.parse import urlsplit

from .url_normalizer import normalize_url, validate_and_normalize_url, extract_domain
from .dns_service import resolve_dns, now, is_forbidden_ip
from .redirect_service import inspect_redirects
from .rdap_service import lookup_rdap
from .reputation_service import lookup_reputation

KNOWN_BRANDS = ('paypal', 'apple', 'google', 'microsoft', 'amazon', 'netflix', 'facebook', 'binance', 'sbi', 'hdfc', 'icici', 'paytm')
SHORTENERS = {'bit.ly', 't.co', 'tinyurl.com', 'is.gd', 'ow.ly', 'rb.gy', 'shorturl.at'}


def url_indicators(parsed):
    indicators = []
    def add(code, observation):
        indicators.append({'code': code, 'source': 'Deterministic URL heuristic', 'observation': observation,
                           'interpretation': 'Weak structural indicator; not proof of maliciousness.',
                           'action': 'Verify the exact domain and source before sharing information or paying.', 'risk_level': 'Caution'})
    host = parsed['hostname']
    ext = extract_domain(host)
    if parsed['is_ip']:
        add('ip_hostname', 'The hostname is a literal IP address, not a domain name.')
    if parsed['port'] not in (None, 80, 443):
        add('unusual_port', f"URL specifies nonstandard port {parsed['port']}; network inspection is restricted to ports 80 and 443.")
    if parsed['embedded_credentials']:
        add('credentials', 'URL contains embedded credentials. They were stripped and were not sent to any destination or provider.')
    if ext.subdomain.count('.') >= 3:
        add('subdomains', f'Hostname contains {ext.subdomain.count(".") + 1} subdomain labels.')
    if len(host) > 100:
        add('long_hostname', f'Hostname contains {len(host)} characters.')
    if any(label.startswith('xn--') for label in host.split('.')):
        add('idn', f"Internationalized hostname: {parsed['unicode_hostname']} (canonical: {host}). IDNs are legitimate, but can need closer inspection.")
    if host in SHORTENERS:
        add('shortener', 'Known URL-shortener domain conceals the final destination until redirects are inspected.')
    if any(brand in ext.subdomain.lower() and brand not in ext.domain.lower() for brand in KNOWN_BRANDS):
        add('brand_subdomain', f"Brand Impersonation indicator: a familiar brand appears only in a subdomain; registered domain is {parsed['registered_domain']}.")
    if ext.domain.count('-') >= 4:
        add('domain_structure', 'Registered domain contains at least four hyphens.')
    if urlsplit(parsed['normalized_url']).scheme == 'http':
        add('unencrypted', 'URL uses HTTP, which does not encrypt traffic.')
    return indicators


def decide_risk(dns, rdap, reputation, redirects, indicators):
    if any(item['status'] == 'listed' for item in reputation.get('lookups', [reputation])):
        return 'High Risk', 'Google Web Risk reported an authoritative threat match. Do not interact with this destination.'
    if dns['status'] == 'blocked' or redirects['status'] == 'blocked':
        return 'Unable to Assess', 'Inspection was blocked because a destination resolves to non-public network space. No blocked destination was requested.'
    meaningful = [indicator for indicator in indicators if indicator.get('code') != 'new_registration']
    if meaningful:
        return 'Caution', f'{len(meaningful)} explainable structural indicator(s) require verification. These are heuristics, not proof of maliciousness.'
    complete = dns['status'] == 'resolved' and rdap['status'] == 'available' and reputation['status'] == 'not_listed' and redirects['status'] == 'completed'
    if complete:
        return 'Low Risk', 'All required checks completed without a known threat match or significant structural indicator. Not listed does not mean safe; no automated tool guarantees safety.'
    return 'Unable to Assess', 'Required checks are unavailable or inconclusive. The available evidence is insufficient to classify this URL as Low Risk.'


async def analyze_link(raw_url: str, on_stage=None) -> dict:
    def stage(name):
        if on_stage:
            on_stage(name)
    stage('Validating and normalizing URL')
    parsed = normalize_url(raw_url)
    url = parsed['normalized_url']
    indicators = url_indicators(parsed)
    stage('Resolving A and AAAA records and checking public addresses')
    dns = await resolve_dns(parsed['hostname'])
    if dns['status'] == 'resolved':
        stage('Looking up domain registration through IANA RDAP bootstrap')
        rdap = await lookup_rdap(parsed['registered_domain'])
        stage('Querying configured Google Web Risk reputation provider')
        reputation = await lookup_reputation(url)
        stage('Inspecting bounded redirects with validated public IPs')
        redirects = await inspect_redirects(url)
        visited = list(dict.fromkeys(hop['source'] for hop in redirects['chain'] if hop['status_code'] is not None))
        lookups = [reputation]
        if reputation['status'] != 'unavailable':
            for destination in visited:
                if destination != url:
                    stage('Checking reputation of an inspected redirect destination')
                    lookups.append(await lookup_reputation(destination))
        reputation = {**reputation, 'lookups': [{**item, 'url': destination} for item, destination in zip(lookups, [url] + [u for u in visited if u != url])],
                      'status': 'listed' if any(item['status'] == 'listed' for item in lookups) else 'unavailable' if any(item['status'] == 'unavailable' for item in lookups) else 'not_listed'}
        if redirects['redirect_count'] >= 2:
            indicators.append({'code': 'multiple_redirects', 'source': 'Deterministic redirect heuristic', 'observation': f"Observed {redirects['redirect_count']} redirects.", 'interpretation': 'Multiple redirects can obscure a destination, but are not proof of maliciousness.', 'action': 'Verify the final destination.', 'risk_level': 'Caution'})
        # Evaluate structure at every followed hop, not just the first URL.
        for destination in visited:
            if destination != url:
                for indicator in url_indicators(normalize_url(destination)):
                    indicator['observation'] = f"At {destination}: {indicator['observation']}"
                    if not any(i['code'] == indicator['code'] for i in indicators):
                        indicators.append(indicator)
        if rdap.get('age_days', 365) < 30:
            indicators.append({'code': 'new_registration', 'source': 'RDAP-derived weak heuristic', 'observation': f"Domain was registered {rdap['age_days']} days ago according to {rdap['source_url']}.", 'interpretation': 'New registrations can be legitimate. Age alone does not establish maliciousness.', 'action': 'Independently verify the organization.', 'risk_level': 'Caution'})
    else:
        reason = 'Skipped because destination DNS validation failed or was blocked'
        rdap = {'status': 'unavailable', 'provider': 'IANA RDAP bootstrap', 'lookup_time': now(), 'error': reason}
        reputation = {'status': 'unavailable', 'provider': 'Google Web Risk Lookup API', 'lookup_time': now(), 'error': reason, 'threats': []}
        redirects = {'status': 'blocked' if dns['status'] == 'blocked' else 'unavailable', 'provider': 'httpx public-IP validation', 'lookup_time': now(), 'error': reason, 'chain': [], 'redirect_count': 0, 'final_url': url, 'downloaded_body_bytes': 0}
    stage('Combining factual observations with documented risk policy')
    risk, explanation = decide_risk(dns, rdap, reputation, redirects, indicators)
    performed, unavailable = [], []
    def check(name, status, detail, successful):
        row = {'name': name, 'status': status, 'detail': detail}
        (performed if successful else unavailable).append(row)
    check('URL normalization / bundled Public Suffix List', 'passed', f"Canonical host: {parsed['hostname']}; registered domain: {parsed['registered_domain'] or 'not applicable'}", True)
    check('DNS / public address validation', 'passed' if dns['status'] == 'resolved' else 'flagged' if dns['status'] == 'blocked' else 'unavailable', ', '.join(dns['addresses']) if dns['status'] == 'resolved' else dns.get('error', 'Unavailable'), dns['status'] in ('resolved', 'blocked'))
    check('RDAP registration', 'passed' if rdap['status'] == 'available' else 'unavailable', f"Retrieved from {rdap.get('source_url')}" if rdap['status'] == 'available' else rdap.get('error', 'Unavailable'), rdap['status'] == 'available')
    reputation_errors = [r.get('error', 'Unavailable') for r in reputation.get('lookups', [reputation]) if r['status'] == 'unavailable']
    check('Google Web Risk Lookup API', 'flagged' if reputation['status'] == 'listed' else 'passed' if reputation['status'] == 'not_listed' else 'unavailable', 'Listed threat reported by this reputation provider' if reputation['status'] == 'listed' else 'Not listed by this reputation provider' if reputation['status'] == 'not_listed' else '; '.join(reputation_errors), reputation['status'] in ('listed', 'not_listed'))
    if reputation['status'] == 'listed' and reputation_errors:
        unavailable.append({'name': 'Additional redirect reputation lookups', 'status': 'unavailable', 'detail': '; '.join(reputation_errors)})
    check('Safe HEAD redirect inspection', 'passed' if redirects['status'] == 'completed' else 'flagged' if redirects['status'] == 'blocked' else 'unavailable', f"{redirects['redirect_count']} redirects; final URL: {redirects['final_url']}" if redirects['status'] == 'completed' else redirects.get('error', 'Unavailable'), redirects['status'] in ('completed', 'blocked'))
    check('Deterministic URL heuristics', 'flagged' if indicators else 'passed', f'{len(indicators)} weak indicator(s); no AI interpretation', True)
    findings = [{k: v for k, v in indicator.items() if k != 'code'} for indicator in indicators]
    if reputation['status'] == 'listed':
        findings.insert(0, {'source': 'Google Web Risk Lookup API', 'observation': 'Provider threat match: ' + ', '.join(sorted({t for r in reputation.get('lookups', [reputation]) for t in r.get('threats', [])})), 'interpretation': 'Authoritative reputation match, not a heuristic.', 'action': 'Do not open this destination or provide information.', 'risk_level': 'High Risk'})
    observations = {'dns': dns, 'rdap': rdap, 'reputation': reputation, 'redirects': redirects}
    return {'module_type': 'link', 'input_summary': url, 'normalized_url': url, 'hostname': parsed['hostname'], 'registered_domain': parsed['registered_domain'],
            'risk_category': risk, 'explanation': explanation, 'findings': findings,
            'evidence': [{'source_type': 'URL normalization', 'snippet': url, 'detail': 'Actual submitted URL; fragment and embedded credentials omitted.'}],
            'checks_performed': performed, 'unavailable_checks': unavailable, 'heuristic_findings': indicators,
            'recommended_actions': ['Verify the source and exact domain independently.', 'Do not share OTPs, passwords, or pay based on an unsolicited link.', 'A reputation non-match does not guarantee safety.'],
            'score': None, 'checked_at': now(), **observations,
            'provider_info': {'engine': 'SafeLens deterministic Link Inspector v2', 'tldextract_version': __import__('tldextract').__version__, 'registered_domain': parsed['registered_domain'], 'target_host': parsed['hostname'], 'link_analysis': {**observations, 'normalized_url': url, 'hostname': parsed['hostname'], 'registered_domain': parsed['registered_domain'], 'heuristic_findings': indicators, 'checked_at': now()}}}


# Keep callers from other threat modules compatible with the hardened inspector.
trace_redirects_safely = inspect_redirects
