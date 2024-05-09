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
from collections import OrderedDict
from typing import List

from django.core.cache import cache
from django.db.models import Q
from django.utils.translation import ugettext as _
from rest_framework import serializers
from rest_framework.exceptions import ValidationError

from bkmonitor.utils.request import get_request
from bkmonitor.utils.user import get_local_username, get_request_username
from core.drf_resource import Resource
from core.errors.bkmonitor.space import SpaceNotFound
from metadata.models import space
from metadata.models.space import constants, utils
from metadata.service.space_redis import (
    get_kihan_prom_field_list,
    get_space_config_from_redis,
)
from metadata.utils.redis_tools import RedisTools

logger = logging.getLogger("metadata")


class ListSpaceTypesResource(Resource):
    """查询空间类型"""

    def perform_request(self, request_data):
        return space.SpaceType.objects.list_all_space_types()


class SpaceSerializer(serializers.Serializer):
    space_uid = serializers.CharField(label="空间唯一标识", required=False, default="")
    space_type_id = serializers.CharField(label="空间类型", required=False, default="")
    space_id = serializers.CharField(label="空间 ID", required=False, default="")

    def validate(self, data: OrderedDict) -> OrderedDict:
        space_uid = data.pop("space_uid", None)
        # 当空间唯一标识存在，切空间类型和空间ID不存在时，拆分空间唯一标识为类型和ID
        if space_uid and not (data["space_type_id"] and data["space_id"]):
            data["space_type_id"], data["space_id"] = space.Space.objects.split_space_uid(space_uid)
        return data


class ListSpacesResource(Resource):
    """查询空间实例信息"""

    class RequestSerializer(SpaceSerializer):
        space_name = serializers.CharField(label="空间名称", required=False, default="")
        id = serializers.IntegerField(label="空间自增 ID", required=False, default=None)
        is_exact = serializers.BooleanField(label="是否精确查询", required=False, default=False)
        is_detail = serializers.BooleanField(label="是否返回更详细信息", required=False, default=False)
        page = serializers.IntegerField(label="页数", min_value=0, required=False, default=constants.DEFAULT_PAGE)
        page_size = serializers.IntegerField(
            label="每页的数量", max_value=1000, min_value=1, required=False, default=constants.DEFAULT_PAGE_SIZE
        )
        exclude_platform_space = serializers.BooleanField(label="过滤掉平台级的空间", required=False, default=True)
        include_resource_id = serializers.BooleanField(label="过滤掉平台级的空间", required=False, default=False)

    def perform_request(self, request_data):
        return utils.list_spaces(**request_data)


class GetSpaceDetailResource(Resource):
    """查询单个空间详情"""

    class RequestSerializer(SpaceSerializer):
        id = serializers.IntegerField(label="空间自增 ID", required=False, default=None)

        def validate(self, data: OrderedDict) -> OrderedDict:
            space_uid, space_type_id, space_id = data["space_uid"], data["space_type_id"], data["space_id"]
            if not (space_uid or (space_type_id and space_id) or data["id"]):
                raise ValidationError(_("参数[space_uid]、[space_type_id, space_id]和[id]不能同时为空"))
            # 如果space_uid和(space_type_id, space_id)同时存在，则以(space_type_id, space_id)为准
            data = super().validate(data)
            return data

    def perform_request(self, request_data):
        return utils.get_space_detail(**request_data)


class ResourceConfig(serializers.Serializer):
    resource_type = serializers.CharField(label="资源类型")
    resource_id = serializers.CharField(label="资源标识")


class CreateSpaceResource(Resource):
    """创建空间实例"""

    class RequestSerializer(SpaceSerializer):
        creator = serializers.CharField(label="创建者")
        space_name = serializers.CharField(label="空间中文名称")
        resources = serializers.ListField(label="关联的资源", required=False, default=[], child=ResourceConfig())
        space_code = serializers.CharField(label="空间编码", required=False, default="")

        def validate(self, data: OrderedDict) -> OrderedDict:
            """校验参数
            1. 校验 space_type_id 存在及是否允许绑定资源
            2. 如果资源存在，校验是否资源类型是否存在
            3. 校验空间类型下 space_id、name 唯一
            """
            # TODO: 校验放到后面还是在前面处理？
            data = super().validate(data)
            # 校验类型
            try:
                space_type = space.SpaceType.objects.get(type_id=data["space_type_id"])
            except space.SpaceType.DoesNotExist:
                raise ValidationError(_("空间类型:{}不存在").format(data["space_type_id"]))
            if data["resources"] and not space_type.allow_bind:
                raise ValidationError(_("当前空间类型不允许绑定资源"))

            # 校验绑定资源的类型存在
            resource_type_list = [r["resource_type"] for r in data["resources"]]
            filter_type_list = space.SpaceType.objects.filter(type_id__in=resource_type_list).values_list(
                "type_id", flat=True
            )
            diff = set(resource_type_list) - set(filter_type_list)
            if diff:
                raise ValidationError(_("资源类型:{}不存在").format(";".join(diff)))

            # 校验 space_id 和 space_name
            if space.Space.objects.filter(
                Q(space_type_id=data["space_type_id"], space_id=data["space_id"])
                | Q(space_type_id=data["space_type_id"], space_name=data["space_name"])
            ).exists():
                raise ValidationError(_("空间中文名称:{}或者 ID :{}已经存在").format(data["space_name"], data["space_id"]))

            return data

    def perform_request(self, request_data):
        space = utils.create_space(**request_data)

        # 空间信息刷新到 redis
        from metadata.task.tasks import (
            push_and_publish_space_router,
            push_space_to_redis,
        )

        push_space_to_redis.delay(space_type=space["space_type_id"], space_id=space["space_id"])
        push_and_publish_space_router.delay(space_type=space["space_type_id"], space_id=space["space_id"])

        return space


