# -*- coding: utf-8 -*-
"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2021 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import abc

import six
from django.conf import settings
from rest_framework import serializers

from bkm_space.validate import validate_bk_biz_id
from bkmonitor.commons.tools import batch_request
from bkmonitor.utils.user import get_backend_username, get_global_user
from constants.cmdb import TargetNodeType
from core.drf_resource import APIResource
from core.drf_resource.base import Resource


class NodeManAPIGWResource(six.with_metaclass(abc.ABCMeta, APIResource)):
    # 设置超时时间为 300s
    TIMEOUT = 300

    base_url_statement = None
    base_url = settings.BKNODEMAN_API_BASE_URL or "%s/api/c/compapi/v2/nodeman/" % settings.BK_COMPONENT_API_URL

    # 模块名
    module_name = "node_man"

    @property
    def label(self):
        return self.__doc__

    def get_request_url(self, validated_request_data):
        return (
            super(NodeManAPIGWResource, self).get_request_url(validated_request_data).format(**validated_request_data)
        )

    def validate_response_data(self, response_data):
        return response_data

    def full_request_data(self, validated_request_data):
        validated_request_data = super(NodeManAPIGWResource, self).full_request_data(validated_request_data)
        # 业务id判定
        if "bk_biz_id" not in validated_request_data:
            return validated_request_data
        # 业务id关联
        bk_biz_id = int(validated_request_data["bk_biz_id"])
        validated_request_data["bk_biz_id"] = validate_bk_biz_id(bk_biz_id)
        return validated_request_data


class RenderConfigTemplateResource(NodeManAPIGWResource):
    """
    渲染配置模板
    """

    action = "plugin_render_config_template/"
    method = "POST"

    class RequestSerializer(serializers.Serializer):
        id = serializers.IntegerField(required=False, label="配置文件ID")
        plugin_name = serializers.CharField(required=False, label="插件英文名")
        plugin_version = serializers.CharField(default="*", label="插件版本")
        name = serializers.CharField(required=False, label="配置模板文件名称")
        version = serializers.CharField(required=False, label="config_version")
        data = serializers.DictField(required=True, label="渲染值")

    class ResponseSerializer(serializers.Serializer):
        id = serializers.IntegerField(label="配置文件实例ID")
        md5 = serializers.CharField(label="配置文件的MD5")


class StartDebugResource(NodeManAPIGWResource):
    """
    启动插件调试
    """

    action = "plugin_start_debug/"
    method = "POST"

    class RequestSerializer(serializers.Serializer):
        plugin_id = serializers.IntegerField(required=False, label="配置文件ID")
        plugin_name = serializers.CharField(required=False, label="插件英文名")
        version = serializers.CharField(required=False, label="插件版本")
        config_ids = serializers.ListField(required=True, label="配置文件ID列表")
        host_info = serializers.DictField(required=True, label="主机信息")

    class ResponseSerializer(serializers.Serializer):
        task_id = serializers.CharField(required=True, label="任务ID")


class QueryDebugResource(NodeManAPIGWResource):
    """
    查询调试结果
    """

    action = "plugin_query_debug/"
    method = "GET"

    class RequestSerializer(serializers.Serializer):
        task_id = serializers.CharField(required=True, label="任务ID")

    class ResponseSerializer(serializers.Serializer):
        status = serializers.ChoiceField(required=True, label="任务状态", choices=["QUEUE", "RUNNING", "SUCCESS", "FAILED"])
        step = serializers.CharField(required=True, label="当前步骤")
        # error_code = serializers.CharField(required=True, label="状态代码")
        message = serializers.CharField(required=True, label="任务日志", allow_blank=True)


class StopDebugResource(NodeManAPIGWResource):
    """
    停止插件调试
    """

    action = "plugin_stop_debug/"
    method = "POST"

    class RequestSerializer(serializers.Serializer):
        task_id = serializers.CharField(required=True, label="任务ID")


class UploadResource(NodeManAPIGWResource):
    """
    上传插件包
    """

    base_url = settings.BK_NODEMAN_INNER_HOST
    action = "/backend/package/upload/"
    method = "POST"
    support_data_collect = False


class UploadCosResource(NodeManAPIGWResource):
    """
    上传COS插件包
    """

    action = "/backend/api/plugin/upload/"
    method = "POST"

    class RequestSerializer(serializers.Serializer):
        file_name = serializers.CharField(label="文件包名")
        download_url = serializers.CharField(label="文件下载路径")
        md5 = serializers.CharField(label="文件md5")


