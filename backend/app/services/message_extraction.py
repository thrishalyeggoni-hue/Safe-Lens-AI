"""Offset-preserving extraction and bounded, contextual deterministic rules.

Offsets are Python Unicode code points. Never strip/normalize the original text.
Script screening is not a claim of reliable natural-language identification.
"""
import re
from ..config import settings

URL_REGEX = re.compile(r'(?:https?://|www\.)[^\s<>"\'{}|\\^`]+', re.I)
EMAIL = re.compile(r'(?<![\w.+-])[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}(?!\w)')
PHONE = re.compile(r'(?<!\w)\+?\d[\d ()-]{7,18}\d(?!\w)')
AMOUNT = re.compile(r'(?:[₹$€£]\s*\d[\d,]*(?:\.\d{1,2})?|\b(?:INR|USD|Rs\.?)\s*\d[\d,]*(?:\.\d{1,2})?|\b\d[\d,]*\s*(?:rupees|dollars)\b)', re.I)
PAYMENT = re.compile(r'\b(?:UPI|bank transfer|wire transfer|gift cards?|bitcoin|crypto(?:currency)?|USDT|PayPal)\b', re.I)
URGENCY = re.compile(r'\b(?:now|today|immediately|urgent|within\s+\d+\s+(?:hours?|minutes?)|last chance|act fast)\b|अभी|तुरंत|आज|ఇప్పుడే|వెంటనే|ఈరోజు', re.I)
IDENTITY = re.compile(r'\b(?:I am|we are|this is|on behalf of|from)\s+(?:the\s+)?(?:bank|SBI|HDFC|ICICI|government|police|support|customer support)\b|हम.*(?:बैंक|सरकार)|మేము.*(?:బ్యాంక్|ప్రభుత్వ)', re.I)
EDUCATIONAL = re.compile(r'\b(?:scammers? (?:often )?(?:say|ask|send|use)|example of (?:a )?(?:scam|phishing)|scam (?:example|warning)|article (?:about|explains)|beware of scams|safety tips|educational|quoted scam|scam message (?:says|reads))\b', re.I)
NEGATION = re.compile(r"\b(?:never|do not|don't|must not|should not|avoid|not to|no need to)\b|मत|न करें|न भेजें|साझा न|कभी.*न|పంచుకోవద్దు|పంపవద్దు|ఇవ్వకండి|చెప్పవద్దు", re.I)
QUOTES = re.compile(r'"[^"\n]*"|“[^”\n]*”|‘[^’\n]*’')

RULES = [
    ('credential_request', re.compile(r'\b(?:share|send|give|provide|tell|forward)\s+(?:(?:me|us)\s+)?(?:(?:your|the|a|this)\s+)?(?:OTP|one[ -]time password|PIN|password|CVV|security code|verification code)\b|(?:OTP|ओटीपी|पासवर्ड|पिन).{0,30}(?:भेजें|बताएं|बताएँ|साझा करें|शेयर करें)|(?:OTP|ఓటీపీ|పాస్‌వర్డ్|పిన్).{0,30}(?:పంపండి|ఇవ్వండి|చెప్పండి)', re.I)),
    ('credential_input', re.compile(r'\b(?:enter|verify|confirm)\s+(?:(?:your|the)\s+)?(?:OTP|PIN|password|CVV)\b', re.I)),
    ('advance_payment', re.compile(r'\b(?:pay|deposit|transfer|send)\b[^.!?\n]{0,75}\b(?:registration|processing|activation|verification|security)\s+(?:fee|deposit|charge)\b|(?:रजिस्ट्रेशन|पंजीकरण).{0,25}(?:फीस|शुल्क).{0,25}(?:भेजें|देना|जमा|भुगतान)|(?:రిజిస్ట్రేషన్|నమోదు).{0,25}(?:ఫీజు|రుసుము).{0,25}(?:చెల్లించండి|పంపండి)', re.I)),
    ('remote_access', re.compile(r'\b(?:install|download|open|enable)\s+(?:AnyDesk|TeamViewer|remote access|screen sharing)\b', re.I)),
    ('unusual_payment', re.compile(r'\b(?:pay|send|buy|transfer)\b[^.!?\n]{0,45}\b(?:gift cards?|bitcoin|crypto(?:currency)?|USDT)\b', re.I)),
    ('account_threat', re.compile(r'\b(?:your\s+)?account\s+(?:will be|has been|is)\s+(?:suspended|blocked|closed|terminated)\b', re.I)),
    ('off_platform', re.compile(r'\b(?:move|switch|contact|message)\s+(?:me|us)?\s*(?:on|to|via)\s+(?:Telegram|WhatsApp|private chat)\b', re.I)),
    ('prize_claim', re.compile(r'\b(?:you (?:have )?won|claim your (?:prize|reward)|selected for a lottery)\b', re.I)),
]