class UpdateSpaceResource(Resource):
    class RequestSerializer(SpaceSerializer):
        updater = serializers.CharField(label="更新者")
        space_name = serializers.CharField(label="空间中文名称", required=False, default="")
        space_code = serializers.CharField(label="空间编码", required=False, default="")
        resources = serializers.ListField(label="关联的资源", required=False, default=[], child=ResourceConfig())

        def validate(self, data: OrderedDict) -> OrderedDict:
            data = super().validate(data)
            # 校验空间存在
            if not space.Space.objects.filter(space_type_id=data["space_type_id"], space_id=data["space_id"]).exists():
                raise SpaceNotFound(space_type_id=data["space_type_id"], space_id=data["space_id"])
            # 校验名称唯一
            # 判断依据: 如果空间类型下，根据`名称`或`ID`能过滤到两条记录，则认为名称已经存在
            if data.get("space_name") and (
                space.Space.objects.filter(
                    Q(space_name=data["space_name"], space_type_id=data["space_type_id"])
                    | Q(space_id=data["space_id"], space_type_id=data["space_type_id"])
                ).count()
                == 2
            ):
                raise ValidationError(_("空间中文名称:{}已经存在").format(data["space_name"]))
            # 如果不需要绑定资源，则直接返回
            if not data["resources"]:
                return data
            # 校验绑定资源的类型存在
            resource_type_list = [r["resource_type"] for r in data["resources"]]
            filter_type_list = space.SpaceType.objects.filter(type_id__in=resource_type_list).values_list(
                "type_id", flat=True
            )
            diff = set(resource_type_list) - set(filter_type_list)
            if diff:
                raise ValidationError(_("资源类型:{}不存在").format(";".join(diff)))

            return data

    def perform_request(self, request_data):
        return utils.update_space(**request_data)


class MergeSpaceResource(Resource):
    class RequestSerializer(serializers.Serializer):
        src_space_type_id = serializers.CharField(label="源空间类型")
        src_space_id = serializers.CharField(label="源空间 ID", help_text="要合并的空间，合并后，源空间仅允许在空间管理处操作")
        dst_space_type_id = serializers.CharField(label="目的空间类型")
        dst_space_id = serializers.CharField(label="目的空间 ID", help_text="合并后的空间，合并后，当前空间会关联所属的资源及data id")

        def validate(self, data: OrderedDict) -> OrderedDict:
            # 校验空间必须存在，并且允许合并
            src_space_type_id, src_space_id, dst_space_type_id, dst_space_id = (
                data["src_space_type_id"],
                data["src_space_id"],
                data["dst_space_type_id"],
                data["dst_space_id"],
            )
            try:
                src_space = space.Space.objects.get(space_type_id=src_space_type_id, space_id=src_space_id)
            except space.Space.DoesNotExist:
                raise SpaceNotFound(space_type_id=src_space_type_id, space_id=src_space_id)
            if not src_space.allow_merge:
                raise ValidationError(_("类型:{}，空间:{}不能合并").format(src_space_type_id, src_space_id))
            # TODO: 如果关联的资源为顶级类型(如BKCC, BCS)，应该也不允许合并
            if not space.Space.objects.filter(space_type_id=dst_space_type_id, space_id=dst_space_id).exists():
                raise SpaceNotFound(space_type_id=dst_space_type_id, space_id=dst_space_id)

            return data

    def perform_request(self, request_data):
        return utils.merge_space(**request_data)


class DisableSpaceResource(Resource):
    """禁用空间"""

    class RequestSerializer(serializers.Serializer):
        spaces = serializers.ListField(label="空间信息", child=SpaceSerializer())

        def validate(self, data: OrderedDict) -> OrderedDict:
            filter_q = Q()
            for s in data["spaces"]:
                filter_q |= Q(space_type_id=s["space_type_id"], space_id=s["space_id"])
            if space.Space.objects.filter(filter_q).count() != len(data["spaces"]):
                raise ValidationError(_("部分空间不存在"))

            return data

    def perform_request(self, request_data):
        return utils.disable_space(request_data["spaces"])


