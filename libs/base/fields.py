import base64

from ast import literal_eval

from cryptography.fernet import Fernet
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from django.db.models import CharField
from rest_framework import serializers

from main.settings import CRYPT_KEY, CRYPTOR, SECRET_KEY


class PasswordField(serializers.CharField):
    """
    敏感數據，在serializer使用 PasswordFields
    密碼字段，正常寫入，讀取顯示 *
    """

    def to_representation(self, value):
        if value:
            _, value = CRYPTOR.pass_decrypt(value)
        return '*' * len(value)

    def to_internal_value(self, data):
        data = CRYPTOR.make_password(data)
        return super().to_internal_value(data)


class SecureCryptField(CharField):
    """自订资料库加密栏位"""

    # 最多能支援127个位元密码
    max_length = 255
    salt = bytes(SECRET_KEY, encoding="raw_unicode_escape")
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=100000,
        backend=default_backend(),
    )

    key = base64.urlsafe_b64encode(kdf.derive(CRYPT_KEY.encode("utf-8")))
    f = Fernet(key)

    def from_db_value(self, value, expression, connection):
        if value is None or not isinstance(value, str):
            return value
        return self.f.decrypt(bytes(value, encoding="utf-8")).decode("utf-8")

    def get_prep_value(self, value):
        if value is None or not isinstance(value, str):
            return value
        return self.f.encrypt(bytes(value, encoding="utf-8"))

    def decrypt(self, data):
        return self.f.decrypt(bytes(data, encoding="utf-8"))

    def encrypt(self, data):
        return self.f.encrypt(bytes(data, encoding="utf-8"))


class ListField(serializers.ListField):
    def to_representation(self, data):
        """
        List of object instances -> List of dicts of primitive datatypes.
        """
        if not data:
            return []
        else:
            data = literal_eval(data)
            return [
                self.child.to_representation(item) if item is not None else None for item in data
            ]
