import re

from django.core.exceptions import ValidationError


_UNSAFE_KEY_PARTS = (
    "password",
    "passwd",
    "token",
    "secret",
    "apikey",
    "authorization",
    "credential",
)
_KEY_NORMALIZER = re.compile(r"[^a-z0-9]+")


def validate_safe_metadata(value):
    """Reject credential-bearing keys at every level of audit metadata."""
    if not isinstance(value, dict):
        raise ValidationError("Audit metadata must be a JSON object.")

    def inspect(item):
        if isinstance(item, dict):
            for key, child in item.items():
                normalized_key = _KEY_NORMALIZER.sub("", str(key).lower())
                if any(part in normalized_key for part in _UNSAFE_KEY_PARTS):
                    raise ValidationError(
                        "Audit metadata cannot contain passwords, tokens, secrets, or credentials."
                    )
                inspect(child)
        elif isinstance(item, list):
            for child in item:
                inspect(child)

    inspect(value)
