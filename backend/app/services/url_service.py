import re
import ipaddress
import socket
from typing import Dict, Any, List, Optional
from urllib.parse import urlparse, urljoin
import httpx
import tldextract
import dns.resolver
from ..config import settings
from ..schemas import FindingItem, CheckItem, EvidenceItem

HOMOGLYPH_MAP = {
    'а': 'a', 'с': 'c', 'е': 'e', 'о': 'o', 'р': 'p', 'х': 'x', 'у': 'y',
    '1': 'i', '0': 'o', '5': 's', '3': 'e', '8': 'b',
}

KNOWN_BRANDS = [
    "paypal", "apple", "google", "microsoft", "amazon", "netflix", "facebook",
    "instagram", "whatsapp", "telegram", "binance", "coinbase", "chase",
    "wellsfargo", "bankofamerica", "sbi", "hdfc", "icici", "paytm", "phonepe"
]

def is_ip_address(hostname: str) -> bool:
    try:
        ipaddress.ip_address(hostname)
        return True
    except ValueError:
        return False

def is_forbidden_ip(ip_str: str) -> bool:
    try:
        ip = ipaddress.ip_address(ip_str)
        return ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast
    except ValueError:
        return True

def validate_and_normalize_url(raw_url: str) -> str:
    url = raw_url.strip()
    if not url:
        raise ValueError("URL cannot be empty")
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    parsed = urlparse(url)
    if not parsed.hostname:
        raise ValueError(f"Invalid domain or hostname in URL: {raw_url}")
    return url

async def check_google_safe_browsing(url: str) -> Optional[Dict[str, Any]]:
    if not settings.SAFE_BROWSING_API_KEY:
        return None
    api_url = f"https://safebrowsing.googleapis.com/v4/threatMatches:find?key={settings.SAFE_BROWSING_API_KEY}"
    payload = {
        "client": {
            "clientId": "safelens-ai",
            "clientVersion": "1.0.0"
        },
        "threatInfo": {
            "threatTypes": ["MALWARE", "SOCIAL_ENGINEERING", "UNWANTED_SOFTWARE", "POTENTIALLY_HARMFUL_APPLICATION"],
            "platformTypes": ["ANY_PLATFORM"],
            "threatEntryTypes": ["URL"],
            "threatEntries": [{"url": url}]
        }
    }
    try:
        async with httpx.AsyncClient(timeout=4.0) as client:
            resp = await client.post(api_url, json=payload)
            if resp.status_code == 200:
                data = resp.json()
                matches = data.get("matches", [])
                if matches:
                    threat_types = [m.get("threatType") for m in matches]
                    return {
                        "listed": True,
                        "threats": threat_types,
                        "detail": f"Listed by Google Safe Browsing: {', '.join(threat_types)}"
                    }
                return {
                    "listed": False,
                    "detail": "Not listed on Google Safe Browsing threat database"
                }
    except Exception as e:
        return {"error": str(e), "detail": "Safe Browsing request timed out or unavailable"}
    return None

async def trace_redirects_safely(start_url: str, max_hops: int = 5) -> Dict[str, Any]:
    hops = []
    current_url = start_url
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) SafeLensSecurityScanner/1.0",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
    }
    
    async with httpx.AsyncClient(timeout=4.0, verify=False, follow_redirects=False) as client:
        for hop_index in range(max_hops):
            parsed = urlparse(current_url)
            host = parsed.hostname
            if not host:
                break
                
            # DNS resolution & SSRF check
            try:
                ip_list = socket.gethostbyname_ex(host)[2]
                for ip in ip_list:
                    if is_forbidden_ip(ip):
                        return {
                            "error": f"Security restriction: redirect destination resolves to private or loopback IP ({ip})",
                            "hops": hops,
                            "final_url": current_url,
                            "aborted_ssrf": True
                        }
            except Exception:
                pass
                
            try:
                resp = await client.head(current_url, headers=headers)
                status = resp.status_code
                hops.append({
                    "hop": hop_index + 1,
                    "url": current_url,
                    "status_code": status
                })
                
                if 300 <= status < 400 and "location" in resp.headers:
                    next_url = urljoin(current_url, resp.headers["location"])
                    if next_url == current_url:
                        break
                    current_url = next_url
                else:
                    break
            except Exception as e:
                hops.append({
                    "hop": hop_index + 1,
                    "url": current_url,
                    "status_code": "failed",
                    "error": str(e)
                })
                break
                
    return {
        "hops": hops,
        "final_url": current_url,
        "hop_count": len(hops)
    }

