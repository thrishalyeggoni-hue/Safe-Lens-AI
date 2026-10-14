import pytest
from backend.app.services.offer_service import analyze_offer

@pytest.mark.asyncio
async def test_analyze_offer_task_scam(monkeypatch):
    from backend.app.config import settings
    monkeypatch.setattr(settings, "MESSAGE_AI_ENABLED", False)
    text = "Work from home part-time: like YouTube videos and earn ₹5000 per day! Pay registration fee of ₹500 to join our VIP Telegram group."
    res = await analyze_offer(text)
    assert res["module_type"] == "offer"
    assert res["risk_category"] == "Caution"
    fees = [f for f in res["findings"] if f["source"] == "Offer deterministic · advance_payment"]
    assert fees
    assert all(text[f["text_offset"]["start"]:f["text_offset"]["end"]] == f["observation"] for f in fees)

@pytest.mark.asyncio
async def test_analyze_offer_benign(monkeypatch):
    from backend.app.config import settings
    monkeypatch.setattr(settings, "MESSAGE_AI_ENABLED", False)
    text = "Senior Frontend Engineer position at Acme Corp. Looking for React and TypeScript experience. Competitive salary and healthcare benefits."
    res = await analyze_offer(text)
    assert res["module_type"] == "offer"
    # Ordinary wording does not authenticate an offer when required checks are missing.
    assert res["risk_category"] == "Unable to Assess"
    assert not any(f["risk_level"] == "High Risk" for f in res["findings"])
    assert any(c["name"] == "Organisation, regulatory, price and contact verification" for c in res["unavailable_checks"])
