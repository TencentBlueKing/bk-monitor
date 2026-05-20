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

import re

_MULTI_UNDERSCORE_RE = re.compile(r"_+")

# BKData result_table_name 的长度上限 (databus_cleans 接口约束).
BKDATA_RT_NAME_MAX_LEN = 50

# bklog 侧 result_table_name 的统一前缀, 用于避免与其它系统同名冲突.
BKLOG_RT_NAME_PREFIX = "bklog_"


def collapse_underscores(name: str) -> str:
    """合并 result_table_name 中的连续下划线为单个下划线.

    BKData databus_cleans 对 result_table_name 不接受连续下划线 (会返回 1500001
    "结果表名称: 输入值不匹配要求的模式"), 但 bklog 侧的 COLLECTOR_CONFIG_NAME_EN_REGEX
    = r"^[A-Za-z0-9_]+$" 是允许的, 所以在调 BKData 前做一次兜底.

    其他字符 / 大小写 / 长度 / 首字符 均不变, 保持调用方原有行为.
    """
    return _MULTI_UNDERSCORE_RE.sub("_", name)


def make_bkdata_rt_name(
    name_en: str,
    prefix: str = BKLOG_RT_NAME_PREFIX,
    max_len: int = BKDATA_RT_NAME_MAX_LEN,
) -> str:
    """构造满足 BKData ``result_table_name`` 约束的名字.

    BKData databus_cleans 对 ``result_table_name`` 的约束:

    - 必须以字母开头
    - 仅允许 ``[A-Za-z0-9_]``
    - 不允许连续下划线 (违反时返回 1500001 "结果表名称: 输入值不匹配要求的模式")
    - 长度 <= 50

    本函数对齐 "首字符是字母" + "禁止连续下划线" + "长度上限" 三条; 字符集由 bklog 侧的
    ``COLLECTOR_CONFIG_NAME_EN_REGEX = r"^[A-Za-z0-9_]+$"`` 保证, 此处不再做替换以保持
    历史行为 (大小写 / 数字开头的 ``name_en`` 也允许进来, 因为前缀会接管首字符).

    实现要点 (避免历史踩过的坑):

    1. **先截短 ``name_en`` 再拼 ``prefix``**, 保证 ``prefix`` 完整保留. 早期实现走的是
       ``f"{prefix}{name_en}"[-max_len:]``, 当 ``name_en`` 较长时会把 ``prefix`` 尾截掉,
       导致首字符落到 ``name_en`` 中的下划线 / 数字, 触发 BKData 校验失败 (见
       ``bc091e515 (PR #3902) --bug=133971919`` 的不完整修复).
    2. 拼接后调 :func:`collapse_underscores` 折叠 ``prefix`` 与 ``name_en`` 衔接处可能
       产生的 ``__`` (如 ``prefix="bklog_"`` 配上 ``name_en="_foo"`` 会得到 ``bklog__foo``).
    3. 折叠后长度只会变短不会变长, 仍按 ``max_len`` 兜底裁剪一次, 防御 ``prefix`` 自身超长.

    :param name_en: 用户提交的英文名, 通常是 ``CollectorConfig.collector_config_name_en``.
    :param prefix: 表名前缀, 必须以字母开头且长度 < ``max_len``, 默认 ``"bklog_"``.
    :param max_len: 表名长度上限, 默认 ``50`` (BKData 约束).
    :return: 满足上述四条约束的 result_table_name.
    """
    if len(prefix) >= max_len:
        # 防御: prefix 自己就超长 (调用姿势错误), 仍尽量返回合法字符串而不抛异常.
        return collapse_underscores(prefix)[:max_len]

    truncated_name_en = name_en[: max_len - len(prefix)]
    rt = f"{prefix}{truncated_name_en}"
    rt = collapse_underscores(rt)
    return rt[:max_len]