def analyze_url_heuristics(url: str, extract_res: Any) -> List[Dict[str, Any]]:
    findings = []
    parsed = urlparse(url)
    hostname = parsed.hostname or ""
    subdomain = extract_res.subdomain
    domain = extract_res.domain
    suffix = extract_res.suffix
    registered_domain = f"{domain}.{suffix}" if domain and suffix else hostname

    # Check 1: Raw IP used as host
    if is_ip_address(hostname):
        findings.append({
            "source": "URL Structure Analysis",
            "observation": f"URL uses raw IP address '{hostname}' instead of a registered domain name.",
            "interpretation": "Legitimate websites overwhelmingly use registered domain names. IP URLs often bypass basic domain-based security filters.",
            "action": "Do not enter passwords or personal details on raw IP web pages.",
            "risk_level": "High Risk"
        })

    # Check 2: Brand Impersonation / Typosquatting in subdomain or domain
    for brand in KNOWN_BRANDS:
        if brand in subdomain.lower() and brand not in domain.lower():
            findings.append({
                "source": "Brand Impersonation Detection",
                "observation": f"The brand name '{brand}' appears in the subdomain '{subdomain}', but the registered domain is '{registered_domain}'.",
                "interpretation": f"Attackers frequently craft subdomains mimicking recognized companies (e.g. {brand}.fake-site.com) to deceive users into assuming brand authority.",
                "action": f"Check whether the official domain is {brand}.com before interacting.",
                "risk_level": "High Risk"
            })
            break

    # Check 3: Lookalike characters / Leetspeak / Homoglyphs
    homoglyphs_found = []
    for char, canonical in HOMOGLYPH_MAP.items():
        if char in domain and any(b in domain.replace(char, canonical) for b in KNOWN_BRANDS):
            homoglyphs_found.append(f"'{char}' instead of '{canonical}'")
    
    if homoglyphs_found:
        findings.append({
            "source": "Homoglyph & Deceptive Lookalike Detection",
            "observation": f"Potential lookalike character substitution detected in domain '{domain}': {', '.join(homoglyphs_found)}.",
            "interpretation": "Typosquatting and homoglyphs are used to deceive the human eye into mistaking a fraudulent website for a legitimate brand.",
            "action": "Do not proceed. Type the URL manually into your browser address bar.",
            "risk_level": "High Risk"
        })

    # Check 4: Suspicious path keywords indicating credential lure
    path_query = (parsed.path + "?" + parsed.query).lower()
    lure_patterns = ["login", "signin", "verify", "update-payment", "secure-account", "wallet", "seed-phrase", "claim-reward", "otp"]
    matched_lures = [pat for pat in lure_patterns if pat in path_query]
    if matched_lures and not any(b in registered_domain for b in KNOWN_BRANDS):
        findings.append({
            "source": "Path & Endpoint Pattern Check",
            "observation": f"Path and query contain sensitive authentication lures: {', '.join(matched_lures)}.",
            "interpretation": "Sensitive credential collection keywords on unfamiliar domains are a primary indicator of phishing landing pages.",
            "action": "Never provide credentials, seed phrases, or OTPs on links received unexpectedly.",
            "risk_level": "Caution"
        })

    # Check 5: Internationalized Domain Name (Punycode / xn--)
    if hostname.startswith("xn--") or ".xn--" in hostname:
        findings.append({
            "source": "Internationalized Domain (IDN) Check",
            "observation": f"Hostname '{hostname}' uses Punycode encoding.",
            "interpretation": "Punycode permits non-ASCII unicode characters which can closely resemble standard latin letters (IDN homograph attack).",
            "action": "Inspect the decoded unicode characters carefully.",
            "risk_level": "Caution"
        })

    return findings

