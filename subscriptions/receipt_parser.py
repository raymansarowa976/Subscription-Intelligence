import html
import re
from calendar import monthrange
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation


PARSER_VERSION = "receipt-parser-v1"

SUBSCRIPTION_TERMS = [
    "subscription",
    "membership",
    "renewal",
    "renews",
    "recurring",
    "monthly",
    "annual",
    "yearly",
    "plan",
    "next billing",
]

GENERIC_SENDER_NAMES = {
    "billing",
    "payments",
    "receipt",
    "receipts",
    "support",
    "team",
    "no-reply",
    "noreply",
    "notification",
    "notifications",
}

MONTHS = {
    "jan": 1,
    "january": 1,
    "feb": 2,
    "february": 2,
    "mar": 3,
    "march": 3,
    "apr": 4,
    "april": 4,
    "may": 5,
    "jun": 6,
    "june": 6,
    "jul": 7,
    "july": 7,
    "aug": 8,
    "august": 8,
    "sep": 9,
    "sept": 9,
    "september": 9,
    "oct": 10,
    "october": 10,
    "nov": 11,
    "november": 11,
    "dec": 12,
    "december": 12,
}


@dataclass(frozen=True)
class ReceiptExtraction:
    merchant_name: str
    amount: Decimal | None
    currency: str
    billing_date: date | None
    likely_renewal_date: date | None
    cadence: str
    confidence_score: int
    parser_version: str
    raw_entity_metadata: dict

    @property
    def has_required_candidate_fields(self):
        return bool(self.merchant_name and self.amount is not None and self.billing_date and self.cadence)


def clean_email_html(value):
    text = value or ""
    text = re.sub(r"(?is)<(script|style).*?>.*?</\1>", " ", text)
    text = re.sub(r"(?i)<\s*br\s*/?\s*>", "\n", text)
    text = re.sub(r"(?i)</\s*(p|div|tr|li|h[1-6])\s*>", "\n", text)
    text = re.sub(r"(?s)<[^>]+>", " ", text)
    text = html.unescape(text).replace("\xa0", " ")
    lines = [re.sub(r"[ \t]+", " ", line).strip() for line in text.splitlines()]
    return "\n".join(line for line in lines if line)


def parse_receipt_text(text, *, subject="", sender_name="", sender_email="", received_at=None):
    cleaned_text = clean_email_html(text)
    searchable = "\n".join(part for part in [subject, sender_name, sender_email, cleaned_text] if part)
    raw_entities = {
        "subject": subject,
        "sender_name": sender_name,
        "sender_email": sender_email,
        "cleaned_text": cleaned_text[:4000],
        "entities": {},
        "signals": [],
    }

    merchant_name = _extract_merchant(sender_name, sender_email, subject, cleaned_text)
    amount, amount_meta = _extract_amount(cleaned_text)
    billing_date, billing_meta = _extract_billing_date(searchable, received_at)
    likely_renewal_date, renewal_meta = _extract_renewal_date(searchable)
    cadence = _extract_cadence(searchable, billing_date, likely_renewal_date)

    if likely_renewal_date is None and billing_date is not None and cadence:
        likely_renewal_date = _add_period(billing_date, cadence)
        renewal_meta = {"source": "inferred_from_billing_date", "value": likely_renewal_date.isoformat()}

    raw_entities["entities"] = {
        "merchant": {"value": merchant_name, "source": "sender_subject_body" if merchant_name else ""},
        "amount": amount_meta,
        "billing_date": billing_meta,
        "likely_renewal_date": renewal_meta,
        "cadence": {"value": cadence, "source": "text_or_date_delta" if cadence else ""},
    }
    confidence = _score_extraction(searchable, merchant_name, amount, billing_date, likely_renewal_date, cadence)
    raw_entities["signals"] = _subscription_signals(searchable)

    return ReceiptExtraction(
        merchant_name=merchant_name,
        amount=amount,
        currency=(amount_meta.get("currency") or "USD"),
        billing_date=billing_date,
        likely_renewal_date=likely_renewal_date,
        cadence=cadence,
        confidence_score=confidence,
        parser_version=PARSER_VERSION,
        raw_entity_metadata=raw_entities,
    )


