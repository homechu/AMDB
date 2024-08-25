import base64
import secrets

from Crypto.Cipher import AES
from Crypto.Cipher._mode_cbc import CbcMode
from Crypto.Util.Padding import pad, unpad


class AES_128_CBC:
    def __init__(self, key: str, iv: str = '') -> None:
        self.key = key
        self.iv = iv

    @classmethod
    def from_default(cls) -> 'AES_128_CBC':
        return cls(key=secrets.token_hex(16), iv=secrets.token_hex(8))

    @property
    def cipher(self) -> CbcMode:
        if getattr(self, '_cipher', None) is None:
            self._cipher = AES.new(self.key.encode(), AES.MODE_CBC, self.iv.encode())

        return self._cipher

    def cbc_encrypt(self, plaintext: str):
        """AES_128_CBC_decrypt 加密方法.

        説明:
            plaintext 為 預加密字段.
            key 為 AES KEY.
            iv 為 IV KEY.

        """
        plaintext = pad(plaintext.encode('utf-8'), AES.block_size)
        ct_bytes = self.cipher.encrypt(plaintext)
        return base64.b64encode(self.iv.encode() + ct_bytes).decode('utf-8')

    def cbc_decrypt(self, ciphertext: str):
        """AES_128_CBC_decrypt 解密方法.

        説明:
            ciphertext 為 預解密字段.
            key 為 AES KEY.
            iv 為 ciphertext 前 16 位元.

        """
        enc = base64.b64decode(ciphertext)
        self.iv = enc[:16].decode()
        return unpad(self.cipher.decrypt(enc[16:]), AES.block_size).decode('utf-8')
