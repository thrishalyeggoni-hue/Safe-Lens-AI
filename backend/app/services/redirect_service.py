import asyncio
from urllib.parse import urlsplit, urljoin

import httpx

from .dns_service import resolve_dns, now
from .url_normalizer import normalize_url

MAX_REDIRECTS = 4
MAX_JSON_BYTES = 1024 * 1024


async def pinned_request(client, url, dns_result, method='HEAD'):
    parsed = urlsplit(url)
    # Connect to the validated literal IP. DNS cannot change between validation
    # and connection. Preserve the original Host and certificate/SNI hostname.
    target = httpx.URL(url).copy_with(host=dns_result['addresses'][0])
    async with client.stream(method, target, headers={'Host': parsed.netloc, 'User-Agent': 'SafeLens-Link-Inspector/2.0', 'Accept-Encoding': 'identity'},
                             extensions={'sni_hostname': parsed.hostname}) as response:
        body = b''
        if method != 'HEAD':
            async for chunk in response.aiter_raw():
                if len(body) + len(chunk) > MAX_JSON_BYTES:
                    raise ValueError('Response exceeded the 1 MiB limit')
                body += chunk
        return response.status_code, dict(response.headers), body


async def inspect_redirects(start_url: str, max_hops=MAX_REDIRECTS) -> dict:
    result = {'provider': 'httpx / pinned public IP / verified TLS / HEAD only', 'lookup_time': now(), 'status': 'unavailable',
              'chain': [], 'final_url': start_url, 'redirect_count': 0, 'downloaded_body_bytes': 0}
    current = start_url
    seen = set()
    try:
        async with asyncio.timeout(15), httpx.AsyncClient(timeout=3, follow_redirects=False, trust_env=False) as client:
            for hop in range(max_hops + 1):
                parsed = normalize_url(current)
                current = parsed['normalized_url']
                if parsed['embedded_credentials']:
                    raise ValueError('Redirect containing embedded credentials was not followed')
                if parsed['port'] not in (None, 80, 443):
                    raise ValueError('Only ports 80 and 443 are permitted for inspection')
                if current in seen:
                    raise ValueError('Redirect loop detected')
                seen.add(current)
                dns_result = await resolve_dns(parsed['hostname'])
                entry = {'source': current, 'status_code': None, 'destination': None, 'resolved_addresses': dns_result['addresses'], 'lookup_time': now()}
                result['chain'].append(entry)
                if dns_result['status'] != 'resolved':
                    entry.update(blocked=dns_result['status'] == 'blocked', error=dns_result.get('error', 'DNS unavailable'))
                    result.update(status='blocked' if entry['blocked'] else 'unavailable', error=entry['error'], final_url=current)
                    return result
                try:
                    status, headers, _ = await pinned_request(client, current, dns_result)
                except Exception as exc:
                    entry['error'] = type(exc).__name__
                    raise ValueError(entry['error']) from None
                entry['status_code'] = status
                result['final_url'] = current
                if status in (301, 302, 303, 307, 308):
                    destination = headers.get('location')
                    if not destination:
                        raise ValueError('Redirect did not provide a Location header')
                    next_url = urljoin(current, destination)
                    # Record original destination, even when validation will block it.
                    entry['destination'] = next_url
                    if hop == max_hops:
                        raise ValueError(f'Redirect limit ({max_hops}) reached')
                    result['redirect_count'] += 1
                    current = next_url
                elif 200 <= status < 300:
                    result['status'] = 'completed'
                    return result
                else:
                    raise ValueError(f'HTTP {status}; inspection is inconclusive (no GET fallback)')
    except Exception as exc:
        result['error'] = str(exc) if isinstance(exc, ValueError) else type(exc).__name__
        if result['chain']:
            result['chain'][-1].setdefault('error', result['error'])
    return result


async def fetch_public_json(url: str) -> tuple[dict, str]:
    """Bounded JSON requests for IANA/RDAP, validating and pinning each redirect."""
    current = url
    async with asyncio.timeout(12), httpx.AsyncClient(timeout=4, follow_redirects=False, trust_env=False) as client:
        for _ in range(4):
            parsed = normalize_url(current)
            if parsed['embedded_credentials'] or parsed['port'] not in (None, 80, 443):
                raise ValueError('RDAP service URL is not permitted')
            current = parsed['normalized_url']
            resolved = await resolve_dns(parsed['hostname'])
            if resolved['status'] != 'resolved':
                raise ValueError(resolved.get('error', 'RDAP service DNS unavailable'))
            status, headers, body = await pinned_request(client, current, resolved, 'GET')
            if status in (301, 302, 303, 307, 308) and headers.get('location'):
                current = urljoin(current, headers['location'])
                continue
            if status != 200:
                raise ValueError(f'HTTP {status}' + (' (rate limited)' if status == 429 else ''))
            import json
            data = json.loads(body)
            if not isinstance(data, dict):
                raise ValueError('JSON response must be an object')
            return data, current
    raise ValueError('RDAP service redirect limit reached')
