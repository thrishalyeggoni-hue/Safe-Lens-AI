import ipaddress
import re
from urllib.parse import urlsplit, urlunsplit, quote

import idna
import tldextract

# Bundled Public Suffix List: no blocking network update during URL parsing.
extract_domain = tldextract.TLDExtract(suffix_list_urls=(), include_psl_private_domains=True)


def normalize_url(raw_url: str) -> dict:
    if not isinstance(raw_url, str) or not raw_url.strip():
        raise ValueError('URL cannot be empty')
    value = raw_url.strip()
    if len(value) > 4096 or re.search(r'[\x00-\x20\x7f\\]', value):
        raise ValueError('URL contains whitespace, control characters, backslashes, or exceeds 4096 characters')
    if '://' not in value:
        value = 'https://' + value
    try:
        parsed = urlsplit(value)
        if parsed.scheme.lower() not in ('http', 'https'):
            raise ValueError('Only HTTP and HTTPS URLs are supported')
        host = (parsed.hostname or '').rstrip('.')
        if not host or '%' in host:
            raise ValueError('Invalid or scoped hostname')
        try:
            host = str(ipaddress.ip_address(host))
            is_ip = True
        except ValueError:
            host = idna.encode(host, uts46=True, std3_rules=True).decode().lower()
            is_ip = False
        port = parsed.port
        if port is not None and not 1 <= port <= 65535:
            raise ValueError('Port must be between 1 and 65535')
    except (ValueError, idna.IDNAError) as exc:
        raise ValueError(f'Invalid URL: {exc}') from None
    scheme = parsed.scheme.lower()
    authority = f'[{host}]' if ':' in host else host
    if port and port != (443 if scheme == 'https' else 80):
        authority += f':{port}'
    url = urlunsplit((scheme, authority, quote(parsed.path or '/', safe="/%:@!$&'()*+,;=-._~"), quote(parsed.query, safe="%/:?@!$&'()*+,;=-._~"), ''))
    ext = extract_domain(host)
    return {'normalized_url': url, 'hostname': host, 'registered_domain': ext.top_domain_under_public_suffix or None,
            'subdomain': ext.subdomain, 'is_ip': is_ip, 'embedded_credentials': parsed.username is not None,
            'port': port, 'unicode_hostname': idna.decode(host) if not is_ip else host}


def validate_and_normalize_url(raw_url: str) -> str:
    return normalize_url(raw_url)['normalized_url']
