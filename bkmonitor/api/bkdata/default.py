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

from bkmonitor.utils.cache import CacheType
from bkmonitor.utils.request import get_request
from constants.dataflow import AutoOffsetResets
from core.drf_resource import APIResource


class UseSaaSAuthInfoMixin:

    """
    计算平台当前是按 AppCode 分配 data token，考虑到监控在企业版二进制部署模式下后台和 Web AppCode 独立
    当前情况下依赖 BKDATA_DATA_TOKEN 的接口都使用 SaaS 侧应用认证信息进行请求
    Q：后台如何获取 SaaS 侧应用认证信息
    A：packages/monitor_web/apps.py ready 时由 web 进程写入 GlobalSettings，为通用逻辑
    """

    def full_request_data(self, validated_request_data):
        validated_request_data = super(UseSaaSAuthInfoMixin, self).full_request_data(validated_request_data)
        validated_request_data.update(
            {
                "bk_app_code": settings.SAAS_APP_CODE,
                "bk_app_secret": settings.SAAS_SECRET_KEY,
            }
        )
        return validated_request_data

    def get_headers(self):
        headers = super(UseSaaSAuthInfoMixin, self).get_headers()
        headers["X-Bk-App-Code"] = settings.SAAS_APP_CODE
        headers["X-Bk-App-Secret"] = settings.SAAS_SECRET_KEY
        return headers


class BkDataAPIGWResource(six.with_metaclass(abc.ABCMeta, APIResource)):
    base_url_statement = None
    base_url = settings.BKDATA_API_BASE_URL or "%s/api/c/compapi/data/" % settings.BK_COMPONENT_API_URL

    # 模块名
    module_name = "bkdata"

    TIMEOUT = 5 * 60

    @property
    def label(self):
        return self.__doc__

    def get_request_url(self, validated_request_data):
        return super(BkDataAPIGWResource, self).get_request_url(validated_request_data).format(**validated_request_data)


class BkDataQueryAPIGWResource(BkDataAPIGWResource):
    base_url = settings.BKDATA_QUERY_API_BASE_URL or BkDataAPIGWResource.base_url


class ListResultTableResource(BkDataAPIGWResource):
    """
    查询监控结果表
    """

    action = "/v3/meta/result_tables/"
    method = "GET"
    backend_cache_type = CacheType.METADATA

    class RequestSerializer(serializers.Serializer):
        related = serializers.ListField(required=False, default=["fields", "storages"], label="查询条件")
        bk_biz_id = serializers.IntegerField(required=False, label="业务ID")
        genereage_type = serializers.CharField(required=False, default="user")
        page_size = serializers.IntegerField(required=False, default=5000, max_value=5000)

    def perform_request(self, params):
        # 分页拉取，当前接口为返回 total_count 因此同步翻页拉取
        result_table_list = []
        page = 1
        while True:
            params.update(
                {
                    "page": page,
                }
            )
            data = super().perform_request(params)
            result_table_list += data
            if len(data) < params["page_size"]:
                break
            page += 1
        return result_table_list


class GetResultTableResource(BkDataAPIGWResource):
    """
    查询指定结果表
    """

    action = "/v3/meta/result_tables/{result_table_id}"
    method = "GET"

    class RequestSerializer(serializers.Serializer):
        result_table_id = serializers.CharField(required=True, label="结果表名称")
        related = serializers.ListField(required=False, default=["fields", "storages"], label="查询条件")

    def get_request_url(self, validated_request_data):
        return (
            super(GetResultTableResource, self).get_request_url(validated_request_data).format(**validated_request_data)
        )


class QueryDataResource(UseSaaSAuthInfoMixin, BkDataQueryAPIGWResource):
    """
    查询数据
    """

    action = "/v3/queryengine/query_sync/"
    method = "POST"

    class RequestSerializer(serializers.Serializer):
        sql = serializers.CharField(required=True, label="查询SQL语句")
        prefer_storage = serializers.CharField(required=False, label="查询引擎")
        _user_request = serializers.BooleanField(required=False, label="是否指定使用 user 鉴权请求接口", default=False)

    def perform_request(self, params):
        if params.get("_user_request", False):
            params["bkdata_authentication_method"] = "user"
            self.bk_username = settings.COMMON_USERNAME
            params.pop("_user_request", None)
        else:
            if settings.BKDATA_DATA_TOKEN:
                params["bkdata_authentication_method"] = "token"
                params["bkdata_data_token"] = settings.BKDATA_DATA_TOKEN
            else:
                params["bkdata_authentication_method"] = "user"
                self.bk_username = settings.COMMON_USERNAME
                try:
                    params["_origin_user"] = get_request().user.username
                except Exception:
                    pass
        return super(QueryDataResource, self).perform_request(params)


