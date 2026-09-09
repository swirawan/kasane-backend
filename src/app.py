from __future__ import annotations

import base64
import hashlib
import html
import json
import logging
import os
import re
import secrets
import time
from datetime import datetime, timezone
from typing import Any
from urllib import parse, request

import boto3
from botocore.exceptions import BotoCoreError, ClientError
from boto3.dynamodb.types import TypeSerializer

LOGGER = logging.getLogger()
LOGGER.setLevel(os.getenv("LOG_LEVEL", "INFO"))

TABLE_NAME = os.environ.get("TABLE_NAME", "")
STAGE = os.environ.get("STAGE", "dev")
EMAIL_ENABLED = os.environ.get("EMAIL_ENABLED", "false").lower() == "true"
FROM_EMAIL = os.environ.get("FROM_EMAIL", "")
NOTIFICATION_EMAILS = [x.strip() for x in os.environ.get("NOTIFICATION_EMAILS", "").split(",") if x.strip()]
CAPTCHA_REQUIRED = os.environ.get("CAPTCHA_REQUIRED", "false").lower() == "true"
TURNSTILE_SECRET_ARN = os.environ.get("TURNSTILE_SECRET_ARN", "")
TURNSTILE_EXPECTED_ACTION = os.environ.get("TURNSTILE_EXPECTED_ACTION", "kasane_brief")
TURNSTILE_EXPECTED_HOSTNAMES = {
    x.strip().lower() for x in os.environ.get("TURNSTILE_EXPECTED_HOSTNAMES", "").split(",") if x.strip()
}
ALLOWED_ORIGINS = {x.strip() for x in os.environ.get("ALLOWED_ORIGINS", "").split(",") if x.strip()}
LEAD_RETENTION_DAYS = int(os.environ.get("LEAD_RETENTION_DAYS", "730"))

_ddb = None
_ddb_client_instance = None
_ses = None
_secrets = None
_turnstile_secret_cache: str | None = None

EVENT_TYPES = {
    "Wedding",
    "Sweet Seventeen",
    "Private Celebration",
    "Corporate / Brand Event",
    "Event Production",
    "Other",
}
PREFERRED_CONTACTS = {"WhatsApp", "Email", "Call", "SMS"}
LANGUAGES = {"en", "id"}
EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
PHONE_RE = re.compile(r"^[0-9+()\-\.\s]{6,60}$")


def _ddb_table():
    global _ddb
    if _ddb is None:
        _ddb = boto3.resource("dynamodb").Table(TABLE_NAME)
    return _ddb


def _ddb_client():
    global _ddb_client_instance
    if _ddb_client_instance is None:
        _ddb_client_instance = boto3.client("dynamodb")
    return _ddb_client_instance


def _serialize_item(item: dict[str, Any]) -> dict[str, Any]:
    serializer = TypeSerializer()
    return {key: serializer.serialize(value) for key, value in item.items()}


def _ses_client():
    global _ses
    if _ses is None:
        _ses = boto3.client("sesv2")
    return _ses


def _secrets_client():
    global _secrets
    if _secrets is None:
        _secrets = boto3.client("secretsmanager")
    return _secrets


def _response(status: int, body: dict[str, Any], origin: str | None = None) -> dict[str, Any]:
    headers = {
        "content-type": "application/json; charset=utf-8",
        "cache-control": "no-store",
        "x-content-type-options": "nosniff",
    }
    if origin and (not ALLOWED_ORIGINS or origin in ALLOWED_ORIGINS):
        headers["access-control-allow-origin"] = origin
        headers["vary"] = "Origin"
    return {"statusCode": status, "headers": headers, "body": json.dumps(body, ensure_ascii=False)}


def _origin(event: dict[str, Any]) -> str:
    headers = event.get("headers") or {}
    return (headers.get("origin") or headers.get("Origin") or "").strip()


def _is_origin_allowed(origin: str) -> bool:
    if not origin:
        return True  # CLI / health tests do not necessarily send Origin.
    return not ALLOWED_ORIGINS or origin in ALLOWED_ORIGINS


