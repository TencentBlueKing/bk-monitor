"""
测试 uploaded_file.operation 模块
"""

import hashlib
import io

import pytest
from django.core.exceptions import ObjectDoesNotExist
from django.core.files.base import ContentFile, File
from django.core.files.uploadedfile import SimpleUploadedFile

from bk_monitor_base.domains.uploaded_file.models import FileModel
from bk_monitor_base.domains.uploaded_file.operation import FileInfo, get_file, save_file


@pytest.mark.django_db(databases=["default"])
class TestSaveFile:
    """测试 save_file 函数"""

    def test_save_file_with_content_file(self):
        """测试使用ContentFile保存文件"""
        content = ContentFile(b"test content", name="test.txt")
        file_info = save_file(
            bk_tenant_id="test_tenant",
            usage="logo",
            created_by="test_user",
            file_or_content=content,
            filename="test.txt",
        )

        assert isinstance(file_info, FileInfo)
        assert len(file_info.token) == 64  # 32字节转换为十六进制 = 64个字符
        assert file_info.md5 == hashlib.md5(b"test content").hexdigest()

        # 验证文件已保存
        file_model = FileModel.objects.get(token=file_info.token)
        assert file_model.bk_tenant_id == "test_tenant"
        assert file_model.usage == "logo"
        assert file_model.created_by == "test_user"
        assert file_model.original_filename == "test.txt"
        assert file_model.file.read() == b"test content"

        # 清理
        file_model.delete()

    def test_save_file_with_simple_uploaded_file(self):
        """测试使用SimpleUploadedFile保存文件"""
        uploaded_file = SimpleUploadedFile("test.txt", b"test content")
        file_info = save_file(
            bk_tenant_id="test_tenant",
            usage="document",
            created_by="test_user",
            file_or_content=uploaded_file,
            filename="test.txt",
        )

        assert isinstance(file_info, FileInfo)

        # 验证文件已保存
        file_model = FileModel.objects.get(token=file_info.token)
        assert file_model.original_filename == "test.txt"

        # 清理
        file_model.delete()

    def test_save_file_with_bytes(self):
        """测试使用bytes保存文件"""
        content_bytes = b"test bytes content"
        file_info = save_file(
            bk_tenant_id="test_tenant",
            usage="logo",
            created_by="test_user",
            file_or_content=content_bytes,
            filename="test.bin",
        )

        assert isinstance(file_info, FileInfo)

        # 验证文件已保存
        file_model = FileModel.objects.get(token=file_info.token)
        assert file_model.original_filename == "test.bin"
        assert file_model.file.read() == content_bytes

        # 清理
        file_model.delete()

    def test_save_file_with_string(self):
        """测试使用字符串保存文件"""
        content_str = "test string content"
        file_info = save_file(
            bk_tenant_id="test_tenant",
            usage="logo",
            created_by="test_user",
            file_or_content=content_str,
            filename="test.txt",
        )

        assert isinstance(file_info, FileInfo)

        # 验证文件已保存
        file_model = FileModel.objects.get(token=file_info.token)
        assert file_model.original_filename == "test.txt"
        assert file_model.file.read() == content_str.encode("utf-8")

        # 清理
        file_model.delete()

    def test_save_file_with_file_object_with_name(self):
        """测试使用有name属性的文件对象保存文件"""
        file_obj = SimpleUploadedFile("original.txt", b"test content")
        file_info = save_file(
            bk_tenant_id="test_tenant",
            usage="logo",
            created_by="test_user",
            file_or_content=file_obj,
            # 不提供filename，应该从file_obj.name获取
        )

        assert isinstance(file_info, FileInfo)

        # 验证文件已保存
        file_model = FileModel.objects.get(token=file_info.token)
        assert file_model.original_filename == "original.txt"

        # 清理
        file_model.delete()

    def test_save_file_with_file_object_without_name(self):
        """测试使用没有name属性的文件对象保存文件（需要提供filename）"""
        file_obj = ContentFile(b"test content")  # ContentFile没有name属性

        # 不提供filename应该抛出异常
        with pytest.raises(ValueError, match="Filename must be provided"):
            save_file(
                bk_tenant_id="test_tenant",
                usage="logo",
                created_by="test_user",
                file_or_content=file_obj,
                # 不提供filename
            )

    def test_save_file_with_bytes_without_filename(self):
        """测试使用bytes但不提供filename时抛出异常"""
        content_bytes = b"test content"

        with pytest.raises(ValueError, match="Filename must be provided"):
            save_file(
                bk_tenant_id="test_tenant",
                usage="logo",
                created_by="test_user",
                file_or_content=content_bytes,
                # 不提供filename
            )

    def test_save_file_with_string_without_filename(self):
        """测试使用字符串但不提供filename时抛出异常"""
        content_str = "test content"

        with pytest.raises(ValueError, match="Filename must be provided"):
            save_file(
                bk_tenant_id="test_tenant",
                usage="logo",
                created_by="test_user",
                file_or_content=content_str,
                # 不提供filename
            )

    def test_save_file_different_usages(self):
        """测试保存不同用途的文件"""
        content = ContentFile(b"test content", name="test.txt")

        usages = ["logo", "document", "avatar", "attachment"]
        tokens = []

        for usage in usages:
            file_info = save_file(
                bk_tenant_id="test_tenant",
                usage=usage,
                created_by="test_user",
                file_or_content=content,
                filename="test.txt",
            )
            tokens.append(file_info.token)

            # 验证文件已保存
            file_model = FileModel.objects.get(token=file_info.token)
            assert file_model.usage == usage

        # 清理
        for token in tokens:
            FileModel.objects.get(token=token).delete()

    def test_save_file_different_tenants(self):
        """测试不同租户保存文件"""
        content = ContentFile(b"test content", name="test.txt")

        file_info1 = save_file(
            bk_tenant_id="tenant1",
            usage="logo",
            created_by="test_user",
            file_or_content=content,
            filename="test.txt",
        )

        file_info2 = save_file(
            bk_tenant_id="tenant2",
            usage="logo",
            created_by="test_user",
            file_or_content=content,
            filename="test.txt",
        )

        # 两个token应该不同
        assert file_info1.token != file_info2.token

        # 验证两个文件都已保存
        file1 = FileModel.objects.get(token=file_info1.token)
        file2 = FileModel.objects.get(token=file_info2.token)

        assert file1.bk_tenant_id == "tenant1"
        assert file2.bk_tenant_id == "tenant2"

        # 清理
        file1.delete()
        file2.delete()

    def test_save_file_returns_file_info(self):
        """测试save_file返回 FileInfo。"""
        content = ContentFile(b"test content", name="test.txt")
        file_info = save_file(
            bk_tenant_id="test_tenant",
            usage="logo",
            created_by="test_user",
            file_or_content=content,
            filename="test.txt",
        )

        assert isinstance(file_info, FileInfo)
        assert len(file_info.token) == 64
        assert file_info.filename == "test.txt"
        assert file_info.md5 == hashlib.md5(b"test content").hexdigest()

        # 清理
        FileModel.objects.get(token=file_info.token).delete()

    def test_save_file_preserves_file_content(self):
        """测试保存文件时保留文件内容"""
        original_content = b"original file content with special chars: \x00\x01\x02"
        content = ContentFile(original_content, name="test.bin")
        file_info = save_file(
            bk_tenant_id="test_tenant",
            usage="logo",
            created_by="test_user",
            file_or_content=content,
            filename="test.bin",
        )

        # 验证文件内容完整保留
        file_model = FileModel.objects.get(token=file_info.token)
        saved_content = file_model.file.read()
        assert saved_content == original_content

        # 清理
        file_model.delete()

    def test_save_file_with_large_content(self):
        """测试保存大文件"""
        large_content = b"x" * 1024 * 1024  # 1MB
        content = ContentFile(large_content, name="large.bin")
        file_info = save_file(
            bk_tenant_id="test_tenant",
            usage="logo",
            created_by="test_user",
            file_or_content=content,
            filename="large.bin",
        )

        # 验证大文件已保存
        file_model = FileModel.objects.get(token=file_info.token)
        assert len(file_model.file.read()) == len(large_content)

        # 清理
        file_model.delete()

    def test_save_file_with_unicode_filename(self):
        """测试保存带Unicode字符的文件名"""
        content = ContentFile(b"test content", name="测试文件.txt")
        file_info = save_file(
            bk_tenant_id="test_tenant",
            usage="logo",
            created_by="test_user",
            file_or_content=content,
            filename="测试文件.txt",
        )

        # 验证Unicode文件名已保存
        file_model = FileModel.objects.get(token=file_info.token)
        assert file_model.original_filename == "测试文件.txt"

        # 清理
        file_model.delete()

    def test_save_file_with_empty_content(self):
        """测试保存空文件"""
        content = ContentFile(b"", name="empty.txt")
        file_info = save_file(
            bk_tenant_id="test_tenant",
            usage="logo",
            created_by="test_user",
            file_or_content=content,
            filename="empty.txt",
        )

        # 验证空文件已保存
        file_model = FileModel.objects.get(token=file_info.token)
        assert file_model.file.read() == b""

        # 清理
        file_model.delete()

    def test_save_file_with_bytesio(self):
        """测试使用BytesIO保存文件"""
        bytes_io = io.BytesIO(b"bytesio content")
        file_info = save_file(
            bk_tenant_id="test_tenant",
            usage="logo",
            created_by="test_user",
            file_or_content=bytes_io,
            filename="bytesio.txt",
        )

        # 验证文件已保存
        file_model = FileModel.objects.get(token=file_info.token)
        assert file_model.original_filename == "bytesio.txt"
        assert file_model.file.read() == b"bytesio content"

        # 清理
        file_model.delete()

    def test_save_file_with_stringio(self):
        """测试使用StringIO保存文件"""
        string_io = io.StringIO("stringio content")
        file_info = save_file(
            bk_tenant_id="test_tenant",
            usage="logo",
            created_by="test_user",
            file_or_content=string_io,
            filename="stringio.txt",
        )

        # 验证文件已保存
        file_model = FileModel.objects.get(token=file_info.token)
        assert file_model.original_filename == "stringio.txt"

        # 清理
        file_model.delete()