def _extract_merchant(sender_name, sender_email, subject, body):
    cleaned_sender = _clean_merchant_name(sender_name)
    if cleaned_sender:
        return cleaned_sender[:255]

    patterns = [
        r"(?im)^receipt\s+from\s+([A-Z][\w&.' -]{2,80})",
        r"(?im)^merchant[:\s]+([A-Z][\w&.' -]{2,80})",
        r"(?i)thanks\s+for\s+subscribing\s+to\s+([A-Z][\w&.' -]{2,80})",
        r"(?i)your\s+([A-Z][\w&.' -]{2,80})\s+(?:receipt|invoice|subscription)",
    ]
    for source in [subject, body]:
        for pattern in patterns:
            match = re.search(pattern, source or "")
            if match:
                merchant = _clean_merchant_name(match.group(1))
                if merchant:
                    return merchant[:255]

    if "@" in sender_email:
        domain = sender_email.rsplit("@", 1)[-1].split(".", 1)[0]
        merchant = _clean_merchant_name(domain.replace("-", " ").replace("_", " "))
        if merchant:
            return merchant[:255]
    return ""


def _clean_merchant_name(value):
    value = re.sub(r"(?i)\b(billing|payments|support|notifications?|receipts?|team|inc\.?|llc)\b", " ", value or "")
    value = re.sub(r"[^A-Za-z0-9&.' -]+", " ", value)
    value = re.sub(r"\s+", " ", value).strip(" -")
    if not value or value.lower() in GENERIC_SENDER_NAMES:
        return ""
    return value.title() if value.islower() else value


def _extract_amount(text):
    label_pattern = (
        r"(?i)\b(?:total|amount\s+paid|amount|charged|payment|paid|subscription\s+fee)"
        r"[:\s-]*(?:USD|US\$|\$)?\s*([0-9]{1,4}(?:,[0-9]{3})*(?:\.[0-9]{2})?)"
    )
    labeled = []
    for match in re.finditer(label_pattern, text or ""):
        amount = _decimal_from_match(match.group(1))
        if amount is not None:
            labeled.append((amount, match.group(0).strip()))
    if labeled:
        amount, raw = max(labeled, key=lambda item: item[0])
        return amount, {"value": str(amount), "currency": "USD", "source": "labeled_amount", "raw": raw}

    amounts = []
    for match in re.finditer(r"(?i)(?:USD|US\$|\$)\s*([0-9]{1,4}(?:,[0-9]{3})*(?:\.[0-9]{2})?)", text or ""):
        amount = _decimal_from_match(match.group(1))
        if amount is not None:
            amounts.append((amount, match.group(0)))
    if amounts:
        amount, raw = max(amounts, key=lambda item: item[0])
        return amount, {"value": str(amount), "currency": "USD", "source": "money_entity", "raw": raw}

    return None, {"value": None, "currency": "USD", "source": ""}


def _decimal_from_match(value):
    try:
        return Decimal(value.replace(",", "")).quantize(Decimal("0.01"))
    except (InvalidOperation, AttributeError):
        return None


