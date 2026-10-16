"""Small RFC 6238 TOTP implementation for administrator login."""
import base64
import hashlib
import hmac
import secrets
import struct
import time
from urllib.parse import quote


def new_secret() -> str:
    return base64.b32encode(secrets.token_bytes(20)).decode("ascii").rstrip("=")


def provisioning_uri(secret: str, username: str) -> str:
    label = quote(f"Auto Group:{username}")
    return f"otpauth://totp/{label}?secret={secret}&issuer=Auto%20Group&digits=6&period=30"


def verify_totp(secret: str, code: str, now: float | None = None) -> bool:
    if len(code) != 6 or not code.isdigit():
        return False
    try:
        key = base64.b32decode(secret + "=" * (-len(secret) % 8), casefold=True)
    except (ValueError, TypeError):
        return False
    counter = int((time.time() if now is None else now) // 30)
    for offset in (-1, 0, 1):
        digest = hmac.new(key, struct.pack(">Q", counter + offset), hashlib.sha1).digest()
        index = digest[-1] & 0x0F
        value = struct.unpack(">I", digest[index:index + 4])[0] & 0x7FFFFFFF
        if hmac.compare_digest(f"{value % 1_000_000:06d}", code):
            return True
    return False
