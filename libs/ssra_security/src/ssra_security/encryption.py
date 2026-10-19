"""OpenBao Transit column-level encryption client, multi-version keyring & re-wrapping (Section 12.3).

Encrypts sensitive fields (such as bound TINs or phone numbers in identity_link) using
OpenBao Transit (`vault:v<key_version>:<payload>`) so plaintext PII is never stored at rest,
and supports zero-downtime key rotation (`rewrap_ciphertext`).
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import os
import re
import unicodedata

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from ssra_core import McpErrorCode, SSRAError

_ENVELOPE_RE = re.compile(r"^vault:v(\d+):(.+)$")
_ARABIC_INDIC_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹", "01234567890123456789")


class OpenBaoTransitEncryptor:
    """Envelope encryptor compatible with OpenBao Transit `vault:v<N>:...` wire format and key rotation."""

    def __init__(
        self,
        master_key_material: str | None = None,
        key_version: int = 1,
        *,
        previous_keys: dict[int, str] | None = None,
    ) -> None:
        seed = (master_key_material or "ssra-openbao-transit-dev-key").encode("utf-8")
        self._key = hashlib.sha256(seed).digest()
        self._blind_index_key = hmac.new(
            self._key, b"ssra-openbao-blind-index-v1", hashlib.sha256
        ).digest()
        self._key_version = key_version
        self._keyring: dict[int, AESGCM] = {key_version: AESGCM(self._key)}
        if previous_keys:
            for ver, mat in previous_keys.items():
                k_bytes = hashlib.sha256(mat.encode("utf-8")).digest()
                self._keyring[int(ver)] = AESGCM(k_bytes)

    def encrypt_field(self, plaintext: str, *, context: str = "ssra-identity-link") -> str:
        nonce = os.urandom(12)
        aad = context.encode("utf-8")
        ct = self._keyring[self._key_version].encrypt(nonce, plaintext.encode("utf-8"), aad)
        b64 = base64.urlsafe_b64encode(nonce + ct).decode("ascii")
        return f"vault:v{self._key_version}:{b64}"

    def decrypt_field(self, ciphertext: str, *, context: str = "ssra-identity-link") -> str:
        match = _ENVELOPE_RE.match(ciphertext)
        if not match:
            raise SSRAError(
                McpErrorCode.VALIDATION_FAILED,
                "Invalid OpenBao transit ciphertext envelope prefix",
                status_code=400,
            )
        ver = int(match.group(1))
        b64 = match.group(2)
        cipher = self._keyring.get(ver)
        if cipher is None:
            raise SSRAError(
                McpErrorCode.VALIDATION_FAILED,
                f"Unknown OpenBao transit key version 'v{ver}'",
                status_code=400,
            )
        try:
            raw = base64.urlsafe_b64decode(b64.encode("ascii"))
            nonce, ct = raw[:12], raw[12:]
            pt = cipher.decrypt(nonce, ct, context.encode("utf-8"))
            return pt.decode("utf-8")
        except Exception as exc:
            raise SSRAError(
                McpErrorCode.NOT_AUTHORIZED,
                "OpenBao transit decryption failed (invalid AAD context or tampered ciphertext)",
                status_code=403,
            ) from exc

    def rewrap_ciphertext(self, ciphertext: str, *, context: str = "ssra-identity-link") -> str:
        """Re-encrypt a ciphertext from an older key version under the active key version."""
        pt = self.decrypt_field(ciphertext, context=context)
        return self.encrypt_field(pt, context=context)

    def blind_index(self, plaintext: str) -> str:
        """Compute a domain-separated HMAC-SHA256 blind index normalizing Arabic-Indic digits."""
        normalised = (
            unicodedata.normalize("NFKC", plaintext).translate(_ARABIC_INDIC_DIGITS).strip()
        )
        return hmac.new(
            self._blind_index_key, normalised.encode("utf-8"), hashlib.sha256
        ).hexdigest()
