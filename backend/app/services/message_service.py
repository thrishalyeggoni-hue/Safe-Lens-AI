import re
from typing import Dict, Any, List
from .url_service import analyze_link
from .ai_service import query_ollama_qwen
from ..schemas import FindingItem, CheckItem, EvidenceItem

URL_REGEX = re.compile(
    r'(?:https?://|www\.)[^\s<>"\'{}|\\^`]+',
    re.IGNORECASE
)

# Pattern dictionaries with explanation and risk level
LURE_PATTERNS = [
    {
        "category": "OTP / Credential Request",
        "regex": re.compile(r'\b(share|send|provide|verify|enter)\s+(the\s+|your\s+|this\s+|any\s+)?(otp|one[-\s]?time\s+password|pin|password|cvv|secret\s+code)\b', re.I),
        "observation": "Explicit request to share an OTP, PIN, or confidential security credential.",
        "interpretation": "Legitimate banking and support representatives never ask for OTPs or PINs. This is the primary signature of credential harvesting.",
        "action": "Never share OTPs or authentication codes with anyone, under any circumstances.",
        "risk_level": "High Risk"
    },
    {
        "category": "Artificial Urgency & Threat",
        "regex": re.compile(r'\b(account\s+(will\s+be|has\s+been|is)\s+(suspended|blocked|terminated|closed)|within\s+\d+\s+(hours?|mins?|minutes?)|immediate\s+action\s+required|electricity\s+power\s+cut|legal\s+notice\s+issued|arrest\s+warrant|incomplete\s+kyc|kyc\s+(suspended|blocked|pending|update))\b', re.I),
        "observation": "Coercive urgency threatening immediate account loss, service cutoff, or legal penalties.",
        "interpretation": "Social engineers induce cognitive overload using artificial deadlines so victims act impulsively without verifying.",
        "action": "Do not panic. Verify status independently by logging directly into the official portal.",
        "risk_level": "Caution"
    },
    {
        "category": "Advance Fee / Processing Charge",
        "regex": re.compile(r'\b(pay\s+(a\s+|the\s+)?(registration|processing|customs|refundable|security|verification)\s+(fee|deposit|charge)|send\s+₹?\d+\s+to\s+(claim|verify|reactivate)|deposit\s+₹?\d+|transfer\s+\$?\d+\s+first)\b', re.I),
        "observation": "Demand for an upfront payment or processing fee prior to receiving a prize, job, or service reactivation.",
        "interpretation": "Classic 419 / advance-fee scam mechanism. Genuine organizations and employers do not charge applicants or account holders upfront verification deposits.",
        "action": "Refuse all advance fee payments. Do not transfer funds.",
        "risk_level": "High Risk"
    },
    {
        "category": "Authority Impersonation",
        "regex": re.compile(r'\b(income\s+tax\s+department|customs\s+department|courier\s+service|fedex|dhl|postal\s+department|mbi|fbi|cyber\s+crime\s+cell|rbi|sbi|hdfc|icici|paytm|bank\s+account)\b', re.I),
        "observation": "Claiming authority from a financial institution, government body, or delivery service.",
        "interpretation": "Impersonating recognized institutions creates an artificial appearance of legitimacy and compliance pressure.",
        "action": "Confirm with the official customer care phone number found on the organization's verified website.",
        "risk_level": "Caution"
    },
    {
        "category": "Unusual Payment / Gift Cards / Crypto",
        "regex": re.compile(r'\b(google\s+play\s+card|apple\s+gift\s+card|steam\s+card|crypto|bitcoin|usdt|unverified\s+upi)\b', re.I),
        "observation": "Request for payment through gift cards, cryptocurrency, or irregular payment rails.",
        "interpretation": "Untraceable and irreversible payment methods are universally favored by fraud syndicates.",
        "action": "Government agencies and major corporations never accept gift cards or cryptocurrency as payment.",
        "risk_level": "High Risk"
    }
]

def detect_educational_context(text: str) -> bool:
    """Check if the text is quoting a scam for awareness or warning purposes."""
    lower = text.lower()
    educational_patterns = [
        r'\bbeware\s+of\s+(scams?|phishing|fraud)\b',
        r'\bscammers?\s+(often\s+)?(say|use|send)\b',
        r'\b(warning|caution|alert)\s*[:\-]\s*(fraud|scam|phishing)',
        r'\bexample\s+of\s+(phishing|scam|fraud)\b',
        r'\beducational\s+purposes?\b',
        r'\bdo\s+not\s+fall\s+for\b',
        r'\bsafety\s+tips?\b',
        r'\b(scam|fraud)\s+alert\b'
    ]
    return any(re.search(pat, lower) for pat in educational_patterns)

