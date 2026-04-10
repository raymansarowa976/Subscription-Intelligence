import secrets

from django.core.cache import cache


TOKEN_TTL_SECONDS = 600


def _cache_key(email):
    return f"email-verification:{email.lower()}"


def issue_email_token(email):
    token = f"{secrets.randbelow(1000000):06d}"
    cache.set(_cache_key(email), token, TOKEN_TTL_SECONDS)
    return token


def verify_email_token(email, submitted_token):
    stored_token = cache.get(_cache_key(email))
    if not stored_token:
        return False
    return secrets.compare_digest(stored_token, submitted_token.strip())


def clear_email_token(email):
    cache.delete(_cache_key(email))


def get_email_token(email):
    return cache.get(_cache_key(email.lower()))
