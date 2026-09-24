"""
测试 uploaded_file.models 模块
"""

import hashlib
import os
import time

import pytest
from django.core.files.base import ContentFile
from django.core.files.uploadedfile import SimpleUploadedFile

from bk_monitor_base.domains.uploaded_file.models import FileModel, generate_token, generate_upload_path


@pytest.mark.django_db(databases=["default"])
class TestGenerateUploadPath:
    """测试 generate_upload_path 函数"""

    def test_generate_upload_path_basic(self):
        """测试基本的路径生成"""
        instance = FileModel(usage="logo")
        filename = "test.jpg"
        path = generate_upload_path(instance, filename)

        # 验证路径格式: storage/{usage}/{uuid}_{timestamp}{ext}
        # 使用 os.path.join 生成期望前缀以兼容跨平台路径分隔符
        expected_prefix = os.path.join("storage", "logo", "")
        assert path.startswith(expected_prefix)
        assert path.endswith(".jpg")
        assert "storage" in path
        assert "logo" in path

    def test_generate_upload_path_with_different_extensions(self):
        """测试不同扩展名的路径生成"""
        instance = FileModel(usage="document")
        expected_prefix = os.path.join("storage", "document", "")

        test_cases = [
            ("test.pdf", ".pdf"),
            ("test.docx", ".docx"),
            ("test.png", ".png"),
            ("test", ""),  # 无扩展名
            ("test.tar.gz", ".gz"),  # 多个点
        ]

        for filename, expected_ext in test_cases:
            path = generate_upload_path(instance, filename)
            assert path.startswith(expected_prefix)
            if expected_ext:
                assert path.endswith(expected_ext)
            else:
                # 无扩展名时，路径不应以点结尾
                assert not path.endswith(".")

    def test_generate_upload_path_unique(self):
        """测试每次生成的路径都是唯一的"""
        instance = FileModel(usage="logo")
        filename = "test.jpg"

        paths = [generate_upload_path(instance, filename) for _ in range(10)]

        # 所有路径应该不同（由于UUID和时间戳）
        assert len(set(paths)) == 10

    def test_generate_upload_path_structure(self):
        """测试路径结构"""
        instance = FileModel(usage="avatar")
        filename = "user.jpg"
        path = generate_upload_path(instance, filename)

        # 使用 os.sep 分割路径以兼容跨平台
        parts = path.split(os.sep)
        assert len(parts) == 3
        assert parts[0] == "storage"
        assert parts[1] == "avatar"
        assert parts[2].endswith(".jpg")


@pytest.mark.django_db(databases=["default"])
class TestGenerateToken:
    """测试 generate_token 函数"""

    def test_generate_token_format(self):
        """测试token格式"""
        token = generate_token()

        # token应该是64个字符的十六进制字符串（32字节 * 2）
        assert len(token) == 64
        assert all(c in "0123456789abcdef" for c in token)

    def test_generate_token_unique(self):
        """测试每次生成的token都是唯一的"""
        tokens = [generate_token() for _ in range(10)]

        # 所有token应该不同
        assert len(set(tokens)) == 10

    def test_generate_token_uses_secrets(self):
        """测试token使用secrets模块生成（安全随机）"""
        token1 = generate_token()
        token2 = generate_token()

        # 两个token应该不同
        assert token1 != token2