class RegisterPackageResource(NodeManAPIGWResource):
    """
    注册插件包
    """

    action = "plugin_create_register_task/"
    method = "POST"

    class RequestSerializer(serializers.Serializer):
        file_name = serializers.CharField(required=True, label="文件包名")
        is_release = serializers.BooleanField(required=True, label="是否为发布版本")

    class ReponseSerializer(serializers.Serializer):
        job_id = serializers.IntegerField(label="注册任务ID")


class QueryRegisterTaskResource(NodeManAPIGWResource):
    """
    查询注册任务
    """

    action = "plugin_query_register_task/"
    method = "GET"

    class RequestSerializer(serializers.Serializer):
        job_id = serializers.IntegerField(required=True, label="注册任务ID")

    class ReponseSerializer(serializers.Serializer):
        is_finish = serializers.BooleanField(label="是否完成")
        message = serializers.CharField(label="错误信息", allow_blank=True)


class PluginInfoResource(NodeManAPIGWResource):
    """
    查询插件信息
    """

    action = "plugin_info/"
    method = "GET"

    class RequestSerializer(serializers.Serializer):
        name = serializers.CharField(required=True, label="插件名")
        version = serializers.CharField(required=False, label="版本号")


class CreateConfigTemplateResource(NodeManAPIGWResource):
    action = "plugin_create_config_template/"
    method = "POST"

    """
        {
      "plugin_name": "externel_plugins",  # 配置文件是供何插件使用的
      "plugin_version": "*",  # 可以使用该配置文件的版本号， *为任意版本
      "name": "config.yaml",  # 配置文件的名字
      "path": "etc/windows",  # 部署时，配置文件的路径，该目录相对于插件根目录
      "format": "json",  # 配置文件格式，json | yaml | bash | bat
      "content": "aasdfasi1231jhka"  # 配置文件内容，base64编码, 解码后的文字是unicode编码
      "md5": "asdfasdf",  # 文件md5哈希值，用于校验内容是否符合预期
      "version": "1.0.1",   # 配置文件版本
      "is_release": true  # 配置文件是否正式版本
    }
    """

    class RequestSerializer(serializers.Serializer):
        plugin_name = serializers.CharField(label="插件名")
        plugin_version = serializers.CharField(label="插件版本")
        name = serializers.CharField(label="配置文件名称")
        file_path = serializers.CharField(label="配置文件的下发路径，该目录相对于插件根目录", allow_blank=True)
        format = serializers.CharField(label="配置文件格式")
        content = serializers.CharField(label="配置文件内容，base64编码", allow_blank=True)
        md5 = serializers.CharField(label="配置文件MD5")
        version = serializers.CharField(label="配置文件版本")
        is_release_version = serializers.BooleanField(label="配置文件是否正式版本")


class ReleasePluginResource(NodeManAPIGWResource):
    action = "plugin_release/"
    method = "POST"

    class RequestSerializer(serializers.Serializer):
        name = serializers.CharField(required=True, label="插件名")
        version = serializers.CharField(required=True, label="版本号")
        md5_list = serializers.ListField(required=True, label="插件md5")


class ReleaseConfigResource(NodeManAPIGWResource):
    action = "plugin_release_config_template/"
    method = "POST"

    class RequestSerializer(serializers.Serializer):
        plugin_name = serializers.CharField(required=True, label="插件名")
        plugin_version = serializers.CharField(required=True, label="插件版本号")
        name = serializers.CharField(required=True, label="配置文件模板")
        version = serializers.CharField(required=True, label="配置文件版本")


class ExportRawPackageResource(NodeManAPIGWResource):
    action = "plugin_create_export_task/"
    method = "POST"

    class RequestSerializer(serializers.Serializer):
        class QueryParams(serializers.Serializer):
            project = serializers.CharField(required=True, label="插件名")
            version = serializers.CharField(required=True, label="插件版本")

        category = serializers.CharField(required=True, label="插件名")
        query_params = QueryParams(required=True)
        creator = serializers.CharField(required=True, label="调用者")
        bk_app_code = serializers.CharField(default=settings.APP_CODE, label="调用方app_code")


class ExportQueryTaskResource(NodeManAPIGWResource):
    action = "plugin_query_export_task/"
    method = "GET"

    class RequestSerializer(serializers.Serializer):
        job_id = serializers.IntegerField(required=True, label="任务ID")


class DeletePluginResource(NodeManAPIGWResource):
    action = "plugin_delete/"
    method = "POST"

    class RequestSerializer(serializers.Serializer):
        name = serializers.CharField(required=True, label="插件ID")


