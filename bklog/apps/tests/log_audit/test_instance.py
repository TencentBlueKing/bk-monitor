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

from django.test import SimpleTestCase

from apps.iam import ActionEnum
from apps.log_audit.instance import InstanceFilter, LogExtractInstance, LogSearchInstance

INDEX_SET_ID = "12345"
EXTRACT_TASK_ID = "678"

# 由正则反推样例路径，替换顺序不可调整：命名捕获组必须先于裸 \d+ 处理
SAMPLE_SUBSTITUTIONS = (
    (r"(?P<uid>\d+)", "123"),
    (r"\d+", "123"),
    (r"\w+", "sample"),
    (r"\?", "?"),
)

# 补齐资源实例后，这些路由必须能把资源 ID 带进审计事件
RESOURCE_ID_CASES = (
    (f"/api/v1/search/index_set/{INDEX_SET_ID}/search/?bk_biz_id=2", LogSearchInstance, INDEX_SET_ID),
    (f"/api/v1/search/index_set/{INDEX_SET_ID}/fields/", LogSearchInstance, INDEX_SET_ID),
    (f"/api/v1/search/index_set/{INDEX_SET_ID}/context/", LogSearchInstance, INDEX_SET_ID),
    (f"/api/v1/search/index_set/{INDEX_SET_ID}/tail_f/", LogSearchInstance, INDEX_SET_ID),
    (f"/api/v1/search/index_set/{INDEX_SET_ID}/export/", LogSearchInstance, INDEX_SET_ID),
    (f"/api/v1/search/index_set/{INDEX_SET_ID}/async_export/", LogSearchInstance, INDEX_SET_ID),
    (f"/api/v1/search/index_set/{INDEX_SET_ID}/export_history/", LogSearchInstance, INDEX_SET_ID),
    (f"/api/v1/search/index_set/{INDEX_SET_ID}/history/", LogSearchInstance, INDEX_SET_ID),
    (f"/api/v1/search/index_set/{INDEX_SET_ID}/retrieve_config/", LogSearchInstance, INDEX_SET_ID),
    (f"/api/v1/search/index_set/{INDEX_SET_ID}/aggs/terms/", LogSearchInstance, INDEX_SET_ID),
    (f"/api/v1/search/index_set/{INDEX_SET_ID}/aggs/date_histogram/", LogSearchInstance, INDEX_SET_ID),
    (f"/api/v1/log_extract/tasks/{EXTRACT_TASK_ID}/", LogExtractInstance, EXTRACT_TASK_ID),
)

EXTRACT_TASK_PATHS = (
    "/api/v1/log_extract/tasks/",
    "/api/v1/log_extract/tasks/download/?task_id=1",
    "/api/v1/log_extract/tasks/recreate/",
    "/api/v1/log_extract/tasks/polling/",
    "/api/v1/log_extract/tasks/link_list/",
    f"/api/v1/log_extract/tasks/{EXTRACT_TASK_ID}/",
)


def build_sample_path(pattern):
    """把正则还原成一条必然命中它的请求路径"""
    sample = pattern
    for token, replacement in SAMPLE_SUBSTITUTIONS:
        sample = sample.replace(token, replacement)
    return sample.rstrip("$")


def match_rule(path):
    """复刻 push_event 的匹配逻辑：顺序前缀匹配，首个命中即生效"""
    for index, (regex, instance_cls) in enumerate(InstanceFilter):
        ret = regex.match(path)
        if ret:
            return index, instance_cls, ret.groupdict()
    return None, None, None


class TestInstanceFilterStructure(SimpleTestCase):
    def test_no_rule_is_shadowed_by_an_earlier_rule(self):
        """
        push_event 用 re.match 做前缀匹配并在首个命中处 break，
        被前置宽泛正则覆盖的规则永远不生效，会让维护者误以为该路由已单独归类。
        """
        for index, (regex, _) in enumerate(InstanceFilter):
            with self.subTest(pattern=regex.pattern):
                sample = build_sample_path(regex.pattern)
                hit_index, _, _ = match_rule(sample)
                self.assertIsNotNone(hit_index, f"{regex.pattern} 命中不了自身样例路径 {sample}")
                shadowed_by = InstanceFilter[hit_index][0].pattern
                self.assertEqual(hit_index, index, f"{regex.pattern} 被前置规则 {shadowed_by} 遮蔽")

    def test_no_duplicate_patterns(self):
        patterns = [regex.pattern for regex, _ in InstanceFilter]
        duplicates = sorted({pattern for pattern in patterns if patterns.count(pattern) > 1})
        self.assertEqual(duplicates, [])


class TestResourceInstanceId(SimpleTestCase):
    def test_routes_with_resource_id_capture_it(self):
        """审计事件要能回答「操作了哪个索引集 / 哪个提取任务」，instance_id 不能是空串"""
        for path, expected_cls, expected_uid in RESOURCE_ID_CASES:
            with self.subTest(path=path):
                _, instance_cls, kwargs = match_rule(path)
                self.assertIs(instance_cls, expected_cls)

                instance = instance_cls(**kwargs)
                self.assertEqual(instance.instance_id, expected_uid)
                self.assertEqual(instance.instance_name, expected_uid)

    def test_routes_without_resource_id_stay_empty(self):
        """无资源 ID 的路由保持空实例，不能把业务 ID 之类的其他维度硬塞进来"""
        for path in (
            "/api/v1/meta/globals/",
            "/api/v1/search/index_set/?space_uid=bkcc__2",
            "/api/v1/search/index_set/list_config/",
        ):
            with self.subTest(path=path):
                _, instance_cls, kwargs = match_rule(path)
                self.assertIs(instance_cls, LogSearchInstance)
                self.assertEqual(instance_cls(**kwargs).instance_id, "")


class TestExtractTaskClassification(SimpleTestCase):
    def test_extract_task_routes_are_not_classified_as_search(self):
        """日志提取任务此前被记成检索，审计中心按操作类型统计会失真"""
        for path in EXTRACT_TASK_PATHS:
            with self.subTest(path=path):
                _, instance_cls, _ = match_rule(path)
                self.assertIs(instance_cls, LogExtractInstance)

    def test_extract_task_reports_extract_action(self):
        _, instance_cls, kwargs = match_rule(f"/api/v1/log_extract/tasks/{EXTRACT_TASK_ID}/")
        instance = instance_cls(**kwargs)

        self.assertEqual(instance.action.id, ActionEnum.MANAGE_EXTRACT_CONFIG.id)
        self.assertEqual(instance.resource_type.id, "LogExtract")
