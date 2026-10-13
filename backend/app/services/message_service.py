"""Real Message Check: exact text, contextual rules, reused Link Check, grounded Qwen."""
import asyncio
from typing import Any

from .message_extraction import extract_message, URL_REGEX
from .message_ai import interpret_message
from .url_service import analyze_link
from .dns_service import now

ACTIONS = ['Never share OTPs, PINs, passwords, or security codes with another person.',
           'Verify requests using contact details obtained independently.',
           'Do not pay fees or install remote-access software solely because a message asks you to.',
           'Text analysis cannot authenticate the sender or guarantee safety.']


def message_risk(text, extraction, links, ai, adequate):
    if not adequate:
        return 'Unable to Assess', 'There is too little meaningful content to distinguish a request from ordinary conversation.'
    # An actual external threat match is not overridden by educational wording.
    if any(link['analysis'].get('reputation', {}).get('status') == 'listed' for link in links):
        return 'High Risk', 'A real URL reputation lookup reported an unsafe destination in the message. This does not establish that the sender is fraudulent.'
    direct = [item for item in extraction['findings'] if item['context'] == 'direct_or_uncertain']
    categories = {item['category'] for item in direct}
    if 'credential_request' in categories:
        return 'High Risk', 'The submitted text directly requests disclosure of a security credential. Do not share it; the sender has not been authenticated.'
    if 'advance_payment' in categories and 'urgency' in categories and ('identity_claim' in categories or any(word in text.lower() for word in ('job', 'employment', 'नौकरी', 'ఉద్యోగ'))):
        return 'High Risk', 'An advance-fee request appears together with pressure and a job or identity claim. This combination warrants avoiding payment pending independent verification.'
    ai_direct = [item for item in ai.get('interpretations', []) if item['context'] == 'direct_or_uncertain']
    if direct or ai_direct or any(link['analysis']['risk_category'] in ('Caution', 'High Risk') for link in links):
        return 'Caution', 'Observed requests, pressure, or grounded contextual concerns require verification. They do not independently prove sender identity or criminal activity.'
    complete = ai['status'] == 'available' and extraction['language']['status'] != 'unsupported_or_uncertain' and all(link['analysis']['risk_category'] == 'Low Risk' for link in links)
    if complete:
        return 'Low Risk', 'No significant concern was found after the required available checks. This assessment cannot authenticate the sender or guarantee safety.'
    return 'Unable to Assess', 'No direct scam request was established, but missing contextual, language, or URL checks prevent a reliable Low Risk assessment.'


