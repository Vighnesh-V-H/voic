from cryptography.fernet import Fernet, InvalidToken


class TokenEncryptionError(ValueError):
    pass


def _fernet(encryption_key: str) -> Fernet:
    if not encryption_key:
        raise TokenEncryptionError("Token encryption is not configured")
    try:
        return Fernet(encryption_key.encode("utf-8"))
    except (TypeError, ValueError) as error:
        raise TokenEncryptionError("Token encryption is not configured") from error


def encrypt_token(token: str, encryption_key: str) -> str:
    return _fernet(encryption_key).encrypt(token.encode("utf-8")).decode("utf-8")


def decrypt_token(encrypted_token: str, encryption_key: str) -> str:
    try:
        return _fernet(encryption_key).decrypt(encrypted_token.encode("utf-8")).decode("utf-8")
    except (InvalidToken, UnicodeDecodeError) as error:
        raise TokenEncryptionError("Token could not be decrypted") from error
