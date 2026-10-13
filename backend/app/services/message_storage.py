import uuid
from datetime import datetime, timedelta, timezone
from ..config import settings
from ..database import AssessmentModel


def persist_message_metadata(result, session_id, db):
    """Persist no submitted text, snippets, entities, URLs, model output, or secrets."""
    module = result.get('module_type', 'message')
    record = AssessmentModel(id=f'asmt_{uuid.uuid4().hex[:12]}', session_id=session_id, created_at=datetime.now(timezone.utc),
                             module_type=module, input_summary=f'{module.capitalize()} · content not retained', risk_category=result['risk_category'],
                             explanation=f'{module.capitalize()} evaluated. Original content and detailed results were not retained.',
                             findings_json='[]', evidence_json='[]', checks_json='[]', unavailable_checks_json='[]',
                             recommended_actions_json='[]', provider_info_json='{"raw_content_retained": false}', score=None,
                             retention_expiry=datetime.now(timezone.utc) + timedelta(hours=settings.RETENTION_HOURS))
    db.add(record)
    db.commit()
    saved = record.to_dict()
    return {**result, 'id': saved['id'], 'created_at': saved['created_at'], 'created_at_iso': saved['created_at_iso'], 'retention_expiry': saved['retention_expiry']}