@pytest.mark.django_db(databases=["default"])
class TestGetFile:
    """测试 get_file 函数"""

    @pytest.fixture
    def saved_file(self):
        """创建已保存的文件fixture"""
        content = ContentFile(b"test file content", name="test.txt")
        file_info = save_file(
            bk_tenant_id="test_tenant",
            usage="logo",
            created_by="test_user",
            file_or_content=content,
            filename="test.txt",
        )
        yield file_info.token
        # 清理
        FileModel.objects.filter(token=file_info.token).delete()

    def test_get_file_success(self, saved_file):
        """测试成功获取文件"""
        file_info = get_file(bk_tenant_id="test_tenant", file_token=saved_file)

        assert file_info is not None
        assert isinstance(file_info, FileInfo)
        assert file_info.file.read() == b"test file content"
        assert file_info.filename == "test.txt"
        assert file_info.usage == "logo"
        assert file_info.token == saved_file
        assert file_info.md5 == hashlib.md5(b"test file content").hexdigest()
        assert file_info.created_by == "test_user"
        assert file_info.description == ""

    def test_get_file_not_found_wrong_token(self, saved_file):
        """测试使用错误的token获取文件时抛出异常"""
        with pytest.raises(ObjectDoesNotExist):
            get_file(bk_tenant_id="test_tenant", file_token="wrong_token" * 16)

    def test_get_file_not_found_wrong_tenant(self, saved_file):
        """测试使用错误的租户ID获取文件时抛出异常"""
        with pytest.raises(ObjectDoesNotExist):
            get_file(bk_tenant_id="wrong_tenant", file_token=saved_file)

    def test_get_file_tenant_isolation(self):
        """测试租户隔离"""
        content = ContentFile(b"tenant1 content", name="test.txt")
        file_info1 = save_file(
            bk_tenant_id="tenant1",
            usage="logo",
            created_by="test_user",
            file_or_content=content,
            filename="test.txt",
        )

        content2 = ContentFile(b"tenant2 content", name="test.txt")
        file_info2 = save_file(
            bk_tenant_id="tenant2",
            usage="logo",
            created_by="test_user",
            file_or_content=content2,
            filename="test.txt",
        )

        # tenant1应该只能获取自己的文件
        tenant1_file = get_file(bk_tenant_id="tenant1", file_token=file_info1.token)
        assert tenant1_file.file.read() == b"tenant1 content"
        assert tenant1_file.filename == "test.txt"

        # tenant1不应该能获取tenant2的文件
        with pytest.raises(ObjectDoesNotExist):
            get_file(bk_tenant_id="tenant1", file_token=file_info2.token)

        # tenant2应该只能获取自己的文件
        tenant2_file = get_file(bk_tenant_id="tenant2", file_token=file_info2.token)
        assert tenant2_file.file.read() == b"tenant2 content"
        assert tenant2_file.filename == "test.txt"

        # 清理
        FileModel.objects.filter(token=file_info1.token).delete()
        FileModel.objects.filter(token=file_info2.token).delete()

    def test_get_file_returns_file_info(self, saved_file):
        """测试get_file返回FileInfo对象"""
        file_info = get_file(bk_tenant_id="test_tenant", file_token=saved_file)

        # 应该返回FileInfo对象
        assert isinstance(file_info, FileInfo)
        assert isinstance(file_info.file, File)
        assert hasattr(file_info.file, "read")

    def test_get_file_can_read_multiple_times(self, saved_file):
        """测试可以多次读取文件"""
        file_info = get_file(bk_tenant_id="test_tenant", file_token=saved_file)
        file_obj = file_info.file

        # 第一次读取
        content1 = file_obj.read()
        assert content1 == b"test file content"

        # 重置文件指针
        file_obj.seek(0)

        # 第二次读取
        content2 = file_obj.read()
        assert content2 == b"test file content"
        assert content1 == content2

    def test_get_file_with_different_content_types(self):
        """测试获取不同类型的文件内容"""
        test_cases = [
            (b"text content", "test.txt", "text/plain"),
            (b"image content", "test.jpg", "image/jpeg"),
            (b"pdf content", "test.pdf", "application/pdf"),
            (b"binary content \x00\x01\x02", "test.bin", "application/octet-stream"),
        ]

        tokens = []

        for content, filename, _ in test_cases:
            file_content = ContentFile(content, name=filename)
            file_info = save_file(
                bk_tenant_id="test_tenant",
                usage="logo",
                created_by="test_user",
                file_or_content=file_content,
                filename=filename,
            )
            tokens.append((file_info.token, content))

        # 验证每个文件都能正确获取
        for token, expected_content in tokens:
            file_info = get_file(bk_tenant_id="test_tenant", file_token=token)
            assert file_info.file.read() == expected_content
            assert isinstance(file_info.filename, str)
            assert file_info.token == token

        # 清理
        for token, _ in tokens:
            FileModel.objects.filter(token=token).delete()

    def test_get_file_with_empty_file(self):
        """测试获取空文件"""
        content = ContentFile(b"", name="empty.txt")
        file_info = save_file(
            bk_tenant_id="test_tenant",
            usage="logo",
            created_by="test_user",
            file_or_content=content,
            filename="empty.txt",
        )

        saved_file_info = get_file(bk_tenant_id="test_tenant", file_token=file_info.token)
        assert saved_file_info.file.read() == b""
        assert saved_file_info.filename == "empty.txt"
        assert saved_file_info.usage == "logo"

        # 清理
        FileModel.objects.filter(token=file_info.token).delete()

    def test_get_file_with_large_file(self):
        """测试获取大文件"""
        large_content = b"x" * 1024 * 1024  # 1MB
        content = ContentFile(large_content, name="large.bin")
        file_info = save_file(
            bk_tenant_id="test_tenant",
            usage="logo",
            created_by="test_user",
            file_or_content=content,
            filename="large.bin",
        )

        saved_file_info = get_file(bk_tenant_id="test_tenant", file_token=file_info.token)
        retrieved_content = saved_file_info.file.read()
        assert len(retrieved_content) == len(large_content)
        assert retrieved_content == large_content
        assert saved_file_info.filename == "large.bin"

        # 清理
        FileModel.objects.filter(token=file_info.token).delete()

    def test_get_file_with_description(self):
        """测试获取带描述的文件，验证FileInfo的所有字段"""
        content = ContentFile(b"test content with description", name="test.txt")
        file_info = save_file(
            bk_tenant_id="test_tenant",
            usage="document",
            created_by="test_user",
            file_or_content=content,
            filename="test.txt",
            description="这是一个测试文件描述",
        )

        saved_file_info = get_file(bk_tenant_id="test_tenant", file_token=file_info.token)

        # 验证所有字段
        assert isinstance(saved_file_info, FileInfo)
        assert saved_file_info.file.read() == b"test content with description"
        assert saved_file_info.filename == "test.txt"
        assert saved_file_info.usage == "document"
        assert saved_file_info.token == file_info.token
        assert saved_file_info.md5 == hashlib.md5(b"test content with description").hexdigest()
        assert saved_file_info.description == "这是一个测试文件描述"
        assert saved_file_info.created_by == "test_user"
        assert saved_file_info.created_at is not None

        # 清理
        FileModel.objects.filter(token=file_info.token).delete()


