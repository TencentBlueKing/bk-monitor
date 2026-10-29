"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import base64
import json
import os

from django.conf import settings
from django.utils.translation import gettext_lazy as _

from apm.models import ProfileDataSource
from apm_web.profile.active_collection import fixtures
from apm_web.profile.active_collection.constants import (
    BKMONITORBEAT_RELATIVE_PATH,
    ERROR_TYPE_CONFIG_INVALID,
    ERROR_TYPE_DISPATCH_FAILED,
    EXECUTION_DETAIL_HOST_COLUMNS,
    EXECUTION_LIST_TASK_COLUMNS,
    HOST_QUERY_COLUMNS,
    META_CONFIG,
    PROCESS_MATCH_SCRIPT,
    PROCESS_PREVIEW_COLUMNS,
    PROCESS_PREVIEW_MAX_HOSTS,
    TASK_LIST_COLUMNS,
)
from apm_web.profile.active_collection.handlers import ActiveProfilingResultMixin
from apm_web.profile.active_collection.serializers import (
    EnableRequestSerializer,
    EventListRequestSerializer,
    ExecutionCancelRequestSerializer,
    ExecutionRenameRequestSerializer,
    ExecutionDetailRequestSerializer,
    MetaConfigRequestSerializer,
    ProcessPreviewRequestSerializer,
    ResultDataTypesRequestSerializer,
    ResultExportRequestSerializer,
    ResultQueryRequestSerializer,
    TaskDeleteRequestSerializer,
    TaskEditRequestSerializer,
    TaskListRequestSerializer,
    TaskSubmitRequestSerializer,
    TaskSwitchRequestSerializer,
    TopKRequestSerializer,
)
from apm_web.profile.constants import DEFAULT_EXPORT_FORMAT
from apm_web.profile.diagrams import get_diagrammer
from apm_web.profile.diagrams.tree_converter import TreeConverter
from apm_web.profile.doris.converter import DorisProfileConverter
from apm_web.profile.resources import QueryServicesDetailResource
from constants.apm import BUILTIN_PROFILING_APP_NAME
from core.drf_resource import Resource, api, resource


def _backend_params(validated_request_data):
    """计划、执行与查询都由后台 apm 处理；is_mock 只在 SaaS 侧生效，不转发给后台"""
    return {key: value for key, value in validated_request_data.items() if key != "is_mock"}


class ActiveProfilingMetaConfigResource(Resource):
    """获取表单默认值、请求枚举，以及当前业务是否已开通"""

    RequestSerializer = MetaConfigRequestSerializer

    def perform_request(self, validated_request_data):
        if validated_request_data.get("is_mock"):
            return {**META_CONFIG, "enabled": True}

        return {**META_CONFIG, "enabled": self._is_enabled(validated_request_data["bk_biz_id"])}

    @staticmethod
    def _is_enabled(bk_biz_id):
        """内置 Profiling 数据源已有 DataID 即视为已开通，事件分组由 enable 一起创建"""
        profile = ProfileDataSource.objects.filter(bk_biz_id=bk_biz_id, app_name=BUILTIN_PROFILING_APP_NAME).first()
        return profile is not None and profile.bk_data_id != -1


class EnableActiveCollectionResource(Resource):
    """按业务幂等创建 Event DataID、Profiling DataID 及存储资源，由后台 apm 完成"""

    RequestSerializer = EnableRequestSerializer

    def perform_request(self, validated_request_data):
        if validated_request_data.get("is_mock"):
            return

        api.apm_api.enable_active_profiling(bk_biz_id=validated_request_data["bk_biz_id"])


