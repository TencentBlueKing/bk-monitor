"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.

蓝鲸应用空间资源刷新：PaaS 集群命名空间接口调用失败不能被当作"没有集群资源"写入。

直接加载生产代码（PaaS 资源的 perform_request、Resource.bulk_request、刷新任务及资源写入函数），
只替换 HTTP 层和 ORM，不依赖 Django/DB。
"""

import ast
import copy
import json
import unittest
from multiprocessing.pool import ThreadPool
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

ROOT = Path(__file__).resolve().parents[3]

SHARED = "shared"
BKSAAS = "bksaas"


def load_definition(path, name, namespace, methods=None, bases=None):
    """从生产源码中取出一个顶层定义并在给定命名空间中执行"""
    tree = ast.parse((ROOT / path).read_text(encoding="utf-8"))
    node = next(node for node in tree.body if getattr(node, "name", None) == name)
    if methods is not None:
        node.body = [child for child in node.body if getattr(child, "name", None) in methods]
    if bases is not None:
        node.bases = [ast.Name(id=base, ctx=ast.Load()) for base in bases]
        node.keywords = []
    module = ast.fix_missing_locations(ast.Module(body=[node], type_ignores=[]))
    exec(compile(module, str(path), "exec"), namespace)
    return namespace[name]


class FakeBKAPIError(Exception):
    def __init__(self, system_name="", url="", result=None):
        super().__init__(system_name, url, result)


# 生产 Resource.bulk_request（线程池并发、ignore_exceptions、整批失败时抛出首个异常）
Resource = load_definition(
    "core/drf_resource/base.py", "Resource", {"ThreadPool": ThreadPool}, methods=["bulk_request"], bases=[]
)


class FakePaaSHTTP(Resource):
    """替代 HTTP 层：按 app_code 返回预设结果，预设为异常时抛出"""

    module_name = "bk_paas"
    action = "/system/bkapps/applications/{app_code}/cluster_namespaces/"
    answers = {}

    def __call__(self, *args, **kwargs):
        return self.request(args[0] if args else kwargs)

    def request(self, request_data=None, **kwargs):
        return self.perform_request(request_data or kwargs)

    def perform_request(self, validated_request_data):
        answer = self.answers[validated_request_data["app_code"]]
        if isinstance(answer, Exception):
            raise answer
        return copy.deepcopy(answer)


def load_paas_resource(logger):
    namespace = {
        "FakePaaSHTTP": FakePaaSHTTP,
        "BKAPIError": FakeBKAPIError,
        "logger": logger,
    }
    return load_definition(
        "api/bk_paas/default.py",
        "GetAppClusterNamespaceResource",
        namespace,
        methods=["perform_request"],
        bases=["FakePaaSHTTP"],
    )


class FakeSpaceResourceManager:
    """只保存 dimension_values，filter 返回副本，必须经 bulk_update/bulk_create 才会落库"""

    def __init__(self, stored):
        self.stored = stored

    def filter(self, space_type_id, space_id__in):
        return [
            SimpleNamespace(space_type_id=space_type_id, space_id=space_id, dimension_values=copy.deepcopy(values))
            for space_id, values in self.stored.items()
            if space_id in set(space_id__in)
        ]

    def bulk_update(self, objs, fields, batch_size=None):
        for obj in objs:
            self.stored[obj.space_id] = copy.deepcopy(obj.dimension_values)

    def bulk_create(self, objs, batch_size=None):
        for obj in objs:
            self.stored[obj.space_id] = copy.deepcopy(obj.dimension_values)

    def create(self, **kwargs):
        self.stored[kwargs["space_id"]] = copy.deepcopy(kwargs["dimension_values"])


def make_space_resource_model(stored):
    class FakeSpaceResource(SimpleNamespace):
        objects = FakeSpaceResourceManager(stored)

    return FakeSpaceResource


def cluster_answer(cluster_id, *namespaces):
    return [{"bcs_cluster_id": cluster_id, "namespace": ns, "environment": "prod"} for ns in namespaces]


def registration(cluster_id, *namespaces):
    return [{"cluster_id": cluster_id, "namespace": list(namespaces), "cluster_type": SHARED}]


class TestGetAppClusterNamespaceResource(unittest.TestCase):
    """PaaS 资源：失败必须抛出，只有可识别的列表才作为结果返回"""

    def setUp(self):
        self.logger = Mock()
        self.resource = load_paas_resource(self.logger)()

    def call(self, answer):
        FakePaaSHTTP.answers = {"demo-app": answer}
        return self.resource.perform_request({"app_code": "demo-app"})

    def test_call_failure_is_raised_instead_of_empty_list(self):
        for error in (FakeBKAPIError("bk_paas", "", "timeout"), ConnectionError("refused")):
            with self.subTest(error=type(error).__name__):
                with self.assertRaises(type(error)):
                    self.call(error)
        # 失败日志带上应用和异常类型
        self.assertIn("demo-app", self.logger.warning.call_args.args)
        self.assertIn("ConnectionError", self.logger.warning.call_args.args)

    def test_unrecognized_response_is_rejected(self):
        for answer in (None, {"data": []}, [{"namespace": "bkapp-demo-app-prod"}], ["bkapp-demo-app-prod"]):
            with self.subTest(answer=answer):
                with self.assertRaises(FakeBKAPIError):
                    self.call(answer)

    def test_explicit_answers_are_returned(self):
        self.assertEqual(self.call([]), [])
        answer = cluster_answer("BCS-K8S-00001", "bkapp-demo-app-prod")
        self.assertEqual(self.call(answer), answer)


class TestRefreshBksaasSpaceResource(unittest.TestCase):
    """刷新任务：调用失败的应用保留已有登记，PaaS 明确返回空时才写空"""

    def setUp(self):
        self.logger = Mock()
        self.stored = {}
        self.spaces = []
        self.authorize = Mock()
        resource = load_paas_resource(Mock())()
        models = SimpleNamespace(
            Space=SimpleNamespace(objects=SimpleNamespace(filter=lambda space_type_id: list(self.spaces))),
            SpaceResource=make_space_resource_model(self.stored),
        )
        self.namespace = {
            "api": SimpleNamespace(bk_paas=SimpleNamespace(get_app_cluster_namespace=resource)),
            "models": models,
            "logger": self.logger,
            "json": json,
            "SpaceTypes": SimpleNamespace(BKSAAS=SimpleNamespace(value=BKSAAS)),
            "BCSClusterTypes": SimpleNamespace(SHARED=SimpleNamespace(value=SHARED)),
            "BULK_UPDATE_BATCH_SIZE": 100,
            "BULK_CREATE_BATCH_SIZE": 100,
            "share_lock": lambda **kwargs: lambda func: func,
            "authorize_paas_space_cluster_data_source": self.authorize,
        }
        load_definition("metadata/task/sync_space.py", "create_and_update_paas_space_resource", self.namespace)
        self.refresh = load_definition("metadata/task/sync_space.py", "refresh_bksaas_space_resouce", self.namespace)

    def given(self, apps):
        """apps: {app_code: (已有登记或 None, PaaS 返回或异常)}"""
        FakePaaSHTTP.answers = {}
        for app_code, (previous, answer) in apps.items():
            self.spaces.append(SimpleNamespace(space_id=app_code, space_type_id=BKSAAS))
            if previous is not None:
                self.stored[app_code] = previous
            FakePaaSHTTP.answers[app_code] = answer

    def summary_error_args(self):
        return [call.args for call in self.logger.error.call_args_list]

    def test_failed_call_keeps_previous_dimension_values(self):
        failed_previous = registration("BCS-K8S-00001", "bkapp-failed-app-prod")
        self.given(
            {
                "failed-app": (failed_previous, FakeBKAPIError("bk_paas", "", "gateway error")),
                "healthy-app": (
                    registration("BCS-K8S-00001", "bkapp-healthy-app-stag"),
                    cluster_answer("BCS-K8S-00002", "bkapp-healthy-app-prod"),
                ),
            }
        )

        self.refresh()

        self.assertEqual(self.stored["failed-app"], failed_previous)
        # 同批其他应用照常更新
        self.assertEqual(self.stored["healthy-app"], registration("BCS-K8S-00002", "bkapp-healthy-app-prod"))
        # 失败应用不参与重新授权
        self.assertEqual(self.authorize.call_args.args[0], {"healthy-app": {"BCS-K8S-00002"}})
        # 本轮失败数与总数被记录
        self.assertTrue(any(1 in args and 2 in args for args in self.summary_error_args()))

    def test_explicit_empty_answer_writes_empty(self):
        self.given(
            {
                "empty-app": (registration("BCS-K8S-00001", "bkapp-empty-app-prod"), []),
                "healthy-app": (None, cluster_answer("BCS-K8S-00001", "bkapp-healthy-app-prod")),
            }
        )

        self.refresh()

        self.assertEqual(self.stored["empty-app"], [])
        self.assertEqual(self.stored["healthy-app"], registration("BCS-K8S-00001", "bkapp-healthy-app-prod"))
        self.assertEqual(self.summary_error_args(), [])

    def test_whole_batch_failure_keeps_every_registration(self):
        previous = {f"app-{index}": registration("BCS-K8S-00001", f"bkapp-app-{index}-prod") for index in range(3)}
        self.given(
            {app_code: (values, ConnectionError("refused")) for app_code, values in copy.deepcopy(previous).items()}
        )

        self.refresh()

        self.assertEqual(self.stored, previous)
        self.assertEqual(self.authorize.call_args.args[0], {})
        self.assertTrue(any(3 in args for args in self.summary_error_args()))


class TestCreateBksaasSpaceResource(unittest.TestCase):
    """创建空间时 PaaS 调用失败：不写入空登记，异常交由 create_space 记录，之后由刷新任务补建"""

    def test_call_failure_writes_nothing(self):
        stored = {}
        resource = load_paas_resource(Mock())()
        FakePaaSHTTP.answers = {"new-app": FakeBKAPIError("bk_paas", "", "gateway error")}
        namespace = {
            "atomic": lambda *args, **kwargs: lambda func: func,
            "config": SimpleNamespace(DATABASE_CONNECTION_NAME="default"),
            "api": SimpleNamespace(bk_paas=SimpleNamespace(get_app_cluster_namespace=resource)),
            "logger": Mock(),
            "SpaceResource": make_space_resource_model(stored),
        }
        create = load_definition("metadata/models/space/utils.py", "create_bksaas_space_resource", namespace)

        with self.assertRaises(FakeBKAPIError):
            create("tenant-a", BKSAAS, "new-app", "system")
        self.assertEqual(stored, {})


if __name__ == "__main__":
    unittest.main()
