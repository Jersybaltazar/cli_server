"""
Script para generar las claves RSA (RS256) para JWT.
Ejecutar una vez antes de iniciar la aplicación:

    python scripts/generate_keys.py
"""

import os
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa


def generate_rsa_keys():
    keys_dir = Path(__file__).parent.parent / "keys"
    keys_dir.mkdir(exist_ok=True)

    private_key_path = keys_dir / "private.pem"
    public_key_path = keys_dir / "public.pem"

    if private_key_path.exists():
        print(f"⚠️  Las claves ya existen en {keys_dir}")
        response = input("¿Desea regenerarlas? (s/N): ").strip().lower()
        if response != "s":
            print("Cancelado.")
            return

    # Generar clave privada RSA 2048
    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048,
    )

    # Guardar clave privada
    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    private_key_path.write_bytes(private_pem)
    print(f"✅ Clave privada generada: {private_key_path}")

    # Guardar clave pública
    public_key = private_key.public_key()
    public_pem = public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    public_key_path.write_bytes(public_pem)
    print(f"✅ Clave pública generada: {public_key_path}")

    # Generar Fernet key
    from cryptography.fernet import Fernet
    fernet_key = Fernet.generate_key().decode()
    print(f"\n🔑 Fernet key para .env (FERNET_KEY):\n   {fernet_key}")

    print("\n📌 Agrega las claves a tu .env:")
    print(f"   JWT_PRIVATE_KEY_PATH=./keys/private.pem")
    print(f"   JWT_PUBLIC_KEY_PATH=./keys/public.pem")
    print(f"   FERNET_KEY={fernet_key}")


if __name__ == "__main__":
    generate_rsa_keys()
