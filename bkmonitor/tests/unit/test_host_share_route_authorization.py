"""Run production share authorization and consumers without service/DB bootstrap.

Imports, external CMDB/storage and metric enrichment are isolated. The
middleware, serializers, permission dispatch and resource methods run unchanged.
Run directly with Python or pytest --noconftest.
"""

import ast
import copy
import logging
import re
import sys
import time
import unittest
from datetime import datetime
from pathlib import Path
from types import ModuleType, SimpleNamespace
from unittest.mock import Mock, patch
from urllib.parse import urljoin

import pytz
from django.db import models
from django.http import HttpResponseForbidden
from rest_framework import serializers
from rest_framework.exceptions import ValidationError

ROOT = Path(__file__).resolve().parents[2]
HANDLER = "bkmonitor/share/handler.py"
HOST = "packages/monitor_web/scene_view/resources/host.py"
PERFORMANCE = "packages/monitor_web/performance/resources.py"
GRAPH = "packages/monitor_web/grafana/resources/unify_query.py"
SCENE_VIEW = "monitor_web.scene_view.views.SceneViewViewSet"
GRAPH_VIEW = "monitor_web.grafana.views.GrafanaViewSet"
METRIC_VIEW = "monitor_web.performance.views.SearchHostMetricViewSet"


def load(path, name, namespace, members=None, bases=None):
    node = next(n for n in ast.parse((ROOT / path).read_text()).body if getattr(n, "name", None) == name)
    if members is not None:
        node.body = [
            child
            for child in node.body
            if getattr(child, "name", None) in members
            or (
                isinstance(child, ast.Assign)
                and any(getattr(target, "id", None) in members for target in child.targets)
            )
        ]
    if bases is not None:
        node.bases = [ast.Name(id=base, ctx=ast.Load()) for base in bases]
    exec(
        compile(ast.fix_missing_locations(ast.Module(body=[node], type_ignores=[])), str(ROOT / path), "exec"),
        namespace,
    )
    return namespace[name]


class InlinePool:
    def __init__(self, *_args):
        pass

    def apply_async(self, function, args=(), kwds=None):
        result = function(*args, **(kwds or {}))
        return SimpleNamespace(get=lambda: result)

    def close(self):
        pass

    def join(self):
        pass