class CommonRequestSerializer(serializers.Serializer):
    bkdata_authentication_method = serializers.CharField(default="user", label="鉴权模式，默认 user 即可")
    appenv = serializers.CharField(default="ieod", label="环境，默认 ieod 即可")


class DataAccessAPIResource(six.with_metaclass(abc.ABCMeta, BkDataAPIGWResource)):
    """
    重写BkDataAPIGWResource，对用户的处理
    """

    def perform_request(self, params):
        try:
            params["_origin_user"] = get_request().user.username
        except Exception:
            pass

        # 优先取参数里面的username(如需要使用特权帐号来请求接口的场景)
        if not params.get("bk_username"):
            self.bk_username = settings.BK_DATA_PROJECT_MAINTAINER
        return super(BkDataAPIGWResource, self).perform_request(params)


class GetAiopsEnvs(BkDataAPIGWResource):  # noqa
    """
    AIOPS环境变量
    """

    action = "/v3/aiops/envs/"
    method = "GET"


####################################
#          auth 模型相关接口         #
####################################
class AuthResultTable(BkDataAPIGWResource):
    """
    授权接口(管理员接口): 给项目加表权限
    """

    action = "/v3/auth/projects/{project_id}/data/add/"
    method = "POST"

    class RequestSerializer(CommonRequestSerializer):
        project_id = serializers.IntegerField(required=True, label="计算平台项目")
        object_id = serializers.CharField(required=True, label="结果表ID")
        bk_biz_id = serializers.IntegerField(required=True, label="业务ID")


class AuthTickets(BkDataAPIGWResource):
    """
    授权接口(需要以用户的身份来请求授权)
    """

    action = "/v3/auth/tickets/"
    method = "POST"

    class RequestSerializer(CommonRequestSerializer):
        class PermissionsSerializer(serializers.Serializer):
            class ScopeSerializer(serializers.Serializer):
                result_table_id = serializers.CharField(required=True, label="结果表ID")

            subject_id = serializers.CharField(required=True, label="对象ID")
            subject_name = serializers.CharField(required=True, label="对象名称")
            subject_class = serializers.CharField(required=True, label="对象类型")
            action = serializers.CharField(required=True, label="授权动作")
            object_class = serializers.CharField(required=True, label="目标类型")
            scope = ScopeSerializer(required=True, label="目标")

        ticket_type = serializers.CharField(required=True, label="凭证类型")
        permissions = serializers.ListField(required=True, child=PermissionsSerializer(), label="权限列表")
        reason = serializers.CharField(default="", label="授权原因")

    def perform_request(self, params):
        return super(BkDataAPIGWResource, self).perform_request(params)


class AuthProjectsDataCheck(DataAccessAPIResource):
    """
    检查项目是否有结果表权限
    """

    action = "/v3/auth/projects/{project_id}/data/check/"
    method = "POST"

    class RequestSerializer(CommonRequestSerializer):
        project_id = serializers.IntegerField(required=True, label="计算平台项目")
        result_table_id = serializers.CharField(required=True, label="结果表名称")
        action_id = serializers.CharField(default="result_table.query_data", label="动作方式")


####################################
#          aiops 模型相关接口        #
####################################
class GetModelReleaseInfo(DataAccessAPIResource):
    """
    获取模型发布信息
    """

    action = "/v3/aiops/models/{model_id}/release/"
    method = "GET"

    class RequestSerializer(CommonRequestSerializer):
        model_id = serializers.CharField(required=True, label="数据模型ID")
        project_id = serializers.IntegerField(required=True, label="计算平台项目")
        extra_filters = serializers.CharField(required=True, label="额外过滤条件(json字符串格式)")


class GetAiopsModelsList(DataAccessAPIResource):
    """
    获取aiops模型列表
    """

    action = "/v3/aiops/models/"
    method = "GET"

    class RequestSerializer(CommonRequestSerializer):
        project_id = serializers.IntegerField(required=True, label="计算平台项目")
        model_ids = serializers.ListField(required=False, label="模型ID列表")


class GetReleaseModelInfo(DataAccessAPIResource):  # noqa
    """
    获取模型发布信息
    """

    action = "/v3/aiops/releases/{model_release_id}/"
    method = "GET"

    class RequestSerializer(CommonRequestSerializer):
        model_release_id = serializers.IntegerField(required=True, label="模型的版本id")
        input_result_table = serializers.CharField(required=False, label="输入结果表ID")
        node_type = serializers.CharField(required=False, label="节点类型")


class GetServingResultTableInfo(DataAccessAPIResource):
    """
    应用模型结果表信息
    """

    action = "/v3/aiops/scene_service/application/processing/{result_table_id}/status/"
    method = "GET"

    class RequestSerializer(CommonRequestSerializer):
        result_table_id = serializers.CharField(required=True)


