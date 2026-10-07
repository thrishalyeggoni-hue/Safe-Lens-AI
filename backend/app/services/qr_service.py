import urllib.parse
from typing import Dict, Any, List
from PIL import Image
import zxingcpp
from .url_service import analyze_link
from ..schemas import FindingItem, CheckItem, EvidenceItem

def parse_upi_payload(payload: str) -> Dict[str, Any]:
    """Parse UPI payment payload parameters."""
    parsed = urllib.parse.urlparse(payload)
    params = urllib.parse.parse_qs(parsed.query)
    vpa = params.get("pa", [""])[0]
    payee_name = params.get("pn", [""])[0]
    amount = params.get("am", [""])[0]
    currency = params.get("cu", ["INR"])[0]
    note = params.get("tn", [""])[0]
    return {
        "vpa": vpa,
        "payee_name": payee_name,
        "amount": amount,
        "currency": currency,
        "transaction_note": note
    }

def classify_qr_payload(raw_text: str) -> Dict[str, Any]:
    text = raw_text.strip()
    if text.startswith(("http://", "https://", "www.")):
        return {"type": "URL", "destination": text}
    if text.startswith("upi://pay"):
        upi_details = parse_upi_payload(text)
        return {"type": "UPI_PAYMENT", "destination": text, "details": upi_details}
    if text.startswith("WIFI:"):
        return {"type": "WIFI_CONFIG", "destination": text}
    if text.startswith("BEGIN:VCARD"):
        return {"type": "CONTACT_VCARD", "destination": text}
    return {"type": "PLAIN_TEXT", "destination": text}

