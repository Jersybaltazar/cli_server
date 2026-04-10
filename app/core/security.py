"""
Utilidades de seguridad: hashing de contraseñas y cifrado de PII (Fernet).
"""

import asyncio
import hashlib
import hmac
from concurrent.futures import ThreadPoolExecutor

from cryptography.fernet import Fernet
from passlib.context import CryptContext

from app.config import get_settings

settings = get_settings()

# ── Hashing de contraseñas ───────────────────────────
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Pool de threads dedicado para operaciones CPU-intensivas (bcrypt)
# para no bloquear el event loop de asyncio.
_executor = ThreadPoolExecutor(max_workers=4)


# Hash pre-calculado para timing-safe "usuario no encontrado".
# Evita que un atacante distinga "no existe" (~0ms) de "password mal" (~300ms).
DUMMY_HASH: str = pwd_context.hash("dummy-timing-safe-placeholder")


def hash_password(password: str) -> str:
    """Genera hash bcrypt de una contraseña (síncrono)."""
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verifica una contraseña contra su hash bcrypt (síncrono)."""
    return pwd_context.verify(plain_password, hashed_password)


async def hash_password_async(password: str) -> str:
    """Genera hash bcrypt sin bloquear el event loop."""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(_executor, pwd_context.hash, password)


async def verify_password_async(plain_password: str, hashed_password: str) -> bool:
    """Verifica contraseña contra hash bcrypt sin bloquear el event loop."""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(
        _executor, pwd_context.verify, plain_password, hashed_password
    )


# ── Cifrado de PII (Fernet) ─────────────────────────
_fernet: Fernet | None = None


def _get_fernet() -> Fernet:
    global _fernet
    if _fernet is None:
        key = settings.FERNET_KEY
        if key == "your-fernet-key-here":
            raise RuntimeError(
                "FERNET_KEY no configurada. Genera una con: "
                'python -c "from cryptography.fernet import Fernet; '
                'print(Fernet.generate_key().decode())" y ponla en .env'
            )
        _fernet = Fernet(key.encode() if isinstance(key, str) else key)
    return _fernet


def encrypt_pii(value: str) -> str:
    """Cifra un campo PII (DNI, teléfono, email) con Fernet."""
    if not value:
        return value
    f = _get_fernet()
    return f.encrypt(value.encode()).decode()


def decrypt_pii(encrypted_value: str) -> str:
    """Descifra un campo PII cifrado con Fernet.
    Si el valor no es un token Fernet válido (datos pre-encriptación),
    lo devuelve tal cual.
    """
    if not encrypted_value:
        return encrypted_value
    f = _get_fernet()
    try:
        return f.decrypt(encrypted_value.encode()).decode()
    except Exception:
        # Dato almacenado en texto plano (pre-encriptación)
        return encrypted_value


# ── Verificación QR — HMAC tokens (Fase 2.5) ──────

def generate_verification_token(prescription_id: str) -> str:
    """Genera un token HMAC-SHA256 truncado (8 hex chars) para verificación QR."""
    key = settings.FERNET_KEY.encode()
    msg = f"rx-verify:{prescription_id}".encode()
    mac = hmac.new(key, msg, hashlib.sha256).hexdigest()[:8]
    return mac


def verify_verification_token(prescription_id: str, token: str) -> bool:
    """Verifica un token HMAC de receta (timing-safe)."""
    expected = generate_verification_token(prescription_id)
    return hmac.compare_digest(expected, token)
