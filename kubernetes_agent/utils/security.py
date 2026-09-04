"""Security utilities for masking sensitive data."""

import re

# Regex patterns for common sensitive data
SENSITIVE_PATTERNS = [
    # Bearer tokens / JWTs
    (re.compile(r"Bearer\s+[A-Za-z0-9\-_=]+\.[A-Za-z0-9\-_=]+\.?[A-Za-z0-9\-_=]*"), "Bearer [MASKED_TOKEN]"),
    (re.compile(r"eyJ[A-Za-z0-9\-_=]+\.[A-Za-z0-9\-_=]+\.?[A-Za-z0-9\-_=]*"), "[MASKED_JWT]"),
    
    # Generic passwords in URLs (e.g. mongodb://user:pass@host)
    (re.compile(r"(//[^:]+):([^@]+)(@)"), r"\1:[MASKED_PASSWORD]\3"),
    
    # API Keys / Secrets (basic heuristic: 'key=', 'secret=', 'token=')
    (re.compile(r"(?i)(api_?key|secret|token)[\s:=]+[\"']?([A-Za-z0-9\-_=]{16,})[\"']?"), r"\1=[MASKED_SECRET]"),
    
    # AWS Access Keys
    (re.compile(r"(?<![A-Z0-9])[A-Z0-9]{20}(?![A-Z0-9])"), "[MASKED_AWS_KEY]"),
    
    # Simple email masking (optional, but good for PII)
    (re.compile(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+"), "[MASKED_EMAIL]"),
]

def mask_sensitive_data(text: str) -> str:
    """Scrub common sensitive information from logs or text."""
    if not text:
        return text
        
    masked_text = text
    for pattern, replacement in SENSITIVE_PATTERNS:
        masked_text = pattern.sub(replacement, masked_text)
        
    return masked_text
