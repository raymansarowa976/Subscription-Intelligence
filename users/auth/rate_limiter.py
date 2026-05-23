from django.core.cache import cache


RATE_LIMIT_MESSAGE = "Too many attempts. Please wait a few minutes and try again."


def get_client_ip(request):
    return request.META.get("REMOTE_ADDR", "unknown")


def normalize_identifier(value):
    return str(value or "unknown").strip().lower()


def rate_limit_key(scope, *parts):
    normalized_parts = ":".join(normalize_identifier(part) for part in parts)
    return f"auth-rate-limit:{scope}:{normalized_parts}"


def is_rate_limited(scope, *parts, limit, window_seconds):
    key = rate_limit_key(scope, *parts)
    attempts = cache.get(key, 0)
    return attempts >= limit


def is_identifier_or_ip_rate_limited(scope, identifier, ip_address, *, limit, window_seconds):
    return is_rate_limited(
        f"{scope}:identifier",
        identifier,
        limit=limit,
        window_seconds=window_seconds,
    ) or is_rate_limited(
        f"{scope}:ip",
        ip_address,
        limit=limit,
        window_seconds=window_seconds,
    )


def record_attempt(scope, *parts, limit, window_seconds):
    key = rate_limit_key(scope, *parts)
    if cache.add(key, 1, window_seconds):
        return 1
    try:
        return cache.incr(key)
    except ValueError:
        cache.set(key, 1, window_seconds)
        return 1


def record_identifier_and_ip_attempt(scope, identifier, ip_address, *, limit, window_seconds):
    record_attempt(
        f"{scope}:identifier",
        identifier,
        limit=limit,
        window_seconds=window_seconds,
    )
    record_attempt(
        f"{scope}:ip",
        ip_address,
        limit=limit,
        window_seconds=window_seconds,
    )


def clear_attempts(scope, *parts):
    cache.delete(rate_limit_key(scope, *parts))


def clear_identifier_attempts(scope, identifier):
    clear_attempts(f"{scope}:identifier", identifier)
