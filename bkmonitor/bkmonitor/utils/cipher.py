# -*- coding: utf-8 -*-
"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2021 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import base64
import hashlib
import math

import Crypto
from Crypto.Cipher import AES, PKCS1_v1_5
from Crypto.PublicKey import RSA
from Crypto.Random import new
from django.conf import settings


class RSACipher(object):
    def __init__(self, pri_key=None):
        self.pub_key = None
        self.pri_key = None
        self.load_pri_key(pri_key)

    def load_pri_key(self, pri_key):
        if not pri_key:
            return
        self.pri_key = RSA.importKey(pri_key)
        self.pub_key = self.pri_key.publickey()

    def get_max_length(self, rsa_key, encrypt=True):
        blocksize = int(Crypto.Util.number.size(rsa_key.n) / 8)
        reserve_size = 11
        if not encrypt:
            reserve_size = 0
        maxlength = blocksize - reserve_size
        return maxlength

    def encrypt(self, encrypt_message):
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

    def decrypt(self, decrypt_message):
        decrypt_result = b""
        max_length = self.get_max_length(self.pri_key, False)
        decrypt_message = base64.b64decode(decrypt_message)
        cipher = PKCS1_v1_5.new(self.pri_key)
        while decrypt_message:
            input_data = decrypt_message[:max_length]
            decrypt_message = decrypt_message[max_length:]
            out_data = cipher.decrypt(input_data, "")
            decrypt_result += out_data
        return decrypt_result


class AESCipher(object):
    def __init__(self, key, iv=None):
        self.bs = 16
        self.iv = iv
        self.key = hashlib.sha256(key.encode("utf-8")).digest()

    def encrypt(self, raw):
        if isinstance(raw, str):
            raw = raw.encode("utf-8")
        raw = self._pad(raw)
        iv = new().read(AES.block_size) if not self.iv else self.iv
        cipher = AES.new(self.key, AES.MODE_CBC, iv)
        result = base64.b64encode(iv + cipher.encrypt(raw))
        return result

    # fmt: off
    def decrypt(self, enc):
        if isinstance(enc, str):
            enc = enc.encode("utf-8")
        enc = base64.b64decode(enc)
        iv = enc[: AES.block_size] if not self.iv else self.iv
        cipher = AES.new(self.key, AES.MODE_CBC, iv)

        if not self.iv:
            return self._unpad(cipher.decrypt(enc[AES.block_size:])).decode("utf-8")
        else:
            return self._unpad(cipher.decrypt(enc[len(iv):])).decode("utf-8")

    def _pad(self, s):
        return s + bytes((self.bs - len(s) % self.bs) * chr(self.bs - len(s) % self.bs), encoding="utf-8")

    @staticmethod
    def _unpad(s):
        return s[: -ord(s[len(s) - 1:])]
    # fmt: on

    @staticmethod
    def predict_length(length):
        """
        计算加密后的长度
        :param length: int
        :return: int
        """
        return int(math.ceil(((length + 1) // 16 * 16 + 16) / 3.0)) * 4


def transform_data_id_to_token(metric_data_id=-1, trace_data_id=-1, log_data_id=-1, bk_biz_id=-1, app_name=""):
    """
    将dataid 加密为bk.data.token
    bk.data.token=${metric_data_id}${salt}${trace_data_id}${salt}${log_data_id}${salt}${bk_biz_id}
    """
    bk_data_token_raw = settings.BK_DATA_TOKEN_SALT.join(
        [
            str(x)
            for x in [
                metric_data_id,
                trace_data_id,
                log_data_id,
                bk_biz_id,
                app_name,
            ]
        ]
    )
    # 需要判断是否有指定密钥，如有，优先级最高
    x_key = getattr(settings, settings.AES_X_KEY_FIELD)
    if settings.SPECIFY_AES_KEY != "":
        x_key = settings.SPECIFY_AES_KEY
    return AESCipher(x_key, settings.BK_DATA_AES_IV).encrypt(bk_data_token_raw).decode("utf-8")


def transform_data_id_to_v1_token(
    metric_data_id=-1, trace_data_id=-1, log_data_id=-1, profile_data_id=-1, bk_biz_id=-1, app_name=""
):
    """
    将dataid 加密为bk.data.token
    bk.data.token=
    ${metric_data_id}${s}${trace_data_id}${s}${log_data_id}${s}${profile_data_id}${s}${bk_biz_id}
    """
    bk_data_token_raw = settings.BK_DATA_TOKEN_SALT.join(
        [
            str(x)
            for x in [
                "v1",
                metric_data_id,
                trace_data_id,
                log_data_id,
                profile_data_id,
                bk_biz_id,
                app_name,
            ]
        ]
    )
    # 需要判断是否有指定密钥，如有，优先级最高
    x_key = getattr(settings, settings.AES_X_KEY_FIELD)
    if settings.SPECIFY_AES_KEY != "":
        x_key = settings.SPECIFY_AES_KEY
    return AESCipher(x_key, settings.BK_DATA_AES_IV).encrypt(bk_data_token_raw).decode("utf-8")
