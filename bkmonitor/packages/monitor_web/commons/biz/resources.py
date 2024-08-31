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
import json
import logging
import re
from typing import List

from django.conf import settings
from django.core.cache import caches
from django.utils.translation import ugettext as _

from bkm_space.api import SpaceApi
from bkm_space.define import SpaceFunction, SpaceTypeEnum
from bkmonitor.iam import ActionEnum, Permission, ResourceEnum
from bkmonitor.utils.cache import CacheType
from bkmonitor.utils.common_utils import safe_int
from bkmonitor.utils.request import get_request, get_request_username
from bkmonitor.utils.user import get_local_username
from bkmonitor.views import serializers
from core.drf_resource import CacheResource, api, resource
from core.drf_resource.base import Resource
from core.errors.api import BKAPIError
from monitor_web.commons.biz.func_control import CM

logger = logging.getLogger(__name__)


cache = caches["default"]
for cache_type in ["redis", "locmem"]:
    if cache_type in settings.CACHES:
        cache = caches[cache_type]
        break


class BusinessListOptionResource(Resource):
    class RequestSerializer(serializers.Serializer):
        show_all = serializers.BooleanField(required=False, default=False, allow_null=True)

    def perform_request(self, validated_request_data):
        if validated_request_data["show_all"]:
            # api.cmdb.define.Business
            biz_list = resource.commons.list_spaces(show_all=1)
        else:
            request = get_request()
            biz_list = resource.space.get_space_dict_by_user(request.user)

        select_options = [{"id": biz["bk_biz_id"], "text": biz["display_name"]} for biz in biz_list]
        select_options.sort(key=lambda b: safe_int(b["id"]))
        return select_options


class FetchBusinessInfoResource(Resource):
    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(required=False, default=0)
        space_uid = serializers.CharField(required=False, default="")

        def validate(self, attrs):
            if not attrs.get("space_uid", ""):
                return attrs
            space = SpaceApi.get_space_detail(attrs["space_uid"])
            attrs["bk_biz_id"] = space.bk_biz_id
            attrs["space"] = space
            return attrs

    def perform_request(self, params):
        """
        返回业务相关信息的接口
        """
        bk_biz_id = params["bk_biz_id"]
        bk_biz_name = ""
        maintainers = ""

        try:
            business = api.cmdb.get_business(bk_biz_ids=[bk_biz_id])
            if business:
                business = business[0]
                bk_biz_id = business.bk_biz_id
                bk_biz_name = business.bk_biz_name
                maintainers = business.bk_biz_maintainer
            else:
                bk_biz_id = ""
        except BKAPIError as e:
            bk_biz_id = ""
            logger.error(e)

        permission = Permission()
        if not bk_biz_id:
            access_url = permission.get_apply_url(action_ids=[ActionEnum.VIEW_BUSINESS])
        else:
            access_url = permission.get_apply_url(
                action_ids=[ActionEnum.VIEW_BUSINESS],
                resources=[ResourceEnum.BUSINESS.create_instance(bk_biz_id)],
            )
        space = params.get("space")
        if not space and bk_biz_id:
            space = SpaceApi.get_space_detail(bk_biz_id=bk_biz_id)
        space_info = space.__dict__ if space else {}

        return {
            "bk_biz_id": bk_biz_id,
            "bk_biz_name": bk_biz_name,
            "operator": maintainers,
            "get_access_url": access_url,
            # 如果用户在全局配置中添加了接入跳转链接，则使用用户的配置。如果没有，则使用默认的跳转链接
            "new_biz_apply": settings.DEMO_BIZ_APPLY
            if settings.DEMO_BIZ_APPLY
            else settings.DEFAULT_COMMUNITY_BIZ_APPLY,
            "space_type_id": space_info.get("space_type_id", ""),
            "space_uid": space_info.get("space_uid", ""),
            "space_code": space_info.get("space_code", ""),
        }


