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
import binascii
import os

from Crypto.Hash import SHA
from Crypto.PublicKey import RSA
from Crypto.Signature import PKCS1_v1_5
from django.conf import settings

from bkmonitor.utils.cipher import AESCipher

key_dir = os.path.dirname(__file__)


class RSAVerification(object):
    @classmethod
    def gen_signature(cls, message):
        if isinstance(message, str):
            message = message.encode("utf-8")

        key = cls._load_private_key()
        h = SHA.new(message)
        signer = PKCS1_v1_5.new(key)
        signature = signer.sign(h)
        return signature

    @classmethod
    def _load_private_key(cls):
        key = None
        try:
            with open(os.path.join(key_dir, "bk.key")) as f:
                key = RSA.importKey(f.read())

        except IOError:
            pass

        except ValueError:
            pass

        return key

    @classmethod
    def verify(cls, message, signature):
        with open(os.path.join(key_dir, "bk.key.pub")) as f:
            pub_key = RSA.importKey(f.read())

        if isinstance(message, str):
            message = message.encode("utf-8")

        h = SHA.new(message)
        verifier = PKCS1_v1_5.new(pub_key)
        return verifier.verify(h, signature)


class AESVerification(object):
    @classmethod
    def cipher(cls):
        # 需要判断是否有指定密钥，如有，优先级最高
        x_key = getattr(settings, "PLUGIN_AES_KEY", "bk_monitorv3_enterprise")
        enterprise_code = getattr(settings, "ENTERPRISE_CODE", "")
        if enterprise_code:
            x_key = x_key + "_" + enterprise_code
        return AESCipher(x_key)

    @classmethod
    def gen_signature(cls, message):
        signature = cls.cipher().encrypt(message)
        return signature

    @classmethod
    def verify(cls, message, signature):
        try:
            return message == cls.cipher().decrypt(signature)
        except (binascii.Error, ValueError):
            return False


class Verification(object):
    def __new__(cls, protocol):
        if protocol == "default":
            return AESVerification()
        return RSAVerification()
