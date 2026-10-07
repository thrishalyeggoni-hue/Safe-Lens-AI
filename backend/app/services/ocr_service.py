import os
import re
from typing import Dict, Any, List
from PIL import Image, ImageEnhance, ImageOps
import pytesseract
from .url_service import analyze_link
from .message_service import analyze_message
from ..schemas import FindingItem, CheckItem, EvidenceItem

URL_REGEX = re.compile(r'(?:https?://|www\.)[^\s<>"\'{}|\\^`]+', re.IGNORECASE)
UPI_REGEX = re.compile(r'[a-zA-Z0-9.\-_]{2,256}@[a-zA-Z]{2,64}')

def preprocess_image(image: Image.Image) -> Image.Image:
    """Improve contrast and grayscale for OCR clarity."""
    try:
        gray = ImageOps.grayscale(image)
        enhancer = ImageEnhance.Contrast(gray)
        enhanced = enhancer.enhance(1.8)
        return enhanced
    except Exception:
        return image

async def analyze_screenshot(image_path: str, original_filename: str) -> Dict[str, Any]:
    evidence: List[EvidenceItem] = []
    findings: List[FindingItem] = []
    checks_performed: List[CheckItem] = []
    unavailable_checks: List[CheckItem] = []
    recommended_actions: List[str] = []

    try:
        with Image.open(image_path) as img:
            width, height = img.size
            format_name = img.format or "IMAGE"
            processed_img = preprocess_image(img)
            
            # 1. OCR Extraction using Tesseract
            try:
                ocr_data = pytesseract.image_to_data(processed_img, output_type=pytesseract.Output.DICT)
                extracted_words = []
                confidences = []
                
                n_boxes = len(ocr_data['text'])
                for i in range(n_boxes):
                    word = ocr_data['text'][i].strip()
                    conf = int(ocr_data['conf'][i])
                    if word and conf > 0:
                        extracted_words.append(word)
                        confidences.append(conf)
                        
                extracted_text = " ".join(extracted_words)
                avg_confidence = round(sum(confidences) / len(confidences), 1) if confidences else 0.0
                
            except Exception as ocr_err:
                extracted_text = ""
                avg_confidence = 0.0
                checks_performed.append(CheckItem(
                    name="Optical Character Recognition (OCR)",
                    status="unavailable",
                    detail=f"OCR engine failure: {str(ocr_err)}"
                ))

    except Exception as img_err:
        return {
            "module_type": "screenshot",
            "input_summary": original_filename,
            "risk_category": "Unable to Assess",
            "explanation": f"Unable to decode image container: {str(img_err)}",
            "findings": [],
            "evidence": [],
            "checks_performed": [CheckItem(name="Image Container Decoding", status="flagged", detail=str(img_err))],
            "unavailable_checks": [],
            "recommended_actions": ["Upload a standard PNG, JPG, or WebP screenshot."],
            "score": 0,
            "provider_info": {"engine": "SafeLens Screenshot Inspector"}
        }

    checks_performed.append(CheckItem(
        name="Image Container Decoding",
        status="passed",
        detail=f"Decoded {format_name} image ({width}x{height}px)"
    ))

    if not extracted_text:
        checks_performed.append(CheckItem(
            name="Optical Character Recognition (OCR)",
            status="inconclusive",
            detail="No readable textual content or payment receipts identified in this screenshot"
        ))
        return {
            "module_type": "screenshot",
            "input_summary": f"{original_filename} ({width}x{height}px)",
            "risk_category": "Unable to Assess",
            "explanation": "No readable text or payment details could be extracted from this image. SafeLens does not infer low risk from OCR absence.",
            "findings": [],
            "evidence": [EvidenceItem(snippet="No text detected", source_type="ocr", detail=f"{width}x{height}px")],
            "checks_performed": checks_performed,
            "unavailable_checks": unavailable_checks,
            "recommended_actions": ["Ensure the screenshot has clear, unblurred text and adequate contrast."],
            "score": 20,
            "provider_info": {
                "engine": "SafeLens Tesseract OCR v5.5",
                "ocr_confidence": 0.0
            }
        }

    checks_performed.append(CheckItem(
        name="Optical Character Recognition (OCR)",
        status="passed",
        detail=f"Extracted {len(extracted_words)} words with average confidence {avg_confidence}%"
    ))

    evidence.append(EvidenceItem(
        snippet=extracted_text[:200] + ("..." if len(extracted_text) > 200 else ""),
        source_type="ocr",
        detail=f"OCR confidence: {avg_confidence}% across {len(extracted_words)} words"
    ))

    # 2. Check for extracted URLs
    found_urls = URL_REGEX.findall(extracted_text)
    if found_urls:
        checks_performed.append(CheckItem(
            name="Visual URL Extraction",
            status="flagged",
            detail=f"Detected {len(found_urls)} URL(s) rendered in image"
        ))
        for url in found_urls[:2]:
            link_eval = await analyze_link(url)
            for f in link_eval.get("findings", []):
                findings.append(FindingItem(
                    source=f"Visible URL ({url})",
                    observation=f.get("observation", ""),
                    interpretation=f.get("interpretation", ""),
                    action=f.get("action", ""),
                    risk_level=f.get("risk_level", "Caution")
                ))
    else:
        checks_performed.append(CheckItem(
            name="Visual URL Extraction",
            status="passed",
            detail="No web URLs detected in screenshot text"
        ))

    # 3. Check for Payment VPA / UPI / Transaction Lures
    vpa_matches = UPI_REGEX.findall(extracted_text)
    # filter out common email addresses if not typical UPI banks
    upi_handles = [v for v in vpa_matches if any(bank in v.lower() for bank in ["@ok", "@paytm", "@ibl", "@ybl", "@axl", "@sbi", "@icici", "@hdfc"])]
    if upi_handles:
        findings.append(FindingItem(
            source="Visual Payment Identifier",
            observation=f"Payment VPA / UPI handle detected: {', '.join(upi_handles)}.",
            interpretation="Receipts or requests displaying personal UPI handles should be verified against official merchant settlement channels.",
            action="Do not approve reverse charge or collect requests sent to this UPI handle.",
            risk_level="Caution"
        ))
        checks_performed.append(CheckItem(
            name="Payment Identifier Check",
            status="flagged",
            detail=f"Found UPI identifier(s): {', '.join(upi_handles)}"
        ))
    else:
        checks_performed.append(CheckItem(
            name="Payment Identifier Check",
            status="passed",
            detail="No unstructured UPI handles or payment collect requests found"
        ))

    # 4. Contextual Analysis of Extracted Text
    msg_analysis = await analyze_message(extracted_text)
    for f in msg_analysis.get("findings", []):
        findings.append(FindingItem(
            source=f"Screenshot Context ({f.get('source', '')})",
            observation=f.get("observation", ""),
            interpretation=f.get("interpretation", ""),
            action=f.get("action", ""),
            risk_level=f.get("risk_level", "Caution")
        ))
    for act in msg_analysis.get("recommended_actions", []):
        if act not in recommended_actions:
            recommended_actions.append(act)

    # Determine risk category
    has_high = any(f.risk_level == "High Risk" for f in findings)
    has_caution = any(f.risk_level == "Caution" for f in findings)

    if has_high:
        risk_category = "High Risk"
        explanation = "The screenshot displays high-risk indicators such as known phishing URLs, credential requests, or fraudulent advance fee lures."
        score = 85
    elif has_caution:
        risk_category = "Caution"
        explanation = "The screenshot contains urgency cues, unverified payment handles, or suspicious wording that requires caution."
        score = 55
    else:
        risk_category = "Low Risk"
        explanation = "No overt fraudulent lures, suspicious URLs, or urgent payment coercion identified in the visible text."
        score = 15

    return {
        "module_type": "screenshot",
        "input_summary": f"{original_filename} ({width}x{height}px)",
        "risk_category": risk_category,
        "explanation": explanation,
        "findings": [f.model_dump() for f in findings],
        "evidence": [e.model_dump() for e in evidence],
        "checks_performed": [c.model_dump() for c in checks_performed],
        "unavailable_checks": [u.model_dump() for u in unavailable_checks],
        "recommended_actions": recommended_actions or ["Review all transaction numbers directly on the official banking app."],
        "score": score,
        "provider_info": {
            "engine": "SafeLens Tesseract OCR v5.5",
            "ocr_confidence": avg_confidence,
            "words_extracted": len(extracted_words)
        }
    }
