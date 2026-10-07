import re
from typing import Dict, Any, List
from .url_service import analyze_link
from .ai_service import query_ollama_qwen
from ..schemas import FindingItem, CheckItem, EvidenceItem

URL_REGEX = re.compile(r'(?:https?://|www\.)[^\s<>"\'{}|\\^`]+', re.IGNORECASE)

OFFER_INDICATORS = [
    {
        "category": "Advance Fee / Deposit Demand",
        "regex": re.compile(r'\b(registration\s+fee|processing\s+charge|security\s+deposit|equipment\s+fee|laptop\s+deposit|pay\s+before\s+(start|work|join))\b', re.I),
        "observation": "Offer requires the job applicant or buyer to pay an upfront fee or deposit.",
        "interpretation": "Reputable employers and legitimate gigs never charge candidates for job placement, hardware, or onboarding.",
        "action": "Do not pay any onboarding or registration fee. Stop communication immediately.",
        "risk_level": "High Risk"
    },
    {
        "category": "Guaranteed Unrealistic ROI / Yield",
        "regex": re.compile(r'\b(guaranteed\s+(return|profit|yield)|100%\s+daily|no\s+risk|risk[-\s]free\s+investment|earn\s+₹?\d{4,}\s+per\s+day\s+from\s+home|daily\s+payouts\s+assured)\b', re.I),
        "observation": "Claim of guaranteed high returns with zero financial risk.",
        "interpretation": "All legitimate investments carry risk. Guarantees of effortless high yields or instant daily wealth are the defining trait of Ponzi and task scams.",
        "action": "Avoid speculative yield platforms and unverified investment groups.",
        "risk_level": "High Risk"
    },
    {
        "category": "Task / Rating Scam Mechanism",
        "regex": re.compile(r'\b(like\s+youtube\s+videos|rate\s+google\s+maps|hotel\s+reviews\s+part\s+time|telegram\s+task|crypto\s+recharge|task\s+completion\s+reward)\b', re.I),
        "observation": "Offer involves repetitive low-skill tasks (liking videos, writing fake reviews) coordinated via messaging channels.",
        "interpretation": "Known 'task scam' modus operandi. Victims receive small initial payouts before being coerced into large deposits to unlock earnings.",
        "action": "Do not deposit money into tasks platforms claiming to pay for likes or ratings.",
        "risk_level": "High Risk"
    },
    {
        "category": "High Pressure Recruitment",
        "regex": re.compile(r'\b(only\s+\d+\s+slots\s+left|urgent\s+hiring\s+today|start\s+in\s+1\s+hour|no\s+interview\s+required|immediate\s+selection)\b', re.I),
        "observation": "Offer uses artificial scarcity and skips standard interview or vetting procedures.",
        "interpretation": "Pressure tactics prevent candidates from conducting due diligence on the hiring entity.",
        "action": "Request a formal offer letter on official corporate letterhead and verify the HR contact independently.",
        "risk_level": "Caution"
    }
]

async def analyze_offer(offer_text: str) -> Dict[str, Any]:
    text = offer_text.strip()
    if not text:
        return {
            "module_type": "offer",
            "input_summary": "Empty offer text",
            "risk_category": "Unable to Assess",
            "explanation": "No offer text was supplied.",
            "findings": [],
            "evidence": [],
            "checks_performed": [],
            "unavailable_checks": [],
            "recommended_actions": ["Paste the job, investment, or shopping offer text."],
            "score": 0,
            "provider_info": {"engine": "SafeLens Offer Analyzer"}
        }

    evidence: List[EvidenceItem] = []
    findings: List[FindingItem] = []
    checks_performed: List[CheckItem] = []
    unavailable_checks: List[CheckItem] = []
    recommended_actions: List[str] = [
        "Never transfer money to secure employment.",
        "Verify job openings directly on the official company careers portal."
    ]

    # 1. Content adequacy
    checks_performed.append(CheckItem(
        name="Offer Text Parsing",
        status="passed",
        detail=f"Parsed {len(text.split())} words"
    ))

    # 2. Extract and check URLs
    found_urls = URL_REGEX.findall(text)
    if found_urls:
        checks_performed.append(CheckItem(
            name="Offer Destination Link Check",
            status="flagged",
            detail=f"Extracted {len(found_urls)} link(s)"
        ))
        for url in found_urls[:2]:
            link_eval = await analyze_link(url)
            for f in link_eval.get("findings", []):
                findings.append(FindingItem(
                    source=f"Offer Link ({url})",
                    observation=f.get("observation", ""),
                    interpretation=f.get("interpretation", ""),
                    action=f.get("action", ""),
                    risk_level=f.get("risk_level", "Caution")
                ))
    else:
        checks_performed.append(CheckItem(
            name="Offer Destination Link Check",
            status="passed",
            detail="No external links present in offer text"
        ))

    # 3. Deterministic Offer Patterns
    for ind in OFFER_INDICATORS:
        match = ind["regex"].search(text)
        if match:
            start, end = match.span()
            snippet = text[start:end]
            evidence.append(EvidenceItem(
                snippet=snippet,
                source_type="text",
                text_offset={"start": start, "end": end},
                detail=f"Matched: {ind['category']}"
            ))
            findings.append(FindingItem(
                source=f"Offer Heuristic ({ind['category']})",
                observation=f"{ind['observation']} (Excerpt: \"{snippet}\")",
                interpretation=ind["interpretation"],
                action=ind["action"],
                risk_level=ind["risk_level"]
            ))

    checks_performed.append(CheckItem(
        name="Recruitment & Investment Fraud Detector",
        status="flagged" if findings else "passed",
        detail=f"Scanned for advance-fee recruitment, Ponzi yield guarantees, and rating task patterns"
    ))

    # 4. Local AI (Qwen) contextual reasoning if available
    qwen_eval = await query_ollama_qwen(
        prompt=f"Assess this offer for employment, shopping, or investment fraud:\n\"\"\"{text}\"\"\"",
        system_prompt="You are SafeLens AI. Return JSON: {\"is_fraudulent\": bool, \"findings\": [\"reason1\"], \"action\": \"string\"}"
    )
    if qwen_eval:
        checks_performed.append(CheckItem(
            name="Local Qwen Semantic Reasoning",
            status="flagged" if qwen_eval.get("is_fraudulent") else "passed",
            detail=f"Qwen evaluation completed"
        ))
    else:
        unavailable_checks.append(CheckItem(
            name="Local Qwen Semantic Reasoning",
            status="unavailable",
            detail="Ollama daemon is not currently running locally on port 11434"
        ))

    # Determine risk category
    has_high = any(f.risk_level == "High Risk" for f in findings)
    has_caution = any(f.risk_level == "Caution" for f in findings)

    if has_high:
        risk_category = "High Risk"
        explanation = "The offer exhibits unmistakable signs of recruitment or financial fraud, including advance fee demands or guaranteed risk-free yields."
        score = 90
    elif has_caution:
        risk_category = "Caution"
        explanation = "The offer contains pressure cues or unverified claims that require independent verification before committing funds or personal data."
        score = 55
    else:
        risk_category = "Low Risk"
        explanation = "No overt advance-fee demands, task scam patterns, or guaranteed return claims detected."
        score = 15

    return {
        "module_type": "offer",
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
            "engine": "SafeLens Offer Integrity Inspector v1.0",
            "qwen_integrated": qwen_eval is not None
        }
    }