async def analyze_message(message_text: str) -> Dict[str, Any]:
    text = message_text.strip()
    if not text:
        return {
            "module_type": "message",
            "input_summary": "Empty message text",
            "risk_category": "Unable to Assess",
            "explanation": "No text content was provided for analysis.",
            "findings": [],
            "evidence": [],
            "checks_performed": [],
            "unavailable_checks": [],
            "recommended_actions": ["Submit a message containing text or links to assess."],
            "score": 0,
            "provider_info": {"engine": "SafeLens Message Analyzer"}
        }

    is_educational = detect_educational_context(text)
    findings: List[FindingItem] = []
    evidence: List[EvidenceItem] = []
    checks_performed: List[CheckItem] = []
    unavailable_checks: List[CheckItem] = []
    recommended_actions: List[str] = []

    # 1. Length & Language check
    if len(text) < 15:
        return {
            "module_type": "message",
            "input_summary": text,
            "risk_category": "Unable to Assess",
            "explanation": "The message is too brief to reliably distinguish conversational context from security threats.",
            "findings": [],
            "evidence": [EvidenceItem(snippet=text, source_type="text")],
            "checks_performed": [CheckItem(name="Content Adequacy Check", status="inconclusive", detail="Message under 15 characters")],
            "unavailable_checks": [],
            "recommended_actions": ["Provide the complete message including headers or sender context if possible."],
            "score": 10,
            "provider_info": {"engine": "SafeLens Message Analyzer"}
        }

    checks_performed.append(CheckItem(
        name="Content Adequacy Check",
        status="passed",
        detail=f"Analyzed {len(text)} characters across {len(text.split())} words"
    ))

    # 2. Extract and analyze embedded URLs
    found_urls = URL_REGEX.findall(text)
    if found_urls:
        checks_performed.append(CheckItem(
            name="Embedded URL Extraction",
            status="flagged",
            detail=f"Identified {len(found_urls)} URL(s) in message"
        ))
        for url in found_urls[:2]:
            link_eval = await analyze_link(url)
            for f_dict in link_eval.get("findings", []):
                findings.append(FindingItem(
                    source=f"Embedded Link ({url})",
                    observation=f_dict.get("observation", ""),
                    interpretation=f_dict.get("interpretation", ""),
                    action=f_dict.get("action", ""),
                    risk_level=f_dict.get("risk_level", "Caution")
                ))
            for ev in link_eval.get("evidence", []):
                evidence.append(EvidenceItem(
                    snippet=ev.get("snippet", url),
                    source_type="text",
                    detail=f"Embedded URL: {url}"
                ))
    else:
        checks_performed.append(CheckItem(
            name="Embedded URL Extraction",
            status="passed",
            detail="No embedded links found in text"
        ))

    # 3. Deterministic Lure Detection with text offsets
    for lure in LURE_PATTERNS:
        match = lure["regex"].search(text)
        if match:
            start, end = match.span()
            matched_snippet = text[start:end]
            evidence.append(EvidenceItem(
                snippet=matched_snippet,
                source_type="text",
                text_offset={"start": start, "end": end},
                detail=f"Matched: {lure['category']}"
            ))
            findings.append(FindingItem(
                source=f"Linguistic Pattern ({lure['category']})",
                observation=f"{lure['observation']} (Excerpt: \"{matched_snippet}\")",
                interpretation=lure["interpretation"],
                action=lure["action"],
                risk_level=lure["risk_level"]
            ))

    checks_performed.append(CheckItem(
        name="Social Engineering Pattern Scanner",
        status="flagged" if any(f.source.startswith("Linguistic") for f in findings) else "passed",
        detail=f"Scanned for OTP lures, artificial urgency, advance fees, and impersonation"
    ))

    # 4. Local AI (Qwen) contextual reasoning if available
    qwen_result = await query_ollama_qwen(
        prompt=f"Analyze this message for fraud indicators:\n\"\"\"{text}\"\"\"",
        system_prompt="You are SafeLens AI security evaluator. Return JSON: {\"is_suspicious\": bool, \"reason\": str, \"confidence\": str}"
    )
    if qwen_result:
        checks_performed.append(CheckItem(
            name="Local Qwen Semantic Reasoning",
            status="flagged" if qwen_result.get("is_suspicious") else "passed",
            detail=f"Qwen evaluation: {qwen_result.get('reason', '')}"
        ))
    else:
        unavailable_checks.append(CheckItem(
            name="Local Qwen Semantic Reasoning",
            status="unavailable",
            detail="Ollama daemon is not currently running locally on port 11434"
        ))

    # Handle educational context override
    if is_educational:
        findings.append(FindingItem(
            source="Contextual Awareness Filter",
            observation="Message appears to reference scams in an educational, warning, or quotation context.",
            interpretation="The text contains warning keywords ('beware', 'scam warning') suggesting it may be a shared advisory rather than an active attack.",
            action="Verify whether the forwarder is advising you of a risk.",
            risk_level="Informational"
        ))

    # Calculate overall risk
    has_high = any(f.risk_level == "High Risk" for f in findings)
    has_caution = any(f.risk_level == "Caution" for f in findings)

    if has_high and not is_educational:
        risk_category = "High Risk"
        explanation = "The message exhibits high-confidence deception signals, such as requests for sensitive security codes, advance fees, or suspicious embedded links."
        score = 85
        recommended_actions.extend([
            "Do not reply or click any links in this message.",
            "Never share OTPs, PINs, or bank details.",
            "Report and block the sender in your messaging app."
        ])
    elif has_caution or (has_high and is_educational):
        risk_category = "Caution"
        explanation = "The message contains potential pressure tactics or unverified institutional claims that require validation."
        score = 50
        recommended_actions.extend([
            "Contact the purported sender using their official public phone number, not numbers given in the text.",
            "Do not act immediately despite claims of urgency."
        ])
    else:
        risk_category = "Low Risk"
        explanation = "No deceptive social engineering lures, credential theft patterns, or flagged URLs detected in this text."
        score = 15
        recommended_actions.append("Practice normal security hygiene when receiving unexpected communications.")

    return {
        "module_type": "message",
        "input_summary": text[:80] + ("..." if len(text) > 80 else ""),
        "risk_category": risk_category,
        "explanation": explanation,
        "findings": [f.model_dump() for f in findings],
        "evidence": [e.model_dump() for e in evidence],
        "checks_performed": [c.model_dump() for c in checks_performed],
        "unavailable_checks": [u.model_dump() for u in unavailable_checks],
        "recommended_actions": recommended_actions,
        "score": score,
        "provider_info": {
            "engine": "SafeLens Linguistic Security Engine v1.0",
            "qwen_integrated": qwen_result is not None
        }
    }