def _extract_billing_date(text, received_at):
    patterns = [
        r"(?i)\b(?:billing\s+date|invoice\s+date|receipt\s+date|order\s+date|date\s+paid|charged\s+on|paid\s+on)[:\s-]*([A-Za-z]{3,9}\s+\d{1,2},?\s+\d{4}|\d{4}-\d{2}-\d{2}|\d{1,2}/\d{1,2}/\d{2,4})",
        r"(?i)\b(?:payment|charge)\s+(?:was\s+)?(?:processed|received|made)\s+on\s+([A-Za-z]{3,9}\s+\d{1,2},?\s+\d{4}|\d{4}-\d{2}-\d{2}|\d{1,2}/\d{1,2}/\d{2,4})",
    ]
    for pattern in patterns:
        match = re.search(pattern, text or "")
        if match:
            parsed = _parse_date(match.group(1))
            if parsed:
                return parsed, {"value": parsed.isoformat(), "source": "labeled_billing_date", "raw": match.group(0)}

    if received_at:
        value = received_at.date() if hasattr(received_at, "date") else received_at
        return value, {"value": value.isoformat(), "source": "email_received_at"}
    return None, {"value": None, "source": ""}


def _extract_renewal_date(text):
    pattern = (
        r"(?i)\b(?:next\s+(?:billing|renewal)\s+date|renews\s+on|renewal\s+date|"
        r"next\s+payment|will\s+renew\s+on)[:\s-]*"
        r"([A-Za-z]{3,9}\s+\d{1,2},?\s+\d{4}|\d{4}-\d{2}-\d{2}|\d{1,2}/\d{1,2}/\d{2,4})"
    )
    match = re.search(pattern, text or "")
    if match:
        parsed = _parse_date(match.group(1))
        if parsed:
            return parsed, {"value": parsed.isoformat(), "source": "labeled_renewal_date", "raw": match.group(0)}
    return None, {"value": None, "source": ""}


def _parse_date(value):
    value = (value or "").strip().replace(",", "")
    iso_match = re.fullmatch(r"(\d{4})-(\d{2})-(\d{2})", value)
    if iso_match:
        return _safe_date(int(iso_match.group(1)), int(iso_match.group(2)), int(iso_match.group(3)))

    numeric_match = re.fullmatch(r"(\d{1,2})/(\d{1,2})/(\d{2,4})", value)
    if numeric_match:
        year = int(numeric_match.group(3))
        if year < 100:
            year += 2000
        return _safe_date(year, int(numeric_match.group(1)), int(numeric_match.group(2)))

    month_match = re.fullmatch(r"([A-Za-z]{3,9})\s+(\d{1,2})\s+(\d{4})", value)
    if month_match:
        month = MONTHS.get(month_match.group(1).lower())
        if month:
            return _safe_date(int(month_match.group(3)), month, int(month_match.group(2)))
    return None


def _safe_date(year, month, day):
    try:
        return date(year, month, day)
    except ValueError:
        return None


def _extract_cadence(text, billing_date, renewal_date):
    normalized = (text or "").lower()
    if any(term in normalized for term in ["annual", "annually", "yearly", "per year", "/year"]):
        return "yearly"
    if any(term in normalized for term in ["monthly", "per month", "/month", "every month"]):
        return "monthly"
    if billing_date and renewal_date:
        days = (renewal_date - billing_date).days
        if 28 <= days <= 35:
            return "monthly"
        if 360 <= days <= 370:
            return "yearly"
    return ""


def _add_period(value, cadence):
    if cadence == "yearly":
        return date(value.year + 1, value.month, min(value.day, monthrange(value.year + 1, value.month)[1]))
    if cadence == "monthly":
        month_index = value.month
        year = value.year + month_index // 12
        month = month_index % 12 + 1
        return date(year, month, min(value.day, monthrange(year, month)[1]))
    return None


def _score_extraction(text, merchant_name, amount, billing_date, renewal_date, cadence):
    score = 0
    if merchant_name:
        score += 20
    if amount is not None:
        score += 25
    if billing_date:
        score += 15
    if renewal_date:
        score += 15
    if cadence:
        score += 15
    score += min(10, len(_subscription_signals(text)) * 3)
    if not (merchant_name and amount is not None):
        score = min(score, 55)
    return min(100, score)


def _subscription_signals(text):
    normalized = (text or "").lower()
    return [term for term in SUBSCRIPTION_TERMS if term in normalized]