def _decode_json_body(event: dict[str, Any]) -> dict[str, Any]:
    body = event.get("body") or ""
    if event.get("isBase64Encoded"):
        body = base64.b64decode(body).decode("utf-8")
    if len(body.encode("utf-8")) > 24_000:
        raise ValueError("payload_too_large")
    parsed = json.loads(body)
    if not isinstance(parsed, dict):
        raise ValueError("invalid_json")
    return parsed


def _clean(value: Any, max_length: int) -> str:
    text = str(value or "").strip()
    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", text)
    return text[:max_length]


def _validate_and_normalize(data: dict[str, Any]) -> tuple[dict[str, Any], dict[str, str]]:
    errors: dict[str, str] = {}

    normalized = {
        "version": _clean(data.get("version"), 40) or "phase5.1",
        "language": _clean(data.get("language"), 2).lower() or "en",
        "name": _clean(data.get("name"), 120),
        "phone": _clean(data.get("phone"), 60),
        "email": _clean(data.get("email"), 254).lower(),
        "preferredContact": _clean(data.get("preferredContact"), 20) or "WhatsApp",
        "eventType": _clean(data.get("eventType"), 80),
        "product": _clean(data.get("product"), 120),
        "package": _clean(data.get("package"), 120),
        "direction": _clean(data.get("direction"), 120),
        "city": _clean(data.get("city"), 180),
        "date": _clean(data.get("date"), 20),
        "guests": _clean(data.get("guests"), 20),
        "message": _clean(data.get("message"), 5000),
        "page": _clean(data.get("page"), 700),
        "submissionId": _clean(data.get("submissionId"), 100),
        "captchaToken": _clean(data.get("captchaToken"), 2200),
        "website": _clean(data.get("website"), 200),  # honeypot
    }

    if normalized["language"] not in LANGUAGES:
        errors["language"] = "Unsupported language."
    if len(normalized["name"]) < 2:
        errors["name"] = "Name is required."
    if normalized["preferredContact"] not in PREFERRED_CONTACTS:
        errors["preferredContact"] = "Choose a valid contact method."
    if normalized["eventType"] not in EVENT_TYPES:
        errors["eventType"] = "Choose a valid event type."
    if len(normalized["message"]) < 10:
        errors["message"] = "Please tell us a little more about the event."

    needs_phone = normalized["preferredContact"] in {"WhatsApp", "Call", "SMS"}
    needs_email = normalized["preferredContact"] == "Email"
    if needs_phone and not PHONE_RE.match(normalized["phone"]):
        errors["phone"] = "A valid phone number is required for this contact method."
    if normalized["email"] and not EMAIL_RE.match(normalized["email"]):
        errors["email"] = "Enter a valid email address."
    if needs_email and not EMAIL_RE.match(normalized["email"]):
        errors["email"] = "A valid email address is required for Email contact."

    if normalized["date"]:
        if not DATE_RE.match(normalized["date"]):
            errors["date"] = "Event date must use YYYY-MM-DD."
        else:
            try:
                datetime.strptime(normalized["date"], "%Y-%m-%d")
            except ValueError:
                errors["date"] = "Event date is invalid."

    if normalized["guests"]:
        digits = re.sub(r"[^0-9]", "", normalized["guests"])
        if not digits:
            errors["guests"] = "Guest count must be numeric."
        else:
            guest_count = int(digits)
            if guest_count < 1 or guest_count > 100_000:
                errors["guests"] = "Guest count is outside the accepted range."
            normalized["guests"] = str(guest_count)

    return normalized, errors


def _get_turnstile_secret() -> str:
    global _turnstile_secret_cache
    if _turnstile_secret_cache is not None:
        return _turnstile_secret_cache
    if not TURNSTILE_SECRET_ARN:
        return ""
    result = _secrets_client().get_secret_value(SecretId=TURNSTILE_SECRET_ARN)
    raw = result.get("SecretString") or ""
    try:
        parsed = json.loads(raw)
        secret = str(parsed.get("secret") or "") if isinstance(parsed, dict) else str(raw)
    except json.JSONDecodeError:
        secret = str(raw)
    _turnstile_secret_cache = secret.strip()
    return _turnstile_secret_cache


