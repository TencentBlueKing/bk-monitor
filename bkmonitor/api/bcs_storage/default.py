# -*- coding: utf-8 -*-
import abc
import copy
import logging
from urllib.parse import urljoin

import six
from django.conf import settings
from django.utils.translation import ugettext_lazy as _
from requests.exceptions import HTTPError, ReadTimeout
from rest_framework import serializers

from bkmonitor.utils.cache import CacheType
from core.drf_resource.contrib.api import APIResource
from core.errors.api import BKAPIError

logger = logging.getLogger("bcs_storage")


class BcsStorageBaseResource(six.with_metaclass(abc.ABCMeta, APIResource)):
    cache_type = CacheType.BCS
    module_name = "bcs-storage"

    # BCS目前是非蓝鲸标准的返回格式，所以需要兼容
    IS_STANDARD_FORMAT = False

    def get_request_url(self, validated_request_data):
        request_url = self.base_url.rstrip("/") + "/" + self.action.lstrip("/")
        # BCS_DEBUG_STORAGE_ADAPTER 需要设置为 False，而且不需要通过集群进行判断 debug 和 prod 环境
        if settings.BCS_DEBUG_STORAGE_ADAPTER:
            # 特殊处理上云环境下两套bcs storage自动适配，其他环境无此问题，BCS storage合并需后移除这三行兼容逻辑
            cluster_id = validated_request_data.get("cluster_id")
            if request_url.find("prod-bcs-api") > -1 and cluster_id.find("BCS-K8S-2") > -1:
                request_url = request_url.replace("prod-bcs-api", "debug-bcs-api")

        # 添加field选择字段
        field = validated_request_data.get("field")
        if field:
            request_url = f"{request_url}&field={field}"

        return request_url.format(**validated_request_data)

    def perform_request(self, validated_request_data):
        request_url = self.get_request_url(validated_request_data)
        headers = {"Authorization": f"Bearer {settings.BCS_API_GATEWAY_TOKEN}"}
        try:
            result = self.session.get(
                url=request_url,
                headers=headers,
                verify=False,
                timeout=self.TIMEOUT,
            )
        except ReadTimeout:
            raise BKAPIError(system_name=self.module_name, url=self.action, result=_("接口返回结果超时"))

        try:
            result.raise_for_status()
        except HTTPError as err:
            logger.exception("【模块：{}】请求APIGW错误：{}，请求url: {} ".format(self.module_name, err, request_url))
            raise BKAPIError(system_name=self.module_name, url=self.action, result=str(err.response.content))

        result_json = result.json()
        data = []
        for item in result_json.get("data", []):
            try:
                data.append(item.get("data", {}))
            except Exception as e:
                logger.error(e)
        return data


class FetchResource(BcsStorageBaseResource):
    cache_type = CacheType.BCS
    base_url = urljoin(
        f"{settings.BCS_API_GATEWAY_SCHEMA}://{settings.BCS_API_GATEWAY_HOST}:{settings.BCS_API_GATEWAY_PORT}",
        "/bcsapi/v4/storage/k8s/dynamic/all_resources/clusters",
    )
    action = "{cluster_id}/{type}?offset={offset}&limit={limit}"
    method = "GET"

    class RequestSerializer(serializers.Serializer):
        cluster_id = serializers.CharField(label="集群ID")
        type = serializers.CharField(label="资源类型")
        field = serializers.CharField(label="字段选择器", required=False, allow_null=True)

    def perform_request(self, validated_request_data):
        data = []
        offset = 0
        limit = settings.BCS_STORAGE_PAGE_SIZE
        while True:
            validated_request_data = copy.deepcopy(validated_request_data)
            validated_request_data["offset"] = offset
            validated_request_data["limit"] = limit
            data_per_page = super().perform_request(validated_request_data)
            data.extend(data_per_page)
            data_len = len(data_per_page)
            # 通过判断返回结果的数据判断是否需要获取下一页的数据
            if data_len == limit:
                offset += limit
                validated_request_data["offset"] = offset
                continue
            break

        return data