class ListSceneService(DataAccessAPIResource):
    """
    获取场景服务列表
    """

    action = "/v3/aiops/scene_service/scenes/"
    method = "GET"

    class RequestSerializer(CommonRequestSerializer):
        scene_name = serializers.CharField(label="场景名称", required=False)


class ListSceneServicePlans(DataAccessAPIResource):
    """
    获取场景服务方案列表
    """

    action = "/v3/aiops/scene_service/scenes/{scene_id}/plans/"
    method = "GET"

    class RequestSerializer(CommonRequestSerializer):
        scene_id = serializers.IntegerField(label="场景ID")
        detail = serializers.IntegerField(default=1, label="是否过滤未公开方案")


class GetSceneServicePlan(DataAccessAPIResource):
    """
    获取场景服务详情
    """

    action = "/v3/aiops/scene_service/plans/{plan_id}/"
    method = "GET"

    class RequestSerializer(CommonRequestSerializer):
        plan_id = serializers.IntegerField(label="方案ID")


class SampleSetFeedback(DataAccessAPIResource):
    """
    样本反馈
    """

    action = "/v3/aiops/scene_service/application/processing/{rt_id}/feedback/"
    method = "POST"

    class RequestSerializer(CommonRequestSerializer):
        rt_id = serializers.CharField(label="方案ID")
        feedback_data = serializers.ListField(label="反馈数据", child=serializers.DictField())


class QueryReleaseModelList(DataAccessAPIResource):
    """
    获取已发布的模型列表
    """

    action = "/v3/model/serving/models/"
    method = "GET"

    class RequestSerializer(CommonRequestSerializer):
        project_id = serializers.IntegerField(required=True, label="计算平台项目")
        scene_name = serializers.ChoiceField(
            default="custom", choices=["custom", "timeseries_anomaly_detect"], label="模型场景"
        )


class GetReleaseModelInfo(DataAccessAPIResource):  # noqa
    """
    获取模型详情信息
    """

    action = "/v3/model/releases/{model_release_id}/"
    method = "GET"

    class RequestSerializer(CommonRequestSerializer):
        model_release_id = serializers.IntegerField(required=True, label="发布模型ID")


class ApiServingExecute(UseSaaSAuthInfoMixin, DataAccessAPIResource):  # noqa
    """
    执行模型API Serving并获取算法执行结果
    """

    action = "/v3/aiops/serving/processing/{processing_id}/execute/"
    method = "POST"

    class RequestSerializer(CommonRequestSerializer):
        processing_id = serializers.CharField(required=True, label="数据处理ID")
        data = serializers.DictField(required=True, label="模型输入数据")
        config = serializers.DictField(required=True, label="模型执行参数")
        timeout = serializers.IntegerField(required=False, label="超时时间")

    def perform_request(self, params):
        params["bkdata_authentication_method"] = "token"
        params["bkdata_data_token"] = settings.BKDATA_DATA_TOKEN
        return super(ApiServingExecute, self).perform_request(params)


####################################
#          数据接入 相关接口          #
####################################
class DeployPlanRequestSerializer(CommonRequestSerializer):
    class AccessRawDataSerializer(serializers.Serializer):
        raw_data_name = serializers.CharField(required=True, label="数据源名称，数据英文标识")
        raw_data_alias = serializers.CharField(required=True, label="数据别名（中文名）")
        maintainer = serializers.CharField(required=True, label="数据维护者")
        data_source = serializers.CharField(required=True, label="数据接入方式")
        data_encoding = serializers.CharField(required=True, label="字符集编码")
        sensitivity = serializers.CharField(required=True, label="数据敏感度")
        description = serializers.CharField(required=False, label="数据源描述")
        tags = serializers.ListField(required=False, label="数据标签")
        data_source_tags = serializers.ListField(required=False, label="数据源标签")
        data_region = serializers.CharField(required=False, label="地区")
        preassigned_data_id = serializers.IntegerField(required=False, label="DataId(互认方式下适用)")

    class AccessConfInfoSerializer(serializers.Serializer):
        class CollectionModelSerializer(serializers.Serializer):
            collection_type = serializers.CharField(required=True, label="接入方式")
            start_at = serializers.IntegerField(default=1, label="开始接入时位置")
            period = serializers.CharField(required=True, label="采集周期")

        class ConfResourceSerializer(serializers.Serializer):
            class KafkaConfScopeSerializer(serializers.Serializer):
                master = serializers.CharField(required=True, label="kafka的broker地址")
                group = serializers.CharField(required=True, label="消费者组")
                topic = serializers.CharField(required=True, label="消费topic")
                tasks = serializers.CharField(required=True, label="最大并发度")
                use_sasl = serializers.BooleanField(required=True, label="是否加密")
                security_protocol = serializers.CharField(required=False, label="安全协议")
                sasl_mechanism = serializers.CharField(required=False, label="SASL机制")
                user = serializers.CharField(required=False, allow_blank=True, label="用户名")
                password = serializers.CharField(required=False, allow_blank=True, label="密码")

            type = serializers.CharField(required=True, label="数据源类型")
            # 这里的scope配置，固定只写了kafka的配置，如果有其他接入方式，需要增加对应的serializer
            scope = serializers.ListField(required=True, child=KafkaConfScopeSerializer(), label="接入对象")

        collection_model = CollectionModelSerializer(required=True, label="数据采集接入方式配置")
        resource = ConfResourceSerializer(required=True, label="接入对象资源")

    data_scenario = serializers.CharField(required=True, label="接入场景")
    data_scenario_id = serializers.CharField(required=False, label="接入场景ID")
    bk_biz_id = serializers.IntegerField(required=True, label="业务ID")
    access_raw_data = AccessRawDataSerializer(required=True, label="接入源数据信息")
    access_conf_info = AccessConfInfoSerializer(required=False, label="接入配置信息")
    description = serializers.CharField(required=False, allow_blank=True, label="接入数据备注")
    bk_username = serializers.CharField(required=False, allow_blank=True, label="用户名")