class ListSpacesResource(Resource):
    class RequestSerializer(serializers.Serializer):
        show_all = serializers.BooleanField(required=False, default=False, allow_null=True)
        show_detail = serializers.BooleanField(required=False, default=False, allow_null=True)

    @classmethod
    def get_space_by_user(cls, username, use_cache=True) -> List[dict]:
        perm_client = Permission(username)
        return perm_client.filter_space_list_by_action(ActionEnum.VIEW_BUSINESS, use_cache)

    def perform_request(self, validated_request_data) -> List[dict]:
        username = get_request_username()

        if validated_request_data["show_all"]:
            # 针对特定用户名屏蔽空间信息
            if settings.BLOCK_SPACE_RULE and re.search(settings.BLOCK_SPACE_RULE, username):
                spaces: List[dict] = self.get_space_by_user(username)
            else:
                spaces: List[dict] = SpaceApi.list_spaces_dict()
        else:
            spaces: List[dict] = self.get_space_by_user(username)

        if validated_request_data["show_detail"]:
            list(map(self.enrich_space_func, spaces))
        return spaces

    def enrich_space_func(self, space):
        # todo 使用运营数据判定是否接入
        func_requirment = (
            (
                SpaceFunction.APM.value,
                lambda s: True,
            ),
            (
                SpaceFunction.CUSTOM_REPORT.value,
                lambda s: True,
            ),
            (SpaceFunction.HOST_COLLECT.value, lambda s: s["space_type_id"] == SpaceTypeEnum.BKCC.value),
            (
                SpaceFunction.CONTAINER_COLLECT.value,
                lambda s: s["space_uid"] == SpaceTypeEnum.BKCI.value and s["space_code"],
            ),
            (SpaceFunction.HOST_PROCESS.value, lambda s: s["space_type_id"] == SpaceTypeEnum.BKCC.value),
            (SpaceFunction.UPTIMECHECK.value, lambda s: s["space_type_id"] == SpaceTypeEnum.BKCC.value),
            (
                SpaceFunction.K8S.value,
                lambda s: s["bk_biz_id"] > 0
                or bool(s["space_type_id"] == SpaceTypeEnum.BKCI.value and s["space_code"]),
            ),
            (SpaceFunction.CI_BUILDER.value, lambda s: s["space_type_id"] == SpaceTypeEnum.BKCI.value),
            (SpaceFunction.PAAS_APP.value, lambda s: s["space_type_id"] == SpaceTypeEnum.BKSAAS.value),
        )
        func_info = {}
        for func_name, validator in func_requirment:
            func_info[func_name] = int(validator(space))
        space["func_info"] = func_info


class ListStickySpacesResource(Resource):
    def perform_request(self, validated_request_data):
        return api.metadata.list_sticky_spaces(validated_request_data)


class StickSpaceResource(Resource):
    def perform_request(self, validated_request_data):
        return api.metadata.stick_space(validated_request_data)


class ListDevopsSpacesResource(Resource):
    """
    获取用户有权限的蓝盾空间项目
    """

    def perform_request(self, validated_request_data):
        # 过滤已同步的bcs项目空间
        devops_projects = api.devops.list_user_project(validated_request_data)
        if not devops_projects:
            return []
        # 过滤监控已接入蓝盾和bcs项目空间
        all_space_ids = [
            space["space_id"] for space in SpaceApi.list_spaces_dict() if space["space_type_id"] == SpaceTypeEnum.BKCI
        ]
        return [
            devops_project for devops_project in devops_projects if devops_project["project_code"] not in all_space_ids
        ]


