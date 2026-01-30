
from cryptography.fernet import Fernet
import os
import base64

# Simple key management - in production this should be in secure vault
# We look for a key file, if not found, we generate one
KEY_FILE = "secret.key"

def load_or_generate_key():
    if os.path.exists(KEY_FILE):
        with open(KEY_FILE, "rb") as key_file:
            return key_file.read()
    else:
        key = Fernet.generate_key()
        with open(KEY_FILE, "wb") as key_file:
            key_file.write(key)
        return key

cipher_suite = Fernet(load_or_generate_key())

def encrypt_file(file_data: bytes) -> bytes:
    """Encrypts bytes data using Fernet"""
    return cipher_suite.encrypt(file_data)

def decrypt_file(file_data: bytes) -> bytes:
    """Decrypts bytes data using Fernet"""
    return cipher_suite.decrypt(file_data)