class AccessDeployPlan(DataAccessAPIResource):
    """
    提交接入部署计划(数据源接入)
    """

    action = "/v3/access/deploy_plan/"
    method = "POST"

    RequestSerializer = DeployPlanRequestSerializer


class UpdateDeployPlan(DataAccessAPIResource):
    """
    更新部署计划(数据源更新)
    """

    action = "/v3/access/deploy_plan/{raw_data_id}"
    method = "PUT"

    class RequestSerializer(DeployPlanRequestSerializer):
        raw_data_id = serializers.CharField(required=True, label="数据源ID")


class DatabusCleans(DataAccessAPIResource):
    """
    接入数据清洗
    """

    action = "/v3/databus/cleans/"
    method = "POST"

    class RequestSerializer(CommonRequestSerializer):
        class FieldSerializer(serializers.Serializer):
            field_name = serializers.CharField(required=True, label="字段英文标识")
            field_type = serializers.CharField(required=True, label="字段类型")
            field_alias = serializers.CharField(required=True, label="字段别名")
            is_dimension = serializers.BooleanField(required=True, label="是否为维度字段")
            field_index = serializers.IntegerField(required=True, label="字段顺序索引")

        raw_data_id = serializers.CharField(required=True, label="数据接入源ID")
        json_config = serializers.CharField(required=True, label="数据清洗配置，json格式")
        pe_config = serializers.CharField(default="", allow_blank=True, label="清洗规则的pe配置")
        bk_biz_id = serializers.IntegerField(required=True, label="业务ID")
        clean_config_name = serializers.CharField(required=True, label="清洗配置名称")
        result_table_name = serializers.CharField(required=True, label="清洗配置输出的结果表英文标识")
        result_table_name_alias = serializers.CharField(required=True, label="清洗配置输出的结果表别名")
        fields = serializers.ListField(required=True, child=FieldSerializer(), label="输出字段列表")
        description = serializers.CharField(default="", label="清洗配置描述信息")
        bk_username = serializers.CharField(required=False, allow_blank=True, label="用户名")
        result_table_id = serializers.CharField(required=False, allow_blank=True, label="结果表 ID")
        processing_id = serializers.CharField(required=False, allow_blank=True, label="数据处理 ID")


class GetDatabusCleans(DataAccessAPIResource):
    """
    获取数据清洗信息列表
    """

    action = "/v3/databus/cleans/"
    method = "GET"

    class RequestSerializer(CommonRequestSerializer):
        raw_data_id = serializers.CharField(required=True, label="数据接入源ID")
        bk_username = serializers.CharField(required=False, allow_blank=True, label="用户名")


class UpdateDatabusCleans(DataAccessAPIResource):
    """
    更新数据清洗
    """

    action = "/v3/databus/cleans/{processing_id}/"
    method = "PUT"

    class RequestSerializer(CommonRequestSerializer):
        class FieldSerializer(serializers.Serializer):
            field_name = serializers.CharField(required=True, label="字段英文标识")
            field_type = serializers.CharField(required=True, label="字段类型")
            field_alias = serializers.CharField(required=True, label="字段别名")
            is_dimension = serializers.BooleanField(required=True, label="是否为维度字段")
            field_index = serializers.IntegerField(required=True, label="字段顺序索引")

        processing_id = serializers.CharField(required=True, label="清洗配置ID")
        raw_data_id = serializers.CharField(required=True, label="数据接入源ID")
        json_config = serializers.CharField(required=True, label="数据清洗配置，json格式")
        pe_config = serializers.CharField(default="", allow_blank=True, label="清洗规则的pe配置")
        bk_biz_id = serializers.IntegerField(required=True, label="业务ID")
        clean_config_name = serializers.CharField(required=True, label="清洗配置名称")
        result_table_name = serializers.CharField(required=True, label="清洗配置输出的结果表英文标识")
        result_table_name_alias = serializers.CharField(required=True, label="清洗配置输出的结果表别名")
        fields = serializers.ListField(required=True, child=FieldSerializer(), label="输出字段列表")
        description = serializers.CharField(default="", label="清洗配置描述信息")
        bk_username = serializers.CharField(required=False, allow_blank=True, label="用户名")


