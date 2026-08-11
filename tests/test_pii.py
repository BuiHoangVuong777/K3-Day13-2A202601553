from app.pii import scrub_text, scrub_value

def test_scrub_email() -> None:
    out = scrub_text("Email me at student@vinuni.edu.vn")
    assert "student@" not in out
    assert "REDACTED_EMAIL" in out


def test_scrub_common_vietnamese_phone_formats() -> None:
    phone_numbers = (
        "0901234567",
        "090 123 4567",
        "090.123.4567",
        "090-123-4567",
        "+84 90 123 4567",
    )

    for phone_number in phone_numbers:
        out = scrub_text(f"Contact: {phone_number}")
        assert phone_number not in out
        assert "REDACTED_PHONE_VN" in out

def test_scrub_cccd() -> None:
    raw = "CCCD: 001203012345"

    out = scrub_text(raw)

    assert "001203012345" not in out
    assert "REDACTED_CCCD" in out


def test_scrub_credit_card() -> None:
    raw = "Card: 4111 1111 1111 1111"

    out = scrub_text(raw)

    assert "4111 1111 1111 1111" not in out
    assert "REDACTED_CREDIT_CARD" in out


def test_scrub_bearer_token() -> None:
    raw = "Authorization: Bearer abcdefghijklmnop123456"

    out = scrub_text(raw)

    assert "abcdefghijklmnop123456" not in out
    assert "REDACTED_BEARER_TOKEN" in out


def test_scrub_sensitive_keys() -> None:
    raw = {
        "api_key": "sk-demo-1234567890",
        "password": "my-password-123",
        "tokens_in": 125,
    }

    out = scrub_value(raw)

    assert out["api_key"] == "[REDACTED_SECRET]"
    assert out["password"] == "[REDACTED_SECRET]"

    # Đây là usage metric, không phải secret
    assert out["tokens_in"] == 125


def test_scrub_nested_payload() -> None:
    raw = {
        "payload": {
            "user": {
                "email": "student@vinuni.edu.vn",
                "phone": "090 123 4567",
            }
        }
    }

    out = scrub_value(raw)

    rendered = str(out)

    assert "student@vinuni.edu.vn" not in rendered
    assert "090 123 4567" not in rendered

def test_scrub_entire_log_context() -> None:
    raw_log = {
        "event": "request_received",
        "service": "api",
        "session_id": "student@vinuni.edu.vn",
        "feature": "qa",
        "model": "fake-model",
        "payload": {
            "message": "Call me at 090 123 4567",
            "nested": {
                "cccd": "001203012345",
            },
        },
    }

    out = scrub_value(raw_log)

    rendered = str(out)

    assert "student@vinuni.edu.vn" not in rendered
    assert "090 123 4567" not in rendered
    assert "001203012345" not in rendered

def test_scrub_secret_fields() -> None:
    raw_log = {
        "authorization": "Bearer abcdefghijklmnop",
        "payload": {
            "api_key": "sk-demo-1234567890",
        },
    }

    out = scrub_value(raw_log)

    assert out["authorization"] == "[REDACTED_SECRET]"
    assert out["payload"]["api_key"] == "[REDACTED_SECRET]"

def test_scrub_nested_list() -> None:
    raw = {
        "users": [
            {
                "email": "user1@example.com",
                "phone": "0901234567",
            }
        ]
    }

    out = scrub_value(raw)
    rendered = str(out)

    assert "user1@example.com" not in rendered
    assert "0901234567" not in rendered

def test_phone_regex_does_not_corrupt_trace_id() -> None:
    trace_id = "0123456789fc941b1234567890abcdef"

    out = scrub_text(trace_id)

    assert out == trace_id
    assert "[REDACTED_PHONE_VN]" not in out

def test_real_phone_is_redacted() -> None:
    raw = "My phone is 0901234567"

    out = scrub_text(raw)

    assert "0901234567" not in out
    assert "[REDACTED_PHONE_VN]" in out