class CreateSubscriptionResource(NodeManAPIGWResource):
    action = "subscription_create/"
    method = "POST"

    class RequestSerializer(serializers.Serializer):
        class ScopeParams(serializers.Serializer):
            bk_biz_id = serializers.IntegerField(required=False, label="业务ID")
            object_type = serializers.ChoiceField(required=True, label="采集目标类型", choices=["SERVICE", "HOST"])
            node_type = serializers.ChoiceField(
                required=True,
                label="采集对象类型",
                choices=[
                    TargetNodeType.TOPO,
                    TargetNodeType.INSTANCE,
                    TargetNodeType.SET_TEMPLATE,
                    TargetNodeType.SERVICE_TEMPLATE,
                ],
            )
            nodes = serializers.ListField(required=True, label="节点列表")

            def validate_bk_biz_id(self, value):
                return validate_bk_biz_id(value)

        scope = ScopeParams(required=True, label="事件订阅监听的范围")
        steps = serializers.ListField(required=True, label="事件订阅触发的动作列表")
        target_hosts = serializers.ListField(required=False, label="远程采集机器")
        run_immediately = serializers.BooleanField(required=False, label="是否立即触发")


class SubscriptionInfoResource(NodeManAPIGWResource):
    action = "subscription_info/"
    method = "POST"

    class RequestSerializer(serializers.Serializer):
        subscription_id_list = serializers.ListField(required=True, label="采集配置订阅id列表")


class UpdateSubscriptionResource(NodeManAPIGWResource):
    action = "subscription_update/"
    method = "POST"

    class RequestSerializer(serializers.Serializer):
        class ScopeParams(serializers.Serializer):
            bk_biz_id = serializers.IntegerField(required=False, label="业务ID")
            node_type = serializers.ChoiceField(
                required=True,
                label="采集对象类型",
                choices=[
                    TargetNodeType.INSTANCE,
                    TargetNodeType.TOPO,
                    TargetNodeType.SET_TEMPLATE,
                    TargetNodeType.SERVICE_TEMPLATE,
                ],
            )
            nodes = serializers.ListField(required=True, label="节点列表")

            def validate_bk_biz_id(self, value):
                return validate_bk_biz_id(value)

        subscription_id = serializers.IntegerField(required=True, label="采集配置订阅id")
        scope = ScopeParams(required=True, label="事件订阅监听的范围")
        steps = serializers.ListField(required=True, label="触发的动作")
        run_immediately = serializers.BooleanField(required=False, label="是否立即触发")


class DeleteSubscriptionResource(NodeManAPIGWResource):
    action = "subscription_delete/"
    method = "POST"

    class RequestSerializer(serializers.Serializer):
        subscription_id = serializers.IntegerField(required=True, label="采集配置订阅id")


class RunSubscriptionResource(NodeManAPIGWResource):
    action = "subscription_run/"
    method = "POST"

    class RequestSerializer(serializers.Serializer):
        class ScopeParams(serializers.Serializer):
            node_type = serializers.ChoiceField(required=True, label="采集对象类型", choices=["TOPO", "INSTANCE"])
            nodes = serializers.ListField(required=True, label="节点列表")

        subscription_id = serializers.IntegerField(required=True, label="采集配置订阅id")
        scope = ScopeParams(required=False, label="事件订阅监听的范围")
        actions = serializers.JSONField(required=False, label="触发的动作")


class RetrySubscriptionResource(NodeManAPIGWResource):
    action = "backend/api/subscription/retry/"
    method = "POST"

    class RequestSerializer(serializers.Serializer):
        subscription_id = serializers.IntegerField(required=True, label="采集配置订阅id")
        instance_id_list = serializers.ListField(required=False, label="实例id列表")


class RevokeSubscriptionResource(NodeManAPIGWResource):
    # 注意，此处由于节点管理1.3没有revoke接口，调用的是 节点管理2.0 的revoke接口
    # 因此 action 链接与其他接口的不一致，修改时请按照 节点管理2.0 esb yaml 中相应的接口链接进行调整
    action = "backend/api/subscription/revoke/"
    method = "POST"

    class RequestSerializer(serializers.Serializer):
        subscription_id = serializers.IntegerField(required=True, label="采集配置订阅id")
        instance_id_list = serializers.ListField(required=False, label="主机id列表")


