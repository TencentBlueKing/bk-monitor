import os
import shutil
import tempfile
from unittest import TestCase

from apps.tgpa.handlers.decrypt import XorDecryptHandler


class TestXorDecryptHandler(TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.temp_dir, True)

    def _write_file(self, name, content):
        file_path = os.path.join(self.temp_dir, name)
        with open(file_path, "wb") as f:
            f.write(content)
        return file_path

    def test_decrypt_encrypted_plaintext_file(self):
        key = 0x23
        plaintext = b"Log file open\nhello tgpa\n"
        encrypted = bytes(byte ^ key for byte in plaintext)
        file_path = self._write_file("encrypted.log", encrypted)

        XorDecryptHandler(xor_key=key, unencrypted_prefix="Log file open").decrypt_file(file_path)

        with open(file_path, "rb") as f:
            self.assertEqual(f.read(), plaintext)

    def test_skip_plaintext_file(self):
        plaintext = b"Log file open\nhello tgpa\n"
        file_path = self._write_file("plaintext.log", plaintext)

        XorDecryptHandler(xor_key=0x23, unencrypted_prefix="Log file open").decrypt_file(file_path)

        with open(file_path, "rb") as f:
            self.assertEqual(f.read(), plaintext)

    def test_skip_unencrypted_binary_file(self):
        binary_data = bytes([0x00, 0xFF, 0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A, 0x00, 0x01])
        file_path = self._write_file("image.png", binary_data)

        XorDecryptHandler(xor_key=0x23, unencrypted_prefix="Log file open").decrypt_file(file_path)

        with open(file_path, "rb") as f:
            self.assertEqual(f.read(), binary_data)

    def test_skip_binary_file_without_unencrypted_prefix(self):
        binary_data = bytes([0x00, 0xFF, 0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A, 0x00, 0x01])
        file_path = self._write_file("image_without_prefix.png", binary_data)

        XorDecryptHandler(xor_key=0x23).decrypt_file(file_path)

        with open(file_path, "rb") as f:
            self.assertEqual(f.read(), binary_data)

    def test_skip_encrypted_plaintext_without_log_marker(self):
        key = 0x23
        plaintext = b"hello tgpa\nthis is not target log\n"
        encrypted = bytes(byte ^ key for byte in plaintext)
        file_path = self._write_file("other.log", encrypted)

        XorDecryptHandler(xor_key=key, unencrypted_prefix="Log file open").decrypt_file(file_path)

        with open(file_path, "rb") as f:
            self.assertEqual(f.read(), encrypted)