async def analyze_message(message_text: str, on_stage=None, url_filter=None, link_checker=None, document_context=None, offer_context=False) -> dict[str, Any]:
    def stage(value):
        if on_stage:
            on_stage(value)
    text = message_text  # Preserve whitespace and offsets exactly.
    stage('Validating original text and screening language scripts')
    extracted = extract_message(text)
    strong = any(item['category'] == 'credential_request' and item['context'] == 'direct_or_uncertain' for item in extracted['findings'])
    adequate = sum(char.isalnum() for char in text) >= 12 or strong
    stage('Extracting entities and context-aware deterministic evidence')
    links = []
    if adequate:
        semaphore = asyncio.Semaphore(2)
        async def check_url(url):
            async with semaphore:
                if url_filter is not None and not url_filter(url):
                    return {'url': url, 'occurrences': [item for item in extracted['urls'] if item['text'] == url],
                            'analysis': {'risk_category': 'Unable to Assess', 'reputation': {'status': 'unavailable'},
                                         'explanation': 'URL text has insufficient OCR confidence and was not contacted.',
                                         'unavailable_checks': [{'name': 'OCR URL readability', 'status': 'unavailable', 'detail': 'Upload a clearer image or check the exact URL separately'}]}}
                stage('Checking an extracted URL with the existing real Link Check service')
                try:
                    async with asyncio.timeout(45):
                        analysis = await (link_checker or analyze_link)(url)
                except Exception as exc:
                    analysis = {'module_type': 'link', 'risk_category': 'Unable to Assess', 'explanation': 'Extracted URL analysis was unavailable.',
                                'unavailable_checks': [{'name': 'Embedded Link Check', 'status': 'unavailable', 'detail': str(exc) if isinstance(exc, ValueError) else type(exc).__name__}],
                                'reputation': {'status': 'unavailable'}, 'findings': []}
                return {'url': url, 'occurrences': [item for item in extracted['urls'] if item['text'] == url], 'analysis': analysis}
        links = await asyncio.gather(*(check_url(url) for url in dict.fromkeys(item['text'] for item in extracted['urls'])))
        stage('Checking local Ollama availability and requesting grounded Qwen interpretation')
        ai = await interpret_message(text, extracted, links, document_context=document_context, offer_context=offer_context) if offer_context else await interpret_message(text, extracted, links, document_context=document_context) if document_context else await interpret_message(text, extracted, links)
    else:
        ai = {'provider': 'Local Ollama / Qwen', 'status': 'unavailable', 'error': 'Skipped: insufficient usable text', 'model_used': None,
              'interpretations': [], 'structured_output': None, 'grounding_failures': []}
    stage('Combining external observations, deterministic evidence, and grounded interpretations')
    risk, explanation = message_risk(text, extracted, links, ai, adequate)
    checks = [{'name': 'Content adequacy', 'status': 'passed' if adequate else 'inconclusive', 'detail': f'{len(text)} Unicode code points; original text preserved'},
              {'name': 'Entity extraction', 'status': 'passed', 'detail': f"{len(extracted['entities'])} actual entity span(s)"},
              {'name': 'Context-aware deterministic rules', 'status': 'flagged' if any(item['context'] == 'direct_or_uncertain' for item in extracted['findings']) else 'passed',
               'detail': f"{len(extracted['findings'])} evidence span(s); negation/quotation considered"},
              {'name': 'Embedded Link Check', 'status': 'passed' if adequate else 'inconclusive', 'detail': f'{len(links)} distinct URL(s) processed' if adequate else 'Skipped because content is insufficient'}]
    unavailable = []
    if extracted['language']['status'] == 'unsupported_or_uncertain':
        unavailable.append({'name': 'Language/context coverage', 'status': 'unavailable', 'detail': extracted['language']['limitation']})
    if ai['status'] != 'available':
        unavailable.append({'name': 'Grounded Qwen contextual interpretation', 'status': 'unavailable', 'detail': ai.get('error', f"{len(ai.get('grounding_failures', []))} AI concern(s) rejected during grounding")})
    if ai['status'] in ('available', 'partial'):
        checks.append({'name': 'Qwen JSON schema and quote grounding', 'status': 'passed' if ai['status'] == 'available' else 'inconclusive',
                       'detail': f"{len(ai['interpretations'])} grounded interpretation(s); {len(ai['grounding_failures'])} rejected concern(s)"})
    for index, link in enumerate(links, 1):
        checks.append({'name': f'Embedded URL {index}', 'status': 'flagged' if link['analysis']['risk_category'] in ('High Risk', 'Caution') else 'passed' if link['analysis']['risk_category'] == 'Low Risk' else 'inconclusive', 'detail': link['analysis']['risk_category']})
        unavailable.extend({**item, 'name': f"Embedded URL {index} · {item['name']}"} for item in link['analysis'].get('unavailable_checks', []))
    grounded = extracted['findings'] + ai.get('interpretations', [])
    evidence = [{'source_type': item['source'], 'snippet': item['text'], 'text_offset': {'start': item['start'], 'end': item['end']}, 'detail': f"{item['category']} · {item['context']}"} for item in grounded]
    findings = [{'source': f"{item['source']} · {item['category']}", 'observation': item['text'], 'interpretation': item['interpretation'] + f" Context: {item['context']}.",
                 'action': item.get('recommended_action', ACTIONS[1]), 'risk_level': 'Informational' if item['context'] != 'direct_or_uncertain' else 'High Risk' if item['category'] == 'credential_request' and item['source'] == 'deterministic' else 'Caution'} for item in grounded]
    return {'module_type': 'message', 'input_summary': 'Message content not saved', 'submitted_text': text, 'offset_unit': 'unicode_codepoints',
            'risk_category': risk, 'explanation': explanation, 'extracted_entities': extracted['entities'], 'deterministic_findings': extracted['findings'],
            'ai_interpretations': ai.get('interpretations', []), 'ai': ai, 'url_assessments': links, 'language': extracted['language'],
            'findings': findings, 'evidence': evidence, 'checks_performed': checks, 'unavailable_checks': unavailable, 'recommended_actions': ACTIONS,
            'score': None, 'checked_at': now(), 'content_saved': False,
            'provider_info': {'engine': 'SafeLens Message Inspector v2', 'qwen_integrated': ai['status'] in ('available', 'partial'), 'model_used': ai.get('model_used'), 'raw_message_retained': False}}
