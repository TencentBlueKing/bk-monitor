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

from apps.feature_toggle.handlers.toggle import FeatureToggleObject
from apps.tgpa.constants import FEATURE_TOGGLE_TGPA_TASK
from apps.utils.log import logger


class BaseDecryptHandler(ABC):
    """
    解密处理器基类
    不同业务可以继承此类实现自己的解密逻辑
    """

    @abstractmethod
    def decrypt(self, data: bytes) -> bytes:
        """解密数据"""
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
    """

    # 分块大小：8KB
    CHUNK_SIZE = 8192
    # 可打印字符比例阈值，超过此值认为是明文（未加密）
    PRINTABLE_RATIO_THRESHOLD = 0.90

    def __init__(self, xor_key: int = None, unencrypted_prefix: str = None):
        self.xor_key = xor_key
        self.unencrypted_prefix = unencrypted_prefix

    def decrypt(self, data: bytes) -> bytes:
        """进行异或处理，未配置xor_key时直接返回原数据"""
        if self.xor_key is None:
            return data
        return bytes(byte ^ self.xor_key for byte in data)

    def _is_likely_plaintext(self, data: bytes) -> bool:
        """
        判断数据是否可能是明文（未加密）
        通过检查可打印ASCII字符的比例来判断
        """
        if not data:
            return True

        # 可打印ASCII字符范围：0x20-0x7E（空格到波浪号），加上常见控制字符（换行、回车、制表符）
        printable_count = sum(1 for byte in data if 0x20 <= byte <= 0x7E or byte in (0x09, 0x0A, 0x0D))
        ratio = printable_count / len(data)

        return ratio >= self.PRINTABLE_RATIO_THRESHOLD

    def decrypt_file(self, file_path: str) -> None:
        """解密文件"""
        temp_path = file_path + ".tmp"
        try:
            # 先读取第一块数据来判断是否需要解密
            with open(file_path, "rb") as f:
                first_chunk = f.read(self.CHUNK_SIZE)

            # 检查第一块数据中是否包含未加密特征前缀，如果是则跳过解密
            if self.unencrypted_prefix and self.unencrypted_prefix.encode("utf-8") in first_chunk:
                logger.info(
                    "File %s is not encrypted (contains '%s'), skipping decryption",
                    file_path,
                    self.unencrypted_prefix,
                )
                return
            # 通过可打印字符比例判断是否为明文，如果是则跳过解密
            if self._is_likely_plaintext(first_chunk):
                logger.info(
                    "File %s is likely plaintext (printable ratio >= %.0f%%), skipping decryption",
                    file_path,
                    self.PRINTABLE_RATIO_THRESHOLD * 100,
                )
                return

            # 分块解密，写入临时文件
            with open(file_path, "rb") as f_in, open(temp_path, "wb") as f_out:
                while chunk := f_in.read(self.CHUNK_SIZE):
                    f_out.write(self.decrypt(chunk))

            # 替换原文件
            os.replace(temp_path, file_path)
        except Exception as e:
            logger.exception("Failed to decrypt file %s: %s", file_path, e)
            # 清理临时文件
            if os.path.exists(temp_path):
                os.remove(temp_path)
            raise


DECRYPT_HANDLER_TYPE_MAP = {
    "xor": XorDecryptHandler,
}


def _get_decrypt_config(bk_biz_id: str) -> dict | None:
    """
    从 FeatureConfig 中获取业务对应的解密处理器配置
    配置格式示例（feature_config中的decrypt_config字段）：
    {
        "100231": {
            "handler": "xor",
            "params": {
                "xor_key": 666,
                "unencrypted_prefix": "Log file open"
            }
        }
    }
    其中 params 用于传递处理器的构造参数
    """
    feature_toggle = FeatureToggleObject.toggle(FEATURE_TOGGLE_TGPA_TASK)
    if not feature_toggle or not feature_toggle.feature_config:
        return None

    decrypt_handler_config = feature_toggle.feature_config.get("decrypt_config", {})
    return decrypt_handler_config.get(bk_biz_id)


def get_decrypt_handler(bk_biz_id: int) -> BaseDecryptHandler | None:
    """
    根据业务ID获取解密处理器实例
    """
    if not bk_biz_id:
        return None

    bk_biz_id_str = str(bk_biz_id)
    config = _get_decrypt_config(bk_biz_id_str)
    if not config:
        return None

    handler_type = config.get("handler")
    handler_class = DECRYPT_HANDLER_TYPE_MAP.get(handler_type)
    if handler_class:
        # 从配置中获取动态参数，直接透传给处理器构造函数
        params = config.get("params", {})
        return handler_class(**params)
    else:
        logger.warning("Unknown decrypt handler type: %s for bk_biz_id: %s", handler_type, bk_biz_id_str)
        return None
