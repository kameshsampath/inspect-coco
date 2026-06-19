"""Tests for PEM normalization and base64 transport utilities."""

from __future__ import annotations

from pathlib import Path

from inspect_coco.config.pem import normalize_pem, pem_to_base64_payload, remote_key_path

VALID_PEM = """-----BEGIN PRIVATE KEY-----
MIIEvgIBADANBgkqhkiG9w0BAQEFAASCBKgwggSkAgEAAoIBAQC7o4qne60TB3pY
6rknWBMcKaMYR2RKhGa7RkwGI0R3ZBMZPCkijRiNbJOxBpn0LfEZSKIMQnLPeChi
kgZL4A+eUsYZMJjQEMeMSGafK4cTZ0aJQQRVQ8wlRJlONwB8dFJvSDHvGJPOZmOk
jJWDqCzBVIqWJyIjS+K0qBJfz5RjLKw5jM+hL9nHtLfG5H9ealqlnSr7JKtUfVW
-----END PRIVATE KEY-----
"""

SINGLE_LINE_PEM = "-----BEGIN PRIVATE KEY-----MIIEvgIBADANBgkqhkiG9w0BAQEFAASCBKgwggSkAgEAAoIBAQC7o4qne60TB3pY6rknWBMcKaMYR2RKhGa7RkwGI0R3ZBMZPCkijRiNbJOxBpn0LfEZSKIMQnLPeChikgZL4A-----END PRIVATE KEY-----"


class TestNormalizePem:
    def test_already_valid_pem_unchanged(self):
        result = normalize_pem(VALID_PEM)
        assert result.startswith("-----BEGIN PRIVATE KEY-----\n")
        assert "-----END PRIVATE KEY-----" in result
        assert "\n" in result

    def test_single_line_pem_gets_newlines(self):
        result = normalize_pem(SINGLE_LINE_PEM)
        lines = result.strip().splitlines()
        assert lines[0] == "-----BEGIN PRIVATE KEY-----"
        assert lines[-1] == "-----END PRIVATE KEY-----"
        # Body lines should be at most 64 chars
        for line in lines[1:-1]:
            assert len(line) <= 64

    def test_strips_whitespace(self):
        padded = f"   \n{VALID_PEM}\n   "
        result = normalize_pem(padded)
        assert result.startswith("-----BEGIN")

    def test_empty_string(self):
        result = normalize_pem("")
        assert result == ""


class TestPemToBase64Payload:
    def test_roundtrip(self, tmp_path: Path):
        pem_file = tmp_path / "test.p8"
        pem_file.write_text(VALID_PEM)

        import base64

        payload = pem_to_base64_payload(pem_file)
        decoded = base64.b64decode(payload).decode()
        assert "-----BEGIN PRIVATE KEY-----" in decoded
        assert "-----END PRIVATE KEY-----" in decoded

    def test_single_line_normalized_in_payload(self, tmp_path: Path):
        pem_file = tmp_path / "single.p8"
        pem_file.write_text(SINGLE_LINE_PEM)

        import base64

        payload = pem_to_base64_payload(pem_file)
        decoded = base64.b64decode(payload).decode()
        # Should be normalized with proper newlines
        assert decoded.startswith("-----BEGIN PRIVATE KEY-----\n")


class TestRemoteKeyPath:
    def test_deterministic(self):
        path1 = remote_key_path("default", "some-pem-content")
        path2 = remote_key_path("default", "some-pem-content")
        assert path1 == path2

    def test_different_content_different_path(self):
        path1 = remote_key_path("default", "content-a")
        path2 = remote_key_path("default", "content-b")
        assert path1 != path2

    def test_format(self):
        path = remote_key_path("myconn", "test-content")
        assert path.startswith("/root/.snowflake/private_key_myconn_")
        assert path.endswith(".p8")

    def test_different_connection_names(self):
        path1 = remote_key_path("eval", "content")
        path2 = remote_key_path("admin", "content")
        assert "eval" in path1
        assert "admin" in path2
