import json
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from backend.app.link_main import app
from backend.app.database import Base, get_db
from backend.app.services.reputation_service import lookup_reputation
from backend.app.config import settings


@pytest.fixture
def client():
    engine = create_engine('sqlite://', connect_args={'check_same_thread': False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)
    def database():
        with factory() as session:
            yield session
    app.dependency_overrides[get_db] = database
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
    engine.dispose()


def test_invalid_input_returns_real_error(client):
    result = client.post('/api/check/link', json={'url': 'ftp://example.com'})
    assert result.status_code == 422
    assert 'HTTP' in result.json()['detail']


@pytest.mark.parametrize('url', ['http://localhost/', 'http://127.0.0.1/', 'http://10.0.0.1/', 'http://[::1]/'])
def test_endpoint_blocks_local_destinations(client, url):
    response = client.post('/api/check/link', json={'url': url})
    assert response.status_code == 200
    result = response.json()
    assert result['dns']['status'] == 'blocked'
    assert result['risk_category'] == 'Unable to Assess'
    assert result['score'] is None
    assert result['redirects']['chain'] == []
    # History preserves all actual observations and owner access.
    stored = client.get('/api/assessments/' + result['id'])
    assert stored.json() == result
    client.cookies.set('safelens_session', 'other-session-value', domain='testserver.local', path='/')
    assert client.get('/api/assessments/' + result['id']).status_code == 403


def test_stream_reports_backend_stages_and_exact_result(client):
    response = client.post('/api/check/link?stream=true', json={'url': 'http://127.0.0.1/'})
    assert response.status_code == 200
    events = [json.loads(line) for line in response.text.splitlines()]
    assert events[0] == {'type': 'stage', 'stage': 'Validating and normalizing URL'}
    assert events[-1]['type'] == 'result'
    result = events[-1]['data']
    assert client.get('/api/assessments/' + result['id']).json() == result
    assert result['created_at'].endswith('+00:00')
    assert not any('percent' in json.dumps(event).lower() for event in events)


@pytest.mark.asyncio
@pytest.mark.skipif(not settings.GOOGLE_WEB_RISK_API_KEY, reason='Live Web Risk key is not configured')
async def test_live_provider_approved_malware_fixture():
    # Official Google Web Risk Lookup documentation's test URI. Never load its page.
    result = await lookup_reputation('http://testsafebrowsing.appspot.com/s/malware.html')
    assert result['status'] == 'listed'
    assert 'MALWARE' in result['threats']