class TestHostShareRouteAuthorization(unittest.TestCase):
    def setUp(self):
        from django.conf import settings

        if not settings.configured:
            settings.configure(USE_I18N=False, REST_FRAMEWORK={})
        self.invalid = type("InvalidParamsError", (Exception,), {})
        self.denied = type("ParamsPermissionDeniedError", (Exception,), {})
        self.locked = type("SearchLockedError", (Exception,), {})
        self.request = None
        self.ipv6 = False
        self.hosts = [
            SimpleNamespace(
                bk_host_id=host_id,
                bk_module_ids=[module_id],
                ip=f"192.0.2.{host_id - 100}",
                bk_host_innerip=f"192.0.2.{host_id - 100}",
                bk_host_innerip_v6="",
                bk_host_outerip="",
                bk_host_outerip_v6="",
                bk_cloud_id=0,
                bk_os_type="1",
                bk_os_name="Linux",
                bk_host_name=f"host-{host_id}",
                bk_state="normal",
                ignore_monitoring=False,
                is_shielding=False,
            )
            for host_id, module_id in [(101, 4), (102, 5)]
        ]
        self.cmdb = SimpleNamespace(
            get_host_by_id=Mock(side_effect=self.get_hosts),
            get_host_by_topo_node=Mock(side_effect=self.get_hosts),
            get_host_page=Mock(side_effect=lambda **kw: {"items": self.get_hosts(**kw)}),
            get_topo_tree=Mock(
                return_value=SimpleNamespace(
                    convert_to_topo_link=lambda: {},
                    get_all_nodes_with_relation=lambda: {
                        f"{obj}|{node}": SimpleNamespace(bk_obj_name=obj, bk_inst_name=str(node), child=[])
                        for obj, node in [("biz", 2), ("set", 3), ("module", 4), ("module", 5)]
                    },
                )
            ),
            get_module=Mock(return_value=[]),
        )
        self.storage = Mock(return_value=[])
        cc = SimpleNamespace(
            get_agent_status=Mock(side_effect=lambda **kw: {host.bk_host_id: "ON" for host in kw["hosts"]}),
            get_process_info=Mock(return_value={}),
            get_process_port_health=Mock(return_value={}),
        )
        resource = Mock()
        resource.cc = cc
        self.namespace = dict(
            serializers=serializers,
            ValidationError=ValidationError,
            models=models,
            datetime=datetime,
            pytz=pytz,
            re=re,
            copy=copy,
            time=time,
            urljoin=urljoin,
            _=lambda value: value,
            InvalidParamsError=self.invalid,
            ParamsPermissionDeniedError=self.denied,
            SearchLockedError=self.locked,
            TokenValidatedError=type("TokenValidatedError", (Exception,), {}),
            CustomException=type("CustomException", (Exception,), {}),
            format_serializer_errors=lambda value: str(value.errors),
            logger=logging.getLogger(__name__),
            get_request=lambda **_kw: self.request,
            get_request_tenant_id=lambda: "tenant",
            api=SimpleNamespace(cmdb=self.cmdb),
            resource=resource,
            Host=SimpleNamespace,
            TopoNode=SimpleNamespace,
            Resource=type("Resource", (), {"many_request_data": False}),
            ThreadPool=InlinePool,
            settings=SimpleNamespace(
                OS_TYPE_NAME_DICT={1: "Linux"}, BK_CC_URL="https://cmdb.example.test", SQL_MAX_LIMIT=100
            ),
            AGENT_STATUS=SimpleNamespace(ON="ON", NOT_EXIST="NOT_EXIST", NO_DATA="NO_DATA", UNKNOWN="UNKNOWN"),
            DataSourceLabel=SimpleNamespace(BK_MONITOR_COLLECTOR="bk_monitor", BK_LOG_SEARCH="bk_log_search"),
            DataTypeLabel=SimpleNamespace(TIME_SERIES="time_series"),
            MetricListCache=SimpleNamespace(
                objects=SimpleNamespace(
                    filter=Mock(
                        return_value=SimpleNamespace(values_list=lambda *_args: [("system.cpu_summary", "usage")])
                    )
                )
            ),
            validate_bk_biz_id=int,
            is_ipv6_biz=lambda _biz: self.ipv6,
            load_data_source=lambda *_args: lambda **kwargs: kwargs,
            UnifyQuery=lambda **kwargs: SimpleNamespace(query_data=self.storage),
        )
        token_path = "bkmonitor/models/token.py"
        load(token_path, "AuthType", self.namespace)
        for node in ast.parse((ROOT / token_path).read_text()).body:
            if isinstance(node, ast.Assign) and any(
                isinstance(target, ast.Name) and target.id.startswith(("READONLY_", "HOST_SHARE_", "REGISTERED_"))
                for target in node.targets
            ):
                exec(compile(ast.Module(body=[node], type_ignores=[]), token_path, "exec"), self.namespace)
        token_cls = load(
            token_path, "ApiAuthToken", self.namespace, {"is_allowed_view", "is_allowed_namespace", "is_expired"}, []
        )
        self.token = token_cls()
        vars(self.token).update(
            type="host",
            token="share-token",
            bk_tenant_id="tenant",
            namespaces=["biz#2"],
            expire_time=None,
            params={
                "lock_search": False,
                "start_time": 100,
                "end_time": 200,
                "default_time_range": [],
                "data": {"scope": {"version": 1, "target_type": "host", "bk_host_id": 101}},
            },
        )
        token_cls.objects = SimpleNamespace(get=Mock(return_value=self.token))
        token_cls.DoesNotExist = type("DoesNotExist", (Exception,), {})
        self.models_module = ModuleType("bkmonitor.models")
        self.models_module.ApiAuthToken = token_cls
        for node in ast.parse((ROOT / HANDLER).read_text()).body:
            if isinstance(node, ast.Assign):
                exec(compile(ast.Module(body=[node], type_ignores=[]), HANDLER, "exec"), self.namespace)
        load(HANDLER, "validate_host_share_scope", self.namespace)
        load(HANDLER, "BaseApiAuthChecker", self.namespace)
        checker = load(HANDLER, "HostApiAuthChecker", self.namespace)
        self.namespace["checker_mapping"] = {"host": checker}
        load("bkmonitor/share/utils.py", "check_api_permission", self.namespace)
        load("bkmonitor/share/api_auth_resource.py", "ApiAuthResource", self.namespace)
        self.namespace["HttpResponseForbidden"] = HttpResponseForbidden
        self.middleware = load(
            "bkmonitor/middlewares/authentication.py",
            "ApiTokenAuthenticationMiddleware",
            self.namespace,
            {"api_token_auth"},
            [],
        )()
        # Keep the actual serializer and consumer bodies; isolate only their dependencies.
        self.detail = load(HOST, "GetHostOrTopoNodeDetailResource", self.namespace)
        self.process = load(HOST, "GetHostProcessListResource", self.namespace)
        self.uptime = load(HOST, "GetHostProcessUptimeResource", self.namespace)
        self.port = load(HOST, "GetHostProcessPortStatusResource", self.namespace)
        self.metric = load(PERFORMANCE, "SearchHostMetricResource", self.namespace)
        for section in ["get_agent_status", "get_performance_data", "get_process_status", "get_alarm_count"]:
            setattr(self.metric, section, Mock())
        load(GRAPH, "UnifyQueryRawResource", self.namespace, {"re_down_sample", "RequestSerializer"})
        self.graph = load(
            GRAPH,
            "GraphUnifyQueryResource",
            self.namespace,
            {"CUSTOM_METRIC_METHODS", "get_api_auth_request_data", "fill_custom_metric_method", "perform_request"},
        )
        self.graph_query = Mock(return_value={"series": [], "metrics": []})
        self.graph._perform_query = self.graph_query

    def get_hosts(self, bk_biz_id, bk_host_ids=None, topo_nodes=None, **_kwargs):
        result = self.hosts
        if topo_nodes:
            membership = {("biz", 2): [101, 102], ("set", 3): [101], ("module", 4): [101], ("module", 5): [102]}
            selected = {
                host for obj, ids in topo_nodes.items() for value in ids for host in membership.get((obj, value), [])
            }
            result = [host for host in result if host.bk_host_id in selected]
        if bk_host_ids is not None:
            result = [host for host in result if host.bk_host_id in bk_host_ids]
        return result

    @staticmethod
    def config(host=101, **overrides):
        return {
            "data_source_label": "bk_monitor",
            "data_type_label": "time_series",
            "table": "system.cpu_summary",
            "metrics": [{"field": "usage"}],
            "filter_dict": {"targets": [{"bk_host_id": host}]},
            **overrides,
        }

    def authorize(self, view_name, action):
        module, name = view_name.rsplit(".", 1)
        view = SimpleNamespace(cls=type(name, (), {"__module__": module}), actions={"post": action})
        self.request = SimpleNamespace(
            biz_id="2",
            method="POST",
            META={"HTTP_AUTHORIZATION": "Bearer share-token"},
            resolver_match=SimpleNamespace(func=view),
            user=SimpleNamespace(tenant_id="tenant"),
        )
        with patch.dict(sys.modules, {"bkmonitor.models": self.models_module}):
            return self.middleware.api_token_auth(self.request, view)

    def dispatch(self, resource_cls, view_name, action, payload):
        self.assertIsNone(self.authorize(view_name, action))
        resource = resource_cls()
        params = resource.validate_request_data(copy.deepcopy(payload))
        if resource_cls is not self.graph:
            self.assertNotIn("query_configs", params)
        return resource.perform_request(params)

    def non_graph_routes(self):
        return [
            (self.detail, SCENE_VIEW, "get_host_or_topo_node_detail", {}),
            (self.process, SCENE_VIEW, "get_host_process_list", {}),
            (self.uptime, SCENE_VIEW, "get_host_process_uptime", {"display_name": "process"}),
            (self.port, SCENE_VIEW, "get_host_process_port_status", {"display_name": "process"}),
            (self.metric, METRIC_VIEW, "create", {}),
        ]

    def test_unknown_chart_configuration_cannot_authorize_another_host(self):
        for resource, view, action, extra in self.non_graph_routes():
            with self.subTest(action=action, resource=resource.__name__):
                self.cmdb.get_host_by_id.reset_mock()
                with self.assertRaises(self.denied):
                    self.dispatch(
                        resource,
                        view,
                        action,
                        {
                            "bk_biz_id": 2,
                            "bk_host_id": 102,
                            "query_configs": [self.config()],
                            **extra,
                        },
                    )
                # Only the token's host was resolved; the consumer never queried host 102.
                self.assertEqual(
                    [call.kwargs["bk_host_ids"] for call in self.cmdb.get_host_by_id.call_args_list], [[101]]
                )

    def test_authorized_host_consumers_ignore_unknown_chart_fields(self):
        for resource, view, action, extra in self.non_graph_routes():
            with self.subTest(action=action, resource=resource.__name__):
                self.cmdb.get_host_by_id.reset_mock()
                result = self.dispatch(
                    resource,
                    view,
                    action,
                    {
                        "bk_biz_id": 2,
                        "bk_host_id": 101,
                        "query_configs": [self.config(102)],
                        **extra,
                    },
                )
                self.assertTrue(self.cmdb.get_host_by_id.called)
                self.assertTrue(
                    all(call.kwargs["bk_host_ids"] == [101] for call in self.cmdb.get_host_by_id.call_args_list)
                )
                if resource is self.detail:
                    self.assertEqual(next(row["value"] for row in result if row["name"] == "主机名"), "host-101")

    def test_unknown_chart_configuration_cannot_replace_required_target(self):
        for resource, view, action, extra in self.non_graph_routes():
            # Uptime requires its host in the DRF serializer, before share authorization.
            if resource is self.uptime:
                continue
            with self.subTest(action=action, resource=resource.__name__):
                with self.assertRaises(self.invalid):
                    self.dispatch(
                        resource,
                        view,
                        action,
                        {"bk_biz_id": 2, "query_configs": [self.config()], **extra},
                    )

    def test_metric_host_selection_cannot_expand_the_authorized_scope(self):
        for target in [{"bk_host_id": 101}, {"bk_obj_id": "module", "bk_inst_id": 4}]:
            self.token.params["data"]["scope"] = {
                "version": 1,
                "target_type": "host" if "bk_host_id" in target else "topo",
                **target,
            }
            with self.subTest(target=target):
                payload = {"bk_biz_id": 2, "bk_host_ids": [102], "query_configs": [self.config()], **target}
                with self.assertRaises(self.denied):
                    self.dispatch(self.metric, METRIC_VIEW, "create", payload)
                payload["bk_host_ids"] = [101]
                self.assertEqual(set(self.dispatch(self.metric, METRIC_VIEW, "create", payload)), {101})

    def test_topology_scope_does_not_expand_through_unknown_chart_configuration(self):
        for obj, node in [("biz", 2), ("set", 3), ("module", 4)]:
            self.token.params["data"]["scope"] = {
                "version": 1,
                "target_type": "topo",
                "bk_obj_id": obj,
                "bk_inst_id": node,
            }
            with self.subTest(scope=obj):
                with self.assertRaises(self.denied):
                    self.dispatch(
                        self.detail,
                        SCENE_VIEW,
                        "get_host_or_topo_node_detail",
                        {
                            "bk_biz_id": 2,
                            "bk_obj_id": "module",
                            "bk_inst_id": 5,
                            "query_configs": [self.config()],
                        },
                    )
                result = self.dispatch(
                    self.detail,
                    SCENE_VIEW,
                    "get_host_or_topo_node_detail",
                    {
                        "bk_biz_id": 2,
                        "bk_obj_id": obj,
                        "bk_inst_id": node,
                        "query_configs": [self.config(999)],
                    },
                )
                self.assertEqual(next(row["value"] for row in result if row["name"] == "节点ID"), node)

    def graph_payload(self, target):
        return {
            "bk_biz_id": 2,
            "start_time": 100,
            "end_time": 200,
            "expression": "A",
            "query_configs": [self.config(filter_dict={"targets": [target]})],
        }

    def test_graph_checks_normalized_execution_targets(self):
        for self.ipv6 in [False, True]:
            for host, allowed in [(101, True), (102, False)]:
                with self.subTest(ipv6=self.ipv6, host=host):
                    target = {"bk_host_id": host, "bk_target_ip": f"192.0.2.{host - 100}", "bk_target_cloud_id": 0}
                    self.graph_query.reset_mock()
                    if allowed:
                        self.assertEqual(
                            self.dispatch(
                                self.graph, GRAPH_VIEW, "time_series/unify_query", self.graph_payload(target)
                            ),
                            {"series": [], "metrics": []},
                        )
                        actual = self.graph_query.call_args.args[0]["query_configs"][0]["filter_dict"]["targets"][0]
                        self.assertEqual(
                            set(actual), {"bk_host_id"} if self.ipv6 else {"bk_target_ip", "bk_target_cloud_id"}
                        )
                    else:
                        with self.assertRaises(self.denied):
                            self.dispatch(self.graph, GRAPH_VIEW, "time_series/unify_query", self.graph_payload(target))
                        self.graph_query.assert_not_called()

    def test_graph_cannot_hide_foreign_ip_behind_authorized_host(self):
        with self.assertRaises(self.denied):
            self.dispatch(
                self.graph,
                GRAPH_VIEW,
                "time_series/unify_query",
                self.graph_payload(
                    {
                        "bk_host_id": 101,
                        "bk_target_ip": "192.0.2.2",
                        "bk_target_cloud_id": 0,
                    }
                ),
            )
        self.graph_query.assert_not_called()

    def test_topology_graph_queries_remain_within_authorized_hosts(self):
        for obj, node in [("biz", 2), ("set", 3), ("module", 4)]:
            self.token.params["data"]["scope"] = {
                "version": 1,
                "target_type": "topo",
                "bk_obj_id": obj,
                "bk_inst_id": node,
            }
            for host in [101, 102]:
                with self.subTest(scope=obj, host=host):
                    self.graph_query.reset_mock()
                    payload = self.graph_payload(
                        {
                            "bk_target_ip": f"192.0.2.{host - 100}",
                            "bk_target_cloud_id": 0,
                        }
                    )
                    if obj == "biz" or host == 101:
                        self.dispatch(self.graph, GRAPH_VIEW, "time_series/unify_query", payload)
                        self.graph_query.assert_called_once()
                    else:
                        with self.assertRaises(self.denied):
                            self.dispatch(self.graph, GRAPH_VIEW, "time_series/unify_query", payload)
                        self.graph_query.assert_not_called()

    def test_graph_validates_every_configuration_and_metric(self):
        for override in [
            {"table": "other.cpu"},
            {"metrics": [{"field": "foreign_metric"}]},
            {"promql": "system_cpu_usage"},
        ]:
            with self.subTest(override=override):
                payload = self.graph_payload({"bk_target_ip": "192.0.2.1", "bk_target_cloud_id": 0})
                payload["query_configs"].append(
                    self.config(
                        filter_dict={"targets": [{"bk_target_ip": "192.0.2.1", "bk_target_cloud_id": 0}]},
                        **override,
                    )
                )
                with self.assertRaises(self.denied):
                    self.dispatch(self.graph, GRAPH_VIEW, "time_series/unify_query", payload)
                self.graph_query.assert_not_called()

    def test_locked_time_is_enforced_on_both_route_types(self):
        self.token.params["lock_search"] = True
        for resource, view, action, extra in [
            (self.uptime, SCENE_VIEW, "get_host_process_uptime", {"bk_host_id": 101, "display_name": "process"}),
            (self.graph, GRAPH_VIEW, "time_series/unify_query", {"expression": "A"}),
        ]:
            with self.subTest(action=action):
                payload = {
                    "bk_biz_id": 2,
                    "start_time": 101,
                    "end_time": 200,
                    "query_configs": [
                        self.config(filter_dict={"targets": [{"bk_target_ip": "192.0.2.1", "bk_target_cloud_id": 0}]})
                    ],
                    **extra,
                }
                with self.assertRaises(self.locked):
                    self.dispatch(resource, view, action, payload)
                payload["start_time"] = 100
                self.dispatch(resource, view, action, payload)

    def test_missing_time_requires_valid_dynamic_range_or_independent_route(self):
        self.token.params["lock_search"] = True
        payload = {"bk_biz_id": 2, "bk_host_id": 101, "display_name": "process", "query_configs": [self.config()]}
        for default_range in [[], ["invalid", "range"]]:
            with self.subTest(default_range=default_range):
                self.token.params["default_time_range"] = default_range
                with self.assertRaises(self.invalid):
                    self.dispatch(self.uptime, SCENE_VIEW, "get_host_process_uptime", payload)
        self.token.params["default_time_range"] = ["now-1h", "now"]
        self.dispatch(self.uptime, SCENE_VIEW, "get_host_process_uptime", payload)
        self.token.params["default_time_range"] = []
        self.dispatch(self.detail, SCENE_VIEW, "get_host_or_topo_node_detail", payload)

    def test_write_and_other_graph_routes_are_rejected_by_middleware(self):
        for view, action in [
            (SCENE_VIEW, "update_scene_view"),
            (SCENE_VIEW, "delete_scene_view"),
            (GRAPH_VIEW, "time_series/unify_query_raw"),
            (GRAPH_VIEW, "graph_promql_query"),
        ]:
            with self.subTest(action=action):
                self.assertEqual(self.authorize(view, action).status_code, 403)


if __name__ == "__main__":
    unittest.main()
