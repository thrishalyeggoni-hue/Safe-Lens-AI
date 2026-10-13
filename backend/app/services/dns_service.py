import asyncio
import ipaddress
from datetime import datetime, timezone

import dns.asyncresolver
import dns.resolver


def now():
    return datetime.now(timezone.utc).isoformat()


def is_forbidden_ip(value: str) -> bool:
    try:
        ip = ipaddress.ip_address(value)
        # Reject mapped IPv6 addresses too; no transition-address tunneling.
        if isinstance(ip, ipaddress.IPv6Address) and (ip.ipv4_mapped or ip.sixtofour or ip.teredo):
            return True
        return not ip.is_global or ip.is_multicast
    except ValueError:
        return True


async def resolve_dns(hostname: str) -> dict:
    result = {'provider': 'dnspython / system-configured DNS resolver', 'lookup_time': now(), 'hostname': hostname,
              'status': 'unavailable', 'addresses': [], 'records': {}, 'errors': []}
    if hostname == 'localhost' or hostname.endswith(('.localhost', '.local', '.internal')):
        return {**result, 'status': 'blocked', 'error': 'Local/internal hostname is blocked'}
    try:
        ipaddress.ip_address(hostname)
        result.update(addresses=[hostname], records={'literal_ip': [hostname]}, provider='Python ipaddress (literal address)')
    except ValueError:
        async def query(kind):
            try:
                answers = await dns.asyncresolver.resolve(hostname, kind, lifetime=2.5, search=False)
                return kind, [str(answer) for answer in answers], None
            except dns.resolver.NoAnswer:
                return kind, [], None
            except Exception as exc:
                return kind, [], type(exc).__name__
        for kind, values, error in await asyncio.gather(query('A'), query('AAAA')):
            result['records'][kind] = values
            result['addresses'].extend(values)
            if error:
                result['errors'].append(f'{kind}: {error}')
    forbidden = [ip for ip in result['addresses'] if is_forbidden_ip(ip)]
    if forbidden:
        result.update(status='blocked', error='Non-public destination blocked', blocked_addresses=forbidden)
    elif result['errors']:
        # Fail closed: a partial resolution cannot validate every address family.
        result.update(status='unavailable', error='; '.join(result['errors']))
    elif result['addresses']:
        result['status'] = 'resolved'
    else:
        result['error'] = 'No A or AAAA addresses returned'
    return result
