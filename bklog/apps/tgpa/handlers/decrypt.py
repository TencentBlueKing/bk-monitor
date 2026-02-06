"""
Tencent is pleased to support the open source community by making BK-LOG 蓝鲸日志平台 available.
Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
BK-LOG 蓝鲸日志平台 is licensed under the MIT License.
License for BK-LOG 蓝鲸日志平台:
--------------------------------------------------------------------
Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated
documentation files (the "Software"), to deal in the Software without restriction, including without limitation
the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software,
and to permit persons to whom the Software is furnished to do so, subject to the following conditions:
The above copyright notice and this permission notice shall be included in all copies or substantial
portions of the Software.
THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT
LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN
NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY,
WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE
SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
We undertake not to change the open source license (MIT license) applicable to the current version of
the project delivered to anyone in the future.
"""

import os
from abc import ABC, abstractmethod

from apps.utils.log import logger


class BaseDecryptHandler(ABC):
    """
    解密处理器基类
    不同业务可以继承此类实现自己的解密逻辑
    """

    @abstractmethod
    def decrypt(self, data: bytes) -> bytes:
        """
        解密数据
        :param data: 加密的字节数据
        :return: 解密后的字节数据
        """
        raise NotImplementedError

    def decrypt_file(self, file_path: str) -> None:
        """
        解密文件（原地解密）
        :param file_path: 文件路径
        """
        try:
            with open(file_path, "rb") as f:
                encrypted_data = f.read()

            decrypted_data = self.decrypt(encrypted_data)

            with open(file_path, "wb") as f:
                f.write(decrypted_data)
        except Exception as e:
            logger.exception("Failed to decrypt file %s: %s", file_path, e)
            raise


class XorDecryptHandler(BaseDecryptHandler):
    """
    异或解密处理器
    对每个字节进行异或操作
    如果文件内容包含"Log file open"，则认为文件未加密，跳过解密
    """

    # 未加密文件的特征前缀
    UNENCRYPTED_PREFIX = b"Log file open"
    # 分块大小：8KB
    CHUNK_SIZE = 8192

    def __init__(self, xor_key: int = 0x73):
        """
        初始化异或解密器
        :param xor_key: 异或密钥，默认为0x73
        """
        self.xor_key = xor_key

    def decrypt(self, data: bytes) -> bytes:
        """进行异或处理"""
        return bytes(byte ^ self.xor_key for byte in data)

    def decrypt_file(self, file_path: str) -> None:
        """
        解密文件
        如果文件头部包含"Log file open"，则认为文件未加密，跳过解密
        """
        try:
            # 先读取第一块数据来判断是否需要解密
            with open(file_path, "rb") as f:
                first_chunk = f.read(self.CHUNK_SIZE)

            # 检查第一块数据中是否包含"Log file open"，如果是则跳过解密
            if self.UNENCRYPTED_PREFIX in first_chunk:
                logger.info("File %s is not encrypted (contains 'Log file open'), skipping decryption", file_path)
                return

            # 分块解密，写入临时文件
            temp_path = file_path + ".tmp"
            with open(file_path, "rb") as f_in, open(temp_path, "wb") as f_out:
                while chunk := f_in.read(self.CHUNK_SIZE):
                    f_out.write(self.decrypt(chunk))

            # 替换原文件
            os.replace(temp_path, file_path)
        except Exception as e:
            logger.exception("Failed to decrypt file %s: %s", file_path, e)
            # 清理临时文件
            temp_path = file_path + ".tmp"
            if os.path.exists(temp_path):
                os.remove(temp_path)
            raise


# 解密处理器类型枚举，便于通过类型名称获取解密处理器
DECRYPT_HANDLER_REGISTRY = {"100231": XorDecryptHandler}


def get_decrypt_handler(bk_biz_id, **kwargs) -> BaseDecryptHandler | None:
    """
    根据解密处理器实例
    """
    if not bk_biz_id:
        return None

    handler_class = DECRYPT_HANDLER_REGISTRY.get(str(bk_biz_id))
    if handler_class is None:
        return None

    return handler_class(**kwargs)
