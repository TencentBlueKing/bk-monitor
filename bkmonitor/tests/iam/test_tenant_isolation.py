"""IAM 回调、资源补全和 SDK 缓存的多租户回归测试，不访问外部服务。"""

import base64
import json
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from django.db.models import Q
from rest_framework.test import APIRequestFactory

from bkmonitor.iam.adapters import catalog
from bkmonitor.iam.adapters.resolver import MonitorResourceResolver
from bkmonitor.iam.adapters.v4.callback import auth
from bkmonitor.iam.adapters.v4.callback.views import MonitorV4ResourceCallbackView
from bkmonitor.iam.iam_engine.core.types import (
    ApplyURLRequest,
    AuthRequest,
    BatchByActionRequest,
    BatchByResourceRequest,
    ResourceInstance,
    Subject,
)
from bkmonitor.iam.iam_engine.provider.codec import IdentityCodec
from bkmonitor.iam.iam_engine.schema.definitions import ActionDef, ResourceTypeDef
from bkmonitor.iam.iam_engine.schema.registry import SchemaRegistry
from bkmonitor.iam.iam_v3.client import V3Client
from bkmonitor.iam.iam_v3.provider import V3PermissionProvider
from bkmonitor.iam.iam_v4.provider import V4PermissionProvider
from kernel_api.rpc.functions.admin.permission._v3 import _enrich_permissions
from monitor_web.iam import views


class Rows:
    """为真实目录查询提供内存数据；保留 filter/exclude/Q 和分页的筛选语义。"""

    def __init__(self, rows):
        self.rows = list(rows)

    @staticmethod
    def matches(row, condition):
        if isinstance(condition, Q):
            values = [Rows.matches(row, child) for child in condition.children]
            result = any(values) if condition.connector == Q.OR else all(values)
            return not result if condition.negated else result
        key, expected = condition
        field, _, lookup = key.partition("__")
        actual = getattr(row, field)
        if lookup == "in":
            return actual in expected
        if lookup == "icontains":
            return expected.lower() in actual.lower()
        return str(actual) == str(expected)

    def filter(self, *args, **kwargs):
        conditions = [*args, *kwargs.items()]
        return Rows(row for row in self.rows if all(self.matches(row, c) for c in conditions))

    def exclude(self, **kwargs):
        return Rows(row for row in self.rows if not all(self.matches(row, c) for c in kwargs.items()))

    def all(self):
        return self

    def none(self):
        return Rows([])

    def get(self, **kwargs):
        rows = self.filter(**kwargs).rows
        if len(rows) != 1:
            raise LookupError(kwargs)
        return rows[0]

    def count(self):
        return len(self.rows)

    def values_list(self, field, flat=False):
        assert flat
        return [getattr(row, field) for row in self.rows]

    def __iter__(self):
        return iter(self.rows)

    def __getitem__(self, key):
        return self.rows[key]


def row(**kwargs):
    return SimpleNamespace(**kwargs)


