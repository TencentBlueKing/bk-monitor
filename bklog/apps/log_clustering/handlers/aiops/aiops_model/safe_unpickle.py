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

# AIOPS 模型文件受限反序列化。
#
# 上游 BkData AIOPS 接口返回 base64(cloudpickle.dumps(model))，本仓库无法改变上游协议，
# 因此通过两层防御把"任意代码执行"收敛为"只能构造合法 pattern 数据"：
#   1) RestrictedUnpickler.find_class 白名单：默认空集，拒绝任何 import；
#      若上游真实样本（pickletools 实测）中需要某些纯数据类，可通过
#      settings.AIOPS_UNPICKLE_EXTRA_ALLOWED_GLOBALS 追加，不需要改动代码。
#   2) validate_model_content 结构校验：反序列化结果必须符合 get_pattern 的隐含 schema，
#      否则丢弃。

import io
import logging
import pickle

from django.conf import settings
from django.utils.translation import gettext as _

from apps.log_clustering.constants import (
    CONTENT_PATTERN_INDEX,
    ORIGIN_LOG_INDEX,
    PATTERN_INDEX,
    PATTERN_SIGNATURE_INDEX,
)
from apps.log_clustering.exceptions import (
    ModelFileStructureInvalidException,
    ModelFileUnpickleForbiddenException,
)

logger = logging.getLogger(__name__)

# 默认白名单：staging 实测样本（11 份，跨 9 bizid，累计千万级 opcode）显示 pickle 流中
# GLOBAL/STACK_GLOBAL/REDUCE/BUILD/NEWOBJ 系列 opcode 全部为 0，即模型文件就是纯
# dict/list/tuple/str/int/float 数据。因此默认空集 = 最严格形态。
_DEFAULT_ALLOWED_GLOBALS: frozenset[tuple[str, str]] = frozenset()


def _get_allowed_globals() -> frozenset[tuple[str, str]]:
    """合并默认白名单 + Django settings 中可选的扩展白名单。"""
    extra = getattr(settings, "AIOPS_UNPICKLE_EXTRA_ALLOWED_GLOBALS", ())
    normalized: set[tuple[str, str]] = set()
    for item in extra:
        if isinstance(item, list | tuple) and len(item) == 2:
            normalized.add((str(item[0]), str(item[1])))
    return _DEFAULT_ALLOWED_GLOBALS | frozenset(normalized)


class RestrictedUnpickler(pickle.Unpickler):
    """仅允许 ALLOWED_GLOBALS 中的 (module, name) 被 find_class 解析。

    注意：上游用 cloudpickle.dumps，但 cloudpickle 的扩展只在 dumps 阶段，loads 走标准
    pickle 协议，所以这里直接继承 pickle.Unpickler 即可，且更安全（绕开 cloudpickle 内部
    的 subimport / _make_skel_func 等 helper，避免它们成为绕过 gadget）。
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._allowed = _get_allowed_globals()

    def find_class(self, module: str, name: str):
        if (module, name) in self._allowed:
            return super().find_class(module, name)

        logger.warning("[aiops-unpickle] forbidden global rejected: module=%s name=%s", module, name)
        raise ModelFileUnpickleForbiddenException(
            ModelFileUnpickleForbiddenException.MESSAGE.format(detail=f"{module}.{name}")
        )


def safe_loads(raw: bytes):
    """安全反序列化 AIOPS 模型文件。

    返回反序列化对象；任何被拒、损坏或半截 pickle 流都会抛 ModelFileUnpickleForbiddenException。
    """
    try:
        return RestrictedUnpickler(io.BytesIO(raw)).load()
    except ModelFileUnpickleForbiddenException:
        raise
    except (pickle.UnpicklingError, EOFError, AttributeError, ImportError, ValueError) as e:
        logger.exception("[aiops-unpickle] malformed pickle stream")
        raise ModelFileUnpickleForbiddenException(
            ModelFileUnpickleForbiddenException.MESSAGE.format(detail=str(e))
        ) from e


def validate_model_content(content) -> None:
    """对照 get_pattern 的隐含 schema 做最小化结构校验。

    校验规则来自 sync_pattern.get_pattern 中的实际访问模式，违反任意一条即抛异常，
    避免攻击者即便构造出合法 pickle 也能进入业务逻辑做二次利用。
    """

    def _bad(reason: str):
        raise ModelFileStructureInvalidException(ModelFileStructureInvalidException.MESSAGE.format(detail=reason))

    if isinstance(content, list):
        if len(content) <= CONTENT_PATTERN_INDEX:
            _bad(_("外层 list 长度不足"))
        content = content[CONTENT_PATTERN_INDEX]

    if not isinstance(content, dict):
        _bad(_("CONTENT_PATTERN_INDEX 处不是 dict"))

    required_max_index = max(PATTERN_INDEX, ORIGIN_LOG_INDEX, PATTERN_SIGNATURE_INDEX)
    for key, sensitive_patterns in content.items():
        if not isinstance(key, int | float):
            _bad(_("dict key 类型非法"))
        if not isinstance(sensitive_patterns, list):
            _bad(_("dict value 不是 list"))
        for sp in sensitive_patterns:
            if not isinstance(sp, list | tuple) or len(sp) <= required_max_index:
                _bad(_("sensitive_pattern 结构非法"))
            if not isinstance(sp[PATTERN_INDEX], list | tuple):
                _bad(_("PATTERN_INDEX 项不是 list/tuple"))
            origin_log = sp[ORIGIN_LOG_INDEX]
            if origin_log and not isinstance(origin_log, list | tuple):
                _bad(_("ORIGIN_LOG_INDEX 项类型非法"))
            if not isinstance(sp[PATTERN_SIGNATURE_INDEX], int | str):
                _bad(_("PATTERN_SIGNATURE_INDEX 项类型非法"))