async def analyze_qr_image(image_path: str, original_filename: str) -> Dict[str, Any]:
    evidence: List[EvidenceItem] = []
    findings: List[FindingItem] = []
    checks_performed: List[CheckItem] = []
    unavailable_checks: List[CheckItem] = []
    recommended_actions: List[str] = [
        "Never approve payment requests or scan QRs on incoming calls.",
        "Always review the destination payload before executing."
    ]

    try:
        with Image.open(image_path) as img:
            results = zxingcpp.read_barcodes(img)
    except Exception as e:
        return {
            "module_type": "qr",
            "input_summary": original_filename,
            "risk_category": "Unable to Assess",
            "explanation": f"Unable to read image file: {str(e)}",
            "findings": [],
            "evidence": [],
            "checks_performed": [CheckItem(name="Image Ingestion", status="flagged", detail=str(e))],
            "unavailable_checks": [],
            "recommended_actions": ["Upload a clear image containing a QR code."],
            "score": 0,
            "provider_info": {"engine": "SafeLens ZXing-C++ QR Decoder"}
        }

    if not results:
        checks_performed.append(CheckItem(
            name="Matrix Optical Decoding",
            status="inconclusive",
            detail="No valid QR matrix or barcode symbols detected in image"
        ))
        return {
            "module_type": "qr",
            "input_summary": original_filename,
            "risk_category": "Unable to Assess",
            "explanation": "No QR code could be detected or decoded in the uploaded file. SafeLens does not infer safety from an unreadable QR code.",
            "findings": [],
            "evidence": [EvidenceItem(snippet="No QR pattern found", source_type="qr")],
            "checks_performed": checks_performed,
            "unavailable_checks": [],
            "recommended_actions": [
                "Ensure the QR matrix is fully in frame, in focus, and adequately lit.",
                "Avoid steep perspective distortion."
            ],
            "score": 10,
            "provider_info": {"engine": "SafeLens ZXing-C++ QR Decoder"}
        }

    qr_item = results[0]
    payload = qr_item.text
    format_type = str(qr_item.format)
    classification = classify_qr_payload(payload)
    payload_type = classification["type"]

    checks_performed.append(CheckItem(
        name="Matrix Optical Decoding",
        status="passed",
        detail=f"Successfully decoded {format_type} symbol"
    ))
    checks_performed.append(CheckItem(
        name="Payload Classification",
        status="passed",
        detail=f"Payload identified as: {payload_type}"
    ))

    evidence.append(EvidenceItem(
        snippet=payload,
        source_type="qr",
        detail=f"Decoded payload ({payload_type}): {payload}"
    ))

    # Evaluate based on payload type
    if payload_type == "URL":
        findings.append(FindingItem(
            source="QR Destination Inspector",
            observation=f"QR points directly to web URL: '{payload}'.",
            interpretation="QR codes directing to external web pages should be pre-screened before navigation to avoid zero-click redirects or phishing sites.",
            action="Inspect URL safety analysis below before clicking.",
            risk_level="Caution"
        ))
        
        # Link Check on decoded URL!
        link_eval = await analyze_link(payload)
        for f in link_eval.get("findings", []):
            findings.append(FindingItem(
                source=f"QR Target ({f.get('source', '')})",
                observation=f.get("observation", ""),
                interpretation=f.get("interpretation", ""),
                action=f.get("action", ""),
                risk_level=f.get("risk_level", "Caution")
            ))
        for chk in link_eval.get("checks_performed", []):
            checks_performed.append(CheckItem(
                name=f"URL Target: {chk.get('name', '')}",
                status=chk.get("status", "passed"),
                detail=chk.get("detail", "")
            ))

    elif payload_type == "UPI_PAYMENT":
        details = classification.get("details", {})
        vpa = details.get("vpa", "unknown")
        payee = details.get("payee_name", "unspecified")
        amount = details.get("amount", "")
        
        findings.append(FindingItem(
            source="UPI Payment Payload Verification",
            observation=f"Payment QR encodes transfer to VPA '{vpa}' (Claimed Payee: '{payee}'{f', Amount: {amount}' if amount else ''}).",
            interpretation="Scanning a payment QR only sends money; it NEVER receives money. Fraudsters commonly claim 'scan this QR to receive cashback or refund'. Displayed payee names do not guarantee certified identity.",
            action="Remember: Scanning a QR code always debits your account. Never scan to receive funds.",
            risk_level="Caution"
        ))
        recommended_actions.extend([
            "Verify the merchant or person's name directly with them in person or out-of-band.",
            "Never enter your UPI PIN to receive money."
        ])

    elif payload_type == "WIFI_CONFIG":
        findings.append(FindingItem(
            source="Wi-Fi Configuration Payload",
            observation="QR encodes automated wireless network credentials.",
            interpretation="Connecting to untrusted or spoofed Wi-Fi networks enables local Man-In-The-Middle (MITM) network eavesdropping.",
            action="Only connect to known, trusted Wi-Fi networks.",
            risk_level="Caution"
        ))

    # Determine risk category
    has_high = any(f.risk_level == "High Risk" for f in findings)
    has_caution = any(f.risk_level == "Caution" for f in findings)

    if has_high:
        risk_category = "High Risk"
        explanation = "The QR code directs to a high-risk web destination or fraudulent endpoint."
        score = 85
    elif has_caution:
        risk_category = "Caution"
        explanation = f"Decoded {payload_type} payload. Review destination details before proceeding."
        score = 50
    else:
        risk_category = "Low Risk"
        explanation = "The QR matrix decoded safely and contains benign structured information."
        score = 15

    return {
        "module_type": "qr",
        "input_summary": f"{original_filename} ({payload_type})",
        "risk_category": risk_category,
        "explanation": explanation,
        "findings": [f.model_dump() for f in findings],
        "evidence": [e.model_dump() for e in evidence],
        "checks_performed": [c.model_dump() for c in checks_performed],
        "unavailable_checks": [u.model_dump() for u in unavailable_checks],
        "recommended_actions": recommended_actions,
        "score": score,
        "provider_info": {
            "engine": "SafeLens ZXing-C++ QR Decoder v3.1",
            "payload_type": payload_type,
            "raw_destination": payload
        }
    }