def _verify_turnstile(token: str, remote_ip: str = "") -> tuple[bool, str]:
    if not CAPTCHA_REQUIRED:
        return True, "disabled"
    if not token:
        return False, "missing-token"
    secret = _get_turnstile_secret()
    if not secret or secret == "REPLACE_ME":
        LOGGER.error("CAPTCHA_REQUIRED is true but Turnstile secret is not configured")
        return False, "server-misconfigured"

    payload = {
        "secret": secret,
        "response": token,
        "idempotency_key": secrets.token_hex(16),
    }
    if remote_ip:
        payload["remoteip"] = remote_ip
    encoded = parse.urlencode(payload).encode("utf-8")
    req = request.Request(
        "https://challenges.cloudflare.com/turnstile/v0/siteverify",
        data=encoded,
        headers={"Content-Type": "application/x-www-form-urlencoded", "User-Agent": "kasane-backend/1.0"},
        method="POST",
    )
    try:
        with request.urlopen(req, timeout=4) as resp:
            result = json.loads(resp.read().decode("utf-8"))
    except Exception as exc:  # network/service errors should fail closed for a public form
        LOGGER.warning("Turnstile verification failed: %s", type(exc).__name__)
        return False, "verification-unavailable"

    if not result.get("success"):
        codes = result.get("error-codes") or []
        return False, ",".join(str(x) for x in codes) or "challenge-failed"
    if TURNSTILE_EXPECTED_ACTION and result.get("action") not in {None, "", TURNSTILE_EXPECTED_ACTION}:
        return False, "action-mismatch"
    hostname = str(result.get("hostname") or "").lower()
    if TURNSTILE_EXPECTED_HOSTNAMES and hostname not in TURNSTILE_EXPECTED_HOSTNAMES:
        return False, "hostname-mismatch"
    return True, "ok"


def _reference() -> str:
    date_part = datetime.now(timezone.utc).strftime("%y%m%d")
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    suffix = "".join(secrets.choice(alphabet) for _ in range(6))
    return f"KAS-{date_part}-{suffix}"


_IDEMPOTENCY_DIGEST_FIELDS = (
    "language",
    "name",
    "phone",
    "email",
    "preferredContact",
    "eventType",
    "product",
    "package",
    "direction",
    "city",
    "date",
    "guests",
    "message",
)


class IdempotencyConflict(Exception):
    """A submissionId was reused for a materially different brief."""


def _payload_digest(lead: dict[str, Any]) -> str:
    """Return a stable digest of the meaningful client brief fields.

    Transport/security fields such as CAPTCHA tokens, browser metadata,
    source page, request fingerprint, and server timestamps are excluded.
    """
    payload = {
        key: str(lead.get(key) or "")
        for key in _IDEMPOTENCY_DIGEST_FIELDS
    }

    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")

    return hashlib.sha256(encoded).hexdigest()


def _idempotency_reference(submission_id: str) -> str:
    submission_hash = hashlib.sha256(
        submission_id.encode("utf-8")
    ).hexdigest()

    return f"IDEMPOTENCY#{submission_hash}"


def _existing_submission_reference(
    lead: dict[str, Any],
) -> str | None:
    """Return the original KAS reference for an exact duplicate.

    Raises:
        IdempotencyConflict:
            The same submissionId was previously used for a
            materially different brief.
    """
    submission_id = str(
        lead.get("submissionId") or ""
    ).strip()

    if not submission_id:
        return None

    table = _ddb_table()

    marker_reference = _idempotency_reference(
        submission_id
    )

    marker = table.get_item(
        Key={"reference": marker_reference},
        ConsistentRead=True,
    ).get("Item")

    if not marker or not marker.get("targetReference"):
        return None

    target_reference = str(
        marker["targetReference"]
    )

    current_digest = _payload_digest(lead)

    stored_digest = str(
        marker.get("payloadDigest") or ""
    ).strip()

    # Compatibility with markers created before payloadDigest existed.
    # Read the original stored lead and derive its digest.
    if not stored_digest:
        target_item = table.get_item(
            Key={"reference": target_reference},
            ConsistentRead=True,
        ).get("Item")

        if not target_item:
            raise RuntimeError(
                "idempotency_target_missing"
            )

        stored_digest = _payload_digest(
            target_item
        )

    if not secrets.compare_digest(
        stored_digest,
        current_digest,
    ):
        raise IdempotencyConflict(
            "submission_id_reused_with_different_payload"
        )

    return target_reference