class StartDatabusCleans(DataAccessAPIResource):
    """
    启动清洗配置
    """

    action = "/v3/databus/tasks/"
    method = "POST"

    class RequestSerializer(CommonRequestSerializer):
        result_table_id = serializers.CharField(required=True, label="清洗结果表名称")
        storages = serializers.ListField(default=["kafka"], label="分发任务的存储列表")
        bk_username = serializers.CharField(required=False, allow_blank=True, label="用户名")
        processing_id = serializers.CharField(required=False, allow_blank=True, label="数据处理 ID")


class StopDatabusCleans(DataAccessAPIResource):
    """
    停止清洗配置
    """

    action = "/v3/databus/tasks/{result_table_id}/"
    method = "DELETE"

    class RequestSerializer(CommonRequestSerializer):
        result_table_id = serializers.CharField(required=True, label="清洗结果表名称")
        storages = serializers.ListField(default=["kafka"], label="分发任务的存储列表")
        bk_username = serializers.CharField(required=False, allow_blank=True, label="用户名")


class CreateDataStorages(DataAccessAPIResource):
    """
    创建数据入库
    """

    action = "/v3/databus/data_storages/"
    method = "POST"

    class RequestSerializer(CommonRequestSerializer):
        class FieldSerializer(serializers.Serializer):
            physical_field = serializers.CharField(required=True, label="物理表字段")
            field_name = serializers.CharField(required=True, label="字段英文标识")
            field_type = serializers.CharField(required=True, label="字段类型")
            field_alias = serializers.CharField(required=True, label="字段别名")
            is_dimension = serializers.BooleanField(required=True, label="是否为维度字段")
            field_index = serializers.IntegerField(required=True, label="字段顺序索引")

        class ConfigSerializer(serializers.Serializer):
            schemaless = serializers.BooleanField(required=False, label="schemaless", default=False)

        raw_data_id = serializers.CharField(required=True, label="数据接入源ID")
        data_type = serializers.CharField(required=True, label="数据源类型")
        result_table_name = serializers.CharField(required=True, label="清洗配置输出的结果表英文标识")
        result_table_name_alias = serializers.CharField(required=True, label="清洗配置输出的结果表别名")
        fields = serializers.ListField(required=True, child=FieldSerializer(), label="输出字段列表")
        storage_type = serializers.CharField(required=True, label="存储类型")
        storage_cluster = serializers.CharField(required=True, label="存储集群")
        expires = serializers.CharField(required=True, label="过期时间")
        config = ConfigSerializer(required=False, label="config")


####################################
#          DataFlow 相关接口         #
####################################
class GetDataFlowList(DataAccessAPIResource):
    """
    获取DataFlow列表信息
    """

    action = "/v3/dataflow/flow/flows"
    method = "GET"

    class RequestSerializer(CommonRequestSerializer):
        project_id = serializers.IntegerField(required=True, label="计算平台的项目ID")


class GetDataFlow(DataAccessAPIResource):
    """
    获取DataFlow信息
    """

    action = "/v3/dataflow/flow/flows/{flow_id}"
    method = "GET"

    class RequestSerializer(CommonRequestSerializer):
        flow_id = serializers.IntegerField(required=True, label="DataFlow的ID")


class GetDataFlowGraph(DataAccessAPIResource):
    """
    获取DataFlow里的画布信息，即画布中的节点信息
    """

    action = "/v3/dataflow/flow/flows/{flow_id}/graph"
    method = "GET"

    class RequestSerializer(CommonRequestSerializer):
        flow_id = serializers.IntegerField(required=True, label="DataFlow的ID")


class CreateDataFlow(DataAccessAPIResource):
    """
    创建DataFlow
    """

    action = "/v3/dataflow/flow/flows/"
    method = "POST"

    class RequestSerializer(CommonRequestSerializer):
        project_id = serializers.IntegerField(required=True, label="计算平台的项目ID")
        flow_name = serializers.CharField(required=True, label="DataFlow名称")
        nodes = serializers.ListField(child=serializers.DictField(), required=False, allow_empty=True)