@pytest.fixture
def resource_rows(monkeypatch):
    from apm_web.models import Application as ApmApplication
    from bk_dataview.models import Dashboard, Org
    from metadata.models import Space, SpaceType
    from rum_web.models.application import Application as RumApplication

    tenants = {1: "tenant-a", 2: "tenant-b", 3: "tenant-a", 4: "system"}
    spaces = [
        row(
            id=i,
            pk=i,
            space_type_id="bkcc",
            space_id=str(i),
            space_uid=f"bkcc__{i}",
            space_name=f"space-{i}",
            bk_tenant_id=t,
        )
        for i, t in tenants.items()
    ]
    apps = [
        row(pk=i, application_id=i, app_name=f"app-{i}", app_alias=f"alias-{i}", bk_biz_id=i, bk_tenant_id=t)
        for i, t in tenants.items()
    ]
    orgs = [row(id=100 + i, name=str(i)) for i in tenants]
    dashboards = []
    for i in tenants:
        dashboards.extend(
            [
                row(
                    id=200 + i,
                    pk=200 + i,
                    org_id=100 + i,
                    is_folder=True,
                    title=f"folder-{i}",
                    uid=f"folder-{i}",
                    folder_id=0,
                ),
                row(
                    id=300 + i,
                    pk=300 + i,
                    org_id=100 + i,
                    is_folder=False,
                    title=f"dashboard-{i}",
                    uid=f"dash-{i}",
                    folder_id=200 + i,
                ),
            ]
        )
    for model, records in [
        (Space, spaces),
        (SpaceType, [row(type_id="bkcc", type_name="业务")]),
        (ApmApplication, apps),
        (RumApplication, apps),
        (Org, orgs),
        (Dashboard, dashboards),
    ]:
        manager = Rows(records)
        for name in ("filter", "exclude", "all"):
            monkeypatch.setattr(model.objects, name, getattr(manager, name))
    monkeypatch.setattr(views, "get_org_by_name", lambda org_name: {"id": 100 + int(org_name)})
    monkeypatch.setattr("bk_dataview.api.get_org_by_name", lambda org_name: {"id": 100 + int(org_name)})

    def get_space_detail(space_uid="", bk_biz_id=0):
        if bk_biz_id < 0:
            return Rows(spaces).get(pk=-bk_biz_id)
        space_type, space_id = space_uid.split("__", 1)
        return Rows(spaces).get(space_type_id=space_type, space_id=space_id)

    monkeypatch.setattr("bkmonitor.iam.adapters.resolver.space_api.SpaceApi.get_space_detail", get_space_detail)
    return tenants


@pytest.fixture
def callback(monkeypatch):
    monkeypatch.setattr(auth, "get_callback_token_provider", lambda: row(get_system_token=lambda: "test-token"))

    def call(method="list_instance", rt="space", tenant="tenant-a", filter_data=None, page=None, http_method="post"):
        headers = {"HTTP_AUTHORIZATION": "Basic " + base64.b64encode(b"bk_iam:test-token").decode()}
        if tenant is not None:
            headers["HTTP_X_BK_TENANT_ID"] = tenant
        factory = APIRequestFactory()
        if http_method == "get":
            request = factory.get("/", **headers)
        else:
            request = factory.post(
                "/",
                {
                    "method": method,
                    "type": rt,
                    "filter": filter_data or {},
                    "page": page or {},
                    "bk_tenant_id": "body-must-not-be-used",
                },
                format="json",
                **headers,
            )
        return MonitorV4ResourceCallbackView.as_view()(request)

    return call


@pytest.mark.parametrize("tenant,ids", [("tenant-a", [1, 3]), ("tenant-b", [2]), ("system", [4])])
@pytest.mark.parametrize("rt", ["space", "apm_application", "rum_application", "grafana_dashboard"])
def test_v4_callback_queries_only_requested_tenant(resource_rows, callback, settings, tenant, ids, rt):
    settings.ENABLE_MULTI_TENANT_MODE = True
    expected = [f"space|{i}" for i in ids] if rt == "space" else [str(i) for i in ids]
    all_ids = ["1", "2", "3", "4"]
    if rt == "grafana_dashboard":
        expected = [f"folder:{100 + i}|{200 + i}" for i in ids] + [f"{100 + i}|dash-{i}" for i in ids]
        all_ids = [f"folder:{100 + i}|{200 + i}" for i in range(1, 5)] + [f"{100 + i}|dash-{i}" for i in range(1, 5)]
    listed = callback(rt=rt, tenant=tenant).data["data"]
    assert listed["count"] == len(expected)
    assert {r["id"] for r in listed["results"]} == set(expected)
    detail = callback("fetch_instance_info", rt, tenant, {"ids": all_ids}).data["data"]
    assert {r["id"] for r in detail} == set(expected)
    paged = callback(rt=rt, tenant=tenant, page={"page": 1, "page_size": 1}).data["data"]
    assert paged["count"] == len(expected)
    assert [r["id"] for r in paged["results"]] == expected[:1]
    next_page = callback(rt=rt, tenant=tenant, page={"page": 2, "page_size": 1}).data["data"]
    assert [r["id"] for r in next_page["results"]] == expected[1:2]


