import pytest
import os
import tempfile
from PIL import Image, ImageDraw
from pypdf import PdfWriter
from backend.app.services.ocr_service import analyze_screenshot
from backend.app.services.qr_service import analyze_qr_image
from backend.app.services.document_service import analyze_document

@pytest.mark.asyncio
async def test_ocr_extraction_on_image():
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
        temp_img_path = f.name

    try:
        # Create image with text
        img = Image.new("RGB", (400, 150), color=(255, 255, 255))
        draw = ImageDraw.Draw(img)
        draw.text((20, 40), "Pay 5000 INR to merchant@okhdfcbank", fill=(0, 0, 0))
        img.save(temp_img_path)

        res = await analyze_screenshot(temp_img_path, "receipt.png")
        assert res["module_type"] == "screenshot"
        assert len(res["checks_performed"]) > 0
        # Check that OCR ran
        ocr_check = next((c for c in res["checks_performed"] if "OCR" in c["name"]), None)
        assert ocr_check is not None
        assert ocr_check["status"] == "passed"
    finally:
        if os.path.exists(temp_img_path):
            os.remove(temp_img_path)

@pytest.mark.asyncio
async def test_pdf_document_extraction():
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
        temp_pdf_path = f.name

    try:
        writer = PdfWriter()
        writer.add_blank_page(width=200, height=200)
        with open(temp_pdf_path, "wb") as pf:
            writer.write(pf)

        res = await analyze_document(temp_pdf_path, "test_document.pdf")
        assert res["module_type"] == "document"
        pdf_check = next((c for c in res["checks_performed"] if "Structure" in c["name"]), None)
        assert pdf_check is not None
        assert pdf_check["status"] == "passed"
    finally:
        if os.path.exists(temp_pdf_path):
            os.remove(temp_pdf_path)
