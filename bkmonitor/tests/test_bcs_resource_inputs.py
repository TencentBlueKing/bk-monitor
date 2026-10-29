"""Run with stdlib unittest; exercise production parsers and adapters without Django/DB bootstrap."""

import ast
import copy
import logging
import unittest
from collections.abc import Mapping
from concurrent.futures import ThreadPoolExecutor
from contextvars import ContextVar
from functools import cached_property
from pathlib import Path
from threading import Event
from types import SimpleNamespace
from unittest.mock import Mock

from kubernetes.utils.quantity import parse_quantity
from requests.exceptions import HTTPError, ReadTimeout

ROOT = Path(__file__).resolve().parents[1]


def load_definition(path, name, namespace, methods=None, bases=None):
    tree = ast.parse((ROOT / path).read_text())
    node = next(node for node in tree.body if getattr(node, "name", None) == name)
    if methods is not None:
        node.body = [child for child in node.body if isinstance(child, ast.FunctionDef) and child.name in methods]
        if not node.body:
            node.body = [ast.Pass()]
    if bases is not None:
        node.bases = [ast.Name(id=base, ctx=ast.Load()) for base in bases]
        node.keywords = []
    module = ast.fix_missing_locations(ast.Module(body=[node], type_ignores=[]))
    exec(compile(module, str(path), "exec"), namespace)
    return namespace[name]


class TestKubernetesResourceInputs(unittest.TestCase):
    def setUp(self):
        self.namespace = {"cached_property": cached_property, "Mapping": Mapping, "parse_quantity": parse_quantity}
        path = "bkmonitor/utils/kubernetes.py"
        for name in ("get_cpu_without_unit", "get_memory_without_unit"):
            load_definition(path, name, self.namespace)
        load_definition(path, "KubernetesV1ObjectJsonParser", self.namespace, {"__init__"})
        self.pod_parser = load_definition(path, "KubernetesPodJsonParser", self.namespace, {"resources"})
        self.container_parser = load_definition(
            path, "KubernetesContainerJsonParser", self.namespace, {"__init__", "resources"}
        )
        self.service_parser = load_definition(
            path,
            "KubernetesServiceJsonParser",
            self.namespace,
            {"get_endpoint", "get_pod_name_list", "get_pod_count", "get_endpoints_count"},
        )

    def test_quantity_formats_and_output_types(self):
        cpu = self.namespace["get_cpu_without_unit"]
        memory = self.namespace["get_memory_without_unit"]
        for value, expected in (("1", 1.0), ("250m", 0.25), ("1.020", 1.02), ("0.5", 0.5), ("1e-3", 0.001), (1, 1.0)):
            with self.subTest(cpu=value):
                self.assertEqual(cpu(value), expected)
                self.assertIsInstance(cpu(value), float)
        for value, expected in (
            ("512Mi", 536870912),
            ("1.5Gi", 1610612736),
            ("512k", 512000),
            ("1e6", 1000000),
            (1, 1),
        ):
            with self.subTest(memory=value):
                self.assertEqual(memory(value), expected)
                self.assertIsInstance(memory(value), int)
        self.assertEqual(cpu(None), 0.0)
        self.assertEqual(memory(None), 0)
        for parse in (cpu, memory):
            for value in ("", "invalid", "1MiB", "NaN", "Infinity"):
                with self.subTest(parser=parse.__name__, invalid=value), self.assertRaises(ValueError):
                    parse(value)

    def test_pod_and_container_share_quantity_and_null_defaults(self):
        empty = {"requests_cpu": 0.0, "limits_cpu": 0.0, "requests_memory": 0, "limits_memory": 0}
        resources = {
            "requests": {"cpu": "0.5", "memory": "512k"},
            "limits": {"cpu": "1.020", "memory": "1.5Gi"},
        }
        expected = {
            "requests_cpu": 0.5,
            "limits_cpu": 1.02,
            "requests_memory": 512000,
            "limits_memory": 1610612736,
        }
        for value, result in (
            (resources, expected),
            (None, empty),
            ({}, empty),
            ({"requests": None, "limits": None}, empty),
            ({"requests": {"cpu": None, "memory": None}}, empty),
        ):
            container = {"name": "main", "resources": value}
            pod = {"spec": {"containers": [container]}}
            for parser in (self.pod_parser(pod), self.container_parser(pod, container)):
                with self.subTest(resources=value, parser=type(parser).__name__):
                    self.assertEqual(parser.resources, result)
                    self.assertIsInstance(parser.resources["requests_cpu"], float)
                    self.assertIsInstance(parser.resources["requests_memory"], int)
        for containers in (None, []):
            self.assertEqual(self.pod_parser({"spec": {"containers": containers}}).resources, empty)

        pod = {"spec": {"containers": [{"resources": resources}, {"resources": resources}]}}
        self.assertEqual(self.pod_parser(pod).resources, {key: value * 2 for key, value in expected.items()})

    def test_invalid_quantities_fail_for_both_parsers(self):
        for key in ("cpu", "memory"):
            container = {"resources": {"limits": {key: "invalid"}}}
            pod = {"spec": {"containers": [container]}}
            for parser in (self.pod_parser(pod), self.container_parser(pod, container)):
                with self.subTest(key=key, parser=type(parser).__name__), self.assertRaises(ValueError):
                    _ = parser.resources

    @staticmethod
    def endpoint(namespace, pod_name):
        return {
            "metadata": {"name": "shared-name", "namespace": namespace},
            "subsets": [{"addresses": [{"targetRef": {"kind": "Pod", "name": pod_name}}], "ports": [{"port": 80}]}],
        }

    def test_service_endpoint_identity_for_lists_and_indexes(self):
        service = self.service_parser({"metadata": {"name": "shared-name", "namespace": "ns-b"}})
        endpoints = [self.endpoint("ns-a", "pod-a"), self.endpoint("ns-b", "pod-b")]
        index = {(item["metadata"]["namespace"], item["metadata"]["name"]): item for item in endpoints}
        for source in (endpoints, index):
            self.assertEqual(service.get_pod_name_list(source), ["pod-b"])
            self.assertEqual(service.get_pod_count(source), 1)
            self.assertEqual(service.get_endpoints_count(source), 1)
        for source in ([endpoints[0]], {("ns-a", "shared-name"): endpoints[0]}, []):
            self.assertEqual(service.get_pod_name_list(source), [])
            self.assertEqual(service.get_endpoints_count(source), 0)

    def test_service_endpoint_empty_and_null_collections(self):
        service = self.service_parser({"metadata": {"name": "shared-name", "namespace": "ns-b"}})
        for subsets in (None, [], [{"addresses": None}], [{"addresses": []}], [{}]):
            endpoint = {"metadata": {"name": "shared-name", "namespace": "ns-b"}, "subsets": subsets}
            for source in ([endpoint], {("ns-b", "shared-name"): endpoint}):
                with self.subTest(subsets=subsets):
                    self.assertEqual(service.get_pod_name_list(source), [])
                    self.assertEqual(service.get_endpoints_count(source), 0)