class TaskResultResource(NodeManAPIGWResource):
    action = "subscription_task_result/"
    method = "POST"

    class RequestSerializer(serializers.Serializer):
        subscription_id = serializers.IntegerField(required=True, label="订阅配置id")
        task_id_list = serializers.ListField(required=False, label="任务id列表")
        need_detail = serializers.BooleanField(required=False, label="是否需要详细log")
        page = serializers.IntegerField(required=True, label="页数")
        pagesize = serializers.IntegerField(required=True, label="数量")


class SwitchSubscriptionResource(NodeManAPIGWResource):
    action = "subscription_switch/"
    method = "POST"

    class RequestSerializer(serializers.Serializer):
        subscription_id = serializers.IntegerField(required=True, label="采集配置订阅id")
        action = serializers.ChoiceField(required=True, choices=["enable", "disable"], label="启停选项")


class SubscriptionInstanceStatusResource(NodeManAPIGWResource):
    action = "subscription_instance_status/"
    method = "POST"

    class RequestSerializer(serializers.Serializer):
        subscription_id_list = serializers.ListField(required=True, label="采集配置订阅id列表")
        show_task_detail = serializers.BooleanField(default=False, label="是否展示实例最后一次下发情况")

    def validate_response_data(self, response_data):
        for item in response_data:
            for instance in item.get("instances"):
                adapter_nodeman_bk_cloud_id(instance)
        return response_data


class TaskResultDetailResource(NodeManAPIGWResource):
    action = "subscription_task_result_detail/"
    method = "POST"

    class RequestSerializer(serializers.Serializer):
        subscription_id = serializers.IntegerField(required=True, label="订阅配置id")
        instance_id = serializers.CharField(required=True, label="实例id")
        task_id = serializers.IntegerField(required=False, label="任务id")


class GetProcessInfoResource(NodeManAPIGWResource):
    """
    【节点管理1.3】根据插件名获取插件信息
    """

    action = "process/{process_name}/"
    method = "GET"

    class RequestSerializer(serializers.Serializer):
        process_name = serializers.CharField(required=True, label="插件名")


class GetPackageInfoResource(NodeManAPIGWResource):
    """
    【节点管理1.3】根据插件名获取插件包信息
    """

    action = "{process_name}/package/"
    method = "GET"

    class RequestSerializer(serializers.Serializer):
        process_name = serializers.CharField(required=True, label="插件名")


class GetControlInfoResource(NodeManAPIGWResource):
    """
    【节点管理1.3】根据插件名获取插件安装信息
    """

    action = "process_info/{process_name}/"
    method = "GET"

    class RequestSerializer(serializers.Serializer):
        process_name = serializers.CharField(required=True, label="插件名")
        plugin_package_id = serializers.IntegerField(required=True, label="插件包ID")


class TasksResource(NodeManAPIGWResource):
    """
    【节点管理1.3】下发任务
    """

    action = "{bk_biz_id}/tasks"
    method = "POST"

    class RequestSerializer(serializers.Serializer):
        class GlobalParams(serializers.Serializer):
            option = serializers.JSONField(required=True, label="更新选项")
            upgrade_type = serializers.CharField(required=True, label="更新类型")
            plugin = serializers.JSONField(required=True, label="插件信息")
            package = serializers.JSONField(required=True, label="插件包信息")
            control = serializers.JSONField(required=True, label="控制信息")

        creator = serializers.CharField(required=True, label="任务创建人")
        bk_biz_id = serializers.CharField(required=True, label="业务ID")
        bk_cloud_id = serializers.CharField(required=True, label="云区域ID")
        op_type = serializers.ChoiceField(required=True, label="操作类型", choices=("UPGRADE",))
        node_type = serializers.ChoiceField(required=True, label="节点类型", choices=("PLUGIN",))
        hosts = serializers.ListField(required=True, label="目标机器")
        global_params = GlobalParams(required=True, label="全局参数")


class GetProxiesResource(NodeManAPIGWResource):
    """
    【节点管理2.0】查询云区域下的proxy列表
    """

    action = "api/host/proxies/"
    method = "GET"

    class RequestSerializer(serializers.Serializer):
        bk_cloud_id = serializers.IntegerField(label="云区域ID", required=True)


class GetProxiesByBizResource(NodeManAPIGWResource):
    """
    【节点管理2.0】通过业务查询业务所使用的所有云区域下的ProxyIP
    """

    action = "api/host/biz_proxies/"
    method = "GET"

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(required=True, label="业务ID")

    def perform_request(self, params):
        params["_origin_user"] = get_global_user()
        setattr(self, "bk_username", settings.COMMON_USERNAME)
        return super(GetProxiesByBizResource, self).perform_request(params)


