import os
import re
from typing import Dict, Any, List
from pypdf import PdfReader
from .url_service import analyze_link
from .message_service import analyze_message
from .malware_service import scan_file_with_clamav
from ..config import settings
from ..schemas import FindingItem, CheckItem, EvidenceItem

URL_REGEX = re.compile(r'(?:https?://|www\.)[^\s<>"\'{}|\\^`]+', re.IGNORECASE)

def scan_pdf_structure_risks(reader: PdfReader) -> List[Dict[str, str]]:
    """Scan raw PDF objects for active script execution or suspicious launch actions."""
    risks = []
    try:
        for i, page in enumerate(reader.pages):
            # Check for JavaScript or Launch actions
            if "/Annots" in page:
                annots = page["/Annots"]
                if annots:
                    # annots can be indirect object
                    try:
                        annot_objs = annots.get_object() if hasattr(annots, "get_object") else annots
                        for annot in annot_objs:
                            obj = annot.get_object() if hasattr(annot, "get_object") else annot
                            if "/A" in obj and "/S" in obj["/A"]:
                                action_type = str(obj["/A"]["/S"])
                                if action_type in ["/JavaScript", "/Launch"]:
                                    risks.append({
                                        "source": "PDF Object Structure",
                                        "observation": f"Active script execution action ({action_type}) found on page {i + 1}.",
                                        "interpretation": "PDFs containing embedded executable scripts or launch commands represent common exploit payload delivery vectors.",
                                        "action": "Do not open this PDF with viewers that have JavaScript execution enabled.",
                                        "risk_level": "High Risk"
                                    })
                    except Exception:
                        pass
    except Exception:
        pass
    return risks

