"""
Security utilities and encryption
"""
import base64
from cryptography.fernet import Fernet
from app.core.config import settings


def get_encryption_key() -> bytes:
    """Get encryption key for API keys"""
    # In production, this should be from environment variable
    # For now, derive from secret key
    return base64.urlsafe_b64encode(settings.SECRET_KEY.encode()[:32].ljust(32, b'0'))


def encrypt_api_key(api_key: str) -> str:
    """Encrypt an API key"""
    f = Fernet(get_encryption_key())
    encrypted = f.encrypt(api_key.encode())
    return base64.urlsafe_b64encode(encrypted).decode()


def decrypt_api_key(encrypted_key: str) -> str:
    """Decrypt an API key"""
    f = Fernet(get_encryption_key())
    encrypted_bytes = base64.urlsafe_b64decode(encrypted_key.encode())
    decrypted = f.decrypt(encrypted_bytes)
    return decrypted.decode()