PLUGIN_JOB_TUPLE = (
    "MAIN_START_PLUGIN",
    "MAIN_STOP_PLUGIN",
    "MAIN_RESTART_PLUGIN",
    "MAIN_RELOAD_PLUGIN",
    "MAIN_DELEGATE_PLUGIN",
    "MAIN_UNDELEGATE_PLUGIN",
    "MAIN_INSTALL_PLUGIN",
)


class PluginOperate(NodeManAPIGWResource):
    """
    【节点管理2.0】插件管理接口
    """

    action = "api/plugin/operate/"
    method = "POST"

    class RequestSerializer(serializers.Serializer):
        class PluginInfoSerializer(serializers.Serializer):
            name = serializers.CharField(label="插件名称", required=True)
            version = serializers.CharField(label="插件版本", required=False, default="latest")
            keep_config = serializers.BooleanField(label="保留原有配置", required=False)
            no_restart = serializers.BooleanField(label="不重启进程", required=False)

        job_type = serializers.ChoiceField(label="任务类型", choices=PLUGIN_JOB_TUPLE)
        bk_biz_id = serializers.ListField(label="业务ID", required=False)
        bk_cloud_id = serializers.ListField(label="云区域ID", required=False)
        version = serializers.ListField(label="Agent版本", required=False)
        plugin_params = PluginInfoSerializer(label="插件信息", required=True)
        conditions = serializers.ListField(label="搜索条件", required=False)
        bk_host_id = serializers.ListField(label="主机ID", required=False)
        exclude_hosts = serializers.ListField(label="跨页全选排除主机", required=False)


class PluginSearch(NodeManAPIGWResource):
    """
    【节点管理2.0】插件查询接口
    """

    action = "api/plugin/search/"
    method = "POST"

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.ListField(label="业务ID", required=False)
        conditions = serializers.ListField(label="搜索条件", required=False)
        bk_host_id = serializers.ListField(label="主机ID", required=False)
        exclude_hosts = serializers.ListField(label="跨页全选排除主机", required=False)
        only_ip = serializers.ListField(label="只返回ip", required=False)
        detail = serializers.ListField(label="是否为详情", required=False)
        page = serializers.IntegerField(required=True, label="页数")
        pagesize = serializers.IntegerField(required=True, label="数量")

    def full_request_data(self, validated_request_data):
        # plugin search 在节点管理侧会针对请求用户鉴权，监控有自己的鉴权系统，此处直接使用后台账户进行查询
        setattr(self, "bk_username", get_backend_username())
        return super().full_request_data(validated_request_data)


def adapter_nodeman_bk_cloud_id(instance):
    bk_cloud_id_inst = instance["instance_info"]["host"]["bk_cloud_id"]
    if isinstance(bk_cloud_id_inst, list):
        bk_cloud_id_inst = bk_cloud_id_inst[0]["id"]
    instance["instance_info"]["host"]["bk_cloud_id"] = int(bk_cloud_id_inst)
    return instance


class CheckTaskReady(NodeManAPIGWResource):
    """
    检测任务是否初始化完成
    """

    action = "backend/api/subscription/check_task_ready/"
    method = "POST"

    class RequestSerializer(serializers.Serializer):
        subscription_id = serializers.IntegerField(required=True, label="订阅配置id")
        task_id_list = serializers.ListField(required=False, label="任务id列表")


class FetchSubscriptionStatistic(NodeManAPIGWResource):
    """
    获取统计信息
    """

    action = "backend/api/subscription/statistic/"
    method = "POST"

    class RequestSerializer(serializers.Serializer):
        subscription_id_list = serializers.ListField(required=True, label="订阅配置ID列表")
        plugin_name = serializers.CharField(required=False, label="插件名", default="bkmonitorbeat")


class BatchTaskResultResource(Resource):
    class RequestSerializer(serializers.Serializer):
        subscription_id = serializers.IntegerField(required=True, label="订阅配置id")
        task_id_list = serializers.ListField(required=False, label="任务id列表")
        need_detail = serializers.BooleanField(required=False, label="是否需要详细log")

    def perform_request(self, params):
        def get_data(result):
            if isinstance(result, list):
                return result
            return result.get("list") or []

        def get_count(result):
            if isinstance(result, list):
                return None
            return result.get("total")

        return batch_request(
            TaskResultResource().__call__,
            params,
            get_data=get_data,
            get_count=get_count,
            app="nodeman",
        )

    def validate_response_data(self, response_data):
        for instance in response_data:
            adapter_nodeman_bk_cloud_id(instance)
        return response_data