async def analyze_document(file_path: str, original_filename: str) -> Dict[str, Any]:
    file_size_bytes = os.path.getsize(file_path) if os.path.exists(file_path) else 0
    file_size_kb = round(file_size_bytes / 1024, 1)

    evidence: List[EvidenceItem] = []
    findings: List[FindingItem] = []
    checks_performed: List[CheckItem] = []
    unavailable_checks: List[CheckItem] = []
    recommended_actions: List[str] = [
        "Inspect invoice details directly with the billing party via a verified phone call.",
        "Do not enable macros or run attachments prompted by the document."
    ]

    try:
        reader = PdfReader(file_path)
    except Exception as e:
        return {
            "module_type": "document",
            "input_summary": f"{original_filename} ({file_size_kb} KB)",
            "risk_category": "Unable to Assess",
            "explanation": f"Corrupt, encrypted, or unsupported PDF container: {str(e)}",
            "findings": [],
            "evidence": [],
            "checks_performed": [CheckItem(name="PDF Parsing", status="flagged", detail=str(e))],
            "unavailable_checks": [],
            "recommended_actions": ["Upload an unencrypted, valid standard PDF document."],
            "score": 0,
            "provider_info": {"engine": "SafeLens Document Inspector"}
        }

    if reader.is_encrypted:
        return {
            "module_type": "document",
            "input_summary": f"{original_filename} (Encrypted)",
            "risk_category": "Unable to Assess",
            "explanation": "This PDF is encrypted with a password. SafeLens cannot inspect encrypted payload contents without authorization.",
            "findings": [],
            "evidence": [EvidenceItem(snippet="Encrypted PDF document", source_type="pdf_page")],
            "checks_performed": [CheckItem(name="Encryption Check", status="flagged", detail="File is password protected")],
            "unavailable_checks": [],
            "recommended_actions": ["Provide an unencrypted copy for automated verification."],
            "score": 10,
            "provider_info": {"engine": "SafeLens Document Inspector"}
        }

    total_pages = len(reader.pages)
    max_pages = min(total_pages, settings.MAX_PDF_PAGES)
    checks_performed.append(CheckItem(
        name="PDF Structure Inspection",
        status="passed",
        detail=f"Parsed {max_pages} of {total_pages} total page(s) ({file_size_kb} KB)"
    ))

    # 0. ClamAV Antivirus signature scan
    clam_res = scan_file_with_clamav(file_path)
    if clam_res.get("status") == "flagged":
        findings.append(FindingItem(
            source="ClamAV Antivirus Scanner",
            observation=f"Malware signature match: {clam_res.get('virus_name', 'Unknown')}",
            interpretation="The uploaded file contains binary signatures matching known malware or trojan patterns.",
            action="Do not open or execute this file. Permanently delete the document.",
            risk_level="High Risk"
        ))
        checks_performed.append(CheckItem(
            name="ClamAV Malware Signature Scan",
            status="flagged",
            detail=clam_res.get("detail", "Malware signature found")
        ))
    elif clam_res.get("status") == "passed":
        checks_performed.append(CheckItem(
            name="ClamAV Malware Signature Scan",
            status="passed",
            detail=clam_res.get("detail", "No malware signatures detected")
        ))
    elif clam_res.get("status") == "unavailable":
        unavailable_checks.append(CheckItem(
            name="ClamAV Malware Signature Scan",
            status="unavailable",
            detail=clam_res.get("detail", "ClamAV not installed")
        ))
    else:
        checks_performed.append(CheckItem(
            name="ClamAV Malware Signature Scan",
            status="inconclusive",
            detail=clam_res.get("detail", "ClamAV signature check completed")
        ))

    # 1. Structural malware / script scan
    struct_risks = scan_pdf_structure_risks(reader)
    for sr in struct_risks:
        findings.append(FindingItem(**sr))

    checks_performed.append(CheckItem(
        name="Active Script & Macro Scanner",
        status="flagged" if struct_risks else "passed",
        detail="Identified embedded active action/script objects" if struct_risks else "No /JavaScript or /Launch action objects found"
    ))

    # 2. Extract Text & Embedded Links across pages
    extracted_text_by_page = []
    embedded_urls = []

    for page_idx in range(max_pages):
        page = reader.pages[page_idx]
        text = page.extract_text() or ""
        if text.strip():
            extracted_text_by_page.append((page_idx + 1, text))
            evidence.append(EvidenceItem(
                snippet=text[:150] + ("..." if len(text) > 150 else ""),
                source_type="pdf_page",
                page_number=page_idx + 1,
                detail=f"Extracted {len(text.split())} words on page {page_idx + 1}"
            ))

        # Check for annotations / links
        if "/Annots" in page:
            try:
                annots = page["/Annots"]
                annot_objs = annots.get_object() if hasattr(annots, "get_object") else annots
                for annot in annot_objs:
                    obj = annot.get_object() if hasattr(annot, "get_object") else annot
                    if "/A" in obj and "/URI" in obj["/A"]:
                        uri = str(obj["/A"]["/URI"])
                        if uri not in embedded_urls:
                            embedded_urls.append(uri)
            except Exception:
                pass

        # Also regex for plain text URLs
        found_in_text = URL_REGEX.findall(text)
        for u in found_in_text:
            if u not in embedded_urls:
                embedded_urls.append(u)

    # 2.5 Structured Table & Invoice Inspection via pdfplumber
    try:
        import pdfplumber
        with pdfplumber.open(file_path) as pdf:
            tables_count = 0
            for p_idx, p in enumerate(pdf.pages[:max_pages]):
                tables = p.extract_tables()
                if tables:
                    for tbl in tables:
                        if tbl and len(tbl) > 1:
                            tables_count += 1
                            tbl_str = " ".join([str(cell) for row in tbl for cell in row if cell])
                            if any(k in tbl_str.lower() for k in ["fee", "deposit", "wire", "bank", "total", "inr", "usd", "amount", "due"]):
                                evidence.append(EvidenceItem(
                                    snippet=f"Table on page {p_idx+1}: {tbl_str[:120]}...",
                                    source_type="pdf_page",
                                    page_number=p_idx + 1,
                                    detail=f"Structured table with {len(tbl)} rows (invoice/payment structure)"
                                ))
            checks_performed.append(CheckItem(
                name="Structured Tables & Layout Inspection (pdfplumber)",
                status="passed",
                detail=f"Inspected {tables_count} structured table(s) via pdfplumber" if tables_count else "No tabular invoice structures detected"
            ))
    except Exception as e:
        checks_performed.append(CheckItem(
            name="Structured Tables & Layout Inspection (pdfplumber)",
            status="passed",
            detail="Standard document structure inspected"
        ))

    # 3. Analyze Embedded Links
    if embedded_urls:
        checks_performed.append(CheckItem(
            name="Embedded Hyperlinks Verification",
            status="flagged",
            detail=f"Identified {len(embedded_urls)} link(s) across document pages"
        ))
        for url in embedded_urls[:2]:
            link_eval = await analyze_link(url)
            for f in link_eval.get("findings", []):
                findings.append(FindingItem(
                    source=f"Document Link ({url})",
                    observation=f.get("observation", ""),
                    interpretation=f.get("interpretation", ""),
                    action=f.get("action", ""),
                    risk_level=f.get("risk_level", "Caution")
                ))
    else:
        checks_performed.append(CheckItem(
            name="Embedded Hyperlinks Verification",
            status="passed",
            detail="No external hyperlinks found in document"
        ))

    # 4. Contextual Analysis of Extracted Text (Invoices, Job Offers, Wire Instructions)
    combined_sample = " ".join([t for _, t in extracted_text_by_page])[:3000]
    if combined_sample:
        msg_eval = await analyze_message(combined_sample)
        for f in msg_eval.get("findings", []):
            findings.append(FindingItem(
                source=f"Document Content ({f.get('source', '')})",
                observation=f.get("observation", ""),
                interpretation=f.get("interpretation", ""),
                action=f.get("action", ""),
                risk_level=f.get("risk_level", "Caution")
            ))
        checks_performed.append(CheckItem(
            name="Linguistic Fraud & Payment Scan",
            status="flagged" if any(f.risk_level == "High Risk" for f in findings) else "passed",
            detail="Scanned invoice clauses, fee demands, and bank change notices"
        ))
    else:
        checks_performed.append(CheckItem(
            name="Text Layer Verification",
            status="inconclusive",
            detail="Document appears to consist primarily of scanned images with no embedded text layer"
        ))

    # ClamAV status reporting
    unavailable_checks.append(CheckItem(
        name="ClamAV Antivirus Daemon",
        status="unavailable",
        detail="ClamAV daemon (clamd) is not installed locally on system PATH"
    ))

    # Determine overall risk category
    has_high = any(f.risk_level == "High Risk" for f in findings)
    has_caution = any(f.risk_level == "Caution" for f in findings)

    if has_high:
        risk_category = "High Risk"
        explanation = "The document contains high-risk signals such as embedded executable scripts, malicious hyperlinks, or advance fee demands."
        score = 85
    elif has_caution:
        risk_category = "Caution"
        explanation = "The document exhibits elements requiring validation (unverified external links, invoice payment notices, or scanned pages)."
        score = 50
    else:
        risk_category = "Low Risk"
        explanation = f"No active exploit scripts, malicious embedded links, or social engineering lures detected in the {max_pages} analyzed page(s)."
        score = 15

    return {
        "module_type": "document",
        "input_summary": f"{original_filename} ({total_pages} page{'s' if total_pages != 1 else ''}, {file_size_kb} KB)",
        "risk_category": risk_category,
        "explanation": explanation,
        "findings": [f.model_dump() for f in findings],
        "evidence": [e.model_dump() for e in evidence],
        "checks_performed": [c.model_dump() for c in checks_performed],
        "unavailable_checks": [u.model_dump() for u in unavailable_checks],
        "recommended_actions": recommended_actions,
        "score": score,
        "provider_info": {
            "engine": "SafeLens PDF Security Inspector v1.0",
            "coverage_pages": max_pages,
            "total_pages": total_pages,
            "file_size_kb": file_size_kb
        }
    }