@pytest.mark.parametrize("rt", ["apm_application", "rum_application", "grafana_dashboard"])
def test_v4_parent_cannot_select_another_tenant(resource_rows, callback, settings, rt):
    settings.ENABLE_MULTI_TENANT_MODE = True
    forbidden = callback(rt=rt, filter_data={"parent": {"type": "space", "id": "space|2"}})
    assert forbidden.data["data"] == {"count": 0, "results": []}
    own = callback(rt=rt, filter_data={"parent": {"type": "space", "id": "space|1"}})
    assert own.data["data"]["count"] == (2 if rt == "grafana_dashboard" else 1)


@pytest.mark.parametrize("tenant", [None, "", "   "])
@pytest.mark.parametrize("method", ["list_instance", "fetch_instance_info"])
def test_v4_multitenant_requires_header_before_catalog(monkeypatch, callback, settings, tenant, method):
    settings.ENABLE_MULTI_TENANT_MODE = True
    query = MagicMock(side_effect=AssertionError("must not query"))
    monkeypatch.setattr(catalog, "list_instances", query)
    monkeypatch.setattr(catalog, "fetch_instance_info", query)
    result = callback(method=method, tenant=tenant)
    assert result.status_code == 400
    query.assert_not_called()
    assert callback(tenant=tenant, http_method="get").status_code == 200


@pytest.mark.parametrize(
    "tenant,expected", [(None, "system"), ("", "system"), ("   ", "system"), ("tenant-b", "tenant-b")]
)
def test_callback_single_tenant_compatibility(callback, resource_rows, settings, tenant, expected):
    settings.ENABLE_MULTI_TENANT_MODE = False
    result = callback(tenant=tenant)
    assert result.status_code == 200
    assert result.data["data"]["results"][0]["id"] == ("space|4" if expected == "system" else "space|2")
    dispatcher = views.ResourceApiDispatcher(MagicMock(), "monitor")
    request = APIRequestFactory().post(
        "/", {}, format="json", **({"HTTP_X_BK_TENANT_ID": tenant} if tenant is not None else {})
    )
    assert dispatcher._get_options(request)["bk_tenant_id"] == expected


@pytest.mark.parametrize("tenant", [None, "", "   "])
def test_v3_missing_tenant_uses_protocol_error(settings, tenant):
    settings.ENABLE_MULTI_TENANT_MODE = True
    client = MagicMock()
    dispatcher = views.ResourceApiDispatcher(client, "monitor")
    provider = views.SpaceProvider()
    provider.list_instance = MagicMock()
    dispatcher.register("space", provider)
    request = APIRequestFactory().post(
        "/",
        {"method": "list_instance", "type": "space"},
        format="json",
        **({"HTTP_X_BK_TENANT_ID": tenant} if tenant is not None else {}),
    )
    result = dispatcher.as_view()(request)
    assert json.loads(result.content)["code"] == 400
    client.is_basic_auth_allowed.assert_not_called()
    provider.list_instance.assert_not_called()


@pytest.mark.parametrize("tenant,expected", [("tenant-a", {"1", "3"}), ("tenant-b", {"2"}), ("system", {"4"})])
def test_v3_dispatcher_passes_tenant_to_provider(resource_rows, settings, tenant, expected):
    settings.ENABLE_MULTI_TENANT_MODE = True
    dispatcher = views.ResourceApiDispatcher(row(is_basic_auth_allowed=lambda *args: True), "monitor")
    dispatcher.register("space", views.SpaceProvider())
    request = APIRequestFactory().post(
        "/",
        {"method": "list_instance", "type": "space", "page": {"offset": 0, "limit": 20}},
        format="json",
        HTTP_X_BK_TENANT_ID=tenant,
    )
    result = json.loads(dispatcher.as_view()(request).content)
    assert result["code"] == 0
    assert {r["id"] for r in result["data"]["results"]} == expected


@pytest.mark.parametrize("method", ["list_instance", "search_instance", "list_instance_by_policy"])
def test_v3_apm_parent_queries_are_tenant_scoped(resource_rows, method):
    provider = views.ApmApplicationProvider()
    page = row(slice_from=0, slice_to=20)
    filters = row(parent={"id": 2}, search=None, resource_type_chain=None, keyword=None)
    assert getattr(provider, method)(filters, page, bk_tenant_id="tenant-a").count == 0
    assert getattr(provider, method)(filters, page, bk_tenant_id="tenant-b").count == 1