class AddDataFlowNode(DataAccessAPIResource):
    """
    添加DataFlow节点
    """

    action = "/v3/dataflow/flow/flows/{flow_id}/nodes/"
    method = "POST"

    class RequestSerializer(CommonRequestSerializer):
        class FromLinksSerializer(serializers.Serializer):
            class SourceSerializer(serializers.Serializer):
                node_id = serializers.IntegerField(required=True, label="上游节点ID")
                id = serializers.CharField(required=True, label="节点ID")
                arrow = serializers.CharField(required=True, label="连线箭头方向")

            class TargetSerializer(serializers.Serializer):
                id = serializers.CharField(required=True, label="节点ID")
                arrow = serializers.CharField(required=True, label="连线箭头方向")

            source = SourceSerializer(required=True, label="连线的上游节点信息")
            target = TargetSerializer(required=True, label="连线的下游节点信息")

        class ConfigSerializer(serializers.Serializer):
            from_result_table_ids = serializers.ListField(required=False, label="来源结果表list")
            name = serializers.CharField(required=True, label="节点名称")

            # for stream_source 实时数据源
            bk_biz_id = serializers.IntegerField(required=False, label="业务ID")
            result_table_id = serializers.CharField(required=False, label="输出结果表名称")

            # for realtime 实时计算节点
            # 重复字段
            # bk_biz_id = serializers.IntegerField(required=False, label="业务ID")
            table_name = serializers.CharField(required=False, label="输出表名(英文标识)")
            output_name = serializers.CharField(required=False, label="输出表名（中文名）")
            window_type = serializers.CharField(required=False, label="窗口类型")
            # window_time = serializers.IntegerField(required=False, label="窗口类型")
            waiting_time = serializers.IntegerField(required=False, label="等待时间")
            count_freq = serializers.IntegerField(required=False, label="统计频率")
            sql = serializers.CharField(required=False, label="统计sql语句")

            # for tspider 存储节点
            # 重复字段
            # bk_biz_id = serializers.IntegerField(required=False, label="业务ID")
            # result_table_id = serializers.CharField(required=False, label="输出结果表名称")
            expires = serializers.IntegerField(required=False, label="数据保存周期")
            indexed_fields = serializers.ListField(default=list, label="索引字段")
            cluster = serializers.CharField(required=False, label="存储集群")

            # for model flow
            model_id = serializers.CharField(required=False, label="数据模型ID")
            model_release_id = serializers.IntegerField(required=False, label="发布模型ID")
            serving_mode = serializers.CharField(required=False, label="serving_mode")
            model_extra_config = serializers.DictField(required=False, label="模型参数配置")
            schedule_config = serializers.DictField(required=False, label="模型调度配置")
            input_config = serializers.DictField(required=False, label="模型输入配置")
            output_config = serializers.DictField(required=False, label="模型输出配置")
            sample_feedback_config = serializers.DictField(required=False, label="sample_feedback_config")
            upgrade_config = serializers.DictField(required=False, label="upgrade_config")
            scene_name = serializers.CharField(required=False, label="场景信息")

            # for scene service
            window_info = serializers.DictField(required=False, label="窗口信息")
            inputs = serializers.ListField(required=False, label="输入配置")
            outputs = serializers.ListField(required=False, label="输出配置")
            dedicated_config = serializers.DictField(required=False, label="方案参数配置")

        class FrontendInfoSerializer(serializers.Serializer):
            x = serializers.IntegerField(default=0, label="DataFlow画布上显示的x轴坐标")
            y = serializers.IntegerField(default=0, label="DataFlow画布上显示的y轴坐标")

        flow_id = serializers.IntegerField(required=True, label="DataFlow的ID")
        from_links = serializers.ListField(required=True, child=FromLinksSerializer(), label="与上游节点的连线信息")
        node_type = serializers.CharField(required=True, label="节点类型")
        config = serializers.DictField(required=True, label="节点配置")
        frontend_info = FrontendInfoSerializer(required=True, label="DataFlow画布上的位置信息")


class UpdateDataFlowNode(DataAccessAPIResource):
    """
    更新DataFlow节点
    """

    action = "/v3/dataflow/flow/flows/{flow_id}/nodes/{node_id}"
    method = "PUT"

    class RequestSerializer(AddDataFlowNode.RequestSerializer):
        node_id = serializers.IntegerField(required=True, label="DataFlow的节点ID")


class StartDataFlow(DataAccessAPIResource):
    """
    启动DataFlow
    """

    action = "/v3/dataflow/flow/flows/{flow_id}/start/"
    method = "POST"

    class RequestSerializer(CommonRequestSerializer):
        flow_id = serializers.IntegerField(required=True, label="DataFlow的ID")
        consuming_mode = serializers.CharField(default="continue", label="数据处理模式")
        cluster_group = serializers.CharField(default="default", label="计算集群组")


class StopDataFlow(DataAccessAPIResource):
    """
    停止DataFlow
    """

    action = "/v3/dataflow/flow/flows/{flow_id}/stop/"
    method = "POST"

    class RequestSerializer(CommonRequestSerializer):
        flow_id = serializers.IntegerField(required=True, label="DataFlow的ID")


