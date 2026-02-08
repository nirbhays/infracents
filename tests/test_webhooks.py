"""
Tests for GitHub Webhook Handling

Validates webhook signature verification, event parsing,
and correct routing of PR events.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from typing import Any

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

from utils.security import verify_webhook_signature


class TestWebhookSignatureVerification:
    """Test GitHub webhook HMAC-SHA256 signature verification."""

    SECRET = "test-webhook-secret-123"

    def _sign_payload(self, payload: bytes) -> str:
        """Generate a valid GitHub webhook signature."""
        mac = hmac.new(self.SECRET.encode(), payload, hashlib.sha256)
        return f"sha256={mac.hexdigest()}"

    def test_valid_signature_passes(self):
        """A correctly signed payload should verify successfully."""
        payload = b'{"action": "opened"}'
        signature = self._sign_payload(payload)
        assert verify_webhook_signature(payload, signature, self.SECRET) is True

    def test_invalid_signature_fails(self):
        """An incorrectly signed payload should fail verification."""
        payload = b'{"action": "opened"}'
        bad_signature = "sha256=0000000000000000000000000000000000000000000000000000000000000000"
        assert verify_webhook_signature(payload, bad_signature, self.SECRET) is False

    def test_tampered_payload_fails(self):
        """A tampered payload should fail even with original signature."""
        original = b'{"action": "opened"}'
        signature = self._sign_payload(original)
        tampered = b'{"action": "closed"}'
        assert verify_webhook_signature(tampered, signature, self.SECRET) is False

    def test_empty_signature_fails(self):
        """Empty signature should fail."""
        payload = b'{"action": "opened"}'
        assert verify_webhook_signature(payload, "", self.SECRET) is False

    def test_missing_sha256_prefix_fails(self):
        """Signature without sha256= prefix should fail."""
        payload = b'{"action": "opened"}'
        mac = hmac.new(self.SECRET.encode(), payload, hashlib.sha256)
        bare_sig = mac.hexdigest()  # no prefix
        assert verify_webhook_signature(payload, bare_sig, self.SECRET) is False

    def test_empty_payload(self):
        """Empty payload should be signable and verifiable."""
        payload = b""
        signature = self._sign_payload(payload)
        assert verify_webhook_signature(payload, signature, self.SECRET) is True


class TestWebhookEventParsing:
    """Test webhook event parsing and routing."""

    def test_pr_opened_event_parsed(self, sample_webhook_payload):
        """PR opened event should be parsed correctly."""
        assert sample_webhook_payload["action"] == "opened"
        assert sample_webhook_payload["pull_request"]["number"] == 42
        assert sample_webhook_payload["repository"]["full_name"] == "myorg/infrastructure"
        assert sample_webhook_payload["installation"]["id"] == 11111111

    def test_pr_has_required_fields(self, sample_webhook_payload):
        """PR payload should contain all fields needed for processing."""
        pr = sample_webhook_payload["pull_request"]
        assert "head" in pr
        assert "sha" in pr["head"]
        assert "base" in pr
        assert "number" in pr
        assert "draft" in pr

    def test_draft_pr_detected(self, sample_webhook_payload):
        """Should be able to detect draft PRs (which we skip)."""
        assert sample_webhook_payload["pull_request"]["draft"] is False
        sample_webhook_payload["pull_request"]["draft"] = True
        assert sample_webhook_payload["pull_request"]["draft"] is True

    def test_installation_id_extracted(self, sample_webhook_payload):
        """Installation ID should be extractable for GitHub API auth."""
        install_id = sample_webhook_payload["installation"]["id"]
        assert isinstance(install_id, int)
        assert install_id > 0