class CreateSpaceResource(Resource):
    """
    创建空间
    """

    class RequestSerializer(serializers.Serializer):
        space_name = serializers.CharField(label="空间中文名称")
        space_type_id = serializers.CharField(label="空间类型", required=False, default="default")
        space_id = serializers.CharField(label="空间 ID（蓝盾为englishName)")
        space_code = serializers.CharField(label="空间编码", default="")

        description = serializers.CharField(label="空间描述", required=False, default="")
        project_type = serializers.IntegerField(label="项目类型", default=4, required=False, source="projectType")
        bg_id = serializers.CharField(label="BGid", required=False, source="bgId")
        center_id = serializers.CharField(label="中心id", required=False, source="centerId")
        dept_id = serializers.CharField(label="部门id", required=False, source="deptId")
        access_token = serializers.CharField(label="用户凭证", required=False)
        is_exist = serializers.BooleanField(label="是否为已有项目", default=False)

    def perform_request(self, validated_request_data):
        # 蓝盾空间关联创建
        if validated_request_data.get("space_type_id") == "bkci" and not validated_request_data["is_exist"]:
            api_params = {
                "projectName": validated_request_data["space_name"],
                "englishName": validated_request_data["space_id"],
                **validated_request_data,
            }
            result = api.devops.user_project_create(api_params)
            if not result:
                return result

        username = get_request_username() or get_local_username()
        validated_request_data["username"] = username
        space_info = api.metadata.create_space(validated_request_data)
        # 刷新全量空间列表
        SpaceApi.list_spaces(refresh=True)
        # 主动创建的空间都是负数，只有cmdb业务类型空间和cmdb业务id一致为正数
        bk_biz_id = -space_info["id"]
        # iam 授权
        try:
            permission = Permission()
            permission.grant_creator_action(
                ResourceEnum.BUSINESS.create_simple_instance(bk_biz_id),
                creator=username,
            )
        except Exception as e:  # pylint: disable=broad-except
            logger.exception("space->({}) grant creator action failed, reason: {}".format(space_info["id"], e))

        return space_info


