import os
import shutil
import tempfile
import zipfile
from unittest import TestCase

from apps.tgpa.handlers.base import TGPAFileHandler


class TestSafeExtractall(TestCase):
    """测试 _safe_extractall 方法的路径穿越防护"""

    def setUp(self):
        self.extract_dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.extract_dir, True)
        self._zip_files = []

    def _create_zip(self, members: dict) -> str:
        """
        构造包含指定成员的 zip 文件。
        使用 writestr 直接指定成员名，可包含 ../ 等路径穿越字符。
        """
        tmp = tempfile.NamedTemporaryFile(suffix=".zip", delete=False)
        with zipfile.ZipFile(tmp, "w") as zf:
            for name, content in members.items():
                zf.writestr(name, content)
        tmp.close()
        self.addCleanup(os.unlink, tmp.name)
        return tmp.name

    def _extract(self, members: dict):
        """构造 zip 并执行安全解压，返回解压目录路径"""
        zip_path = self._create_zip(members)
        with zipfile.ZipFile(zip_path, "r") as zf:
            TGPAFileHandler._safe_extractall(zf, self.extract_dir)
        return self.extract_dir

    def test_normal_files_extracted(self):
        """正常文件应被正确解压且内容一致"""
        dest = self._extract(
            {
                "readme.txt": "hello",
                "subdir/data.log": "log content",
            }
        )

        with open(os.path.join(dest, "readme.txt")) as f:
            self.assertEqual(f.read(), "hello")
        with open(os.path.join(dest, "subdir", "data.log")) as f:
            self.assertEqual(f.read(), "log content")

    def test_path_traversal_members_skipped(self):
        """包含路径穿越的成员应被跳过，正常成员不受影响"""
        dest = self._extract(
            {
                "safe.txt": "ok",
                "../evil.txt": "bad",  # 直接穿越
                "../../etc/passwd": "fake",  # 多级穿越
                "dir1/../../escape.txt": "sneaky",  # 伪装子目录穿越
            }
        )

        # 正常文件存在
        self.assertTrue(os.path.isfile(os.path.join(dest, "safe.txt")))

        # 所有恶意文件均不存在（解压目录内和上级目录）
        parent = os.path.dirname(dest)
        for name in ("evil.txt", "escape.txt"):
            self.assertFalse(os.path.exists(os.path.join(dest, name)))
            self.assertFalse(os.path.exists(os.path.join(parent, name)))
        self.assertFalse(os.path.exists(os.path.join(dest, "etc", "passwd")))
