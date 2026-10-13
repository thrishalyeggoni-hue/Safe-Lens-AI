import json
import pytest
from unittest.mock import AsyncMock
from tests.test_link_api import client
from backend.app.services import message_service
from backend.app.services.message_storage import persist_message_metadata
from backend.app.database import AssessmentModel
from backend.app.config import settings


def offline(monkeypatch):
    monkeypatch.setattr(message_service,'interpret_message',AsyncMock(return_value={'status':'unavailable','error':'Test: offline','interpretations':[], 'structured_output':None,'model_used':None,'grounding_failures':[]}))


def test_real_text_submission_and_private_metadata(client,monkeypatch):
    offline(monkeypatch)
    text='  😀 Send me your OTP and password now. Secret fixture 938471.  '
    response=client.post('/api/check/message',json={'message':text})
    assert response.status_code==200
    assert response.headers['cache-control']=='no-store'
    result=response.json()
    assert result['submitted_text']==text and result['risk_category']=='High Risk'
    saved=client.get('/api/assessments/'+result['id']).json()
    assert saved['content_saved'] is False and saved['message_details_retained'] is False
    serialized=json.dumps(saved)
    assert '938471' not in serialized and 'submitted_text' not in serialized and 'OTP' not in serialized
    assert saved['evidence']==[] and saved['findings']==[]
    client.cookies.set('safelens_session','other-session-value',domain='testserver.local',path='/')
    assert client.get('/api/assessments/'+result['id']).status_code==403


def test_actual_stages_and_warning(client,monkeypatch):
    offline(monkeypatch)
    response=client.post('/api/check/message?stream=true',json={'message':'Never share your OTP with anyone.'})
    events=[json.loads(line) for line in response.text.splitlines()]
    assert events[0]['type']=='stage' and events[-1]['type']=='result'
    result=events[-1]['data']
    assert result['risk_category']=='Unable to Assess'
    assert result['deterministic_findings'][0]['context']=='safety_advice_or_negated'
    assert result['ai']['structured_output'] is None


def test_limits_and_empty_input(client,monkeypatch):
    offline(monkeypatch)
    assert client.post('/api/check/message',json={'message':'x'*12001}).status_code==422
    assert client.post('/api/check/message',json={'message':''}).json()['risk_category']=='Unable to Assess'
    assert client.post('/api/check/message',json={'message':'bad\x00'}).status_code==422


@pytest.mark.skipif(not settings.GOOGLE_WEB_RISK_API_KEY, reason='Live Web Risk key is not configured')
def test_real_message_with_provider_approved_malware_url(client,monkeypatch):
    offline(monkeypatch)
    result=client.post('/api/check/message',json={'message':'Please inspect http://testsafebrowsing.appspot.com/s/malware.html before opening.'}).json()
    assert result['url_assessments'][0]['analysis']['reputation']['status']=='listed'
    assert result['risk_category']=='High Risk'
