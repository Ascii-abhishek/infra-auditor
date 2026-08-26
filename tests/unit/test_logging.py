from infra_auditor.logging import redact_value


def test_redact_value_redacts_sensitive_nested_keys() -> None:
    payload = {
        "username": "safe",
        "password": "fake-password",
        "nested": {"SecretString": "fake-secret", "items": [{"access_key": "fake-key"}]},
    }

    redacted = redact_value(payload)

    assert redacted["username"] == "safe"
    assert redacted["password"] == "[REDACTED]"
    assert redacted["nested"]["SecretString"] == "[REDACTED]"
    assert redacted["nested"]["items"][0]["access_key"] == "[REDACTED]"
