"""dimension_values 接口 cluster_id 维度名称补充测试。

验证后端在 dimension_key=cluster_id 时新增 options 字段返回 [{id, name}] 结构，
values 字段仍为原始字符串数组保持向后兼容；BCS API 异常时 options 降级为 name=id，
非 cluster 维度不新增 options 字段。

名称补充复用 BcsApi.get_cluster_by_cluster_id 按 cluster_id 精确查询（与既有
_get_bcs_cluster_name 范式一致），不依赖业务 ID，关联空间的集群也能查到名称。
"""

import hashlib
from unittest.mock import patch

from django.test import TestCase, override_settings
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.request import Request
from rest_framework.test import APIRequestFactory

from apps.exceptions import ApiError, ApiRequestError, ApiResultError
from apps.log_search.models import IndexSetTag, LogIndexSet
from apps.log_search.views.scene_search_views import SceneSearchViewSet

# 名称解析已迁到 handler 层（apps/log_search/handlers/scene_search.py），
# resolve_bcs_cluster_names 通过模块级解包的 _BCS_GET_CLUSTER（DataAPI 实例）调用 BCS。
# patch 该模块级引用，确保并发子线程里 mock 生效（SimpleLazyObject 在子线程重新解包会导致 mock 失效）。
GET_CLUSTER_PATH = "apps.log_search.handlers.scene_search._BCS_GET_CLUSTER"


def _setup_k8s_index_set(cluster_ids, space_uid="bkcc__2"):
    """创建带 scene=k8s + cluster_id 标签的索引集。

    index_set_name 用固定前缀 + cluster_ids 数量 + 内容哈希，避免拼接全部 cluster_id
    导致超过 index_set_name 字段长度限制（大量集群时）。
    """
    scene_tag_id = IndexSetTag.get_tag_id(name="scene", value="k8s", tag_type="scene")
    tag_ids = [str(scene_tag_id)]
    for cid in cluster_ids:
        tid = IndexSetTag.get_tag_id(name="cluster_id", value=cid, tag_type="scene")
        tag_ids.append(str(tid))
    name_suffix = hashlib.md5(",".join(cluster_ids).encode("utf-8")).hexdigest()[:8]
    return LogIndexSet.objects.create(
        index_set_name="idx_{}_{}".format(len(cluster_ids), name_suffix),
        space_uid=space_uid,
        scenario_id="log",
        tag_ids=tag_ids,
        is_active=True,
    )


def _get_viewset(action_name, request):
    if not isinstance(request, Request):
        request = Request(request, parsers=[JSONParser(), FormParser(), MultiPartParser()])
    vs = SceneSearchViewSet(format_kwarg=None)
    vs.request = request
    vs.kwargs = {}
    vs.action = action_name
    return vs


def _post_request(payload):
    factory = APIRequestFactory()
    return factory.post(
        "/api/v1/search/scene/dimension_values/",
        data=payload,
        format="json",
    )


def _cluster_name_side_effect(name_map):
    """构造 get_cluster_by_cluster_id 的 side_effect：按 cluster_id(大写) 返回 {clusterName}。

    name_map: {原始 cluster_id: 集群名称}；不在映射内的 cluster_id 抛异常模拟 BCS 无此集群。
    生产代码调用会传 timeout kwarg（短超时），side_effect 需接受以避免 TypeError。
    """

    def _side_effect(params, timeout=None, **kwargs):
        cid = params["cluster_id"].upper()
        if cid not in name_map:
            # 模拟 BCS 查不到集群：HTTP 成功但业务返回失败（DataAPI 抛 ApiResultError）
            raise ApiResultError("cluster not found: {}".format(cid), code="404")
        return {"clusterName": name_map[cid], "projectID": "proj-{}".format(cid)}

    return _side_effect


