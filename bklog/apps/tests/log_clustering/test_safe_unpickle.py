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

import base64
import os
import pickle
import subprocess

from django.test import SimpleTestCase, override_settings

from apps.log_clustering.exceptions import (
    ModelFileStructureInvalidException,
    ModelFileUnpickleForbiddenException,
)
from apps.log_clustering.handlers.aiops.aiops_model.aiops_model_handler import (
    AiopsModelHandler,
)
from apps.log_clustering.handlers.aiops.aiops_model.safe_unpickle import (
    safe_loads,
    validate_model_content,
)


class _OsSystemExploit:
    """经典 pickle RCE gadget：反序列化时通过 __reduce__ 触发 os.system。"""

    def __reduce__(self):
        return (os.system, ("echo pwned",))


def _benign_pickle_bytes():
    """构造一份贴近真实 aiops 模型文件的纯数据 pickle。

    结构对应 sync_pattern.get_pattern 的隐含 schema：
      [meta, {threshold: [sensitive_pattern, ...]}, ...]
    其中 sensitive_pattern 至少 6 元素，索引语义为：
      [PATTERN_INDEX, _, _, ORIGIN_LOG_INDEX, _, PATTERN_SIGNATURE_INDEX]
    """
    sensitive_pattern = [
        ["if", "checker.check"],  # PATTERN_INDEX = 0
        3903,
        ["if", "checker.check"],
        ["if checker.check():"],  # ORIGIN_LOG_INDEX = 3
        [282, 1877],
        "27886975249790003104399390262688492018705644758766193963474214767849400520551",
        # PATTERN_SIGNATURE_INDEX = 5
    ]
    benign = ["meta_placeholder", {0.1: [sensitive_pattern]}]
    return pickle.dumps(benign)


class RestrictedUnpicklerSecurityTests(SimpleTestCase):
    """攻击面回归：常见 pickle RCE gadget 必须被白名单拒绝。"""

    def test_blocks_os_system_gadget(self):
        payload = pickle.dumps(_OsSystemExploit())
        with self.assertRaises(ModelFileUnpickleForbiddenException):
            safe_loads(payload)

    def test_blocks_subprocess_popen_gadget(self):
        # 直接构造 (subprocess.Popen, args) 形式的 REDUCE 指令
        payload = pickle.dumps((subprocess.Popen, (["/bin/true"],)))
        with self.assertRaises(ModelFileUnpickleForbiddenException):
            safe_loads(payload)

    def test_blocks_builtin_eval_gadget(self):
        payload = pickle.dumps((eval, ("__import__('os').system('echo pwned')",)))
        with self.assertRaises(ModelFileUnpickleForbiddenException):
            safe_loads(payload)

    def test_blocks_malformed_pickle_stream(self):
        # 截断的字节流必须被吃掉异常并归一化抛 ForbiddenException，不允许冒泡
        with self.assertRaises(ModelFileUnpickleForbiddenException):
            safe_loads(b"\x80\x04not-a-real-pickle")


class RestrictedUnpicklerBenignTests(SimpleTestCase):
    """良性数据必须能正常通过。"""

    def test_pure_data_payload_loads(self):
        obj = safe_loads(_benign_pickle_bytes())
        self.assertIsInstance(obj, list)
        self.assertIsInstance(obj[1], dict)

    def test_extra_allowed_globals_via_settings(self):
        """settings.AIOPS_UNPICKLE_EXTRA_ALLOWED_GLOBALS 可临时放行已知 module.name。"""
        from collections import OrderedDict

        payload = pickle.dumps(OrderedDict([("a", 1), ("b", 2)]))
        # 不放行时应当被拒绝
        with self.assertRaises(ModelFileUnpickleForbiddenException):
            safe_loads(payload)
        # 放行后应当通过
        with override_settings(AIOPS_UNPICKLE_EXTRA_ALLOWED_GLOBALS=[("collections", "OrderedDict")]):
            obj = safe_loads(payload)
            self.assertEqual(obj, OrderedDict([("a", 1), ("b", 2)]))


class ModelContentSchemaTests(SimpleTestCase):
    """validate_model_content schema 校验正反面。"""

    def test_accepts_valid_structure(self):
        obj = pickle.loads(_benign_pickle_bytes())
        validate_model_content(obj)  # 不抛异常即通过

    def test_accepts_dict_only_form(self):
        sp = [["x"], 1, ["x"], [], [], "sig"]
        validate_model_content({0.5: [sp]})

    def test_rejects_top_level_garbage_dict(self):
        with self.assertRaises(ModelFileStructureInvalidException):
            validate_model_content({"not-numeric-key": []})

    def test_rejects_too_short_list(self):
        with self.assertRaises(ModelFileStructureInvalidException):
            validate_model_content([None])  # 长度 <= CONTENT_PATTERN_INDEX

    def test_rejects_inner_sensitive_pattern_too_short(self):
        with self.assertRaises(ModelFileStructureInvalidException):
            validate_model_content([None, {0.1: [["too-short"]]}])

    def test_rejects_wrong_pattern_index_type(self):
        bad_sp = ["not-a-list", 1, ["x"], [], [], "sig"]
        with self.assertRaises(ModelFileStructureInvalidException):
            validate_model_content([None, {0.1: [bad_sp]}])

    def test_rejects_wrong_origin_log_type(self):
        bad_sp = [["x"], 1, ["x"], "should-be-list-or-tuple", [], "sig"]
        with self.assertRaises(ModelFileStructureInvalidException):
            validate_model_content([None, {0.1: [bad_sp]}])

    def test_rejects_wrong_signature_type(self):
        bad_sp = [["x"], 1, ["x"], [], [], {"signature": "should-be-int-or-str"}]
        with self.assertRaises(ModelFileStructureInvalidException):
            validate_model_content([None, {0.1: [bad_sp]}])


class AiopsModelHandlerPickleDecodeTests(SimpleTestCase):
    """端到端验证 pickle_decode（base64 + safe_loads + validate）。"""

    def test_end_to_end_blocks_gadget(self):
        content = base64.b64encode(pickle.dumps(_OsSystemExploit())).decode()
        with self.assertRaises(ModelFileUnpickleForbiddenException):
            AiopsModelHandler.pickle_decode(content)

    def test_end_to_end_accepts_benign(self):
        content = base64.b64encode(_benign_pickle_bytes()).decode()
        obj = AiopsModelHandler.pickle_decode(content)
        self.assertIsInstance(obj, list)
        self.assertIn(0.1, obj[1])

    def test_end_to_end_rejects_invalid_structure(self):
        # 良性 pickle 但结构不对：应被 validate_model_content 拦下
        payload = pickle.dumps({"not-numeric-key": []})
        content = base64.b64encode(payload).decode()
        with self.assertRaises(ModelFileStructureInvalidException):
            AiopsModelHandler.pickle_decode(content)
