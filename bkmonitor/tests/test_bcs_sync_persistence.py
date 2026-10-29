"""Run with stdlib unittest; exercise production definitions on a private SQLite alias."""

import ast
import hashlib
import itertools
import logging
import subprocess
import sys
import unittest
from collections import defaultdict
from collections.abc import Callable, Iterable
from itertools import islice
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch


ROOT = Path(__file__).resolve().parents[1]
DATABASE = "bcs_sync_regression"


def definitions(path, names, namespace, class_name=None):
    tree = ast.parse((ROOT / path).read_text())
    body = tree.body
    if class_name:
        body = next(node for node in body if getattr(node, "name", None) == class_name).body
    for node in body:
        if getattr(node, "name", None) in names:
            node.decorator_list = [] if not class_name else node.decorator_list
            exec(compile(ast.Module(body=[node], type_ignores=[]), str(path), "exec"), namespace)


class PersistenceTests(unittest.TestCase):
    # Keep private SQLite models/connections out of the application's pytest process.
    __test__ = __name__ == "__main__"

    @classmethod
    def setUpClass(cls):
        import django
        from django.apps import apps
        from django.conf import settings

        if not settings.configured:
            settings.configure(
                INSTALLED_APPS=[], DATABASES={"default": {"ENGINE": "django.db.backends.sqlite3"}}, USE_TZ=True
            )
        if not apps.ready:
            django.setup()
        from django.db import IntegrityError, connections, models, transaction
        from django.db.models import Q
        from django.utils import timezone

        connections.databases[DATABASE] = {
            **connections.databases["default"],
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": ":memory:",
            "OPTIONS": {},
            "ATOMIC_REQUESTS": False,
            "AUTOCOMMIT": True,
        }

        class HiddenManager(models.Manager):
            def get_queryset(self):
                return super().get_queryset().exclude(name__startswith="eklet-")

        class Fields(models.Model):
            bk_tenant_id = models.CharField(max_length=20, default="tenant")
            bk_biz_id = models.IntegerField(default=1)
            bcs_cluster_id = models.CharField(max_length=40, default="cluster-a")
            name = models.CharField(max_length=40)
            unique_hash = models.CharField(max_length=80, unique=True)
            last_synced_at = models.DateTimeField(null=True)
            config = models.CharField(max_length=40, default="default")
            node_count = models.IntegerField(default=0)
            project_name = models.CharField(max_length=40, default="")
            environment = models.CharField(max_length=40, default="")
            status = models.CharField(max_length=40, default="")
            space_uid = models.CharField(max_length=40, default="")
            created_at = models.DateTimeField(null=True)
            updated_at = models.DateTimeField(null=True)

            class Meta:
                abstract = True
                app_label = "bcs_sync_regression"

        class Resource(Fields):
            SYNC_IDENTITY_FIELDS = ("bcs_cluster_id", "name")
            api_labels = {}
            objects = HiddenManager()

            class Meta:
                app_label = "bcs_sync_regression"
                unique_together = [("bcs_cluster_id", "name")]

        class Cluster(Fields):
            SYNC_IDENTITY_FIELDS = ("bk_tenant_id", "bcs_cluster_id")

            class Meta:
                app_label = "bcs_sync_regression"

        class Label(models.Model):
            hash_id = models.CharField(max_length=64, primary_key=True)
            key = models.CharField(max_length=127)
            value = models.CharField(max_length=127)

            class Meta:
                app_label = "bcs_sync_regression"
                unique_together = [("key", "value")]

        class Relation(models.Model):
            resource_id = models.BigIntegerField()
            label_id = models.CharField(max_length=64)
            bcs_cluster_id = models.CharField(max_length=40)

            class Meta:
                app_label = "bcs_sync_regression"

        label_namespace = {
            "BCSLabel": Label,
            "IGNORE_LABEL_KEYS": set(),
            "router": Mock(),
            "transaction": transaction,
            "IntegrityError": IntegrityError,
        }
        definitions("bkmonitor/models/bcs_base.py", {"bulk_save_labels"}, label_namespace, "BCSBase")
        Resource.bulk_save_labels = label_namespace["bulk_save_labels"]
        Resource.md5str = staticmethod(lambda value: hashlib.md5(value.encode()).hexdigest())
        Resource.labels = SimpleNamespace(through=Relation)
        cls.Resource, cls.Cluster, cls.Label, cls.Relation = Resource, Cluster, Label, Relation
        cls.models = [Resource, Cluster, Label, Relation]
        with connections[DATABASE].schema_editor() as schema:
            for model in cls.models:
                schema.create_model(model)
        cls.namespace = {
            "BCSBase": Resource,
            "BCSCluster": Cluster,
            "Callable": Callable,
            "Iterable": Iterable,
            "islice": islice,
            "Q": Q,
            "transaction": transaction,
            "timezone": timezone,
            "router": SimpleNamespace(db_for_write=lambda model: DATABASE),
            "defaultdict": defaultdict,
            "logger": logging.getLogger("bcs-sync-regression"),
        }
        definitions(
            "api/bcs/tasks.py",
            {
                "bulk_save_resources",
                "save_resource_batch",
                "delete_missing_resources",
                "sync_cluster_resources",
                "populate_node_host_ids",
                "run_sub_task",
                "sync_bcs_cluster_to_db",
                "sync_bcs_pod",
            },
            cls.namespace,
        )
        cls.fields = ["bk_biz_id", "name", "unique_hash"]

    def setUp(self):
        for model in self.models:
            model._base_manager.using(DATABASE).all().delete()

    def row(self, name, biz=1, labels=None, cluster="cluster-a"):
        row = self.Resource(name=name, bk_biz_id=biz, bcs_cluster_id=cluster, unique_hash=f"{biz}:{cluster}:{name}")
        row.api_labels = labels or {}
        return row

    def sync(self, rows, **kwargs):
        return self.namespace["bulk_save_resources"](
            self.Resource, rows, "unique_hash", self.fields, {"bcs_cluster_id": "cluster-a"}, **kwargs
        )

    def test_natural_identity_reuses_hidden_node_and_business_migration(self):
        old = self.row("eklet-node")
        old.config = "preserved"
        old.save(using=DATABASE)
        self.assertEqual(self.Resource.objects.using(DATABASE).count(), 0)
        self.sync([self.row("eklet-node", biz=2), self.row("ordinary-node", biz=2)])
        saved = self.Resource._base_manager.using(DATABASE).get(id=old.id)
        self.assertEqual((saved.bk_biz_id, saved.unique_hash, saved.config), (2, "2:cluster-a:eklet-node", "preserved"))
        self.assertIsNotNone(saved.last_synced_at)
        self.assertEqual(self.Resource._base_manager.using(DATABASE).count(), 2)

    def test_new_id_readback_deduplicates_labels_and_empty_labels_are_scoped(self):
        from django.db.models.query import QuerySet

        create = QuerySet.bulk_create

        def without_returned_ids(query, objects, *args, **kwargs):
            result = create(query, objects, *args, **kwargs)
            if query.model is self.Resource:
                for obj in objects:
                    obj.id = None
            return result

        first, second = self.row("first", labels={"app": "demo"}), self.row("second", labels={"app": "demo"})
        with patch.object(QuerySet, "bulk_create", without_returned_ids):
            self.sync([first, second])
        self.assertTrue(first.id and second.id)
        self.assertEqual(self.Label.objects.using(DATABASE).count(), 1)
        self.assertEqual(self.Relation.objects.using(DATABASE).count(), 2)
        relation_ids = set(self.Relation.objects.using(DATABASE).values_list("id", flat=True))
        self.sync([self.row("first", labels={"app": "demo"}), self.row("second", labels={"app": "demo"})])
        self.assertEqual(set(self.Relation.objects.using(DATABASE).values_list("id", flat=True)), relation_ids)
        empty = self.row("first")
        empty.api_labels = None
        self.sync([empty], delete_missing=False)
        self.assertEqual(list(self.Relation.objects.using(DATABASE).values_list("resource_id", flat=True)), [second.id])
        malformed = self.row("second")
        malformed.api_labels = []
        with self.assertRaises(AttributeError):
            self.sync([malformed], delete_missing=False)

    def test_resource_insert_error_does_not_delete_history(self):
        from django.db import IntegrityError

        old = self.row("old")
        old.save(using=DATABASE)
        broken = self.row("broken")
        broken.name = None
        with self.assertRaises(IntegrityError):
            self.sync([broken])
        self.assertEqual(self.Resource._base_manager.using(DATABASE).get().id, old.id)

    def test_missing_readback_id_rolls_back_insert_and_preserves_history(self):
        from django.db.models.query import QuerySet

        old = self.row("old")
        old.save(using=DATABASE)
        query_filter = QuerySet.filter
        reads = 0

        def incomplete_readback(query, *args, **kwargs):
            nonlocal reads
            result = query_filter(query, *args, **kwargs)
            if query.model is self.Resource and query.query.select_for_update:
                reads += 1
                if reads == 2:
                    return result.none()
            return result

        with patch.object(QuerySet, "filter", incomplete_readback):
            with self.assertRaisesRegex(ValueError, "failed to read back"):
                self.sync([self.row("new", labels={"app": "demo"})])
        self.assertEqual(self.Resource._base_manager.using(DATABASE).get().id, old.id)
        self.assertEqual(self.Label.objects.using(DATABASE).count(), 0)

    def test_update_or_relation_error_rolls_back_batch_and_skips_cleanup(self):
        from django.db import DatabaseError
        from django.db.models.query import QuerySet

        old = self.row("old")
        old.save(using=DATABASE)
        with patch.object(QuerySet, "bulk_update", side_effect=DatabaseError("update failed")):
            with self.assertRaisesRegex(DatabaseError, "update failed"):
                self.sync([self.row("old", biz=2)])
        self.assertEqual(self.Resource._base_manager.using(DATABASE).get().bk_biz_id, 1)
        create = QuerySet.bulk_create

        def fail_relations(query, objects, *args, **kwargs):
            if query.model is self.Relation:
                raise DatabaseError("relation failed")
            return create(query, objects, *args, **kwargs)

        with patch.object(QuerySet, "bulk_create", fail_relations):
            with self.assertRaisesRegex(DatabaseError, "relation failed"):
                self.sync([self.row("new", labels={"app": "demo"})])
        self.assertEqual(self.Resource._base_manager.using(DATABASE).get().id, old.id)
        self.assertEqual(self.Label.objects.using(DATABASE).count(), 0)

        def fail_labels(query, objects, *args, **kwargs):
            if query.model is self.Label:
                raise DatabaseError("label failed")
            return create(query, objects, *args, **kwargs)

        with patch.object(QuerySet, "bulk_create", fail_labels):
            with self.assertRaisesRegex(DatabaseError, "label failed"):
                self.sync([self.row("new", labels={"app": "demo"})])
        self.assertEqual(self.Resource._base_manager.using(DATABASE).get().id, old.id)

    def test_stream_failure_keeps_prior_batches_and_unseen_rows(self):
        old = self.row("unseen")
        old.save(using=DATABASE)

        def source():
            for index in range(100):
                yield self.row(f"new-{index}")
            raise RuntimeError("page failed")

        with self.assertRaisesRegex(RuntimeError, "page failed"):
            self.sync(source())
        self.assertEqual(self.Resource._base_manager.using(DATABASE).count(), 101)
        self.sync([])
        self.assertEqual(self.Resource._base_manager.using(DATABASE).count(), 0)

    def test_label_hash_conflict_is_not_accepted(self):
        hash_id = self.Resource.md5str("app:demo")
        self.Label.objects.using(DATABASE).create(hash_id=hash_id, key="different", value="value")
        with self.assertRaisesRegex(ValueError, "matching label"):
            self.sync([self.row("new", labels={"app": "demo"})])
        self.assertEqual(self.Resource._base_manager.using(DATABASE).count(), 0)

    def test_label_unique_race_reads_matching_committed_row(self):
        from django.db.models.query import QuerySet

        hash_id = self.Resource.md5str("app:demo")
        self.Label.objects.using(DATABASE).create(hash_id=hash_id, key="app", value="demo")
        query_filter = QuerySet.filter
        first_read = True

        def hide_concurrent_label(query, *args, **kwargs):
            nonlocal first_read
            if query.model is self.Label and "hash_id__in" in kwargs and first_read:
                first_read = False
                return query_filter(query, hash_id__in=[])
            return query_filter(query, *args, **kwargs)

        with patch.object(QuerySet, "filter", hide_concurrent_label):
            self.sync([self.row("new", labels={"app": "demo"})])
        self.assertEqual(self.Label.objects.using(DATABASE).count(), 1)
        self.assertEqual(self.Relation.objects.using(DATABASE).count(), 1)

    def test_cluster_reuses_config_and_rejects_ambiguous_mapping(self):
        old = self.Cluster.objects.using(DATABASE).create(name="old", unique_hash="old", config="custom", node_count=9)
        incoming = self.Cluster(name="new", unique_hash="new", bk_biz_id=2)
        save = self.namespace["bulk_save_resources"]
        save(self.Cluster, [incoming], "unique_hash", self.fields, {"bk_tenant_id": "tenant"})
        current = self.Cluster.objects.using(DATABASE).get()
        self.assertEqual((current.id, current.config, current.node_count), (old.id, "custom", 9))
        self.Cluster.objects.using(DATABASE).create(name="duplicate", unique_hash="duplicate")
        with self.assertRaisesRegex(ValueError, "ambiguous"):
            save(self.Cluster, [incoming], "unique_hash", self.fields, {"bk_tenant_id": "tenant"})
        self.assertEqual(self.Cluster.objects.using(DATABASE).count(), 2)

    def test_node_empty_ip_skips_cmdb_and_bk_host_id_is_populated(self):
        lookup = Mock(
            return_value=[SimpleNamespace(bk_host_innerip="::1", bk_host_innerip_v6="", bk_cloud_id=0, bk_host_id=7)]
        )
        self.namespace.update(
            api=SimpleNamespace(cmdb=SimpleNamespace(get_host_by_ip=lookup)), exploded_ip=lambda value: value
        )
        nodes = [
            SimpleNamespace(ip="", bk_biz_id=1, cloud_id="0"),
            SimpleNamespace(ip="::1", bk_biz_id=1, cloud_id="0"),
        ]
        self.namespace["populate_node_host_ids"](nodes)
        self.assertEqual(lookup.call_args.kwargs["ips"], [{"ip": "::1", "bk_cloud_id": "0"}])
        self.assertEqual([node.bk_host_id for node in nodes], [None, 7])

    def test_task_exception_propagates_and_lock_skip_is_deferred(self):
        metrics = SimpleNamespace(
            CRON_BCS_SUB_TASK_EXECUTE_TIME=Mock(),
            CRON_BCS_SUB_TASK_EXECUTE_COUNT=Mock(),
            report_all=Mock(),
            StatusEnum=SimpleNamespace(DEFERRED="deferred", from_exc=lambda error: "failed" if error else "success"),
        )
        self.namespace.update(
            time=SimpleNamespace(time=lambda: 1), metrics=metrics, share_lock=lambda **kwargs: lambda fn: fn
        )
        with self.assertRaisesRegex(RuntimeError, "failed"):
            self.namespace["run_sub_task"]("sync", Mock(side_effect=RuntimeError("failed")), "cluster-a")
        self.assertEqual(metrics.CRON_BCS_SUB_TASK_EXECUTE_COUNT.labels.call_args.kwargs["status"], "failed")
        self.namespace["share_lock"] = lambda **kwargs: lambda fn: lambda *args: None
        wrapper = Mock()
        self.namespace["run_sub_task"]("sync", wrapper, "cluster-a")
        wrapper.assert_not_called()
        self.assertEqual(metrics.CRON_BCS_SUB_TASK_EXECUTE_COUNT.labels.call_args.kwargs["status"], "deferred")

    def test_cluster_read_failure_preserves_rows_and_later_empty_cluster_cleans(self):
        for cluster_id in ("cluster-a", "cluster-b"):
            self.Cluster.objects.using(DATABASE).create(
                name=cluster_id, bcs_cluster_id=cluster_id, unique_hash=cluster_id
            )
            self.row("old", cluster=cluster_id).save(using=DATABASE)

        def load(params):
            if "cluster-a" in params:
                raise RuntimeError("read failed")
            return []

        with patch.object(self.Resource, "load_list_from_api", side_effect=load, create=True):
            # The sync helper uses Cluster.objects; route only this isolated test query to its private alias.
            with patch.object(self.Cluster, "objects", self.Cluster.objects.db_manager(DATABASE)):
                with self.assertRaisesRegex(RuntimeError, "1 clusters"):
                    self.namespace["sync_cluster_resources"](self.Resource, None, self.fields, [])
        self.assertEqual(
            list(self.Resource._base_manager.using(DATABASE).values_list("bcs_cluster_id", flat=True)), ["cluster-a"]
        )

    def test_inventory_commits_all_tenants_before_independent_counts(self):
        old = self.Cluster.objects.using(DATABASE).create(name="old", unique_hash="old", node_count=8)
        protected = self.Cluster.objects.using(DATABASE).create(
            name="protected", unique_hash="protected", bk_tenant_id="failed", bcs_cluster_id="cluster-protected"
        )
        moved = self.Cluster(name="moved", unique_hash="moved", bk_biz_id=2)
        later = self.Cluster(name="later", unique_hash="later", bcs_cluster_id="cluster-later")

        def load(params):
            if params["bk_tenant_id"] == "failed":
                raise RuntimeError("tenant unavailable")
            return [moved, later]

        def count(params):
            self.assertEqual(self.Cluster.objects.using(DATABASE).count(), 3)
            if params["bcs_cluster_id"] == "cluster-a":
                raise RuntimeError("count unavailable")
            return {"master_count": 0, "node_count": 3}

        api = SimpleNamespace(
            bk_login=SimpleNamespace(list_tenant=lambda: [{"id": "failed"}, {"id": "tenant"}]),
            kubernetes=SimpleNamespace(fetch_k8s_node_count_by_cluster=Mock(side_effect=count)),
        )
        with (
            patch.object(self.Cluster, "load_list_from_api", side_effect=load, create=True),
            patch.dict(self.namespace, {"api": api}),
        ):
            with self.assertRaisesRegex(RuntimeError, "2 objects"):
                self.namespace["sync_bcs_cluster_to_db"]()
        self.assertEqual(self.Cluster.objects.using(DATABASE).get(id=old.id).node_count, 8)
        self.assertEqual(self.Cluster.objects.using(DATABASE).get(id=protected.id).name, "protected")
        self.assertEqual(self.Cluster.objects.using(DATABASE).get(bcs_cluster_id="cluster-later").node_count, 3)

    def test_last_cluster_cleanup_includes_all_eight_resource_types(self):
        self.Cluster.objects.using(DATABASE).create(name="last", unique_hash="last")
        resources = {
            name: Mock()
            for name in (
                "BCSNode",
                "BCSPod",
                "BCSContainer",
                "BCSWorkload",
                "BCSService",
                "BCSIngress",
                "BCSServiceMonitor",
                "BCSPodMonitor",
            )
        }
        api = SimpleNamespace(bk_login=SimpleNamespace(list_tenant=lambda: [{"id": "tenant"}]))
        with (
            patch.object(self.Cluster, "load_list_from_api", return_value=[], create=True),
            patch.dict(self.namespace, {"api": api, **resources}),
        ):
            self.namespace["sync_bcs_cluster_to_db"]()
        self.assertEqual(self.Cluster.objects.using(DATABASE).count(), 0)
        for resource in resources.values():
            resource._base_manager.using.return_value.filter.assert_called_once_with(bcs_cluster_id__in={"cluster-a"})
            resource._base_manager.using.return_value.filter.return_value.delete.assert_called_once_with()

    def test_pod_and_container_share_stream_and_defer_cleanup_until_complete(self):
        self.Cluster.objects.using(DATABASE).create(name="cluster", unique_hash="cluster")
        pod = SimpleNamespace(from_api_item=lambda item, biz: item)
        container = SimpleNamespace(from_pod=lambda item, biz: iter([item]))

        def source():
            yield from range(100)
            raise RuntimeError("pod page failed")

        fetch = Mock(return_value=source())
        save = Mock(side_effect=lambda resource, rows, *args, **kwargs: set(rows))
        cleanup = Mock()
        injected = {
            "api": SimpleNamespace(kubernetes=SimpleNamespace(fetch_k8s_pod_list_by_cluster=fetch)),
            "BCSPod": pod,
            "BCSContainer": container,
            "bulk_save_resources": save,
            "delete_missing_resources": cleanup,
        }
        with (
            patch.object(self.Cluster, "objects", self.Cluster.objects.db_manager(DATABASE)),
            patch.dict(self.namespace, injected),
        ):
            with self.assertRaisesRegex(RuntimeError, "pod page failed"):
                self.namespace["sync_bcs_pod"]("cluster-a")
            self.assertEqual(save.call_count, 2)
            cleanup.assert_not_called()
            fetch.assert_called_once()
            fetch.return_value = iter([])
            self.namespace["sync_bcs_pod"]("cluster-a")
        self.assertEqual(cleanup.call_count, 2)

    def test_monitor_endpoint_dedup_preserves_complete_tuple(self):
        class Monitor:
            METRICS_STATE_STATE_SUCCESS = "success"
            fetch_k8s_monitor_list_by_cluster = staticmethod(
                lambda params: [
                    [
                        {
                            "bcs_cluster_id": "cluster-a",
                            "namespace": "sample",
                            "name": "monitor",
                            "created_at": "time",
                            "metric_path": ["/metrics", "/metrics", "/metrics"],
                            "metric_port": ["8080", "9090", "8080"],
                            "metric_interval": ["30s", "60s", "30s"],
                        }
                    ]
                ]
            )

            def get_unique_hash(self):
                return (self.metric_path, self.metric_port, self.metric_interval)

        namespace = {
            "itertools": itertools,
            "parse_datetime": lambda value: value,
            "timezone": SimpleNamespace(now=lambda: 1),
        }
        definitions("bkmonitor/models/bcs_monitor.py", {"load_list_from_api"}, namespace, "BCSMonitor")
        rows = namespace["load_list_from_api"].__get__(None, Monitor)({"cluster-a": ("tenant", 1)})
        self.assertEqual([row.unique_hash for row in rows], [("/metrics", "8080", "30s"), ("/metrics", "9090", "60s")])


def test_persistence_in_isolated_process():
    result = subprocess.run([sys.executable, str(Path(__file__).resolve())], capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr


if __name__ == "__main__":
    unittest.main()
