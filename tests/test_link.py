import pytest
from backend.app.services.url_service import analyze_link, validate_and_normalize_url

@pytest.mark.asyncio
async def test_validate_and_normalize_url():
    assert validate_and_normalize_url("google.com") == "https://google.com"
    assert validate_and_normalize_url("http://example.org/path") == "http://example.org/path"
    with pytest.raises(ValueError):
        validate_and_normalize_url("")

@pytest.mark.asyncio
async def test_analyze_link_homoglyph_detection():
    # Test brand impersonation in subdomain
    res = await analyze_link("http://paypal.account-verify-login.com")
    assert res["module_type"] == "link"
    assert res["risk_category"] in ["Caution", "High Risk"]
    assert any("Brand Impersonation" in f["source"] for f in res["findings"])

@pytest.mark.asyncio
async def test_analyze_link_benign():
    res = await analyze_link("https://www.wikipedia.org")
    assert res["module_type"] == "link"
    assert res["risk_category"] == "Low Risk"
