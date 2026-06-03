"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.

BaseBizQueryHandler.get_biz_filter_ids：把 bk_biz_ids 的 -1（"全部授权业务"哨兵）解析为实际
授权业务集，供按业务过滤（ES terms / ORM __in）安全取值。直接验证取值语义（绕过 __init__ 以免
依赖 DB/ES/鉴权）。
"""

from fta_web.alert.handlers.alert import AlertQueryHandler


def _handler(bk_biz_ids, authorized_bizs=None) -> AlertQueryHandler:
    # 绕过 __init__：被测方法只读 bk_biz_ids / authorized_bizs。authorized_bizs 默认跟随
    # bk_biz_ids（等价 BaseBizQueryHandler 对单业务的解析结果）。
    handler = AlertQueryHandler.__new__(AlertQueryHandler)
    handler.bk_biz_ids = bk_biz_ids
    handler.authorized_bizs = authorized_bizs if authorized_bizs is not None else bk_biz_ids
    return handler


class TestGetBizFilterIds:
    def test_no_scope_returns_none(self):
        # 请求未带业务范围 → None（调用方走兜底，等价 if not self.bk_biz_ids）
        assert _handler(None).get_biz_filter_ids() is None
        assert _handler([]).get_biz_filter_ids() is None

    def test_concrete_biz_uses_requested(self):
        # 不含 -1 → 用请求业务集
        assert _handler([2, 3], authorized_bizs=[2, 3]).get_biz_filter_ids() == [2, 3]

    def test_all_biz_sentinel_resolves_to_authorized(self):
        # 全业务 [-1] → 用 authorized_bizs（已解析的实际授权业务集），而非裸 [-1]
        assert _handler([-1], authorized_bizs=[2, 3]).get_biz_filter_ids() == [2, 3]

    def test_residual_minus_one_stripped(self):
        # 无 request 上下文降级：parse_biz_item 原样返回带 -1 的入参 → 末尾剔除
        assert _handler([-1], authorized_bizs=[-1]).get_biz_filter_ids() == []

    def test_all_biz_empty_authorized(self):
        # [-1] 但用户无任何授权业务 → []
        assert _handler([-1], authorized_bizs=[]).get_biz_filter_ids() == []

    def test_concrete_unauthorized_uses_requested(self):
        # 不含 -1 → 用请求集（与现网既有语义一致，权限交上游 / add_biz_condition 把关）
        assert _handler([2], authorized_bizs=[]).get_biz_filter_ids() == [2]