class TestBcsStorageResponseValidation(unittest.TestCase):
    def setUp(self):
        self.namespace = {"logging": logging, "_lazy": lambda value: value, "_": lambda value: value}
        for name in ("ErrorDetails", "Error"):
            load_definition("core/errors/__init__.py", name, self.namespace)
        self.api_error = load_definition("core/errors/api.py", "BKAPIError", self.namespace)
        self.namespace.update(
            {
                "logger": Mock(),
                "HTTPError": HTTPError,
                "ReadTimeout": ReadTimeout,
                "APIPermissionDeniedCodeList": [],
                "_response_validated": ContextVar("test_storage_response_validated", default=None),
                "settings": SimpleNamespace(BCS_STORAGE_PAGE_SIZE=2),
                "copy": copy,
            }
        )
        transport = load_definition(
            "core/drf_resource/contrib/api.py", "APIResource", self.namespace, {"perform_request"}, bases=[]
        )
        transport.module_name = "bcs-storage"
        transport.action = "resources"
        transport.method = "GET"
        transport.TIMEOUT = 1
        transport.bk_tenant_id = "tenant"
        transport.IS_STANDARD_FORMAT = False
        transport.full_request_data = lambda self, params: params
        transport.get_request_url = lambda self, params: "https://example.invalid/resources"
        transport.get_headers = lambda self: {}
        transport.before_request = lambda self, params: params
        transport.record_request_data_to_span = lambda *args: None
        transport.report_api_request_count_metric = lambda *args, **kwargs: None
        transport.report_api_failure_metric = lambda *args, **kwargs: None
        transport.ignore_error_msg_list = []
        self.responses = Mock()
        transport.session = SimpleNamespace(get=lambda **kwargs: self.response(self.responses(kwargs["params"])))
        storage = load_definition(
            "api/bcs_storage/default.py",
            "BcsStorageBaseResource",
            self.namespace,
            {"perform_request", "render_response_data"},
            bases=["APIResource"],
        )
        self.fetch = load_definition("api/bcs_storage/default.py", "FetchResource", self.namespace, {"perform_request"})
        load_definition("api/bcs_storage/default.py", "FetchPageResource", self.namespace, set())
        self.iterator = load_definition("api/bcs_storage/default.py", "fetch_iterator", self.namespace)
        self.storage = storage()

    @staticmethod
    def response(data):
        return SimpleNamespace(raise_for_status=lambda: None, json=lambda: data, headers={})

    def test_empty_and_valid_data_keep_original_page_length(self):
        self.responses.return_value = {"code": 0, "data": []}
        self.assertEqual(self.storage.perform_request({}), [])
        self.responses.return_value = {"code": 0, "data": [{"data": {}}, {"data": {"metadata": {"name": "pod-a"}}}]}
        self.assertEqual(self.storage.perform_request({}), [{}, {"metadata": {"name": "pod-a"}}])
        self.assertIsNone(self.namespace["_response_validated"].get())

    def test_error_codes_missing_data_and_malformed_pages_raise(self):
        for response in (
            {"code": 1, "message": "storage unavailable"},
            {"code": 1, "data": []},
            {"data": []},
            {"code": 0},
            {"code": 0, "data": None},
            {"code": 0, "data": {}},
            {"code": 0, "data": [None]},
            {"code": 0, "data": [{}]},
            {"code": 0, "data": [{"data": None}]},
            {"code": 0, "data": [{"data": []}]},
            [],
            None,
            "invalid",
        ):
            with self.subTest(response=response):
                self.responses.return_value = response
                with self.assertRaises(self.api_error):
                    self.storage.perform_request({})
                self.assertIsNone(self.namespace["_response_validated"].get())

    def test_fetch_and_iterator_continue_after_full_page_and_fail_on_bad_item(self):
        full_page = {"code": 0, "data": [{"data": {"name": "first"}}, {"data": {"name": "second"}}]}
        for fetch in (
            lambda: self.fetch().perform_request({}),
            lambda: list(self.iterator("tenant", "cluster", "Pod")),
        ):
            self.responses.reset_mock()
            self.responses.side_effect = [full_page, {"code": 0, "data": []}]
            self.assertEqual(fetch(), [{"name": "first"}, {"name": "second"}])
            self.assertEqual([call.args[0]["offset"] for call in self.responses.call_args_list], [0, 2])

            self.responses.reset_mock()
            self.responses.side_effect = [full_page, {"code": 0, "data": [{"data": {"name": "third"}}, None]}]
            with self.assertRaisesRegex(self.api_error, "item 1"):
                fetch()
            self.assertEqual(self.responses.call_count, 2)

    def test_response_validation_is_isolated_for_same_instance_concurrency(self):
        rendered = Event()
        invalid_finished = Event()
        render = self.storage.render_response_data

        def render_and_wait(params, response):
            result = render(params, response)
            rendered.set()
            if not invalid_finished.wait(5):
                raise AssertionError("concurrent invalid response did not finish")
            return result

        self.storage.render_response_data = render_and_wait

        def response_for_params(params):
            if params["valid"]:
                return {"code": 0, "data": []}
            if not rendered.wait(5):
                raise AssertionError("concurrent valid response did not render")
            return []

        self.responses.side_effect = response_for_params

        def invalid_request():
            try:
                with self.assertRaises(self.api_error):
                    self.storage.perform_request({"valid": False})
            finally:
                invalid_finished.set()

        with ThreadPoolExecutor(max_workers=2) as executor:
            valid = executor.submit(self.storage.perform_request, {"valid": True})
            invalid = executor.submit(invalid_request)
            invalid.result(timeout=10)
            self.assertEqual(valid.result(timeout=10), [])
        self.assertIsNone(self.namespace["_response_validated"].get())

    def test_nested_request_and_failure_restore_validation_context(self):
        def nested_response(params):
            if params.get("nested"):
                return {"code": 0, "data": []}
            self.assertEqual(self.storage.perform_request({"nested": True}), [])
            return []

        self.responses.side_effect = nested_response
        with self.assertRaises(self.api_error):
            self.storage.perform_request({})
        self.assertIsNone(self.namespace["_response_validated"].get())
        self.responses.side_effect = None
        self.responses.return_value = {"code": 0, "data": []}
        self.assertEqual(self.storage.perform_request({}), [])
        self.assertIsNone(self.namespace["_response_validated"].get())


if __name__ == "__main__":
    unittest.main()
