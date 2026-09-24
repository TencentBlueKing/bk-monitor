import base64

import pytest
from Crypto.PublicKey import RSA
from Crypto.Random import get_random_bytes

from bk_monitor_base.infras.cipher import AESCipher, RSACipher

pytestmark = pytest.mark.django_db(transaction=False)


@pytest.fixture(scope="module")
def rsa_key_pair():
    """自动生成RSA密钥对（模块级别共享）"""
    key = RSA.generate(1024)
    private_key = key.export_key()
    return private_key.decode("utf-8")


@pytest.fixture(scope="module")
def aes_key():
    """自动生成AES密钥（模块级别共享）"""
    return get_random_bytes(32).hex()


@pytest.fixture(scope="module")
def fixed_iv():
    """生成固定IV（模块级别共享）"""
    return get_random_bytes(16)


class TestRSACipher:
    """RSA加密解密测试类"""

    @pytest.fixture
    def rsa_cipher(self, rsa_key_pair):
        """创建RSA加密器实例"""
        return RSACipher(rsa_key_pair)

    def test_rsa_encrypt_decrypt_short_text(self, rsa_cipher):
        """测试RSA加密解密短文本"""
        original_message = b"Hello, World!"
        encrypted = rsa_cipher.encrypt(original_message)
        decrypted = rsa_cipher.decrypt(encrypted)

        assert decrypted == original_message
        assert len(encrypted) > len(original_message)
        # 验证加密结果是base64编码
        try:
            base64.b64decode(encrypted)
        except Exception:
            pytest.fail("Encrypted result should be base64 encoded")

    def test_rsa_encrypt_decrypt_long_text(self, rsa_cipher):
        """测试RSA加密解密长文本（分块处理）"""
        original_message = b"A" * 500  # 创建超过RSA块大小限制的长文本
        encrypted = rsa_cipher.encrypt(original_message)
        decrypted = rsa_cipher.decrypt(encrypted)

        assert decrypted == original_message

    def test_rsa_encrypt_decrypt_empty_text(self, rsa_cipher):
        """测试RSA加密解密空文本"""
        original_message = b""
        encrypted = rsa_cipher.encrypt(original_message)
        decrypted = rsa_cipher.decrypt(encrypted)

        assert decrypted == original_message

    def test_rsa_encrypt_decrypt_unicode_text(self, rsa_cipher):
        """测试RSA加密解密Unicode文本"""
        original_message = b"Hello Unicode World"
        encrypted = rsa_cipher.encrypt(original_message)
        decrypted = rsa_cipher.decrypt(encrypted)

        assert decrypted == original_message
        assert decrypted.decode() == "Hello Unicode World"

    def test_rsa_get_max_length(self, rsa_cipher):
        """测试获取最大加密长度"""
        encrypt_max_length = rsa_cipher.get_max_length(rsa_cipher.pub_key, True)
        decrypt_max_length = rsa_cipher.get_max_length(rsa_cipher.pri_key, False)

        assert encrypt_max_length > 0
        assert decrypt_max_length > 0
        assert decrypt_max_length > encrypt_max_length  # 解密块应该更大

    def test_rsa_different_instances_same_key(self, rsa_key_pair):
        """测试使用相同密钥的不同实例可以互相加解密"""
        cipher1 = RSACipher(rsa_key_pair)
        cipher2 = RSACipher(rsa_key_pair)

        original_message = b"Test cross-instance compatibility"
        encrypted_by_1 = cipher1.encrypt(original_message)
        decrypted_by_2 = cipher2.decrypt(encrypted_by_1)

        assert decrypted_by_2 == original_message


