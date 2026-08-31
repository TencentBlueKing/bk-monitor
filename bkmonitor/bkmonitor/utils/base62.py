"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import logging

logger = logging.getLogger(__name__)


class Base62Decoder:
    """galileo SDK compact base62 解码器，对应 jxskiss/base62 的 encodeV2。

    SDK 侧上报前会把不满足 ``[a-zA-Z0-9_]`` 的指标名、维度名编码成 ``base62`` 前缀的标识符
    （见 eco/go/sdk/base/model/name_format.go 的 NameToIdentifier），存储与查询都使用编码后的
    名字，原始名需要在展示前解码还原。
    """

    charset = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789"
    decode_map = {ord(c): i for i, c in enumerate(charset)}
    compact_mask = 0x1E  # 00011110
    mask5bits = 0x1F  # 00011111
    prefix = "base62"

    @classmethod
    def decode_string(cls, encoded_string: str) -> str:
        if not encoded_string.startswith(cls.prefix):
            return encoded_string
        encoded_bytes = encoded_string[len(cls.prefix) :].encode("utf-8")
        try:
            decoded_bytes = cls.decode(encoded_bytes)
        except Exception as e:  # pylint: disable=broad-except
            logger.warning(f"Decode base62 string [{encoded_string}] failed: {e}")
            # 如果解码失败 打印日志，然后返回原字符串
            return encoded_string
        return decoded_bytes.decode("utf-8", errors="ignore")

    @classmethod
    def decode(cls, encoded_bytes: bytes) -> bytes:
        # Initialize the destination list
        dst = [0] * ((len(encoded_bytes) * 6 // 8) + 1)
        idx = len(dst)
        pos = 0
        b = 0

        for i, c in enumerate(encoded_bytes):
            x = cls.decode_map.get(c, 0xFF)

            if x == 0xFF:
                raise ValueError(f"Corrupt input at byte {i}")

            if i == len(encoded_bytes) - 1:
                b |= x << pos
                pos += x.bit_length()
            elif x & cls.compact_mask == cls.compact_mask:
                b |= x << pos
                pos += 5
            else:
                b |= x << pos
                pos += 6

            if pos >= 8:
                idx -= 1
                dst[idx] = b & 0xFF
                pos %= 8
                b >>= 8

        if pos > 0:
            idx -= 1
            dst[idx] = b & 0xFF

        return bytes(dst[idx:])


def decode_identifier(name: str) -> str:
    """还原 SDK 编码前的原始字段名，非编码字段名原样返回。

    SDK 仅以 ``base62`` 前缀区分编码字段，用户把字段命名成 ``base62xxx`` 时同样会命中前缀，
    这类字段解出来是乱码，因此要求解码结果可打印，否则视为未编码。
    """
    if not name.startswith(Base62Decoder.prefix):
        return name

    decoded = Base62Decoder.decode_string(name)
    if not decoded or decoded == name or not decoded.isprintable():
        return name
    return decoded
