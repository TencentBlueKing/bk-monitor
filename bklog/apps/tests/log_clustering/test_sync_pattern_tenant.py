from unittest.mock import MagicMock, call, patch

from django.test import SimpleTestCase, TestCase

from apps.log_clustering.models import AiopsSignatureAndPattern
from apps.log_clustering.tasks.sync_pattern import (
    SIGNATURE_QUERY_BATCH_SIZE,
    SIGNATURE_SYNC_FIELDS,
    SIGNATURE_WRITE_BATCH_SIZE,
    get_pattern,
    make_signature_objects,
    sync,
    sync_pattern,
)


def build_pattern(signature, pattern="pattern", origin_pattern="origin pattern", origin_log="origin log"):
    return {
        "signature": signature,
        "pattern": pattern,
        "origin_pattern": origin_pattern,
        "origin_log": origin_log,
    }


def sync_fields(record):
    """按同步字段集合取记录上的字段值，与实现共用同一字段定义"""
    return tuple(getattr(record, field) for field in SIGNATURE_SYNC_FIELDS)


class TestSyncPatternTenant(SimpleTestCase):
    @patch("apps.log_clustering.tasks.sync_pattern.sync.delay")
    @patch("apps.log_clustering.tasks.sync_pattern.LogIndexSet.objects.filter")
    @patch("apps.log_clustering.tasks.sync_pattern.ClusteringConfig.objects.filter")
    def test_same_model_from_two_businesses_schedules_two_tenant_calls(self, mock_configs, mock_index_sets, mock_delay):
        mock_configs.return_value.values.return_value = [
            {"model_id": "model_1", "model_output_rt": "", "index_set_id": 1, "bk_biz_id": 2},
            {"model_id": "model_1", "model_output_rt": "", "index_set_id": 2, "bk_biz_id": 3},
        ]
        mock_index_sets.return_value.values_list.return_value = [1, 2]

        sync_pattern()

        self.assertEqual(mock_delay.call_count, 2)
        mock_delay.assert_any_call(model_id="model_1", bk_biz_id=2)
        mock_delay.assert_any_call(model_id="model_1", bk_biz_id=3)


class TestSyncModelFileTenant(SimpleTestCase):
    @patch("apps.log_clustering.tasks.sync_pattern.AiopsSignatureAndPattern.objects.bulk_update")
    @patch("apps.log_clustering.tasks.sync_pattern.AiopsSignatureAndPattern.objects.bulk_create")
    @patch("apps.log_clustering.tasks.sync_pattern.make_signature_objects", return_value=([], []))
    @patch("apps.log_clustering.tasks.sync_pattern.get_pattern", return_value=[])
    @patch("apps.log_clustering.tasks.sync_pattern.AiopsModelHandler")
    def test_sync_model_file_constructs_handler_with_business_context(
        self, mock_handler_cls, mock_get_pattern, mock_make_objects, mock_bulk_create, mock_bulk_update
    ):
        handler = mock_handler_cls.return_value
        handler.get_latest_released_id.return_value = "release_1"
        handler.aiops_release_model_release_id_model_file.return_value = {"file_content": "content"}
        mock_handler_cls.pickle_decode.return_value = []

        sync(model_id="model_1", bk_biz_id=2)

        mock_handler_cls.assert_called_once_with()
        handler.get_latest_released_id.assert_called_once_with(model_id="model_1", bk_biz_id=2)
        handler.aiops_release_model_release_id_model_file.assert_called_once_with(
            model_id="model_1", model_release_id="release_1", bk_biz_id=2
        )


class TestSignatureSyncFields(SimpleTestCase):
    def test_sync_fields_match_pattern_payload_keys(self):
        """同步字段集合必须与 get_pattern 产出的负载键完全一致，避免加字段时创建/更新漏写。"""
        content = ["meta", {0.1: [[["if", "checker.check"], 3903, ["x"], ["if checker.check():"], [282, 1877], "sig"]]}]

        produced = get_pattern(content)[0]

        self.assertEqual(set(SIGNATURE_SYNC_FIELDS), set(produced) - {"signature"})


