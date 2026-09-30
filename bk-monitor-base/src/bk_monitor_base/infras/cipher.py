# Removed unnecessary import of CbcMode


import base64
import hashlib
import math
from typing import final

from Crypto.Cipher import AES, PKCS1_v1_5
from Crypto.Cipher._mode_cbc import CbcMode
from Crypto.PublicKey import RSA
from Crypto.Random import get_random_bytes
from Crypto.Util import number


@final
class RSACipher:
    """RSA加密解密工具类

    使用PKCS1_v1_5填充方式的RSA加密解密实现。
    支持大数据分块加密解密，自动处理超长文本。
    """

    def __init__(self, pri_key: str):
        """初始化RSA加密器

        Args:
            pri_key (str): RSA私钥字符串
        """
        self.pri_key = RSA.importKey(pri_key)
        self.pub_key = self.pri_key.publickey()

    def get_max_length(self, rsa_key: RSA.RsaKey, encrypt: bool = True):
        """获取最大加密长度

        Args:
            rsa_key (RSA.RsaKey): RSA密钥
            encrypt (bool): 是否为加密模式

        Returns:
            int: 最大加密长度
        """
        blocksize = int(number.size(rsa_key.n) / 8)
        reserve_size = 11
        if not encrypt:
            reserve_size = 0
        maxlength = blocksize - reserve_size
        return maxlength

    def encrypt(self, encrypt_message: bytes) -> bytes:
        """加密文本

        Args:
            encrypt_message (bytes): 需要加密的消息

        Returns:
            bytes: 加密后的消息(base64)
        """
        encrypt_result = b""
        max_length = self.get_max_length(self.pub_key)
        cipher = PKCS1_v1_5.new(self.pub_key)
        while encrypt_message:
            input_data = encrypt_message[:max_length]
            encrypt_message = encrypt_message[max_length:]
            out_data = cipher.encrypt(input_data)
            encrypt_result += out_data
        encrypt_result = base64.b64encode(encrypt_result)
        return encrypt_result

    def decrypt(self, decrypt_message: bytes) -> bytes:
        """解密文本

        Args:
            decrypt_message (bytes): 需要解密的消息

        Returns:
            bytes: 解密后的消息
        """
        decrypt_result = b""
        max_length = self.get_max_length(self.pri_key, False)
        decrypt_message = base64.b64decode(decrypt_message)
        cipher = PKCS1_v1_5.new(self.pri_key)
        while decrypt_message:
            input_data = decrypt_message[:max_length]
            decrypt_message = decrypt_message[max_length:]
            out_data = cipher.decrypt(input_data, b"")
            decrypt_result += out_data
        return decrypt_result


@final
class AESCipher:
    """AES加密解密工具类

    使用AES-256-CBC模式进行加密解密。
    支持自定义IV或使用随机IV，使用PKCS#7填充方式。
    """

    def __init__(self, key: str, iv: bytes | None = None):
        """初始化AES加密器

        Args:
            key (str): 加密密钥字符串，将通过SHA256哈希处理
            iv (bytes | None): 初始化向量，如果为None则使用随机IV
        """
        self.bs: int = 16
        self.iv: bytes | None = iv
        self.key: bytes = hashlib.sha256(key.encode("utf-8")).digest()

    def encrypt(self, raw: bytes | str):
        """AES加密

        Args:
            raw (bytes | str): 需要加密的原始数据

        Returns:
            bytes: Base64编码的加密结果，包含IV和密文
        """
        if isinstance(raw, str):
            raw = raw.encode("utf-8")

        raw = self._pad(raw)
        iv = get_random_bytes(AES.block_size) if not self.iv else self.iv
        cipher: CbcMode = AES.new(self.key, AES.MODE_CBC, iv)  # pyright: ignore[reportUnknownMemberType]
        result = base64.b64encode(iv + cipher.encrypt(raw))
        return result

    def decrypt(self, enc: bytes | str):
        """AES解密

        Args:
            enc (bytes | str): Base64编码的加密数据

        Returns:
            str: 解密后的原始文本
        """
        if isinstance(enc, str):
            enc = enc.encode("utf-8")
        enc = base64.b64decode(enc)
        iv = enc[: AES.block_size] if not self.iv else self.iv
        cipher: CbcMode = AES.new(self.key, AES.MODE_CBC, iv)  # pyright: ignore[reportUnknownMemberType]

        if not self.iv:
            return self._unpad(cipher.decrypt(enc[AES.block_size :])).decode("utf-8")
        else:
            return self._unpad(cipher.decrypt(enc[len(iv) :])).decode("utf-8")

    def _pad(self, s: bytes):
        """
        使用PKCS#7填充给定的字节串，使其长度成为块大小（self.bs）的倍数。

        填充方法是添加若干个字节，每个字节的值为需要添加的字节数。

        参数:
            s (bytes): 需要填充的字节串。

        返回:
            bytes: 填充后的字节串。
        """
        padding_length = self.bs - len(s) % self.bs
        return s + bytes([padding_length] * padding_length)

    @staticmethod
    def _unpad(s: bytes):
        """
        去除填充的静态方法。

        该方法用于移除输入字节序列末尾的填充数据。填充数据的长度由字节序列的最后一个字节的值决定。

        参数:
            s (bytes): 输入的字节序列。

        返回:
            bytes: 去除填充后的字节序列。
        """
        return s[: -ord(s[len(s) - 1 :])]

    @staticmethod
    def predict_length(length: int):
        """预测AES加密后Base64编码的长度

        根据原始数据长度预测加密后经过Base64编码的字符串长度。
        考虑了PKCS#7填充和Base64编码的开销。

        Args:
            length (int): 原始数据长度

        Returns:
            int: 预测的加密后Base64字符串长度
        """
        return int(math.ceil(((length + 1) // 16 * 16 + 16) / 3.0)) * 4