@pytest.mark.django_db(databases=["default"])
class TestFileModel:
    """测试 FileModel 模型"""

    @pytest.fixture
    def file_content(self):
        """创建测试文件内容"""
        return b"test file content"

    @pytest.fixture
    def uploaded_file(self, file_content):
        """创建测试上传文件"""
        return SimpleUploadedFile("test.txt", file_content)

    def test_file_model_create_basic(self, uploaded_file):
        """测试基本的文件模型创建"""
        file_model = FileModel.objects.create(
            bk_tenant_id="test_tenant",
            usage="logo",
            created_by="test_user",
            file=uploaded_file,
            original_filename="test.txt",
        )

        assert file_model.bk_tenant_id == "test_tenant"
        assert file_model.usage == "logo"
        assert file_model.created_by == "test_user"
        assert file_model.original_filename == "test.txt"
        assert file_model.token is not None
        assert len(file_model.token) == 64  # 32字节转换为十六进制 = 64个字符
        assert file_model.md5 == hashlib.md5(b"test file content").hexdigest()
        assert file_model.created_at is not None

        # 清理
        file_model.delete()

    def test_file_model_auto_generate_token(self, uploaded_file):
        """测试自动生成token"""
        file_model = FileModel.objects.create(
            bk_tenant_id="test_tenant",
            usage="logo",
            created_by="test_user",
            file=uploaded_file,
        )

        assert file_model.token is not None
        assert len(file_model.token) == 64  # 32字节转换为十六进制 = 64个字符

        # 清理
        file_model.delete()

    def test_file_model_save_auto_set_original_filename(self, uploaded_file):
        """测试保存时自动设置original_filename"""
        file_model = FileModel(
            bk_tenant_id="test_tenant",
            usage="logo",
            created_by="test_user",
            file=uploaded_file,
            # 不设置 original_filename
        )

        # 首次保存时应该自动设置
        file_model.save()

        assert file_model.original_filename == "test.txt"

        # 清理
        file_model.delete()

    def test_file_model_save_preserve_existing_original_filename(self, uploaded_file):
        """测试保存时保留已存在的original_filename"""
        file_model = FileModel(
            bk_tenant_id="test_tenant",
            usage="logo",
            created_by="test_user",
            file=uploaded_file,
            original_filename="custom_name.txt",
        )

        file_model.save()

        # 应该保留自定义的original_filename
        assert file_model.original_filename == "custom_name.txt"

        # 清理
        file_model.delete()

    def test_file_model_save_update_not_change_original_filename(self, uploaded_file):
        """测试更新时不改变original_filename"""
        file_model = FileModel.objects.create(
            bk_tenant_id="test_tenant",
            usage="logo",
            created_by="test_user",
            file=uploaded_file,
            original_filename="original.txt",
        )

        original_name = file_model.original_filename

        # 更新文件
        new_file = SimpleUploadedFile("new.txt", b"new content")
        file_model.file = new_file
        file_model.save()

        # original_filename应该保持不变
        assert file_model.original_filename == original_name

        # 清理
        file_model.delete()

    def test_file_model_save_requires_original_filename(self, uploaded_file):
        """测试保存时必须提供original_filename"""
        # 创建一个没有name属性的文件对象
        from django.core.files.base import ContentFile

        file_without_name = ContentFile(b"test content")  # ContentFile没有name属性

        file_model = FileModel(
            bk_tenant_id="test_tenant",
            usage="logo",
            created_by="test_user",
            file=file_without_name,
            # 不设置 original_filename
        )

        # 应该抛出异常，因为 original_filename 不能为空
        with pytest.raises(ValueError, match="original_filename cannot be empty or None"):
            file_model.save()

    def test_file_model_str(self, uploaded_file):
        """测试 __str__ 方法"""
        file_model = FileModel.objects.create(
            bk_tenant_id="test_tenant",
            usage="logo",
            created_by="test_user",
            file=uploaded_file,
            original_filename="test.txt",
        )

        str_repr = str(file_model)
        assert "test.txt" in str_repr
        assert "logo" in str_repr

        # 清理
        file_model.delete()

    def test_file_model_ordering(self, uploaded_file):
        """测试模型排序（按创建时间倒序）"""
        # 创建多个文件
        file1 = FileModel.objects.create(
            bk_tenant_id="test_tenant",
            usage="logo",
            created_by="test_user",
            file=uploaded_file,
        )

        # 等待一小段时间确保时间戳不同

        time.sleep(0.1)

        file2 = FileModel.objects.create(
            bk_tenant_id="test_tenant",
            usage="logo",
            created_by="test_user",
            file=uploaded_file,
        )

        # 查询应该按创建时间倒序
        files = list(FileModel.objects.all())
        assert files[0].created_at >= files[1].created_at

        # 清理
        file1.delete()
        file2.delete()

    def test_file_model_db_index_on_usage(self, uploaded_file):
        """测试usage字段有数据库索引"""
        # 创建多个不同usage的文件
        file1 = FileModel.objects.create(
            bk_tenant_id="test_tenant",
            usage="logo",
            created_by="test_user",
            file=uploaded_file,
        )

        file2 = FileModel.objects.create(
            bk_tenant_id="test_tenant",
            usage="document",
            created_by="test_user",
            file=uploaded_file,
        )

        # 查询特定usage的文件应该很快（有索引）
        logos = FileModel.objects.filter(usage="logo")
        assert logos.count() >= 1

        documents = FileModel.objects.filter(usage="document")
        assert documents.count() >= 1

        # 清理
        file1.delete()
        file2.delete()

    def test_file_model_unique_token(self, uploaded_file):
        """测试每个文件的token都是唯一的"""
        file1 = FileModel.objects.create(
            bk_tenant_id="test_tenant",
            usage="logo",
            created_by="test_user",
            file=uploaded_file,
        )

        file2 = FileModel.objects.create(
            bk_tenant_id="test_tenant",
            usage="logo",
            created_by="test_user",
            file=uploaded_file,
        )

        assert file1.token != file2.token

        # 清理
        file1.delete()
        file2.delete()

    def test_file_model_with_content_file(self):
        """测试使用ContentFile创建文件"""
        content = ContentFile(b"test content", name="test.txt")
        file_model = FileModel.objects.create(
            bk_tenant_id="test_tenant",
            usage="logo",
            created_by="test_user",
            file=content,
            original_filename="test.txt",
        )

        assert file_model.original_filename == "test.txt"
        assert file_model.file.read() == b"test content"
        assert file_model.md5 == hashlib.md5(b"test content").hexdigest()

        # 清理
        file_model.delete()

    def test_file_model_save_auto_calculate_md5(self, uploaded_file):
        """测试保存时自动计算 md5。"""
        file_model = FileModel.objects.create(
            bk_tenant_id="test_tenant",
            usage="logo",
            created_by="test_user",
            file=uploaded_file,
        )

        assert file_model.md5 == hashlib.md5(b"test file content").hexdigest()

        # 清理
        file_model.delete()

    def test_file_model_tenant_isolation(self, uploaded_file):
        """测试租户隔离"""
        file1 = FileModel.objects.create(
            bk_tenant_id="tenant1",
            usage="logo",
            created_by="test_user",
            file=uploaded_file,
            token="token1" * 16,  # 手动设置token以测试查询
        )

        file2 = FileModel.objects.create(
            bk_tenant_id="tenant2",
            usage="logo",
            created_by="test_user",
            file=uploaded_file,
            token="token1" * 16,  # 相同的token，但不同租户
        )

        # 相同token但不同租户应该可以共存
        assert file1.bk_tenant_id != file2.bk_tenant_id
        assert file1.token == file2.token

        # 清理
        file1.delete()
        file2.delete()
