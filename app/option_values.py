"""Stored codes for answer options. Display text lives in the web UI and locale catalog.

Older settings stored the Chinese display text itself; normalize() maps those
values to codes when settings load, so saved choices survive the upgrade.
"""

ON, OFF = 'on', 'off'
QUESTIONS, SEGMENTS = 'questions', 'segments'
UNLIMITED = 'unlimited'
SERVICE_DEFAULT = 'service_default'

CHOICES = {
    'warm_context': (ON, OFF),
    'incremental_context': (ON, OFF),
    'spare_session': (ON, OFF),
    'speculate': (QUESTIONS, SEGMENTS, OFF),
    'deadline': (UNLIMITED, '120', '300', '600', '1800'),
    'max_output': (SERVICE_DEFAULT, '4096', '8192', '16384', '32768'),
}
DEFAULTS = {
    'warm_context': ON,
    'incremental_context': ON,
    'spare_session': OFF,
    'speculate': QUESTIONS,
    'deadline': UNLIMITED,
    'max_output': SERVICE_DEFAULT,
}
# Keys whose value may also be any positive whole number (seconds or tokens).
NUMERIC = {'deadline', 'max_output'}
LEGACY = {
    '开启': ON,
    '关闭': OFF,
    '仅疑问句': QUESTIONS,
    '每段定稿': SEGMENTS,
    '不限时': UNLIMITED,
    '服务默认': SERVICE_DEFAULT,
}


def allowed(key, value):
    if value in CHOICES[key]:
        return True
    return key in NUMERIC and isinstance(value, str) and value.isdigit() and int(value) > 0


def normalize(key, value):
    """Return the stored code for value, translating legacy text; unknown values fall back to the default."""
    value = LEGACY.get(value, value)
    return value if allowed(key, value) else DEFAULTS[key]


def validate(key, value):
    """Raise ValueError for a value the interface should never send."""
    if not allowed(key, value):
        raise ValueError('Invalid setting: ' + key)
    return value


def seconds(value):
    return float('inf') if value == UNLIMITED else int(value)


def tokens(value):
    return None if value == SERVICE_DEFAULT else int(value)