def _store_lead(
    lead: dict[str, Any],
) -> tuple[str, bool]:
    """Store a lead exactly once when submissionId is supplied.

    Returns:
        (reference, created)

        created=False means this exact submissionId and
        brief payload were already accepted earlier.
    """
    table = _ddb_table()

    submission_id = str(
        lead.get("submissionId") or ""
    ).strip()

    # Compatibility path for clients that do not yet send submissionId.
    if not submission_id:
        for _ in range(4):
            reference = _reference()
            now = int(time.time())

            created_at = datetime.now(
                timezone.utc
            ).isoformat()

            item = {
                **lead,
                "reference": reference,
                "recordType": "EVENT_BRIEF",
                "stage": STAGE,
                "createdAt": created_at,
                "LeadIndexPK": "LEADS",
                "LeadIndexSK": (
                    f"{created_at}#{reference}"
                ),
                "expiresAt": (
                    now
                    + LEAD_RETENTION_DAYS * 86400
                ),
            }

            item.pop("captchaToken", None)
            item.pop("website", None)

            try:
                table.put_item(
                    Item=item,
                    ConditionExpression=(
                        "attribute_not_exists(#ref)"
                    ),
                    ExpressionAttributeNames={
                        "#ref": "reference"
                    },
                )

                return reference, True

            except ClientError as exc:
                if (
                    exc.response
                    .get("Error", {})
                    .get("Code")
                    != "ConditionalCheckFailedException"
                ):
                    raise

        raise RuntimeError(
            "reference_collision"
        )

    idempotency_reference = (
        _idempotency_reference(
            submission_id
        )
    )

    payload_digest = _payload_digest(
        lead
    )

    # Keep _store_lead independently safe even when called somewhere
    # other than the HTTP handler.
    existing_reference = (
        _existing_submission_reference(
            lead
        )
    )

    if existing_reference:
        return existing_reference, False

    for _ in range(4):
        reference = _reference()
        now = int(time.time())

        created_at = datetime.now(
            timezone.utc
        ).isoformat()

        expires_at = (
            now
            + LEAD_RETENTION_DAYS * 86400
        )

        lead_item = {
            **lead,
            "reference": reference,
            "recordType": "EVENT_BRIEF",
            "stage": STAGE,
            "createdAt": created_at,
            "LeadIndexPK": "LEADS",
            "LeadIndexSK": (
                f"{created_at}#{reference}"
            ),
            "expiresAt": expires_at,
        }

        lead_item.pop(
            "captchaToken",
            None,
        )

        lead_item.pop(
            "website",
            None,
        )

        marker_item = {
            "reference": idempotency_reference,
            "recordType": "IDEMPOTENCY",
            "targetReference": reference,
            "submissionId": submission_id,
            "payloadDigest": payload_digest,
            "stage": STAGE,
            "createdAt": created_at,
            "expiresAt": expires_at,
        }

        try:
            _ddb_client().transact_write_items(
                TransactItems=[
                    {
                        "Put": {
                            "TableName": TABLE_NAME,
                            "Item": _serialize_item(
                                marker_item
                            ),
                            "ConditionExpression": (
                                "attribute_not_exists(#ref)"
                            ),
                            "ExpressionAttributeNames": {
                                "#ref": "reference"
                            },
                        }
                    },
                    {
                        "Put": {
                            "TableName": TABLE_NAME,
                            "Item": _serialize_item(
                                lead_item
                            ),
                            "ConditionExpression": (
                                "attribute_not_exists(#ref)"
                            ),
                            "ExpressionAttributeNames": {
                                "#ref": "reference"
                            },
                        }
                    },
                ]
            )

            return reference, True

        except ClientError as exc:
            code = (
                exc.response
                .get("Error", {})
                .get("Code")
            )

            if code != "TransactionCanceledException":
                raise

            # Another request may have won the same
            # submissionId race. Re-read and verify that
            # its payload is identical before returning it.
            existing_reference = (
                _existing_submission_reference(
                    lead
                )
            )

            if existing_reference:
                return (
                    existing_reference,
                    False,
                )

            # Otherwise retry. The generated human-readable
            # KAS reference may have collided.

    raise RuntimeError(
        "idempotency_transaction_failed"
    )