async def analyze_link(raw_url: str) -> Dict[str, Any]:
    url = validate_and_normalize_url(raw_url)
    ext = tldextract.extract(url)
    hostname = (urlparse(url).hostname or "").lower()
    registered_domain = f"{ext.domain}.{ext.suffix}" if ext.domain and ext.suffix else hostname

    evidence: List[EvidenceItem] = [
        EvidenceItem(
            snippet=url,
            source_type="text",
            detail=f"Normalized URL: {url} (Host: {hostname})"
        )
    ]
    findings: List[FindingItem] = []
    checks_performed: List[CheckItem] = []
    unavailable_checks: List[CheckItem] = []
    recommended_actions: List[str] = [
        "Do not enter passwords or banking details if this URL arrived unsolicited.",
        "Check that the address bar shows the exact official domain name."
    ]

    # 1. DNS Resolution Check
    dns_records = []
    try:
        answers = dns.resolver.resolve(hostname, 'A', lifetime=2.0)
        dns_records = [str(rdata) for rdata in answers]
        checks_performed.append(CheckItem(
            name="DNS Resolution Check",
            status="passed",
            detail=f"Host resolved to {len(dns_records)} IP addresses ({', '.join(dns_records[:3])})"
        ))
    except Exception as e:
        checks_performed.append(CheckItem(
            name="DNS Resolution Check",
            status="flagged",
            detail=f"Domain failed DNS resolution: {type(e).__name__}"
        ))
        findings.append(FindingItem(
            source="DNS Resolution",
            observation=f"The domain '{hostname}' could not be resolved through standard DNS.",
            interpretation="The domain may have been newly created, suspended by a registrar, or abandoned.",
            action="Do not attempt to access or load payloads from unresolvable domains.",
            risk_level="Caution"
        ))

    # 2. Redirect Traversal
    redirect_res = await trace_redirects_safely(url, max_hops=4)
    if redirect_res.get("aborted_ssrf"):
        findings.append(FindingItem(
            source="Network Sandbox Protection",
            observation="Redirect trace blocked: target points to internal/private IP space.",
            interpretation="Potential Server-Side Request Forgery (SSRF) attempt targeting internal infrastructure.",
            action="Access blocked by security sandbox.",
            risk_level="High Risk"
        ))
        checks_performed.append(CheckItem(
            name="HTTP Redirect Path Traversal",
            status="flagged",
            detail="Redirects to private/internal network IP"
        ))
    elif redirect_res.get("hops"):
        hop_count = redirect_res.get("hop_count", 1)
        final_url = redirect_res.get("final_url", url)
        status_str = "passed" if hop_count <= 2 else "flagged"
        checks_performed.append(CheckItem(
            name="HTTP Redirect Path Traversal",
            status=status_str,
            detail=f"{hop_count} hop(s) detected. Final destination: {final_url}"
        ))
        if hop_count > 2:
            findings.append(FindingItem(
                source="HTTP Redirect Chain",
                observation=f"URL performed {hop_count} consecutive redirect hops to reach '{final_url}'.",
                interpretation="Excessive redirect chains are commonly deployed by phishing kits to conceal the real destination from automated scanners.",
                action="Verify the final landing page rather than the initial shortened or intermediary link.",
                risk_level="Caution"
            ))

    # 3. Google Safe Browsing Check
    gsb_res = await check_google_safe_browsing(url)
    if gsb_res is None:
        unavailable_checks.append(CheckItem(
            name="Google Safe Browsing Reputation",
            status="unavailable",
            detail="API key not configured in environment (SAFE_BROWSING_API_KEY)"
        ))
    elif gsb_res.get("listed"):
        checks_performed.append(CheckItem(
            name="Google Safe Browsing Reputation",
            status="flagged",
            detail=gsb_res.get("detail", "Listed threat")
        ))
        findings.append(FindingItem(
            source="Google Safe Browsing",
            observation=f"URL is actively flagged on Google Safe Browsing as: {', '.join(gsb_res.get('threats', []))}.",
            interpretation="Verified threat intelligence record indicating confirmed malicious activity or phishing distribution.",
            action="Close the tab immediately. Do not download or interact with content from this site.",
            risk_level="High Risk"
        ))
    else:
        checks_performed.append(CheckItem(
            name="Google Safe Browsing Reputation",
            status="passed",
            detail="Not currently listed in Google Safe Browsing database"
        ))

    # 4. Deterministic Heuristics
    heuristic_findings = analyze_url_heuristics(url, ext)
    for hf in heuristic_findings:
        findings.append(FindingItem(**hf))

    checks_performed.append(CheckItem(
        name="Domain & URL Structure Heuristics",
        status="flagged" if heuristic_findings else "passed",
        detail=f"{len(heuristic_findings)} structural warning(s) identified" if heuristic_findings else "No anomalous structure or homoglyph patterns detected"
    ))

    # Determine Overall Risk Category
    has_high = any(f.risk_level == "High Risk" for f in findings)
    has_caution = any(f.risk_level == "Caution" for f in findings)
    
    if has_high:
        risk_category = "High Risk"
        explanation = f"SafeLens identified critical indicators on '{registered_domain}', including potential brand impersonation, deceptive lookalike characters, or threat listings."
        score = 88
    elif has_caution:
        risk_category = "Caution"
        explanation = f"SafeLens identified anomalous patterns on '{registered_domain}' that warrant caution before interacting or submitting data."
        score = 55
    else:
        risk_category = "Low Risk"
        explanation = f"No immediate suspicious structure, deceptive homoglyphs, or active threat listings found for '{registered_domain}'."
        score = 15

    return {
        "module_type": "link",
        "input_summary": url,
        "risk_category": risk_category,
        "explanation": explanation,
        "findings": [f.model_dump() for f in findings],
        "evidence": [e.model_dump() for e in evidence],
        "checks_performed": [c.model_dump() for c in checks_performed],
        "unavailable_checks": [u.model_dump() for u in unavailable_checks],
        "recommended_actions": recommended_actions,
        "score": score,
        "provider_info": {
            "tldextract_version": getattr(tldextract, "__version__", "5.x"),
            "registered_domain": registered_domain,
            "target_host": hostname,
            "engine": "SafeLens Link Inspector v1.0"
        }
    }