@pytest.mark.django_db(databases=["default"])
class TestSaveAndGetFileIntegration:
    """测试 save_file 和 get_file 的集成"""

    def test_save_and_get_roundtrip(self):
        """测试保存和获取文件的完整流程"""
        original_content = b"roundtrip test content"
        content = ContentFile(original_content, name="roundtrip.txt")

        # 保存文件
        file_info = save_file(
            bk_tenant_id="test_tenant",
            usage="logo",
            created_by="test_user",
            file_or_content=content,
            filename="roundtrip.txt",
        )

        # 获取文件
        saved_file_info = get_file(bk_tenant_id="test_tenant", file_token=file_info.token)

        # 验证内容一致
        assert saved_file_info.file.read() == original_content
        assert saved_file_info.filename == "roundtrip.txt"
        assert saved_file_info.token == file_info.token

        # 清理
        FileModel.objects.filter(token=file_info.token).delete()

    def test_save_and_get_multiple_files(self):
        """测试保存和获取多个文件"""
        files_data = [
            (b"file1 content", "file1.txt"),
            (b"file2 content", "file2.txt"),
            (b"file3 content", "file3.txt"),
        ]

        tokens = []

        # 保存多个文件
        for content_bytes, filename in files_data:
            content = ContentFile(content_bytes, name=filename)
            file_info = save_file(
                bk_tenant_id="test_tenant",
                usage="logo",
                created_by="test_user",
                file_or_content=content,
                filename=filename,
            )
            tokens.append((file_info.token, content_bytes, filename))

        # 获取并验证每个文件
        for token, expected_content, filename in tokens:
            file_info = get_file(bk_tenant_id="test_tenant", file_token=token)
            assert file_info.file.read() == expected_content
            assert file_info.filename == filename
            assert file_info.token == token

            # 验证文件模型信息
            file_model = FileModel.objects.get(token=token)
            assert file_model.original_filename == filename

        # 清理
        for token, _, _ in tokens:
            FileModel.objects.filter(token=token).delete()
