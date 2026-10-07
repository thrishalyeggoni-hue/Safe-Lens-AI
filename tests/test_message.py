import pytest
from backend.app.services.message_service import analyze_message

@pytest.mark.asyncio
async def test_analyze_message_otp_lure():
    text = "Dear Customer, your bank account will be blocked within 2 hours. Kindly share OTP to verify your identity immediately."
    res = await analyze_message(text)
    assert res["module_type"] == "message"
    assert res["risk_category"] == "High Risk"
    assert any("OTP" in f["source"] for f in res["findings"])
    assert len(res["evidence"]) > 0

@pytest.mark.asyncio
async def test_analyze_message_benign():
    text = "Hey Sarah, are we still meeting for lunch tomorrow at 1 PM at the diner?"
    res = await analyze_message(text)
    assert res["module_type"] == "message"
    assert res["risk_category"] == "Low Risk"

@pytest.mark.asyncio
async def test_analyze_message_educational_context():
    text = "Beware of scams saying: your bank account is suspended and please enter your password here."
    res = await analyze_message(text)
    assert res["module_type"] == "message"
    assert res["risk_category"] != "High Risk"