def span(text, start, end, category, **extra):
    return {'start': start, 'end': end, 'text': text[start:end], 'category': category, **extra}


def validate_text(text):
    if not isinstance(text, str):
        raise ValueError('Message must be text')
    if len(text) > settings.MESSAGE_MAX_CHARACTERS:
        raise ValueError(f'Message exceeds {settings.MESSAGE_MAX_CHARACTERS} characters')
    if any(ord(char) < 32 and char not in '\n\r\t' for char in text):
        raise ValueError('Message contains unsupported control characters')


def screen_language(text):
    scripts = set()
    for char in text:
        if not char.isalpha():
            continue
        if '\u0900' <= char <= '\u097f': scripts.add('hi')
        elif '\u0c00' <= char <= '\u0c7f': scripts.add('te')
        elif char.isascii(): scripts.add('en')
        else: scripts.add('other')
    return {'method': 'Unicode script screening, not statistical language detection', 'scripts': sorted(scripts),
            'status': 'unsupported_or_uncertain' if 'other' in scripts or not scripts else 'limited_rule_support',
            'rule_languages': ['en', 'hi', 'te'], 'contextual_language_support': 'not verified until a real model succeeds',
            'limitation': 'English rules plus targeted Hindi/Telugu requests are tested. Script alone cannot authenticate language or establish comprehensive support.'}


def context_for(text, start, end):
    sentence_start = max(text.rfind('\n', 0, start), text.rfind('.', 0, start), text.rfind('!', 0, start), text.rfind('?', 0, start)) + 1
    tail = re.search(r'[\n.!?]', text[end:])
    sentence_end = end + tail.start() if tail else len(text)
    sentence = text[sentence_start:sentence_end]
    # Negation belongs to a clause; a separate warning must not erase an active request.
    separators = list(re.finditer(r';|\b(?:but|however)\b', text[sentence_start:start], re.I))
    clause_start = sentence_start + separators[-1].end() if separators else sentence_start
    next_separator = re.search(r';|\b(?:but|however)\b', text[end:sentence_end], re.I)
    clause_end = end + next_separator.start() if next_separator else sentence_end
    if NEGATION.search(text[max(clause_start, start - 50):clause_end]):
        return 'safety_advice_or_negated'
    if EDUCATIONAL.search(sentence):
        return 'educational_or_attributed'
    if any(match.start() <= start and end <= match.end() for match in QUOTES.finditer(text)) or sentence.lstrip().startswith('>'):
        return 'quoted_or_reported'
    return 'direct_or_uncertain'


def extract_message(text):
    validate_text(text)
    entities = []
    urls = []
    for match in URL_REGEX.finditer(text):
        end = match.end()
        while end > match.start() and text[end - 1] in '.,;!?)':
            end -= 1
        item = span(text, match.start(), end, 'url')
        urls.append(item)
        entities.append(item)
    if len({item['text'] for item in urls}) > settings.MESSAGE_MAX_LINKS:
        raise ValueError(f'Message contains more than {settings.MESSAGE_MAX_LINKS} distinct URLs; shorten it so every URL can be checked')
    for category, pattern in [('email', EMAIL), ('phone', PHONE), ('amount', AMOUNT), ('payment_method', PAYMENT), ('urgency', URGENCY), ('identity_claim', IDENTITY)]:
        for match in pattern.finditer(text):
            if category == 'phone' and any(item['start'] <= match.start() < item['end'] for item in entities if item['category'] in ('url', 'amount')):
                continue
            entities.append(span(text, *match.span(), category))
    findings = []
    for category, pattern in RULES:
        for match in pattern.finditer(text):
            context = context_for(text, *match.span())
            findings.append(span(text, *match.span(), category, source='deterministic', context=context,
                                 interpretation='An observed request or pressure pattern; sender legitimacy is not verified.'))
    # Urgency and identity terms matter only in a message containing a request,
    # not in an ordinary discussion mentioning a bank or meeting today.
    requests = [item for item in findings if item['context'] == 'direct_or_uncertain']
    if requests:
        findings.extend({**item, 'source': 'deterministic', 'context': context_for(text, item['start'], item['end']),
                         'interpretation': 'Pressure or an identity claim accompanying an observed request; not an authenticated identity.'}
                        for item in entities if item['category'] in ('urgency', 'identity_claim'))
    return {'entities': sorted(entities, key=lambda item: item['start']), 'urls': urls, 'findings': sorted(findings, key=lambda item: item['start']), 'language': screen_language(text)}
