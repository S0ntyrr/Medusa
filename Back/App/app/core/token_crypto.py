import base64
import hashlib

from cryptography.fernet import Fernet

from app.core.config import get_settings


def _cipher() -> Fernet:
    key = base64.urlsafe_b64encode(hashlib.sha256(get_settings().secret_key.encode()).digest())
    return Fernet(key)


def encrypt_token(value: str) -> str:
    return _cipher().encrypt(value.encode()).decode()


def decrypt_token(value: str) -> str:
    return _cipher().decrypt(value.encode()).decode()