class ListStickySpacesResource(Resource):
    """
    用户置顶空间列表
    """

    class RequestSerializer(serializers.Serializer):
        def validate(self, attrs):
            attrs["username"] = get_request_username() or get_local_username()
            return attrs

    def perform_request(self, validated_request_data):
        if not validated_request_data["username"]:
            return []

        record, _ = space.SpaceStickyInfo.objects.get_or_create(username=validated_request_data["username"])
        return record.space_uid_list


class StickSpaceResource(Resource):
    """
    用户置顶空间
    """

    class RequestSerializer(serializers.Serializer):
        space_uid = serializers.CharField(label="空间uid", default="")
        action = serializers.ChoiceField(label="置顶动作", choices=(("on", _("置顶")), ("off", _("取消置顶"))))

        def validate(self, attrs):
            attrs["username"] = get_request_username() or get_local_username()
            return attrs

        def validate_space_uid(self, value):
            space_type_id, space_id = space.Space.objects.split_space_uid(value)
            space.Space.objects.get(space_type_id=space_type_id, space_id=space_id)
            return value

    def perform_request(self, validated_request_data):
        record, _ = space.SpaceStickyInfo.objects.get_or_create(username=validated_request_data["username"])
        space_uid = validated_request_data["space_uid"]
        space_uid_set = set(record.space_uid_list)
        action = validated_request_data["action"]
        if action == "on":
            space_uid_set.add(space_uid)
        elif space_uid in space_uid_set:
            space_uid_set.remove(space_uid)
        record.space_uid_list = list(space_uid_set)
        record.save()
        return record.space_uid_list


class GetClustersBySpaceUidResource(Resource):
    """查询空间下的集群信息"""

    class RequestSerializer(SpaceSerializer):
        def validate(self, data: OrderedDict) -> OrderedDict:
            space_uid, space_type_id, space_id = data["space_uid"], data["space_type_id"], data["space_id"]
            if not (space_uid or (space_type_id and space_id) or data["id"]):
                raise ValidationError(_("参数[space_uid]、[space_type_id, space_id]和[id]不能同时为空"))
            # 如果space_uid和(space_type_id, space_id)同时存在，则以(space_type_id, space_id)为准
            data = super().validate(data)
            if data.get("space_type_id") != constants.SpaceTypes.BKCI.value:
                raise ValidationError("not support bcs type")
            return data

    def perform_request(self, request_data):
        request_data["resource_type"] = constants.SpaceTypes.BCS.value
        clusters = utils.get_dimension_values(**request_data)
        if not clusters:
            return []
        return [
            {
                "cluster_id": c["cluster_id"],
                "namespace_list": c["namespace"] or [],
                "cluster_type": c.get("cluster_type", ""),
            }
            for c in clusters
        ]


class RefreshMetricForKihan(Resource):
    """仅供 kihan 使用

    限制:
    - 限制 APP_CODE(APIGW 中校验认证和权限校验)
    - 访问频率 1/min
    - 指标上限，暂定最大值为 1000
    """

    SPACE_UID = "bkcc__555"
    TABLE_ID = "555_bkmonitor_time_series_539389.__default__"
    PROM_DOMAIN_KEY = "HTTP_X_PROM_DOMAIN"
    MAX_METRIC_COUNT = 1000
    # 这里仅针对 kihan，不需要严格的频率控制
    # 采用 cache 的 ttl 方式，使用计数的方式控制访问
    RATE_LIMIT_KEY = "bkcc__555:refresh_metric"
    RATE_LIMIT_TIMEOUT = 60

    def perform_request(self, request_data):
        self._check_rate_limit()
        # 获取已有的数据
        data = get_space_config_from_redis(self.SPACE_UID, self.TABLE_ID)
        # 因为仅是一段时间使用，domain 配置到 apigw，通过 header 传递
        request = get_request()
        kihan_prom_domain = request.META.get(self.PROM_DOMAIN_KEY)
        if not kihan_prom_domain:
            raise ValidationError("kihan prom domain is null")
        field_list = get_kihan_prom_field_list(kihan_prom_domain)
        # 组装数据
        data["field"] = list(set(data["field"]).union(field_list))

        # 校验指标数量
        self._check_metric_count(data["field"])

        # 刷新数据并发布
        RedisTools.hmset_to_redis(f"{constants.SPACE_REDIS_KEY}:{self.SPACE_UID}", {self.TABLE_ID: json.dumps(data)})
        RedisTools.publish(constants.SPACE_REDIS_KEY, [self.TABLE_ID])

    def _check_rate_limit(self):
        """检查访问频率"""
        if cache.get(self.RATE_LIMIT_KEY):
            raise ValidationError("request limit 1/min")
        # 记录超时配置
        cache.set(self.RATE_LIMIT_KEY, 1, self.RATE_LIMIT_TIMEOUT)

    def _check_metric_count(self, metric_list: List):
        # 当指标超过 `1000`, 不允许写入
        if len(metric_list) < self.MAX_METRIC_COUNT:
            return
        logger.error("metric count gt %s", self.MAX_METRIC_COUNT)
        raise ValidationError(f"metric count gt {self.MAX_METRIC_COUNT}")
