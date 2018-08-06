import re

MURPHY_MATCHER = re.compile(r'^\s*\[MURPHY\]\s+', flags=re.IGNORECASE)

VALID_IDENTITY_TYPES = ['group', 'entity']