def test_v3_details_exclude_foreign_applications_and_folders(resource_rows):
    apm = views.ApmApplicationProvider().fetch_instance_info(row(ids=["1", "2"]), bk_tenant_id="tenant-a")
    assert [r["id"] for r in apm.results] == ["1"]
    grafana = views.GrafanaDashboardProvider().fetch_instance_info(
        row(ids=["folder:101|201", "folder:102|202", "102|dash-2"]), bk_tenant_id="tenant-a"
    )
    assert [r["id"] for r in grafana.results] == ["folder:101|201"]


@pytest.mark.parametrize("rt", ["apm_application", "rum_application"])
def test_resolver_application_cache_includes_tenant(monkeypatch, rt):
    fetch = MagicMock(
        side_effect=lambda typ, ids, requires, bk_tenant_id: [
            {"id": ids[0], "name": bk_tenant_id, "_bk_iam_path_": "/space,1/"}
        ]
    )
    monkeypatch.setattr(catalog, "fetch_instance_info", fetch)
    resolver = MonitorResourceResolver()
    resource = ResourceInstance(type=rt, id=f"cache-isolation-{rt}")
    assert resolver.resolve(resource, tenant_id="tenant-a").name == "tenant-a"
    assert resolver.resolve(resource, tenant_id="tenant-b").name == "tenant-b"
    assert resolver.resolve(resource, tenant_id="tenant-a").name == "tenant-a"
    assert fetch.call_count == 2


@pytest.mark.parametrize(
    "rt,rid",
    [
        ("space", "2"),
        ("space", "bkcc__2"),
        ("space", "-2"),
        ("apm_application", "2"),
        ("rum_application", "2"),
        ("grafana_dashboard", "102|dash-2"),
    ],
)
def test_resolver_does_not_enrich_foreign_resources(resource_rows, rt, rid):
    resolver = MonitorResourceResolver()
    resource = ResourceInstance(type=rt, id=rid)
    own = resolver.resolve(resource, tenant_id="tenant-b")
    foreign = resolver.resolve(resource, tenant_id="tenant-a")
    assert own.name and own.name != rid
    assert foreign.name in ("", rid)
    assert foreign.ancestor_chain == ()


def test_v3_rpc_enrichment_passes_tenant(resource_rows):
    schema = SchemaRegistry()
    schema.register_resource_type(ResourceTypeDef(id="space", name="Space"))
    schema.register_resource_type(ResourceTypeDef(id="apm_application", name="APM", ancestor="space"))
    actions = [{"permissions": [{"path": [{"type": "apm_application", "id": "2"}]}]}]
    assert _enrich_permissions(actions, schema, "tenant-b") == 0
    assert actions[0]["permissions"][0]["path"] == [
        {"type": "space", "id": "2", "display_name": "[业务] space-2"},
        {"type": "apm_application", "id": "2", "display_name": "app-2"},
    ]


def make_provider(cls, **overrides):
    schema = SchemaRegistry()
    schema.register_resource_type(ResourceTypeDef(id="space", name="Space"))
    schema.register_action(ActionDef(id="view_business", name="View", resource_type="space"))
    schema.freeze()
    options = {
        "base_url": "https://iam.example.test",
        "credentials": {"app_code": "test", "app_secret": "secret"},
        "system": {"id": "monitor", "name": "Monitor", "name_en": "Monitor"},
    }
    options.update(overrides)
    return cls(schema, **options)


