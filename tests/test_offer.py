import pytest
from backend.app.services.offer_service import analyze_offer

@pytest.mark.asyncio
async def test_analyze_offer_task_scam():
    text = "Work from home part-time: like YouTube videos and earn ₹5000 per day! Pay registration fee of ₹500 to join our VIP Telegram group."
    res = await analyze_offer(text)
    assert res["module_type"] == "offer"
    assert res["risk_category"] == "High Risk"
    assert any("Advance Fee" in f["source"] or "Task / Rating" in f["source"] for f in res["findings"])

@pytest.mark.asyncio
async def test_analyze_offer_benign():
    text = "Senior Frontend Engineer position at Acme Corp. Looking for React and TypeScript experience. Competitive salary and healthcare benefits."
    res = await analyze_offer(text)
    assert res["module_type"] == "offer"
    assert res["risk_category"] == "Low Risk"