class RestartDataFlow(DataAccessAPIResource):
    """
    重启DataFlow
    """

    action = "/v3/dataflow/flow/flows/{flow_id}/restart/"
    method = "POST"

    class RequestSerializer(CommonRequestSerializer):
        flow_id = serializers.IntegerField(required=True, label="DataFlow的ID")
        consuming_mode = serializers.CharField(default="continue", label="数据处理模式")
        cluster_group = serializers.CharField(default="default", label="计算集群组")


class DeleteDataFlow(DataAccessAPIResource):
    """
    删除DataFlow
    """

    action = "/v3/dataflow/flow/flows/{flow_id}/"
    method = "DELETE"

    class RequestSerializer(CommonRequestSerializer):
        flow_id = serializers.IntegerField(required=True, label="DataFlow的ID")


class GetLatestDeployDataFlow(DataAccessAPIResource):
    """
    获取DataFlow的最近部署信息
    """

    action = "/v3/dataflow/flow/flows/{flow_id}/latest_deploy_data/"
    method = "GET"

    class RequestSerializer(CommonRequestSerializer):
        flow_id = serializers.IntegerField(required=True, label="DataFlow的ID")


################################################################
# 降精度相关 API
################################################################


class CreateDataHubForDownsample(DataAccessAPIResource):
    """数据接入"""

    action = "/v3/datahub/hubs/"
    method = "POST"

    class RequestSerializer(CommonRequestSerializer):
        class DataHubCommonParamsSerializer(serializers.Serializer):
            """公共配置，包含用户认证和鉴权"""

            bk_biz_id = serializers.IntegerField(label="业务 ID")
            maintainer = serializers.CharField(
                default=settings.BK_DATA_PROJECT_MAINTAINER, required=False, label="数据管理员"
            )
            bk_username = serializers.CharField(
                default=settings.BK_DATA_PROJECT_MAINTAINER, required=False, label="操作人"
            )

        class RawDataParamsSerializer(serializers.Serializer):
            """原始数据配置
            包含两个步骤，数据接入和数据清洗
            """

            class DataScenarioParamsSerializer(serializers.Serializer):
                """数据接入"""

                class DataScenarioConfigParamsSerializer(serializers.Serializer):
                    """数据接入配置参数"""

                    type = serializers.CharField(required=False, default="kafka", label="接入场景类型")
                    auto_offset_reset = serializers.ChoiceField(
                        required=False, choices=AutoOffsetResets, default=AutoOffsetResets[0], label="默认消费位置"
                    )
                    broker = serializers.CharField(label="Broker 地址")
                    group = serializers.CharField(label="消费组")
                    topic = serializers.CharField(label="Topic 名称")
                    tasks = serializers.IntegerField(label="消费任务个数（并行度）", default=1)
                    use_sasl = serializers.BooleanField(required=False, default=False, label="是否使用加密")
                    user = serializers.CharField(required=False, label="用户名", default="")
                    password = serializers.CharField(required=False, label="密码", default="")
                    sasl_mechanism = serializers.CharField(required=False, default="SCRAM-SHA-512", label="sasl 机制")
                    security_protocol = serializers.CharField(required=False, default="SASL_PLAINTEXT", label="协议")

                name = serializers.CharField(required=False, default="kafka", label="名称")
                config = DataScenarioConfigParamsSerializer(label="数据接入配置")

            # 允许使用默认名称
            raw_data_name = serializers.CharField(default="down_sample_data_source", label="数据源英文名称")
            raw_data_alias = serializers.CharField(default="降精度数据源", label="数据源英文名称")
            sensitivity = serializers.CharField(required=False, default="private", label="数据敏感度")
            data_encoding = serializers.CharField(required=False, default="UTF-8", label="数据编码")
            data_region = serializers.CharField(required=False, default="inland", label="数据所属区域")
            description = serializers.CharField(required=False, default="降精度数据接入", label="数据源描述")
            data_source_tags = serializers.ListField(required=False, default=["kafka"], label="数据来源标签")
            tags = serializers.ListField(required=False, default=[], label="数据标签")
            data_scenario = DataScenarioParamsSerializer(label="数据接入")

        common = DataHubCommonParamsSerializer(label="公共配置")
        raw_data = RawDataParamsSerializer(label="原始数据配置")
        clean = serializers.ListField(child=serializers.JSONField(label="模板配置"), label="数据清洗")
        storage = serializers.ListField(required=False, default=list, label="数据存储")


class CreateDataFlowForDownsample(DataAccessAPIResource):
    """创建将精度流程 DataFlow"""

    action = "/v3/dataflow/flow/flows/create/"
    method = "POST"

    class RequestSerializer(CommonRequestSerializer):
        project_id = serializers.IntegerField(label="计算平台的项目 ID")
        flow_name = serializers.CharField(label="Flow 名称")
        nodes = serializers.JSONField(label="模板配置")