class TestMakeSignatureObjects(SimpleTestCase):
    @patch("apps.log_clustering.tasks.sync_pattern.AiopsSignatureAndPattern.objects.filter")
    def test_queries_existing_signatures_in_batches(self, mock_filter):
        patterns = [build_pattern(str(index)) for index in range(SIGNATURE_QUERY_BATCH_SIZE + 1)]
        mock_filter.return_value.only.return_value = []

        objects_to_create, objects_to_update = make_signature_objects(patterns, model_id="model_1")

        self.assertEqual(len(objects_to_create), SIGNATURE_QUERY_BATCH_SIZE + 1)
        self.assertEqual(objects_to_update, [])
        self.assertEqual(
            mock_filter.call_args_list,
            [
                call(model_id="model_1", signature__in=[str(index) for index in range(SIGNATURE_QUERY_BATCH_SIZE)]),
                call(model_id="model_1", signature__in=[str(SIGNATURE_QUERY_BATCH_SIZE)]),
            ],
        )
        mock_filter.return_value.only.assert_called_with("id", "signature", "pattern", "origin_pattern", "origin_log")

    @patch("apps.log_clustering.tasks.sync_pattern.AiopsSignatureAndPattern.objects.filter")
    def test_only_updates_changed_objects(self, mock_filter):
        unchanged = AiopsSignatureAndPattern(
            id=1,
            model_id="model_1",
            signature="unchanged",
            pattern="same",
            origin_pattern="same origin",
            origin_log="same log",
        )
        changed = AiopsSignatureAndPattern(
            id=2,
            model_id="model_1",
            signature="changed",
            pattern="old",
            origin_pattern="old origin",
            origin_log="old log",
        )
        queryset = MagicMock()
        queryset.only.return_value = [unchanged, changed]
        mock_filter.return_value = queryset
        patterns = [
            build_pattern("unchanged", "same", "same origin", "same log"),
            build_pattern("changed", "new", "new origin", "new log"),
            build_pattern("new"),
        ]

        objects_to_create, objects_to_update = make_signature_objects(patterns, model_id="model_1")

        self.assertEqual([obj.signature for obj in objects_to_create], ["new"])
        self.assertEqual(objects_to_update, [changed])
        self.assertEqual(
            (changed.pattern, changed.origin_pattern, changed.origin_log), ("new", "new origin", "new log")
        )

    @patch("apps.log_clustering.tasks.sync_pattern.AiopsSignatureAndPattern.objects.filter")
    def test_empty_patterns_do_not_query_database(self, mock_filter):
        self.assertEqual(make_signature_objects([], model_id="model_1"), ([], []))
        mock_filter.assert_not_called()


class TestMakeSignatureObjectsWithDatabase(TestCase):
    """真实数据库场景：分片查询与差异写入必须保持原有同步语义。"""

    def create_signature(self, signature, pattern, origin_pattern, origin_log, **extra):
        return AiopsSignatureAndPattern.objects.create(
            model_id="model_1",
            signature=signature,
            pattern=pattern,
            origin_pattern=origin_pattern,
            origin_log=origin_log,
            **extra,
        )

    def sync_signature_objects(self, patterns, model_id="model_1"):
        """按 sync() 的实际写库配置落库，返回待写入对象供断言"""
        objects_to_create, objects_to_update = make_signature_objects(patterns, model_id=model_id)
        AiopsSignatureAndPattern.objects.bulk_create(objects_to_create, batch_size=SIGNATURE_WRITE_BATCH_SIZE)
        AiopsSignatureAndPattern.objects.bulk_update(
            objects_to_update, fields=list(SIGNATURE_SYNC_FIELDS), batch_size=SIGNATURE_WRITE_BATCH_SIZE
        )
        return objects_to_create, objects_to_update

    def test_bulk_write_touches_only_changed_records(self):
        unchanged = self.create_signature(
            "unchanged", "same", "same origin", "same log", label="keep-label", remark=[{"key": "value"}]
        )
        changed = self.create_signature("changed", "old", "old origin", "old log")
        patterns = [
            build_pattern("unchanged", "same", "same origin", "same log"),
            build_pattern("changed", "new", "new origin", "new log"),
            build_pattern("new"),
        ]

        objects_to_create, objects_to_update = self.sync_signature_objects(patterns)

        self.assertEqual([obj.signature for obj in objects_to_create], ["new"])
        # 未变化记录不参与写入
        self.assertEqual([obj.pk for obj in objects_to_update], [changed.pk])

        changed.refresh_from_db()
        self.assertEqual(sync_fields(changed), ("new", "new origin", "new log"))

        # .only() 延迟加载的字段不参与 bulk_update，也不会被批量写入覆盖
        unchanged.refresh_from_db()
        self.assertEqual(sync_fields(unchanged), ("same", "same origin", "same log"))
        self.assertEqual(unchanged.label, "keep-label")
        self.assertEqual(unchanged.remark, [{"key": "value"}])

        # 新建记录必须覆盖全部同步字段，且取值来自模型文件负载
        created = AiopsSignatureAndPattern.objects.get(model_id="model_1", signature="new")
        for field in SIGNATURE_SYNC_FIELDS:
            self.assertEqual(getattr(created, field), patterns[-1][field])
        self.assertEqual(AiopsSignatureAndPattern.objects.filter(model_id="model_1").count(), 3)

    def test_other_model_records_are_not_matched(self):
        AiopsSignatureAndPattern.objects.create(
            model_id="model_2",
            signature="shared",
            pattern="other pattern",
            origin_pattern="other origin pattern",
            origin_log="other origin log",
        )
        patterns = [build_pattern("shared", "new pattern", "new origin pattern", "new origin log")]

        objects_to_create, objects_to_update = self.sync_signature_objects(patterns)

        # 其他 model 的同名 signature 既不会被更新，也不会阻止当前 model 新建
        self.assertEqual([obj.signature for obj in objects_to_create], ["shared"])
        self.assertEqual(objects_to_update, [])
        other = AiopsSignatureAndPattern.objects.get(model_id="model_2", signature="shared")
        self.assertEqual(other.pattern, "other pattern")
