"""Credential redaction for log text.

Shared by the Telegram /log command and the web live-log viewer, so both
apply exactly the same rules. No ``bot`` imports: the web process uses it.
Not exhaustive; operators should still avoid logging secrets.
"""

from re import IGNORECASE as re_IGNORECASE, compile as re_compile

# Each pattern is replaced with its captured prefix + '[REDACTED]'.
REDACT_PATTERNS = [
    # /qbit/?pass=... / /nzb/?pass=...
    re_compile(r"(pass=)[A-Za-z0-9]+"),
    # api_key=..., apikey=..., key=..., token=..., password=..., secret=...
    re_compile(r"((?:api_?key|key|token|password|secret|apikey)=)[^\s&]+", re_IGNORECASE),
    # Authorization: Bearer ...
    re_compile(r"(Authorization:\s*Bearer\s+)[A-Za-z0-9._\-]+", re_IGNORECASE),
    # MongoDB connection string with credentials:
    # mongodb://user:pass@host
    re_compile(r"(mongodb(?:\+srv)?://[^:/@\s]+:)[^@/\s]+(@)"),
    # Generic email:pass pairs (e.g. JD_EMAIL:JD_PASS, MEGA_EMAIL:MEGA_PASSWORD)
    re_compile(r"((?:JD_PASS|MEGA_PASSWORD|LOGIN_PASS)\s*=\s*)[^\s]+", re_IGNORECASE),
    # BOT_TOKEN value patterns (numeric:id:hex) — common when log lines
    # echo the token by accident
    re_compile(r"(\bBOT_TOKEN\s*=\s*)\d+:[A-Za-z0-9_\-]+", re_IGNORECASE),
    # Bare Telegram bot tokens anywhere (keep the bot id, hide the secret).
    re_compile(r"(\b\d{6,12}:)[A-Za-z0-9_\-]{30,}"),
]


def redact_log_text(text: str) -> str:
    """Redact known credential patterns from log text."""

    def _replace(m):
        out = m.group(1) + "[REDACTED]"
        if m.lastindex and m.lastindex >= 2:
            out += m.group(2)
        return out

    for pattern in REDACT_PATTERNS:
        text = pattern.sub(_replace, text)
    return text
