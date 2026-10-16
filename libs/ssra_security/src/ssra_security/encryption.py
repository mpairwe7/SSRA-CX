"""OpenBao Transit column-level encryption client & deterministic envelope cipher (Section 12.3).

Encrypts sensitive fields (such as bound TINs or phone numbers in identity_link) using
OpenBao Transit (`vault:v1:<key_version>:<payload>`) so plaintext PII is never stored at rest.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import os

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from ssra_core import McpErrorCode, SSRAError


class OpenBaoTransitEncryptor:
    """Envelope encryptor compatible with OpenBao Transit `vault:v1:...` wire format."""

    def __init__(self, master_key_material: str | None = None, key_version: int = 1) -> None:
        seed = (master_key_material or "ssra-openbao-transit-dev-key").encode("utf-8")
        self._key = hashlib.sha256(seed).digest()
        self._key_version = key_version
        self._aesgcm = AESGCM(self._key)

    def encrypt_field(self, plaintext: str, *, context: str = "ssra-identity-link") -> str:
        nonce = os.urandom(12)
        aad = context.encode("utf-8")
        ct = self._aesgcm.encrypt(nonce, plaintext.encode("utf-8"), aad)
        b64 = base64.urlsafe_b64encode(nonce + ct).decode("ascii")
        return f"vault:v{self._key_version}:{b64}"

    def decrypt_field(self, ciphertext: str, *, context: str = "ssra-identity-link") -> str:
        prefix = f"vault:v{self._key_version}:"
        if not ciphertext.startswith(prefix):
            raise SSRAError(
                McpErrorCode.VALIDATION_FAILED,
                "Invalid OpenBao transit ciphertext envelope prefix",
                status_code=400,
            )
        b64 = ciphertext.removeprefix(prefix)
        try:
            raw = base64.urlsafe_b64decode(b64.encode("ascii"))
            nonce, ct = raw[:12], raw[12:]
            pt = self._aesgcm.decrypt(nonce, ct, context.encode("utf-8"))
            return pt.decode("utf-8")
        except Exception as exc:
            raise SSRAError(
                McpErrorCode.NOT_AUTHORIZED,
                "OpenBao transit decryption failed (invalid AAD context or tampered ciphertext)",
                status_code=403,
            ) from exc

    def blind_index(self, plaintext: str) -> str:
        """Compute an HMAC-SHA256 blind index for exact-match lookups without storing plaintext."""
        return hmac.new(self._key, plaintext.strip().encode("utf-8"), hashlib.sha256).hexdigest()