class PreviewProcessesResource(Resource):
    """预览命令行匹配进程"""

    RequestSerializer = ProcessPreviewRequestSerializer

    def perform_request(self, validated_request_data):
        if validated_request_data.get("is_mock"):
            return fixtures.PROCESS_PREVIEW

        nodes = validated_request_data["target_config"]["nodes"]
        if len(nodes) > PROCESS_PREVIEW_MAX_HOSTS:
            raise ValueError(_("预览主机数不能超过 {} 台").format(PROCESS_PREVIEW_MAX_HOSTS))

        beat_path = os.path.join(settings.LINUX_GSE_AGENT_PATH, BKMONITORBEAT_RELATIVE_PATH)
        task_result = resource.commons.fast_execute_script(
            bk_biz_id=validated_request_data["bk_biz_id"],
            host_list=[{"bk_host_id": node["bk_host_id"]} for node in nodes],
            script_content=PROCESS_MATCH_SCRIPT.format(beat_path=beat_path),
            script_param=self._build_selector_param(validated_request_data["process_selector"]),
            account_alias=settings.LINUX_JOB_EXECUTE_ACCOUNT,
        )
        return {
            "columns": PROCESS_PREVIEW_COLUMNS,
            "data": self._matched_processes(task_result["success"]) + self._failed_hosts(task_result["failed"]),
        }

    def _build_selector_param(self, process_selector):
        """选择器展开 config 后以 base64 传给脚本，base64 字符集不含 shell 元字符"""
        payload = json.dumps({"process_selector": {"type": process_selector["type"], **process_selector["config"]}})
        return base64.b64encode(payload.encode("utf-8")).decode("utf-8")

    def _matched_processes(self, success_hosts):
        """退出码为 0 时 stdout 是单个 JSON 对象；匹配不到进程的主机也返回一行，只有 bk_host_id 与 ip"""
        rows = []
        for host in success_hosts:
            processes = json.loads(host["log_content"])["processes"]
            if not processes:
                rows.append({"bk_host_id": host["bk_host_id"], "ip": host["ip"]})
            rows.extend({"bk_host_id": host["bk_host_id"], "ip": host["ip"], **process} for process in processes)
        return rows

    def _failed_hosts(self, failed_hosts):
        return [
            {"bk_host_id": host["bk_host_id"], "ip": host["ip"], **self._parse_failure(host)} for host in failed_hosts
        ]

    @staticmethod
    def _parse_failure(host):
        """退出码非 0 时 bkmonitorbeat 的 stdout 是带 error_type 的 JSON，作业平台把它放进 errmsg；
        旧版采集端输出的是错误文本，按配置不被支持归类。退出码为 0 说明作业平台没有执行成功"""
        if not host["exit_code"]:
            return {"error_type": ERROR_TYPE_DISPATCH_FAILED, "err_msg": host["errmsg"]}
        try:
            failure = json.loads(host["errmsg"])
        except ValueError:
            return {"error_type": ERROR_TYPE_CONFIG_INVALID, "err_msg": host["errmsg"]}
        return {"error_type": failure["error_type"], "err_msg": failure["message"]}


class ListTasksResource(Resource):
    """查询指定时间/周期计划"""

    RequestSerializer = TaskListRequestSerializer

    def perform_request(self, validated_request_data):
        if validated_request_data.get("is_mock"):
            return fixtures.TASK_LIST

        return {
            "columns": TASK_LIST_COLUMNS,
            **api.apm_api.list_active_profiling_tasks(**_backend_params(validated_request_data)),
        }


class SubmitTaskResource(Resource):
    """统一提交立即、指定时间或周期采集"""

    RequestSerializer = TaskSubmitRequestSerializer

    def perform_request(self, validated_request_data):
        if validated_request_data.get("is_mock"):
            return

        api.apm_api.submit_active_profiling_task(**_backend_params(validated_request_data))


class EditTaskResource(Resource):
    """编辑计划"""

    RequestSerializer = TaskEditRequestSerializer

    def perform_request(self, validated_request_data):
        if validated_request_data.get("is_mock"):
            return

        api.apm_api.edit_active_profiling_task(**_backend_params(validated_request_data))


class DeleteTaskResource(Resource):
    """删除计划"""

    RequestSerializer = TaskDeleteRequestSerializer

    def perform_request(self, validated_request_data):
        if validated_request_data.get("is_mock"):
            return

        api.apm_api.delete_active_profiling_task(**_backend_params(validated_request_data))


class SwitchTaskResource(Resource):
    """启停计划"""

    RequestSerializer = TaskSwitchRequestSerializer

    def perform_request(self, validated_request_data):
        if validated_request_data.get("is_mock"):
            return

        api.apm_api.switch_active_profiling_task(**_backend_params(validated_request_data))


class QueryHostsResource(Resource):
    """查询已采数据主机"""

    RequestSerializer = EventListRequestSerializer

    def perform_request(self, validated_request_data):
        if validated_request_data.get("is_mock"):
            return fixtures.HOST_QUERY

        return {
            "columns": HOST_QUERY_COLUMNS,
            "data": api.apm_api.query_active_profiling_hosts(**_backend_params(validated_request_data)),
        }


