"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from django.db import IntegrityError, transaction
from django.test import TestCase

from bkmonitor.models import IssueSourceAnalysisConfig, IssueSourceAnalysisRule


class TestIssueSourceAnalysisConfig(TestCase):
    databases = {"default", "monitor_api"}

    def test_business_has_only_one_config(self):
        IssueSourceAnalysisConfig.objects.create(
            bk_biz_id=2,
            bkci_project_id="project-a",
            repository_alias="repo-a",
        )

        with self.assertRaises(IntegrityError), transaction.atomic():
            IssueSourceAnalysisConfig.objects.create(
                bk_biz_id=2,
                bkci_project_id="project-b",
                repository_alias="repo-b",
            )

    def test_different_businesses_can_reuse_repository_alias(self):
        for bk_biz_id in (2, 3):
            IssueSourceAnalysisConfig.objects.create(
                bk_biz_id=bk_biz_id,
                bkci_project_id="shared-project",
                repository_alias="shared-repo",
            )

        self.assertEqual(IssueSourceAnalysisConfig.objects.count(), 2)

    def test_repository_snapshot_field_lengths_match_bkci(self):
        self.assertEqual(IssueSourceAnalysisConfig._meta.get_field("bkci_project_id").max_length, 128)
        self.assertEqual(IssueSourceAnalysisRule._meta.get_field("bkci_project_id").max_length, 128)
        self.assertEqual(IssueSourceAnalysisConfig._meta.get_field("repository_alias").max_length, 255)
        self.assertEqual(IssueSourceAnalysisRule._meta.get_field("repository_alias").max_length, 255)


class TestIssueSourceAnalysisRule(TestCase):
    databases = {"default", "monitor_api"}

    @staticmethod
    def create_rule(**kwargs):
        defaults = {
            "bk_biz_id": 2,
            "name": "custom rule",
            "priority": 0,
            "is_enabled": False,
            "is_default": False,
        }
        defaults.update(kwargs)
        return IssueSourceAnalysisRule.objects.create(**defaults)

    def test_priority_is_unique_within_business(self):
        self.create_rule(priority=10)

        with self.assertRaises(IntegrityError), transaction.atomic():
            self.create_rule(name="duplicate priority", priority=10)

    def test_different_businesses_can_reuse_priority(self):
        self.create_rule(bk_biz_id=2, priority=10)
        self.create_rule(bk_biz_id=3, priority=10)

        self.assertEqual(IssueSourceAnalysisRule.objects.count(), 2)

    def test_default_rule_requires_priority_minus_one(self):
        rule = self.create_rule(name="default rule", priority=-1, is_default=True)

        self.assertTrue(rule.is_default)

        with self.assertRaises(IntegrityError), transaction.atomic():
            self.create_rule(name="invalid default rule", priority=0, is_default=True)

    def test_custom_rule_priority_cannot_be_negative(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            self.create_rule(priority=-1, is_default=False)

    def test_disabled_rule_allows_incomplete_configuration(self):
        rule = self.create_rule()

        self.assertFalse(rule.is_enabled)
        self.assertEqual(rule.conditions, [])
        self.assertIsNone(rule.bkci_project_id)
        self.assertIsNone(rule.repository_alias)
        self.assertEqual(rule.agent_ids, [])
        self.assertEqual(rule.skill_ids, [])
        self.assertEqual(rule.knowledge_base_ids, [])

    def test_json_field_defaults_are_not_shared(self):
        first = IssueSourceAnalysisRule(bk_biz_id=2, name="first", priority=1)
        second = IssueSourceAnalysisRule(bk_biz_id=2, name="second", priority=2)

        first.agent_ids.append("agent-a")

        self.assertEqual(second.agent_ids, [])

    def test_default_ordering_is_priority_descending(self):
        self.create_rule(name="default", priority=-1, is_default=True)
        self.create_rule(name="low", priority=0)
        self.create_rule(name="high", priority=100)

        priorities = list(IssueSourceAnalysisRule.objects.values_list("priority", flat=True))

        self.assertEqual(priorities, [100, 0, -1])