@pytest.mark.parametrize("cls", [V3PermissionProvider, V4PermissionProvider])
@pytest.mark.parametrize("tenant,expected", [("tenant-b", "tenant-b"), ("", "system")])
@pytest.mark.parametrize(
    "operation", ["is_allowed", "batch_by_resource", "batch_by_action", "get_apply_url", "get_apply_data"]
)
def test_provider_passes_effective_tenant_to_resolver(monkeypatch, cls, tenant, expected, operation):
    provider = make_provider(cls)
    seen = []

    def resolve(resource, *, tenant_id):
        seen.append(tenant_id)
        return resource

    provider.resolver = row(resolve=resolve)
    monkeypatch.setattr(provider, "_is_allowed_dialect", lambda request: True)
    monkeypatch.setattr(provider, "_batch_by_resource_dialect_page", lambda request: [])
    monkeypatch.setattr(provider, "_batch_by_action_dialect_page", lambda request: [])
    monkeypatch.setattr(provider, "_get_apply_url_dialect", lambda request: "https://iam.example.test/apply")
    subject = Subject(id="user", tenant_id=tenant)
    resource = ResourceInstance(type="space", id="2")
    requests = {
        "is_allowed": lambda: provider.is_allowed(
            AuthRequest(subject=subject, action_id="view_business", resource=resource)
        ),
        "batch_by_resource": lambda: provider.batch_by_resource(
            BatchByResourceRequest(subject=subject, action_id="view_business", resources=(resource,))
        ),
        "batch_by_action": lambda: provider.batch_by_action(
            BatchByActionRequest(subject=subject, action_ids=("view_business",), resource=resource)
        ),
        "get_apply_url": lambda: provider.get_apply_url(
            ApplyURLRequest(subject=subject, action_ids=("view_business",), resources=(resource,))
        ),
        "get_apply_data": lambda: provider.get_apply_data(["view_business"], [resource], subject),
    }
    requests[operation]()
    assert seen == [expected]


@pytest.mark.parametrize(
    "method,backend", [("is_allowed_with_cache", "is_allowed"), ("_do_policy_query_with_cache", "_do_policy_query")]
)
def test_real_v3_caches_are_per_client_and_thread_safe(monkeypatch, method, backend):
    clients = [
        V3Client(
            "test",
            secret,
            "https://iam.example.test",
            "monitor",
            IdentityCodec(),
            bk_tenant_id=tenant,
            enable_v1_compat=False,
        )
        for tenant, secret in [("tenant-a", "secret"), ("tenant-b", "secret"), ("tenant-a", "rotated")]
    ]
    values = (
        [True, False, False]
        if method == "is_allowed_with_cache"
        else [[{"id": "a"}], [{"id": "b"}], [{"id": "rotated"}]]
    )
    backends = []
    for client, value in zip(clients, values):
        mock = MagicMock(return_value=value)
        monkeypatch.setattr(client, backend, mock)
        backends.append(mock)

    def check(index):
        client = clients[index]
        request = client.make_request("same-user", "same-action", [client.make_resource("space", "1")])
        return getattr(client, method)(request)

    assert [check(i) for i in range(3)] == values
    with ThreadPoolExecutor(max_workers=6) as pool:
        indices = [0, 1, 2] * 20
        assert list(pool.map(check, indices)) == [values[i] for i in indices]
    for mock in backends:
        mock.assert_called_once()
    assert clients[0]._allowed_cache.maxsize == clients[0]._policy_cache.maxsize == 1024
    assert clients[0]._allowed_cache.ttl == 10
    assert clients[0]._policy_cache.ttl == 60


@pytest.mark.parametrize("backend", ["is_allowed", "_do_policy_query"])
def test_provider_credential_rotation_starts_with_empty_caches(monkeypatch, settings, backend):
    from config.tools.iam_credentials import saas_setting

    # 与生产配置一致，通过延迟 SaaS 凭据验证同一 Provider 生命周期内的更新。
    provider = make_provider(
        V3PermissionProvider,
        credentials={"app_code": saas_setting("SAAS_APP_CODE"), "app_secret": saas_setting("SAAS_SECRET_KEY")},
    )
    settings.SAAS_APP_CODE = "test"
    settings.SAAS_SECRET_KEY = "first-secret"
    first = provider._get_client("tenant-a")
    method = "is_allowed_with_cache" if backend == "is_allowed" else "_do_policy_query_with_cache"
    monkeypatch.setattr(first, backend, MagicMock(return_value=True))
    request = first.make_request("user", "view_business", [])
    assert getattr(first, method)(request) is True

    settings.SAAS_SECRET_KEY = "next-secret"
    second = provider._get_client("tenant-a")
    assert second is not first
    query = MagicMock(return_value=False)
    monkeypatch.setattr(second, backend, query)
    assert getattr(second, method)(request) is False
    query.assert_called_once()
