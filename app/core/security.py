"""
Utilidades de seguridad: hashing de contraseñas y cifrado de PII (Fernet).
"""

from cryptography.fernet import Fernet
from passlib.context import CryptContext

from app.config import get_settings

settings = get_settings()

# ── Hashing de contraseñas ───────────────────────────
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    """Genera hash bcrypt de una contraseña."""
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verifica una contraseña contra su hash bcrypt."""
    return pwd_context.verify(plain_password, hashed_password)


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
