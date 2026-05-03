import secrets

from django.core.cache import cache


TOKEN_TTL_SECONDS = 600


def _cache_key(email, purpose="login"):
    return f"email-verification:{purpose}:{email.lower()}"


def issue_email_token(email, purpose="login"):
    token = f"{secrets.randbelow(1000000):06d}"
    cache.set(_cache_key(email, purpose), token, TOKEN_TTL_SECONDS)
    return token


def verify_email_token(email, submitted_token, purpose="login"):
    stored_token = cache.get(_cache_key(email, purpose))
    if not stored_token:
        return False
    return secrets.compare_digest(stored_token, submitted_token.strip())


def clear_email_token(email, purpose="login"):
    cache.delete(_cache_key(email, purpose))


def get_email_token(email, purpose="login"):
    return cache.get(_cache_key(email.lower(), purpose))
