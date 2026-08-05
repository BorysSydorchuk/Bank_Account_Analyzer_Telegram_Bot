"""Fernet symmetric encryption for secrets stored at rest (S2-03: LLM provider API keys).

Fernet is AES-128-CBC + HMAC under one key, from the `cryptography` package's
recipes layer. Symmetric (one key encrypts and decrypts) is the right choice here —
asymmetric key pairs exist to let two different parties hold "can encrypt" vs "can
decrypt" separately (e.g. a public key anyone can encrypt with, but only the private
key holder can read); this app is both the writer and the only reader of these keys,
so there's no second party to separate a public key from, and asymmetric crypto would
just add key-pair management for no benefit.
"""
import os
from functools import lru_cache

from cryptography.fernet import Fernet, InvalidToken

__all__ = ["encrypt", "decrypt"]


@lru_cache(maxsize=1)
def _fernet() -> Fernet:
    secret = os.getenv("SETTINGS_SECRET")
    if not secret:
        raise RuntimeError(
            "SETTINGS_SECRET is not set. Generate one with: "
            "python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\""
        )
    return Fernet(secret.encode())


def encrypt(plaintext: str) -> str:
    """Encrypt a string for storage. Returns a URL-safe token, empty string stays empty
    (an unset API key shouldn't require decrypting anything when read back)."""
    if not plaintext:
        return ""
    return _fernet().encrypt(plaintext.encode()).decode()


def decrypt(ciphertext: str) -> str:
    """Decrypt a value produced by encrypt(). Raises ValueError if it can't be decrypted
    (wrong SETTINGS_SECRET, or the value was never actually encrypted)."""
    if not ciphertext:
        return ""
    try:
        return _fernet().decrypt(ciphertext.encode()).decode()
    except InvalidToken as exc:
        raise ValueError("Stored value could not be decrypted — SETTINGS_SECRET may have changed.") from exc