class SpaceIntroduceResource(CacheResource):
    """
    生成功能接入指引
    """

    cache_type = CacheType.OVERVIEW

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(required=True)
        tag = serializers.CharField(required=False, allow_null=True)

    @staticmethod
    def get_introduce(tag, bk_biz_id):
        def performance():
            return {
                'is_no_data': not CM.get_controller(SpaceFunction.HOST_PROCESS.value, bk_biz_id).accessed,
                'is_no_source': not CM.get_controller(SpaceFunction.HOST_PROCESS.value, bk_biz_id).related,
                'data': {
                    'title': _('开启主机监控'),
                    'subTitle': _('默认录入到蓝鲸配置平台的主机，将会采集操作系统和进程相关的指标数据和事件数据，所以开启主机监控需要关联业务资源。'),
                    'introduce': [_('采集的指标丰富多达100个指标和8种系统事件'), _('可以按集群和模块拓扑进行数据的汇总'), _('提供默认的主机和事件策略')],
                    'buttons': [{'name': _('接入主机'), 'url': settings.AGENT_SETUP_URL}, {'name': 'DEMO', 'url': ''}],
                    'links': [
                        {'name': _('快速接入'), 'url': _('产品白皮书/scene-host/host_monitor.md')},
                        {'name': _('进程配置'), 'url': _('产品白皮书/scene-process/process_monitor_overview.md')},
                        {'name': _('操作系统指标'), 'url': _('产品白皮书/scene-host/host_metrics.md')},
                        {'name': _('进程指标'), 'url': _('产品白皮书/scene-process/process_metrics.md')},
                        {'name': _('操作系统事件'), 'url': _('产品白皮书/scene-host/host_events.md')},
                    ],
                },
            }

        def uptime_check():
            return {
                'is_no_data': not CM.get_controller(SpaceFunction.UPTIMECHECK.value, bk_biz_id).accessed,
                'is_no_source': not CM.get_controller(SpaceFunction.UPTIMECHECK.value, bk_biz_id).related,
                'data': {
                    'title': _('开启拨测'),
                    'subTitle': _('拨测是主动探测应用可用性的监控方式，通过拨测节点对目标进行周期性探测，通过可用性和响应时间来度量目标的状态。帮助业务主动发现问题和提升用户体验。'),
                    'introduce': [_('支持HTTP(s)、TCP、UDP、ICMP协议'), _('提供单点可用率、响应时长、期望响应码等指标'), _('提供节点TOP和地图等图表')],
                    'buttons': [{'name': _('新建拨测'), 'url': '#/uptime-check/task-add'}, {'name': 'DEMO', 'url': ''}],
                    'links': [
                        {'name': _('开启拨测'), 'url': _('产品白皮书/scene-synthetic/synthetic_monitor.md')},
                        {'name': _('拨测指标说明'), 'url': _('产品白皮书/scene-synthetic/synthetic_metrics.md')},
                        {'name': _('拨测策略说明'), 'url': _('产品白皮书/scene-synthetic/synthetic_default_rules.md')},
                    ],
                },
            }

        def apm_home():
            return {
                'is_no_data': not CM.get_controller(SpaceFunction.APM.value, bk_biz_id).accessed,
                'is_no_source': not CM.get_controller(SpaceFunction.APM.value, bk_biz_id).related,
                'data': {
                    'title': _('开启APM'),
                    'subTitle': _('APM即应用性能监控，通过Trace数据分析应用中各服务的运行情况，尤其是在微服务和云原生情况下非常依赖Trace数据的发现来解决接口级别的调用问题。'),
                    'introduce': [
                        _('通过应用拓扑图，可以了解服务之间调用的关系和出现问题的节点'),
                        _('通过调用次数、耗时、错误率等指标可以了解服务本身的运行状况'),
                        _('可以添加告警即时的发现问题'),
                    ],
                    'buttons': [{'name': _('新建应用'), 'url': '#/apm/application/add'}, {'name': 'DEMO', 'url': ''}],
                    'links': [
                        {'name': _('开启APM'), 'url': _('产品白皮书/scene-apm/apm_monitor_overview.md')},
                        {'name': _('APM指标说明'), 'url': _('产品白皮书/scene-apm/apm_metrics.md')},
                        {'name': _('APM策略说明'), 'url': _('产品白皮书/scene-apm/apm_default_rules.md')},
                    ],
                },
            }

        def k8s():
            return {
                'is_no_data': not CM.get_controller(SpaceFunction.K8S.value, bk_biz_id).accessed,
                'is_no_source': not CM.get_controller(SpaceFunction.K8S.value, bk_biz_id).related,
                'data': {
                    'title': _('开启Kubernetes监控'),
                    'subTitle': _(
                        '基于Kubernetes的云原生场景，提供了围绕云平台本身及上的应用数据监控解决方案。'
                        '兼容了Prometheus的使用并且解决了原本的一些短板问题。'
                        '开启容器监控需要将Kubernetes接入到蓝鲸容器管理平台中。'
                    ),
                    'introduce': [
                        _('提供开箱即用的K8s服务组件的各种监控视角'),
                        _('兼容serviceMonitor、podMonitor的使用'),
                        _('提供了Events、Log、Metrics的采集方案'),
                        _('提供远程服务注册的方式'),
                        _('提供本地拉取和均衡拉取的能力'),
                    ],
                    'buttons': [{'name': _('接入Kubernetes'), 'url': settings.BK_BCS_HOST}, {'name': 'DEMO', 'url': ''}],
                    'links': [
                        {'name': _('开启容器监控'), 'url': _('产品白皮书/scene-k8s/k8s_monitor_overview.md')},
                        {'name': _('容器指标说明'), 'url': _('产品白皮书/scene-k8s/k8s_metrics.md')},
                        {'name': _('k8s策略说明'), 'url': _('产品白皮书/scene-k8s/k8s_default_rules.md')},
                    ],
                },
            }

        def custom_scenes():
            return {
                'is_no_data': not CM.get_controller(SpaceFunction.CUSTOM_REPORT.value, bk_biz_id).accessed,
                'is_no_source': not CM.get_controller(SpaceFunction.CUSTOM_REPORT.value, bk_biz_id).related,
                'data': {
                    'title': _('自定义场景'),
                    'subTitle': _('自定义场景是除了平台自带的场景之外可以根据监控需求来自定义监控场景，平台提供了快速定义场景的能力，从数据源接入到数据可视化、关联功能联动都可以很快速的完成。'),
                    'introduce': [_('基于数据源提供默认的数据可视化'), _('支持快速进行数据查看和检验'), _('支持指标分组和标签配置'), _('支持变量过滤和数据分组')],
                    'buttons': [{'name': _('开始自定义'), 'url': '#/collect-config'}, {'name': 'DEMO', 'url': ''}],
                },
            }

        def collect_config():
            return {
                'is_no_data': not CM.get_controller(SpaceFunction.HOST_COLLECT.value, bk_biz_id).accessed,
                'is_no_source': not CM.get_controller(SpaceFunction.HOST_COLLECT.value, bk_biz_id).related,
                'data': {
                    'title': _('开始数据采集'),
                    'subTitle': _('数据采集是通过下发监控插件或配置来实现数据采集，并且提供插件和配置的全生命周期管理，所以依赖服务器安装bkmonitorbeat采集器。'),
                    'introduce': [_('结合插件提供本地和远程采集两种方式'), _('提供基于配置平台节点的动态扩缩容'), _('提供物理和容器环境的采集')],
                    'buttons': [{'name': _('新建数据采集'), 'url': '#/collect-config/add'}, {'name': 'DEMO', 'url': ''}],
                    'links': [
                        {'name': _('什么是指标和维度'), 'url': _('产品白皮书/integrations-metrics/what_metrics.md')},
                        {'name': _('开始指标数据采集'), 'url': _('产品白皮书/integrations-metrics/collect_tasks.md')},
                        {'name': _('插件制作快速入门'), 'url': _('产品白皮书/integrations-metric-plugins/plugins.md')},
                    ],
                },
            }

        tag_intro_key = "introduce:{}:{}".format(tag, bk_biz_id)
        func = {
            "performance": performance,
            "uptime-check": uptime_check,
            "apm-home": apm_home,
            "k8s": k8s,
            "custom-scenes": custom_scenes,
            "collect-config": collect_config,
            "plugin-manager": collect_config,
        }.get(tag, lambda: {})
        ret_from_cache = cache.get(tag_intro_key)
        if ret_from_cache:
            return json.loads(ret_from_cache)

        ret = func()
        if not ret["is_no_data"] and not ret["is_no_source"]:
            # 该业务对应场景已经在使用中， 持久化该结果
            cache.set(tag_intro_key, json.dumps(ret), None)
        return ret

    def perform_request(self, validated_request_data):
        bk_biz_id = validated_request_data["bk_biz_id"]
        tag = validated_request_data.get("tag")
        if tag:
            try:
                return self.get_introduce(tag, bk_biz_id)
            except BKAPIError as e:
                logger.exception("get biz({}) introduce error: {}".format(bk_biz_id, e))
                return {}
        else:
            tags = ['performance', 'uptime-check', 'apm-home', 'k8s', 'custom-scenes', 'collect-config']
            return {_tag: self.get_introduce(_tag, bk_biz_id) for _tag in tags}