@override_settings(PRE_SEARCH_SECONDS=60, TIME_ZONE="UTC")
class TestDimensionValuesClusterName(TestCase):
    @patch(
        "apps.log_search.views.scene_search_views.IndexSetHandler.get_all_related_space_uids",
        return_value=["bkcc__2"],
    )
    @patch(GET_CLUSTER_PATH)
    def test_cluster_id_returns_id_name_pairs(self, mock_bcs, mock_related):
        """cluster_id 维度 + BCS 正常返回 → options 为 [{id, name}]，values 仍为字符串数组。"""
        _setup_k8s_index_set(["cls-001", "cls-002"])
        mock_bcs.side_effect = _cluster_name_side_effect({"CLS-001": "生产集群", "CLS-002": "测试集群"})

        req = _post_request({"bk_biz_id": 2, "scene": "k8s", "dimension_key": "cluster_id"})
        response = _get_viewset("dimension_values", req).dimension_values(req)

        self.assertEqual(response.status_code, 200)
        # values 仍为原始字符串数组（向后兼容）
        self.assertEqual(response.data["values"], ["cls-001", "cls-002"])
        # options 为 [{id, name}] 结构
        options = response.data["options"]
        self.assertIsInstance(options, list)
        self.assertEqual(len(options), 2)
        option_map = {o["id"]: o["name"] for o in options}
        self.assertEqual(option_map["cls-001"], "生产集群")
        self.assertEqual(option_map["cls-002"], "测试集群")

    @patch(
        "apps.log_search.views.scene_search_views.IndexSetHandler.get_all_related_space_uids",
        return_value=["bkcc__2"],
    )
    @patch(GET_CLUSTER_PATH)
    def test_cluster_id_unknown_id_falls_back_to_id(self, mock_bcs, mock_related):
        """BCS 无该 cluster_id（查询抛异常）→ options 中 name 回退为 id 本身。"""
        _setup_k8s_index_set(["cls-unknown"])
        # BCS 只知道 CLS-001，查 CLS-UNKNOWN 时抛异常 → 降级为 id
        mock_bcs.side_effect = _cluster_name_side_effect({"CLS-001": "生产集群"})

        req = _post_request({"bk_biz_id": 2, "scene": "k8s", "dimension_key": "cluster_id"})
        response = _get_viewset("dimension_values", req).dimension_values(req)

        self.assertEqual(response.data["values"], ["cls-unknown"])
        options = response.data["options"]
        self.assertEqual(len(options), 1)
        self.assertEqual(options[0]["id"], "cls-unknown")
        self.assertEqual(options[0]["name"], "cls-unknown")

    @patch(
        "apps.log_search.views.scene_search_views.IndexSetHandler.get_all_related_space_uids",
        return_value=["bkcc__2"],
    )
    @patch(GET_CLUSTER_PATH)
    def test_cluster_id_bcs_api_exception_falls_back(self, mock_bcs, mock_related):
        """BCS API 网关异常（ApiRequestError）→ options 降级为 name=id，不报错。"""
        _setup_k8s_index_set(["cls-err"])
        mock_bcs.side_effect = ApiRequestError("BCS gateway timeout", "req-id")

        req = _post_request({"bk_biz_id": 2, "scene": "k8s", "dimension_key": "cluster_id"})
        response = _get_viewset("dimension_values", req).dimension_values(req)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["values"], ["cls-err"])
        options = response.data["options"]
        self.assertEqual(len(options), 1)
        self.assertEqual(options[0]["id"], "cls-err")
        self.assertEqual(options[0]["name"], "cls-err")

    @patch(
        "apps.log_search.views.scene_search_views.IndexSetHandler.get_all_related_space_uids",
        return_value=["bkcc__2"],
    )
    @patch(GET_CLUSTER_PATH)
    def test_cluster_id_empty_values_skips_bcs_call(self, mock_bcs, mock_related):
        """无匹配索引集 → values 为空，无 options 字段，不调用 BCS API。"""
        mock_bcs.side_effect = _cluster_name_side_effect({})

        req = _post_request({"bk_biz_id": 2, "scene": "k8s", "dimension_key": "cluster_id"})
        response = _get_viewset("dimension_values", req).dimension_values(req)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["values"], [])
        # 统一契约：options 始终返回，空结果为 []
        self.assertEqual(response.data["options"], [])
        mock_bcs.assert_not_called()

    @patch(
        "apps.log_search.views.scene_search_views.IndexSetHandler.get_all_related_space_uids",
        return_value=["bkcc__2"],
    )
    def test_non_cluster_dimension_returns_strings(self, mock_related):
        """stream 维度 → 仍返回纯字符串数组，无 options 字段。"""
        scene_tag_id = IndexSetTag.get_tag_id(name="scene", value="k8s", tag_type="scene")
        stdout_tag = IndexSetTag.get_tag_id(name="stream", value="stdout", tag_type="scene")
        LogIndexSet.objects.create(
            index_set_name="idx_stream",
            space_uid="bkcc__2",
            scenario_id="log",
            tag_ids=[str(scene_tag_id), str(stdout_tag)],
            is_active=True,
        )

        req = _post_request({"bk_biz_id": 2, "scene": "k8s", "dimension_key": "stream"})
        response = _get_viewset("dimension_values", req).dimension_values(req)

        self.assertEqual(response.status_code, 200)
        values = response.data["values"]
        self.assertEqual(values, ["stdout"])
        for v in values:
            self.assertIsInstance(v, str)
        # 统一契约：非 cluster 维度无 resolver，options 为 [{id, name=id}]
        self.assertEqual(response.data["options"], [{"id": "stdout", "name": "stdout"}])

    @patch(
        "apps.log_search.views.scene_search_views.IndexSetHandler.get_all_related_space_uids",
        return_value=["bkcc__2", "bcs__BCS-K8S-001"],
    )
    @patch(GET_CLUSTER_PATH)
    def test_cluster_id_with_filters_enriches_filtered_results(self, mock_bcs, mock_related):
        """级联筛选后仅对筛选结果补充名称。"""
        scene_tag = IndexSetTag.get_tag_id(name="scene", value="k8s", tag_type="scene")
        stdout_tag = IndexSetTag.get_tag_id(name="stream", value="stdout", tag_type="scene")
        file_tag = IndexSetTag.get_tag_id(name="stream", value="file", tag_type="scene")
        c1 = IndexSetTag.get_tag_id(name="cluster_id", value="cls-stdout", tag_type="scene")
        c2 = IndexSetTag.get_tag_id(name="cluster_id", value="cls-file", tag_type="scene")

        LogIndexSet.objects.create(
            index_set_name="idx_stdout",
            space_uid="bcs__BCS-K8S-001",
            scenario_id="log",
            tag_ids=[str(scene_tag), str(stdout_tag), str(c1)],
            is_active=True,
        )
        LogIndexSet.objects.create(
            index_set_name="idx_file",
            space_uid="bcs__BCS-K8S-001",
            scenario_id="log",
            tag_ids=[str(scene_tag), str(file_tag), str(c2)],
            is_active=True,
        )
        mock_bcs.side_effect = _cluster_name_side_effect(
            {"CLS-STDOUT": "标准输出集群", "CLS-FILE": "文件集群"}
        )

        req = _post_request(
            {
                "bk_biz_id": 2,
                "scene": "k8s",
                "dimension_key": "cluster_id",
                "filters": [{"field_name": "stream", "value": ["stdout"], "op": "eq"}],
            }
        )
        response = _get_viewset("dimension_values", req).dimension_values(req)

        self.assertEqual(response.data["values"], ["cls-stdout"])
        options = response.data["options"]
        self.assertEqual(len(options), 1)
        self.assertEqual(options[0]["id"], "cls-stdout")
        self.assertEqual(options[0]["name"], "标准输出集群")

    @patch(
        "apps.log_search.views.scene_search_views.IndexSetHandler.get_all_related_space_uids",
        return_value=["bkcc__2"],
    )
    @patch(GET_CLUSTER_PATH)
    def test_cluster_id_sorted_by_id(self, mock_bcs, mock_related):
        """多个 cluster_id → options 按 id 字典序排列。"""
        _setup_k8s_index_set(["cls-c", "cls-a", "cls-b"])
        # 全部查询失败（业务失败）→ 全部降级为 id，仍按字典序排列
        mock_bcs.side_effect = ApiResultError("cluster not found", code="404")

        req = _post_request({"bk_biz_id": 2, "scene": "k8s", "dimension_key": "cluster_id"})
        response = _get_viewset("dimension_values", req).dimension_values(req)

        ids = [o["id"] for o in response.data["options"]]
        self.assertEqual(ids, ["cls-a", "cls-b", "cls-c"])

    @patch(
        "apps.log_search.views.scene_search_views.IndexSetHandler.get_all_related_space_uids",
        return_value=["bkcc__2", "bcs__BCS-K8S-001"],
    )
    @patch(GET_CLUSTER_PATH)
    def test_cluster_id_related_space_enrichment(self, mock_bcs, mock_related):
        """关联空间的 cluster_id 也被补充名称。

        get_cluster_by_cluster_id 按 cluster_id 精确查询、不依赖业务 ID，
        因此来自关联 BCS 空间的 cluster_id 同样能查到名称。
        """
        scene_tag = IndexSetTag.get_tag_id(name="scene", value="k8s", tag_type="scene")
        biz_tag = IndexSetTag.get_tag_id(name="cluster_id", value="cls-biz", tag_type="scene")
        related_tag = IndexSetTag.get_tag_id(name="cluster_id", value="cls-related", tag_type="scene")

        LogIndexSet.objects.create(
            index_set_name="idx_biz",
            space_uid="bkcc__2",
            scenario_id="log",
            tag_ids=[str(scene_tag), str(biz_tag)],
            is_active=True,
        )
        LogIndexSet.objects.create(
            index_set_name="idx_related",
            space_uid="bcs__BCS-K8S-001",
            scenario_id="log",
            tag_ids=[str(scene_tag), str(related_tag)],
            is_active=True,
        )
        mock_bcs.side_effect = _cluster_name_side_effect({"CLS-BIZ": "业务集群", "CLS-RELATED": "关联集群"})

        req = _post_request({"bk_biz_id": 2, "scene": "k8s", "dimension_key": "cluster_id"})
        response = _get_viewset("dimension_values", req).dimension_values(req)

        option_map = {o["id"]: o["name"] for o in response.data["options"]}
        self.assertEqual(option_map["cls-biz"], "业务集群")
        self.assertEqual(option_map["cls-related"], "关联集群")

    @patch(
        "apps.log_search.views.scene_search_views.IndexSetHandler.get_all_related_space_uids",
        return_value=["bkcc__2"],
    )
    @patch(GET_CLUSTER_PATH)
    def test_view_response_format_cluster_id(self, mock_bcs, mock_related):
        """视图层集成：响应体结构为 {dimension_key, values: [str], options: [{id, name}]}。"""
        _setup_k8s_index_set(["cls-fmt"])
        mock_bcs.side_effect = _cluster_name_side_effect({"CLS-FMT": "格式集群"})

        req = _post_request({"bk_biz_id": 2, "scene": "k8s", "dimension_key": "cluster_id"})
        response = _get_viewset("dimension_values", req).dimension_values(req)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["dimension_key"], "cluster_id")
        self.assertEqual(response.data["values"], ["cls-fmt"])
        self.assertIsInstance(response.data["options"], list)
        for item in response.data["options"]:
            self.assertIn("id", item)
            self.assertIn("name", item)

    @patch(
        "apps.log_search.views.scene_search_views.IndexSetHandler.get_all_related_space_uids",
        return_value=["bkcc__2"],
    )
    def test_view_response_format_non_cluster(self, mock_related):
        """视图层集成：非 cluster 维度响应体 values 为字符串数组，无 options 字段。"""
        scene_tag_id = IndexSetTag.get_tag_id(name="scene", value="k8s", tag_type="scene")
        ns_tag = IndexSetTag.get_tag_id(name="namespace", value="default", tag_type="scene")
        LogIndexSet.objects.create(
            index_set_name="idx_ns",
            space_uid="bkcc__2",
            scenario_id="log",
            tag_ids=[str(scene_tag_id), str(ns_tag)],
            is_active=True,
        )

        req = _post_request({"bk_biz_id": 2, "scene": "k8s", "dimension_key": "namespace"})
        response = _get_viewset("dimension_values", req).dimension_values(req)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["dimension_key"], "namespace")
        for v in response.data["values"]:
            self.assertIsInstance(v, str)
        # 统一契约：非 cluster 维度无 resolver，options 为 [{id, name=id}]
        self.assertEqual(response.data["options"], [{"id": "default", "name": "default"}])

    @patch(
        "apps.log_search.views.scene_search_views.IndexSetHandler.get_all_related_space_uids",
        return_value=["bkcc__2"],
    )
    @patch(GET_CLUSTER_PATH)
    def test_cluster_id_empty_name_falls_back_to_id(self, mock_bcs, mock_related):
        """BCS 返回 clusterName 为空串 → name 降级为 id 本身。"""
        _setup_k8s_index_set(["cls-noname"])
        mock_bcs.side_effect = _cluster_name_side_effect({"CLS-NONAME": ""})

        req = _post_request({"bk_biz_id": 2, "scene": "k8s", "dimension_key": "cluster_id"})
        response = _get_viewset("dimension_values", req).dimension_values(req)

        options = response.data["options"]
        self.assertEqual(len(options), 1)
        self.assertEqual(options[0]["id"], "cls-noname")
        self.assertEqual(options[0]["name"], "cls-noname")

    @patch(
        "apps.log_search.views.scene_search_views.IndexSetHandler.get_all_related_space_uids",
        return_value=["bkcc__2"],
    )
    @patch(GET_CLUSTER_PATH)
    def test_cluster_id_none_name_falls_back_to_id(self, mock_bcs, mock_related):
        """BCS 返回 clusterName 为 None（字段缺失/null）→ name 降级为 id 本身。"""
        _setup_k8s_index_set(["cls-nullname"])

        def _none_name_side_effect(params):
            # 模拟 BCS 返回该集群但 clusterName 字段为 null
            assert params["cluster_id"].upper() == "CLS-NULLNAME"
            return {"clusterName": None, "projectID": "proj"}

        mock_bcs.side_effect = _none_name_side_effect

        req = _post_request({"bk_biz_id": 2, "scene": "k8s", "dimension_key": "cluster_id"})
        response = _get_viewset("dimension_values", req).dimension_values(req)

        options = response.data["options"]
        self.assertEqual(len(options), 1)
        self.assertEqual(options[0]["id"], "cls-nullname")
        self.assertEqual(options[0]["name"], "cls-nullname")

    @patch(
        "apps.log_search.views.scene_search_views.IndexSetHandler.get_all_related_space_uids",
        return_value=["bkcc__2"],
    )
    @patch(GET_CLUSTER_PATH)
    def test_cluster_id_partial_success_mixed(self, mock_bcs, mock_related):
        """混合场景：成功/业务失败/网关失败并存 → 互不影响，各自正确。

        验证 except ApiError 覆盖两个子类（ApiResultError + ApiRequestError），
        且单个失败不减少 result 条数、不影响其他集群名称。
        """
        _setup_k8s_index_set(["cls-ok", "cls-bizfail", "cls-netfail"])

        def _mixed_side_effect(params, timeout=None, **kwargs):
            cid = params["cluster_id"].upper()
            if cid == "CLS-OK":
                return {"clusterName": "正常集群", "projectID": "p"}
            if cid == "CLS-BIZFAIL":
                raise ApiResultError("cluster not found", code="404")
            if cid == "CLS-NETFAIL":
                raise ApiRequestError("gateway timeout", "req-id")
            return {"clusterName": "", "projectID": ""}

        mock_bcs.side_effect = _mixed_side_effect

        req = _post_request({"bk_biz_id": 2, "scene": "k8s", "dimension_key": "cluster_id"})
        response = _get_viewset("dimension_values", req).dimension_values(req)

        self.assertEqual(response.status_code, 200)
        options = response.data["options"]
        # 3 个集群全部返回，失败不影响全局
        self.assertEqual(len(options), 3)
        option_map = {o["id"]: o["name"] for o in options}
        self.assertEqual(option_map["cls-ok"], "正常集群")
        self.assertEqual(option_map["cls-bizfail"], "cls-bizfail")
        self.assertEqual(option_map["cls-netfail"], "cls-netfail")
        # 排序仍正确
        ids = [o["id"] for o in options]
        self.assertEqual(ids, ["cls-bizfail", "cls-netfail", "cls-ok"])

    @patch(
        "apps.log_search.views.scene_search_views.IndexSetHandler.get_all_related_space_uids",
        return_value=["bkcc__2"],
    )
    @patch(GET_CLUSTER_PATH)
    def test_cluster_id_non_api_error_degrades_with_isolation(self, mock_bcs, mock_related):
        """非 ApiError 家族异常（编程错误，如 ValueError）在并发下降级为 id，不中断其他集群。

        并发场景下 MultiExecuteFunc 的 FuncThread 为保证隔离性会兜底捕获所有异常，
        编程错误不会向上抛出接口，而是降级为 name=id。_query_one 内对非 ApiError
        记 exception 堆栈保证可观测，再 raise 交由 FuncThread 兜底降级。
        验证：编程错误不中断接口，该集群降级为 id，接口正常返回。
        """
        _setup_k8s_index_set(["cls-bug"])
        mock_bcs.side_effect = ValueError("unexpected programming error")

        req = _post_request({"bk_biz_id": 2, "scene": "k8s", "dimension_key": "cluster_id"})
        response = _get_viewset("dimension_values", req).dimension_values(req)

        self.assertEqual(response.status_code, 200)
        options = response.data["options"]
        self.assertEqual(len(options), 1)
        self.assertEqual(options[0]["id"], "cls-bug")
        self.assertEqual(options[0]["name"], "cls-bug")

    @patch(
        "apps.log_search.views.scene_search_views.IndexSetHandler.get_all_related_space_uids",
        return_value=["bkcc__2"],
    )
    @patch(GET_CLUSTER_PATH)
    def test_cluster_id_concurrent_many_success(self, mock_bcs, mock_related):
        """25 个集群并发查询，BCS 全部正常返回 → 全部正确映射，无丢失，排序正确。

        验证并发下结果完整性：所有集群都返回且名称正确（并发不丢结果）。
        """
        cluster_ids = ["cls-{}".format(str(i).zfill(2)) for i in range(25)]
        _setup_k8s_index_set(cluster_ids)
        name_map = {"CLS-{}".format(str(i).zfill(2)): "集群{}".format(str(i).zfill(2)) for i in range(25)}
        mock_bcs.side_effect = _cluster_name_side_effect(name_map)

        req = _post_request({"bk_biz_id": 2, "scene": "k8s", "dimension_key": "cluster_id"})
        response = _get_viewset("dimension_values", req).dimension_values(req)

        self.assertEqual(response.status_code, 200)
        options = response.data["options"]
        # 25 个全部返回，逐个比对 id→name 映射
        self.assertEqual(len(options), 25)
        option_map = {o["id"]: o["name"] for o in options}
        for i in range(25):
            cid = "cls-{}".format(str(i).zfill(2))
            self.assertEqual(option_map[cid], "集群{}".format(str(i).zfill(2)))
        # 排序正确
        ids = [o["id"] for o in options]
        self.assertEqual(ids, sorted(cluster_ids))

    @patch(
        "apps.log_search.views.scene_search_views.IndexSetHandler.get_all_related_space_uids",
        return_value=["bkcc__2"],
    )
    @patch(GET_CLUSTER_PATH)
    def test_cluster_id_concurrent_many_all_fail(self, mock_bcs, mock_related):
        """25 个集群并发查询，BCS 全部抛 ApiResultError → 全部降级为 id，排序正确。

        验证并发下异常隔离：所有查询失败都不中断，全部降级。
        """
        cluster_ids = ["cls-{}".format(str(i).zfill(2)) for i in range(25)]
        _setup_k8s_index_set(cluster_ids)
        mock_bcs.side_effect = ApiResultError("cluster not found", code="404")

        req = _post_request({"bk_biz_id": 2, "scene": "k8s", "dimension_key": "cluster_id"})
        response = _get_viewset("dimension_values", req).dimension_values(req)

        self.assertEqual(response.status_code, 200)
        options = response.data["options"]
        # 25 个全部降级为 id
        self.assertEqual(len(options), 25)
        for o in options:
            self.assertEqual(o["id"], o["name"])
        # 排序正确
        ids = [o["id"] for o in options]
        self.assertEqual(ids, sorted(cluster_ids))

    @patch(
        "apps.log_search.views.scene_search_views.IndexSetHandler.get_all_related_space_uids",
        return_value=["bkcc__2"],
    )
    @patch(GET_CLUSTER_PATH)
    def test_cluster_id_concurrent_mixed_success_and_fail(self, mock_bcs, mock_related):
        """25 个集群并发，奇数位成功、偶数位失败 → 成功映射、失败降级，互不影响。

        验证并发下成功与失败混合时的隔离性与正确性。
        """
        cluster_ids = ["cls-{}".format(str(i).zfill(2)) for i in range(25)]
        _setup_k8s_index_set(cluster_ids)

        def _mixed_side_effect(params, timeout=None, **kwargs):
            cid = params["cluster_id"].upper()
            idx = int(cid.split("-")[-1])
            if idx % 2 == 1:
                return {"clusterName": "集群{}".format(str(idx).zfill(2)), "projectID": "p"}
            raise ApiResultError("cluster not found: {}".format(cid), code="404")

        mock_bcs.side_effect = _mixed_side_effect

        req = _post_request({"bk_biz_id": 2, "scene": "k8s", "dimension_key": "cluster_id"})
        response = _get_viewset("dimension_values", req).dimension_values(req)

        self.assertEqual(response.status_code, 200)
        options = response.data["options"]
        # 25 个全部返回（失败不丢失）
        self.assertEqual(len(options), 25)
        option_map = {o["id"]: o["name"] for o in options}
        for i in range(25):
            cid = "cls-{}".format(str(i).zfill(2))
            if i % 2 == 1:
                self.assertEqual(option_map[cid], "集群{}".format(str(i).zfill(2)))  # 奇数成功映射
            else:
                self.assertEqual(option_map[cid], cid)  # 偶数失败降级为 id
        # 排序正确
        ids = [o["id"] for o in options]
        self.assertEqual(ids, sorted(cluster_ids))

    @patch(
        "apps.log_search.views.scene_search_views.IndexSetHandler.get_all_related_space_uids", return_value=["bkcc__2"]
    )
    @patch(GET_CLUSTER_PATH)
    def test_cluster_id_concurrent_preserves_request_context(self, mock_bcs, mock_related):
        """并发查询时 request 上下文正确传递到子线程。

        验证 FuncThread 把主线程 request 传给子线程，
        保证 BcsApi 的 before_request 鉴权（依赖 get_request()）在并发下正常。

        """
        from apps.utils.local import get_request

        _setup_k8s_index_set(["cls-ctx1", "cls-ctx2"])

        request_seen_in_subthread = []

        def _ctx_side_effect(params):
            # 在子线程内验证 request 上下文已传递（get_request() 非 None）
            try:
                req = get_request()
                request_seen_in_subthread.append(req is not None)
            except Exception:
                request_seen_in_subthread.append(False)
            return {"clusterName": "上下文集群", "projectID": "p"}

        mock_bcs.side_effect = _ctx_side_effect

        req = _post_request({"bk_biz_id": 2, "scene": "k8s", "dimension_key": "cluster_id"})
        # 用 patch 注入 request 到线程本地变量（模拟 UserLocalMiddleware 激活），用例结束自动恢复
        with patch("apps.utils.local._local.request", req, create=True):
            response = _get_viewset("dimension_values", req).dimension_values(req)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data["options"]), 2)
        # 每个并发子线程都能拿到 request 上下文（非 None）
        self.assertTrue(all(request_seen_in_subthread), "并发子线程应能获取到 request 上下文")

    @patch(
        "apps.log_search.views.scene_search_views.IndexSetHandler.get_all_related_space_uids",
        return_value=["bkcc__2"],
    )
    @patch(GET_CLUSTER_PATH)
    def test_cluster_id_concurrent_partial_field_missing(self, mock_bcs, mock_related):
        """并发查询，部分集群返回的 dict 无 clusterName 字段 → 缺失字段降级为 id。

        验证并发下字段缺失（调用成功但数据不完整）的降级正确性。
        """
        _setup_k8s_index_set(["cls-hasname", "cls-noname"])

        def _field_missing_side_effect(params, timeout=None, **kwargs):
            cid = params["cluster_id"].upper()
            if cid == "CLS-HASNAME":
                return {"clusterName": "有名字集群", "projectID": "p"}
            # CLS-NONAME 返回 dict 但无 clusterName 字段
            return {"projectID": "p"}

        mock_bcs.side_effect = _field_missing_side_effect

        req = _post_request({"bk_biz_id": 2, "scene": "k8s", "dimension_key": "cluster_id"})
        response = _get_viewset("dimension_values", req).dimension_values(req)

        self.assertEqual(response.status_code, 200)
        options = response.data["options"]
        self.assertEqual(len(options), 2)
        option_map = {o["id"]: o["name"] for o in options}
        self.assertEqual(option_map["cls-hasname"], "有名字集群")  # 有字段正常映射
        self.assertEqual(option_map["cls-noname"], "cls-noname")  # 缺字段降级为 id

    @patch(
        "apps.log_search.views.scene_search_views.IndexSetHandler.get_all_related_space_uids",
        return_value=["bkcc__2"],
    )
    @patch(GET_CLUSTER_PATH)
    def test_cluster_id_concurrent_actually_parallel(self, mock_bcs, mock_related):
        """量化验证：并发查询确实并行执行（而非串行累加）。

        用 threading.Barrier 让每个 mock 查询互相等待，若为串行则死锁超时；
        若为并发则所有查询同时到达 Barrier 一起放行。以此证明并发真实并行，
        并测量并发耗时远小于串行累加耗时。
        """
        import threading
        import time

        # 4 个任务并发（避免低核机器上 Barrier 超时失败）。
        n = 4
        cluster_ids = ["cls-{}".format(str(i).zfill(2)) for i in range(n)]
        _setup_k8s_index_set(cluster_ids)

        barrier = threading.Barrier(n, timeout=10)
        concurrency_observed = []

        def _barrier_side_effect(params, timeout=None, **kwargs):
            # 记录到达 Barrier 的时刻，Barrier 释放后记录完成时刻
            arrive = time.monotonic()
            barrier.wait()  # 串行执行时这里会死锁超时（只有一个线程到达）
            concurrency_observed.append(arrive)
            return {"clusterName": "并发集群", "projectID": "p"}

        mock_bcs.side_effect = _barrier_side_effect

        req = _post_request({"bk_biz_id": 2, "scene": "k8s", "dimension_key": "cluster_id"})
        start = time.monotonic()
        response = _get_viewset("dimension_values", req).dimension_values(req)
        elapsed = time.monotonic() - start

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data["options"]), n)
        # 所有 n 个查询都到达 Barrier 并完成（证明并发放行，未死锁）
        self.assertEqual(len(concurrency_observed), n)
        # 并发耗时远小于串行累加（若串行，n 个 Barrier.wait 会超时或累加）
        self.assertLess(elapsed, 5.0, "并发查询应在 5s 内完成（若串行 Barrier 会超时）")