class ListExecutionsResource(Resource):
    """查询任务历史列表：按执行汇总全部主机，一次执行一行"""

    RequestSerializer = EventListRequestSerializer

    def perform_request(self, validated_request_data):
        if validated_request_data.get("is_mock"):
            return fixtures.EXECUTION_LIST

        return {
            "task_columns": EXECUTION_LIST_TASK_COLUMNS,
            "data": api.apm_api.list_active_profiling_executions(**_backend_params(validated_request_data)),
        }


class QueryTopKResource(Resource):
    """查询两个列表搜索框的候选值"""

    RequestSerializer = TopKRequestSerializer

    def perform_request(self, validated_request_data):
        if validated_request_data.get("is_mock"):
            return fixtures.topk(validated_request_data["field"])

        return api.apm_api.query_active_profiling_top_k(**_backend_params(validated_request_data))


class ExecutionDetailResource(Resource):
    """查询单次执行详情及全部主机"""

    RequestSerializer = ExecutionDetailRequestSerializer

    def perform_request(self, validated_request_data):
        if validated_request_data.get("is_mock"):
            return fixtures.execution_detail(validated_request_data)

        return {
            "host_columns": EXECUTION_DETAIL_HOST_COLUMNS,
            **api.apm_api.query_active_profiling_execution_detail(**_backend_params(validated_request_data)),
        }


class CancelExecutionResource(Resource):
    """取消执行：后台逐台主机下发 CLI 取消命令，受理后把主机写为 cancelled"""

    RequestSerializer = ExecutionCancelRequestSerializer

    def perform_request(self, validated_request_data):
        if validated_request_data.get("is_mock"):
            return

        api.apm_api.cancel_active_profiling_execution(**_backend_params(validated_request_data))


class RenameExecutionResource(Resource):
    """修改单次执行的任务名：只改执行行上的任务名快照，计划本身的名字不变，允许重复"""

    RequestSerializer = ExecutionRenameRequestSerializer

    def perform_request(self, validated_request_data):
        if validated_request_data.get("is_mock"):
            return

        api.apm_api.rename_active_profiling_execution(**_backend_params(validated_request_data))


class QueryResultsResource(ActiveProfilingResultMixin, Resource):
    """查看 Profiling 结果：取数、转换与绘图复用现有 Profiling 检索"""

    RequestSerializer = ResultQueryRequestSerializer

    def perform_request(self, validated_request_data):
        if validated_request_data.get("is_mock"):
            return fixtures.result_query(validated_request_data["diagram_types"])

        tree_converter = self._convert_samples(validated_request_data, TreeConverter())
        if tree_converter is None or tree_converter.empty():
            return {}

        result = {}
        for diagram_type in validated_request_data["diagram_types"]:
            result.update(get_diagrammer(diagram_type).draw(tree_converter, sort="-total"))
        result.update(tree_converter.get_sample_type())
        return result


class QueryResultDataTypesResource(ActiveProfilingResultMixin, Resource):
    """查询单次采集包含的采样类型：类型筛选与命名复用 Profiling 检索的服务详情"""

    RequestSerializer = ResultDataTypesRequestSerializer

    def perform_request(self, validated_request_data):
        if validated_request_data.get("is_mock"):
            return {"data_types": fixtures.RESULT_DATA_TYPES}

        data_types = QueryServicesDetailResource.to_data_types(self._query_sample_types(validated_request_data))
        return {"data_types": [{"key": data_type["key"], "name": data_type["name"]} for data_type in data_types]}


class ExportResultsResource(ActiveProfilingResultMixin, Resource):
    """导出 Profiling 结果：样本查询与 results/query 共用，pprof 打包复用 Profiling 检索导出"""

    RequestSerializer = ResultExportRequestSerializer

    def perform_request(self, validated_request_data):
        if validated_request_data.get("is_mock"):
            return fixtures.export_response()

        from apm_web.profile.views import ProfileQueryViewSet

        # 没有样本时传 None，由检索导出统一报“未查询到有效数据”
        return ProfileQueryViewSet.build_export_response(
            self._convert_samples(validated_request_data, DorisProfileConverter()),
            BUILTIN_PROFILING_APP_NAME,
            validated_request_data["data_type"],
            DEFAULT_EXPORT_FORMAT,
        )