class ListDataPipelineResource(Resource):
    def perform_request(self, validated_request_data):
        return api.metadata.list_data_pipeline(validated_request_data)


class ListDataSourceByDataPipelineResource(Resource):
    def perform_request(self, validated_request_data):
        return api.metadata.list_data_source_by_data_pipeline(validated_request_data)


class CreateDataPipelineResource(Resource):
    def perform_request(self, validated_request_data):
        return api.metadata.create_data_pipeline(validated_request_data)


class UpdateDataPipelineResource(Resource):
    def perform_request(self, validated_request_data):
        return api.metadata.update_data_pipeline(validated_request_data)


class GetClusterInfoResource(Resource):
    class RequestSerializer(serializers.Serializer):
        cluster_id = serializers.IntegerField(required=False, label="集群 ID", allow_null=True)
        cluster_type = serializers.CharField(required=False, label="集群类型", allow_null=True, allow_blank=True)

    def perform_request(self, validated_request_data):
        return api.metadata.get_storage_cluster_info(validated_request_data)


class GetEtlConfigResource(Resource):
    def perform_request(self, validated_request_data):
        return api.metadata.get_etl_config(validated_request_data)


class GetTransferListResource(Resource):
    def perform_request(self, validated_request_data):
        return api.metadata.get_transfer_list(validated_request_data)


class CheckClusterHealthResource(Resource):
    def perform_request(self, validated_request_data):
        return api.metadata.check_cluster_health(validated_request_data)


class ListClustersResource(Resource):
    def perform_request(self, validated_request_data):
        return api.metadata.list_clusters(validated_request_data)


class GetStorageClusterDetailResource(Resource):
    def perform_request(self, validated_request_data):
        return api.metadata.get_storage_cluster_detail(validated_request_data)


class RegisterClusterResource(Resource):
    def perform_request(self, validated_request_data):
        return api.metadata.register_cluster(validated_request_data)


class UpdateRegisteredClusterResource(Resource):
    def perform_request(self, validated_request_data):
        return api.metadata.update_registered_cluster(validated_request_data)