def _lead_email_text(reference: str, lead: dict[str, Any]) -> str:
    lines = [
        f"KASANE event brief {reference}",
        "",
        f"Name: {lead['name']}",
        f"Preferred contact: {lead['preferredContact']}",
        f"Phone: {lead.get('phone') or '-'}",
        f"Email: {lead.get('email') or '-'}",
        f"Event type: {lead['eventType']}",
        f"Product: {lead.get('product') or '-'}",
        f"Package: {lead.get('package') or '-'}",
        f"Direction: {lead.get('direction') or '-'}",
        f"City / venue: {lead.get('city') or 'TBD'}",
        f"Date: {lead.get('date') or 'TBD'}",
        f"Guests: {lead.get('guests') or 'TBD'}",
        "",
        "Brief:",
        lead["message"],
        "",
        f"Source: {lead.get('page') or '-'}",
    ]
    return "\n".join(lines)


def _lead_email_html(reference: str, lead: dict[str, Any]) -> str:
    esc = lambda x: html.escape(str(x or "-"))
    rows = [
        ("Name", lead["name"]),
        ("Preferred contact", lead["preferredContact"]),
        ("Phone", lead.get("phone") or "-"),
        ("Email", lead.get("email") or "-"),
        ("Event type", lead["eventType"]),
        ("Product", lead.get("product") or "-"),
        ("Package", lead.get("package") or "-"),
        ("Direction", lead.get("direction") or "-"),
        ("City / venue", lead.get("city") or "TBD"),
        ("Date", lead.get("date") or "TBD"),
        ("Guests", lead.get("guests") or "TBD"),
    ]
    trs = "".join(f"<tr><td style='padding:5px 14px 5px 0;color:#777'>{esc(k)}</td><td style='padding:5px 0'>{esc(v)}</td></tr>" for k, v in rows)
    return f"""<!doctype html><html><body style='font-family:Arial,sans-serif;color:#12110f'>
    <h2 style='margin:0 0 6px'>KASANE event brief</h2><p style='margin:0 0 22px;color:#8a6a32'>{esc(reference)}</p>
    <table style='border-collapse:collapse'>{trs}</table>
    <h3 style='margin:28px 0 8px'>Brief</h3><p style='white-space:pre-wrap;line-height:1.6'>{esc(lead['message'])}</p>
    <p style='margin-top:28px;font-size:12px;color:#777'>Source: {esc(lead.get('page') or '-')}</p>
    </body></html>"""


def _send_notification(reference: str, lead: dict[str, Any]) -> bool:
    if not EMAIL_ENABLED:
        return False
    if not FROM_EMAIL or not NOTIFICATION_EMAILS:
        LOGGER.warning("EMAIL_ENABLED=true but sender/recipient configuration is incomplete")
        return False
    kwargs: dict[str, Any] = {
        "FromEmailAddress": FROM_EMAIL,
        "Destination": {"ToAddresses": NOTIFICATION_EMAILS},
        "Content": {
            "Simple": {
                "Subject": {"Data": f"[{reference}] {lead['eventType']} — {lead['name']}", "Charset": "UTF-8"},
                "Body": {
                    "Text": {"Data": _lead_email_text(reference, lead), "Charset": "UTF-8"},
                    "Html": {"Data": _lead_email_html(reference, lead), "Charset": "UTF-8"},
                },
            }
        },
    }
    if lead.get("email") and EMAIL_RE.match(lead["email"]):
        kwargs["ReplyToAddresses"] = [lead["email"]]
    _ses_client().send_email(**kwargs)
    return True


def _health(origin: str) -> dict[str, Any]:
    return _response(200, {"ok": True, "service": "kasane-backend", "stage": STAGE}, origin)


def handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    route_key = (event.get("requestContext") or {}).get("routeKey") or event.get("routeKey") or ""
    method = ((event.get("requestContext") or {}).get("http") or {}).get("method") or event.get("httpMethod") or ""
    path = ((event.get("requestContext") or {}).get("http") or {}).get("path") or event.get("rawPath") or event.get("path") or ""
    origin = _origin(event)

    if method == "GET" and path.endswith("/health"):
        return _health(origin)

    if method != "POST" or not path.endswith("/v1/briefs"):
        return _response(404, {"error": "not_found"}, origin)

    if not _is_origin_allowed(origin):
        return _response(403, {"error": "origin_not_allowed"}, origin)

    try:
        data = _decode_json_body(event)
    except (ValueError, json.JSONDecodeError, UnicodeDecodeError):
        return _response(400, {"error": "invalid_request", "message": "Invalid JSON request."}, origin)

    normalized, errors = _validate_and_normalize(data)

    # Honeypot: look successful to automation, but do not persist anything.
    if normalized.get("website"):
        fake_ref = _reference()
        return _response(201, {"ok": True, "reference": fake_ref}, origin)

    if errors:
        return _response(400, {"error": "validation_failed", "fields": errors}, origin)

    # Idempotency must be checked BEFORE Turnstile because
    # Cloudflare CAPTCHA tokens are single-use. A legitimate retry
    # after an accepted request must be able to recover the original
    # reference without attempting to consume the CAPTCHA again.
    try:
        existing_reference = _existing_submission_reference(
            normalized
        )
    except IdempotencyConflict:
        return _response(
            409,
            {
                "error": "submission_conflict",
                "message": (
                    "This submission was already used for a "
                    "different brief. Please start a new brief."
                ),
            },
            origin,
        )
    except (BotoCoreError, ClientError, RuntimeError) as exc:
        LOGGER.exception(
            "Idempotency lookup failed type=%s",
            type(exc).__name__,
        )
        return _response(
            503,
            {
                "error": "temporarily_unavailable",
                "message": (
                    "We could not verify the brief right now."
                ),
            },
            origin,
        )

    if existing_reference:
        LOGGER.info(
            "Duplicate brief recovered reference=%s",
            existing_reference,
        )

        return _response(
            201,
            {
                "ok": True,
                "reference": existing_reference,
                "created": False,
                "notificationSent": False,
            },
            origin,
        )

    source_ip = (((event.get("requestContext") or {}).get("http") or {}).get("sourceIp") or "").strip()
    captcha_ok, captcha_reason = _verify_turnstile(normalized.get("captchaToken", ""), source_ip)
    if not captcha_ok:
        LOGGER.info("CAPTCHA rejected reason=%s", captcha_reason)
        return _response(403, {"error": "captcha_failed", "message": "Please complete the verification and try again."}, origin)

    # Store a non-reversible fingerprint for rough operational diagnostics, not the raw IP.
    if source_ip:
        normalized["requestFingerprint"] = hashlib.sha256((source_ip + "|" + STAGE).encode()).hexdigest()[:16]
    normalized["origin"] = origin
    normalized.pop("submittedAt", None)  # server timestamp is authoritative

    try:
        reference, created = _store_lead(normalized)
    except IdempotencyConflict:
        return _response(
            409,
            {
                "error": "submission_conflict",
                "message": (
                    "This submission was already used for a "
                    "different brief. Please start a new brief."
                ),
            },
            origin,
        )
    except (BotoCoreError, ClientError, RuntimeError) as exc:
        LOGGER.exception("Lead persistence failed type=%s", type(exc).__name__)
        return _response(503, {"error": "temporarily_unavailable", "message": "We could not save the brief right now."}, origin)

    notification_sent = False
    try:
        if created:
            notification_sent = _send_notification(reference, normalized)
    except (BotoCoreError, ClientError) as exc:
        # The lead is already safely stored, so a notification outage should not make the visitor resubmit.
        LOGGER.exception("SES notification failed reference=%s type=%s", reference, type(exc).__name__)

    LOGGER.info(
        "Lead accepted reference=%s eventType=%s created=%s notification=%s",
        reference,
        normalized["eventType"],
        created,
        notification_sent,
    )
    return _response(
        201,
        {
            "ok": True,
            "reference": reference,
            "created": created,
            "notificationSent": notification_sent,
        },
        origin,
    )