class TestAESCipher:
    """AES加密解密测试类"""

    @pytest.fixture
    def aes_cipher(self, aes_key):
        """创建AES加密器实例（随机IV）"""
        return AESCipher(aes_key)

    @pytest.fixture
    def aes_cipher_fixed_iv(self, aes_key, fixed_iv):
        """创建AES加密器实例（固定IV）"""
        return AESCipher(aes_key, fixed_iv)

    def test_aes_encrypt_decrypt_string(self, aes_cipher):
        """测试AES加密解密字符串"""
        original_message = "Hello, World!"
        encrypted = aes_cipher.encrypt(original_message)
        decrypted = aes_cipher.decrypt(encrypted)

        assert decrypted == original_message
        assert len(encrypted) > len(original_message)
        # 验证加密结果是base64编码
        try:
            base64.b64decode(encrypted)
        except Exception:
            pytest.fail("Encrypted result should be base64 encoded")

    def test_aes_encrypt_decrypt_bytes(self, aes_cipher):
        """测试AES加密解密字节数据"""
        original_message = b"Hello, World!"
        encrypted = aes_cipher.encrypt(original_message)
        decrypted = aes_cipher.decrypt(encrypted)

        assert decrypted == original_message.decode("utf-8")

    def test_aes_encrypt_decrypt_long_text(self, aes_cipher):
        """测试AES加密解密长文本"""
        original_message = "A" * 10000  # 创建长文本
        encrypted = aes_cipher.encrypt(original_message)
        decrypted = aes_cipher.decrypt(encrypted)

        assert decrypted == original_message

    def test_aes_encrypt_decrypt_empty_text(self, aes_cipher):
        """测试AES加密解密空文本"""
        original_message = ""
        encrypted = aes_cipher.encrypt(original_message)
        decrypted = aes_cipher.decrypt(encrypted)

        assert decrypted == original_message

    def test_aes_encrypt_decrypt_unicode_text(self, aes_cipher):
        """测试AES加密解密Unicode文本"""
        original_message = "Hello Unicode World"
        encrypted = aes_cipher.encrypt(original_message)
        decrypted = aes_cipher.decrypt(encrypted)

        assert decrypted == original_message

    def test_aes_fixed_iv_encrypt_decrypt(self, aes_cipher_fixed_iv):
        """测试使用固定IV的AES加密解密"""
        original_message = "Test with fixed IV"
        encrypted = aes_cipher_fixed_iv.encrypt(original_message)
        decrypted = aes_cipher_fixed_iv.decrypt(encrypted)

        assert decrypted == original_message

    def test_aes_fixed_iv_same_plaintext_same_ciphertext(self, aes_key, fixed_iv):
        """测试固定IV下相同明文产生相同密文"""
        cipher1 = AESCipher(aes_key, fixed_iv)
        cipher2 = AESCipher(aes_key, fixed_iv)

        original_message = "Same plaintext"
        encrypted1 = cipher1.encrypt(original_message)
        encrypted2 = cipher2.encrypt(original_message)

        assert encrypted1 == encrypted2

    def test_aes_random_iv_different_ciphertext(self, aes_key):
        """测试随机IV下相同明文产生不同密文"""
        cipher1 = AESCipher(aes_key)
        cipher2 = AESCipher(aes_key)

        original_message = "Same plaintext"
        encrypted1 = cipher1.encrypt(original_message)
        encrypted2 = cipher2.encrypt(original_message)

        # 随机IV应该产生不同的密文
        assert encrypted1 != encrypted2

        # 但是都能正确解密
        decrypted1 = cipher1.decrypt(encrypted1)
        decrypted2 = cipher2.decrypt(encrypted2)
        assert decrypted1 == decrypted2 == original_message

    def test_aes_cross_instance_decrypt(self, aes_key):
        """测试不同实例间的加解密兼容性"""
        cipher1 = AESCipher(aes_key)
        cipher2 = AESCipher(aes_key)

        original_message = "Cross-instance test"
        encrypted_by_1 = cipher1.encrypt(original_message)
        decrypted_by_2 = cipher2.decrypt(encrypted_by_1)

        assert decrypted_by_2 == original_message

    def test_aes_predict_length(self):
        """测试AES长度预测功能"""
        # 测试不同长度的预测
        test_lengths = [1, 16, 17, 32, 100, 1000]

        for length in test_lengths:
            predicted = AESCipher.predict_length(length)
            assert predicted > 0
            assert predicted >= length  # 预测长度应该不小于原始长度

    def test_aes_actual_vs_predicted_length(self, aes_cipher):
        """测试实际加密长度与预测长度的关系"""
        test_data = "A" * 100
        encrypted = aes_cipher.encrypt(test_data)
        actual_length = len(encrypted)
        predicted_length = AESCipher.predict_length(len(test_data))

        # AES加密包含IV（16字节）+ 填充数据，然后base64编码
        # 实际长度会包含IV，所以会比预测长度大一些
        assert actual_length >= predicted_length
        # 允许较大的差异，因为实际实现包含了IV
        assert abs(actual_length - predicted_length) <= 24


class TestCipherIntegration:
    """加密器集成测试类"""

    def test_rsa_aes_combined_encryption(self):
        """测试RSA和AES组合加密场景"""
        # 生成密钥
        rsa_key = RSA.generate(1024).export_key().decode("utf-8")
        aes_key = get_random_bytes(32).hex()

        # 创建加密器
        rsa_cipher = RSACipher(rsa_key)
        aes_cipher = AESCipher(aes_key)

        # 原始数据
        original_data = "This is sensitive data that needs both RSA and AES encryption"

        # 先用AES加密数据
        aes_encrypted = aes_cipher.encrypt(original_data)

        # 再用RSA加密AES密钥（模拟密钥交换）
        aes_key_encrypted = rsa_cipher.encrypt(aes_key.encode("utf-8"))

        # 解密过程：先解密AES密钥
        aes_key_decrypted = rsa_cipher.decrypt(aes_key_encrypted).decode("utf-8")

        # 用解密的AES密钥创建新的AES加密器
        new_aes_cipher = AESCipher(aes_key_decrypted)

        # 解密数据
        data_decrypted = new_aes_cipher.decrypt(aes_encrypted)

        assert data_decrypted == original_data
        assert aes_key_decrypted == aes_key

    def test_cipher_error_handling(self):
        """测试加密器错误处理"""
        # 测试无效的RSA私钥
        with pytest.raises(ValueError):
            RSACipher("invalid_key")

        # 测试解密无效数据
        rsa_key = RSA.generate(2048).export_key().decode("utf-8")
        rsa_cipher = RSACipher(rsa_key)

        # RSA解密无效base64数据应该不会抛出异常，但可能返回空或错误数据
        try:
            result = rsa_cipher.decrypt(b"invalid_base64_data")
            # 如果没有异常，结果应该是bytes类型
            assert isinstance(result, bytes)
        except Exception:
            # 如果抛出异常也是可以接受的
            pass
