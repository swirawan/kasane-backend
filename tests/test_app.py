import json
import os
import sys
from unittest.mock import patch

os.environ.setdefault("AWS_EC2_METADATA_DISABLED", "true")
os.environ.setdefault("AWS_DEFAULT_REGION", "us-east-1")
os.environ.setdefault("TABLE_NAME", "test")
os.environ.setdefault("CAPTCHA_REQUIRED", "false")
os.environ.setdefault("EMAIL_ENABLED", "false")
os.environ.setdefault("ALLOWED_ORIGINS", "https://swirawan.github.io")

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
import app  # noqa: E402


def event(payload, origin="https://swirawan.github.io"):
    return {
        "version": "2.0",
        "routeKey": "POST /v1/briefs",
        "rawPath": "/v1/briefs",
        "headers": {"origin": origin, "content-type": "application/json"},
        "requestContext": {"http": {"method": "POST", "path": "/v1/briefs", "sourceIp": "203.0.113.4"}},
        "body": json.dumps(payload),
        "isBase64Encoded": False,
    }


def good_payload():
    return {
        "version": "phase5.1",
        "language": "en",
        "name": "Alya Prasetyo",
        "phone": "+62 812 0000 0000",
        "email": "alya@example.com",
        "preferredContact": "WhatsApp",
        "eventType": "Wedding",
        "product": "KASANE MUSUBI™ / 結び",
        "package": "Full KASANE",
        "direction": "Quiet Luxury",
        "city": "Surabaya",
        "date": "2027-06-12",
        "guests": "300",
        "message": "We want a calm evening wedding with full planning support.",
        "page": "https://swirawan.github.io/kasane-collective/",
        "captchaToken": "",
        "website": "",
    }


def test_email_contact_requires_email():
    payload = good_payload()
    payload["preferredContact"] = "Email"
    payload["email"] = ""
    _, errors = app._validate_and_normalize(payload)
    assert "email" in errors


def test_whatsapp_requires_phone():
    payload = good_payload()
    payload["phone"] = ""
    _, errors = app._validate_and_normalize(payload)
    assert "phone" in errors


def test_rejects_bad_origin():
    response = app.handler(event(good_payload(), "https://evil.example"), None)
    assert response["statusCode"] == 403


def test_accepts_and_returns_reference_when_storage_succeeds():
    with patch.object(app, "_store_lead", return_value="KAS-260908-ABC123"), patch.object(app, "_send_notification", return_value=False):
        response = app.handler(event(good_payload()), None)
    assert response["statusCode"] == 201
    body = json.loads(response["body"])
    assert body["reference"] == "KAS-260908-ABC123"


def test_honeypot_does_not_store():
    payload = good_payload()
    payload["website"] = "https://spam.invalid"
    with patch.object(app, "_store_lead") as store:
        response = app.handler(event(payload), None)
    assert response["statusCode"] == 201
    store.assert_not_called()