class StartDataFlowForDownsample(DataAccessAPIResource):
    """启动 DataFlow"""

    action = "/v3/dataflow/flow/flows/{flow_id}/start/"
    method = "POST"

    class RequestSerializer(CommonRequestSerializer):
        class ResourceSetsSerializer(serializers.Serializer):
            # NOTE: 计算平台灰度值变动，默认设置为正式环境需要的值，暂不需要动态存储
            stream = serializers.CharField(default="default_inland_stream", label="实时计算资源")
            batch = serializers.CharField(default="default_inland_batch", label="离线计算资源")

        flow_id = serializers.IntegerField(label="DataFlow ID")
        consuming_mode = serializers.CharField(default="continue", label="数据处理模式")
        resource_sets = ResourceSetsSerializer(label="资源组信息")


class StopDataFlowForDownsample(DataAccessAPIResource):
    """停用 DataFlow"""

    action = "/v3/dataflow/flow/flows/{flow_id}/stop/"
    method = "POST"

    class RequestSerializer(CommonRequestSerializer):
        flow_id = serializers.IntegerField(label="DataFlow ID")


class DelDataFlowForDownsample(DataAccessAPIResource):
    """删除 DataFlow"""

    action = "/v3/dataflow/flow/flows/{fid}/"
    method = "DELETE"

    class RequestSerializer(CommonRequestSerializer):
        flow_id = serializers.IntegerField(label="DataFlow ID")


class GetFlowStatusForDownsample(DataAccessAPIResource):
    """获取任务状态"""

    action = "/v3/dataflow/flow/flows/{flow_id}/"
    method = "GET"

    class RequestSerializer(CommonRequestSerializer):
        flow_id = serializers.IntegerField(label="DataFlow ID")


class CreateDataHub(DataAccessAPIResource):
    """数据接入及存储"""

    action = "/v3/datahub/hubs/"
    method = "POST"

    class RequestSerializer(CommonRequestSerializer):
        class DataHubCommonParamsSerializer(serializers.Serializer):
            """公共配置，包含用户认证和鉴权"""

            bk_biz_id = serializers.IntegerField(label="业务 ID")
            maintainer = serializers.CharField(
                default=settings.BK_DATA_PROJECT_MAINTAINER, required=False, label="数据管理员"
            )
            bk_username = serializers.CharField(
                default=settings.BK_DATA_PROJECT_MAINTAINER, required=False, label="操作人"
            )
            data_scenario = serializers.CharField(default="custom", required=False, label="接入类型")

        class RawDataParamsSerializer(serializers.Serializer):
            """原始数据配置
            包含两个步骤，数据接入和数据清洗
            """

            # 允许使用默认名称
            raw_data_name = serializers.CharField(label="数据源英文名称")
            raw_data_alias = serializers.CharField(label="数据源中文名称")
            sensitivity = serializers.CharField(required=False, default="private", label="数据敏感度")
            data_encoding = serializers.CharField(required=False, default="UTF-8", label="数据编码")
            data_region = serializers.CharField(required=False, default="inland", label="数据所属区域")
            description = serializers.CharField(required=False, default="计算平台数据接入", label="数据源描述", allow_blank=True)
            data_source_tags = serializers.ListField(required=False, default=["kafka"], label="数据来源标签")
            tags = serializers.ListField(required=False, default=[], label="数据标签")
            data_scenario = serializers.JSONField(label="数据定义")

        common = DataHubCommonParamsSerializer(label="公共配置")
        raw_data = RawDataParamsSerializer(label="原始数据配置")
        clean = serializers.ListField(child=serializers.JSONField(label="模板配置"), label="数据清洗")
        storage = serializers.ListField(required=False, default=list, label="数据存储")


class GetKafkaInfo(DataAccessAPIResource):
    """查询计算平台使用的 kafka 信息"""

    action = "/v3/databus/bkmonitor/"
    method = "GET"

    class RequestSerializer(CommonRequestSerializer):
        tags = serializers.CharField(required=False, default="bkmonitor_outer", label="tag标识")


class QueryResourceList(DataAccessAPIResource):
    """获取资源管理系统集群信息"""

    action = "/v3/resourcecenter/clusters/query_digest/"
    method = "GET"


class CreateResourceSet(DataAccessAPIResource):
    """创建资源"""

    action = "/v3/resourcecenter/resource_sets/"
    method = "POST"


class UpdateResourceSet(DataAccessAPIResource):
    """更新资源"""

    action = "/v3/resourcecenter/resource_sets/{resource_set_id}/"
    method = "PATCH"


class GetResourceSet(DataAccessAPIResource):
    """获取资源详情"""

    action = "/v3/resourcecenter/resource_sets/{resource_set_id}/"
    method = "GET"
