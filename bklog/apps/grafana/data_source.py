# -*- coding: utf-8 -*-
"""
Tencent is pleased to support the open source community by making BK-LOG 蓝鲸日志平台 available.
Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
BK-LOG 蓝鲸日志平台 is licensed under the MIT License.
License for BK-LOG 蓝鲸日志平台:
--------------------------------------------------------------------
Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated
documentation files (the "Software"), to deal in the Software without restriction, including without limitation
the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software,
and to permit persons to whom the Software is furnished to do so, subject to the following conditions:
The above copyright notice and this permission notice shall be included in all copies or substantial
portions of the Software.
THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT
LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN
NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY,
WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE
SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
We undertake not to change the open source license (MIT license) applicable to the current version of
the project delivered to anyone in the future.
"""
import json
from copy import deepcopy
from dataclasses import dataclass
from typing import Any, Dict, List, Union

from django.conf import settings

from apps.api import BkDataQueryApi
from apps.constants import ApiTokenAuthType
from apps.feature_toggle.handlers.toggle import FeatureToggleObject
from apps.feature_toggle.models import FeatureToggle
from apps.feature_toggle.plugins.constants import GRAFANA_CUSTOM_ES_DATASOURCE
from apps.log_commons.models import ApiAuthToken
from apps.log_esquery.esquery.client.QueryClient import QueryClient
from apps.log_esquery.esquery.client.QueryClientBkData import QueryClientBkData
from apps.log_esquery.esquery.client.QueryClientEs import QueryClientEs
from apps.log_esquery.esquery.client.QueryClientLog import QueryClientLog
from apps.log_search.constants import DEFAULT_TIME_FIELD
from apps.log_search.models import LogIndexSet, Scenario
from apps.utils.thread import MultiExecuteFunc
from bk_dataview.grafana.provisioning import Datasource
from bkm_space.utils import bk_biz_id_to_space_uid


@dataclass
class CustomIndexSetESDataSource:
    """可以转换成Grafana DataSource的索引集"""

    space_uid: str = ""
    index_set_id: int = 0
    index_set_name: str = ""
    time_field: str = DEFAULT_TIME_FIELD
    token: str = ""

    @classmethod
    def get_token(cls, space_uid: str):
        """获取token"""
        token_obj, __ = ApiAuthToken.objects.get_or_create(space_uid=space_uid, type=ApiTokenAuthType.GRAFANA.value)
        return token_obj.token

    @classmethod
    def list(cls, space_uid: str) -> List["CustomIndexSetESDataSource"]:
        """获取列表"""
        token = cls.get_token(space_uid=space_uid)
        index_sets: List["CustomIndexSetESDataSource"] = []
        index_set_objs = LogIndexSet.objects.filter(space_uid=space_uid).iterator()
        for index_set_obj in index_set_objs:
            indexes: List[Dict[str, Any]] = index_set_obj.indexes
            if not indexes:
                continue
            result_table_id = indexes[0].get("result_table_id", "")
            if not result_table_id:
                continue
            index_sets.append(
                cls(
                    space_uid=space_uid,
                    index_set_id=index_set_obj.index_set_id,
                    index_set_name=cls.generate_datasource_name(
                        scenario_id=index_set_obj.scenario_id, index_set_name=index_set_obj.index_set_name
                    ),
                    time_field=index_set_obj.time_field,
                    token=token,
                )
            )
        return index_sets

    @staticmethod
    def generate_datasource_name(scenario_id: str, index_set_name: str) -> str:
        """给数据源添加前缀"""
        prefix = {
            Scenario.BKDATA: "BK-Data-ES",
            Scenario.ES: "Third-Party-ES",
            Scenario.LOG: "BKLOG-ES",
        }.get(scenario_id, "BKLOG-ES")
        return f"{prefix}({index_set_name})"

    def to_datasource(self) -> Datasource:
        """索引 -> Grafana ES数据源"""
        json_data = {
            "timeField": self.time_field,
            # 因为监控的Grafana版本已经到10, 默认支持的ES版本是7.10+, 但是日志的Grafana是8, 兼容两边将自定义ES数据源的版本固定住7.10
            "esVersion": "7.10.0",
            "tlsSkipVerify": True,
            "httpHeaderName1": "X-BKLOG-SPACE-UID",
            "httpHeaderName2": "X-BKLOG-TOKEN",
        }
        return Datasource(
            name=self.index_set_name,
            database=str(self.index_set_id),
            access="proxy",
            type="elasticsearch",
            url=f"{settings.BK_IAM_RESOURCE_API_HOST}/grafana/custom_es_datasource",
            jsonData=json_data,
            secureJsonData={
                "httpHeaderValue1": self.space_uid,
                "httpHeaderValue2": self.token,
            },
        )

    @classmethod
    def list_datasource(cls, bk_biz_id: int) -> List[Datasource]:
        """Grafana ES数据源"""
        if not FeatureToggleObject.switch(name=GRAFANA_CUSTOM_ES_DATASOURCE, biz_id=bk_biz_id):
            return []
        space_uid = bk_biz_id_to_space_uid(bk_biz_id)
        return [i.to_datasource() for i in cls.list(space_uid=space_uid)]

    @classmethod
    def get_or_create_feature_config(cls) -> FeatureToggle:
        obj, __ = FeatureToggle.objects.get_or_create(
            name=GRAFANA_CUSTOM_ES_DATASOURCE,
            defaults={"status": "debug", "is_viewed": False, "feature_config": {}, "biz_id_white_list": [],
                      "biz_id_black_list": []},
        )
        return obj

    @classmethod
    def enable_biz(cls, bk_biz_id: int):
        """启用空间, 在特性开关里biz_id_white_list塞入业务"""
        feature_toggle_obj: FeatureToggle = cls.get_or_create_feature_config()
        feature_toggle_obj.biz_id_white_list.append(bk_biz_id)
        feature_toggle_obj.save()

    @classmethod
    def disable_space(cls, bk_biz_id: int):
        """禁用空间, 在特性开关里移除业务"""
        feature_toggle_obj: FeatureToggle = cls.get_or_create_feature_config()
        if bk_biz_id in feature_toggle_obj.biz_id_white_list:
            feature_toggle_obj.biz_id_white_list.remove(bk_biz_id)
            feature_toggle_obj.save()


class ESBodyAdapter:
    """该类用于兼容Grafana ES7的语法与日志检索的body查询语法"""

    def __init__(self, body: Dict[str, Any]):
        self.body = body

    @staticmethod
    def adapt_interval(body: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        data_histogram的时间间隔字段名为fixed_interval, 但是我们的接口是interval
        """
        new_dict = {}
        for k, v in body.items():
            if k == "date_histogram" and "fixed_interval" in v:
                v["interval"] = v.pop("fixed_interval")
            if isinstance(v, dict):
                new_dict[k] = ESBodyAdapter.adapt_interval(v)
            else:
                new_dict[k] = v
        return new_dict

    @staticmethod
    def adapt_aggs(body: Dict[str, Any] = None):
        """
        聚合的时候, order的字段名为_key, 但是我们的接口是_term
        """
        if isinstance(body, dict):
            for k, v in body.items():
                if k == "aggs":
                    for agg_key in v:
                        if (
                            "terms" in v[agg_key]
                            and "order" in v[agg_key]["terms"]
                            and "_key" in v[agg_key]["terms"]["order"]
                        ):
                            v[agg_key]["terms"]["order"] = {"_term": v[agg_key]["terms"]["order"]["_key"]}
                ESBodyAdapter.adapt_aggs(v)

    def adapt(self):
        """适配Grafana ES请求"""
        body = deepcopy(self.body)
        body = self.adapt_interval(body=body)
        self.adapt_aggs(body=body)
        return body


class CustomESDataSourceTemplate:
    """
    自定义ES数据源模板模板, 各个Scenario的数据源都继承这个模板
    """

    def __init__(self, index_set_id: int):
        self.index_set_id = index_set_id
        self.data: LogIndexSet = LogIndexSet.objects.filter(pk=index_set_id).first()
        self.scenario_id: str = self.data.scenario_id
        self.storage_cluster_id: int = self.data.storage_cluster_id
        self.index: str = self.get_index()

    def get_client(self) -> Union[QueryClientBkData, QueryClientLog, QueryClientEs]:
        return QueryClient(self.scenario_id, storage_cluster_id=self.storage_cluster_id).get_instance()

    def get_index(self):
        """构建查询的索引"""
        indexes = self.data.indexes
        if not indexes:
            return ""

        if self.scenario_id == Scenario.ES:
            return ",".join([index["result_table_id"] for index in indexes if index.get("result_table_id")])

        return ",".join(
            [
                "{result_table_id}_*".format(result_table_id=index["result_table_id"])
                for index in indexes
                if index.get("result_table_id")
            ]
        )

    @staticmethod
    def compatible_mapping(mapping: Dict[str, Any]) -> Dict[str, Any]:
        """
        兼容Grafana高版本只支持7.10+以上的情况, mapping结构需要调整
        """
        result = dict()
        for index, value in mapping.items():
            mapping_dict: dict = value.get("mappings", {})
            # 日志接口返回的mapping结构中有一层是索引名,
            if len(mapping_dict) == 1 and (list(mapping_dict.keys())[0] in index or "properties" not in mapping_dict):
                result[index] = {"mappings": list(mapping_dict.values())[0]}
                continue
            result[index] = value
        return result

    def mapping(self):
        """
        获取mapping
        """
        mapping = self._mapping()
        return self.compatible_mapping(mapping=mapping)

    def _mapping(self):
        """
        各个继承类如果需要自定义mapping, 重写这个方法
        """
        return self.get_client().mapping(index=self.index)

    def query(self, body: Dict[str, Any]):
        body = ESBodyAdapter(body=body).adapt()
        return self._query(body=body)

    def _query(self, body: Dict[str, Any]):
        """
        各个继承类如果需要自定义查询逻辑, 重写这个方法
        """
        return self.get_client().query(index=self.index, body=body)

    def msearch(self, sql_list: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """批量查询"""
        multi_execute_func = MultiExecuteFunc()
        for idx, body in enumerate(sql_list):
            # 奇数位为索引, 索引从外层透传
            if idx % 2 == 0:
                continue
            multi_execute_func.append(result_key=idx, func=self.query, params=body)
        result = multi_execute_func.run()
        # 按照顺序返回, 因为请求的列表是顺序的, 防止数据串位
        return [result[k] for k in sorted(result.keys())]


class LogCustomESDataSource(CustomESDataSourceTemplate):
    pass


class ESCustomESDataSource(CustomESDataSourceTemplate):
    """第三方ES数据源"""

    pass


class BkDataCustomESDataSource(CustomESDataSourceTemplate):
    def __init__(self, index_set_id: int):
        super().__init__(index_set_id=index_set_id)

    def query_bkdata(self, body: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        """
        封装查询bkdata
        查询的时候传body, 不传body为获取mapping
        """
        sql = {"index": self.index}
        if body:
            sql["body"] = body
        else:
            sql["mapping"] = True
        params = {
            "prefer_storage": "es",
            "sql": json.dumps(sql),
            "no_request": True,
        }
        if settings.FEATURE_TOGGLE.get("bkdata_token_auth", "off") == "on":
            params.update({"bkdata_authentication_method": "token", "bkdata_data_token": settings.BKDATA_DATA_TOKEN})
        else:
            params.update({"bkdata_authentication_method": "user", "bk_username": "admin", "operator": "admin"})
        return BkDataQueryApi.query(params, request_cookies=False)["list"]

    def _query(self, body: Dict[str, Any]):
        return self.query_bkdata(body=body)

    def _mapping(self):
        return self.query_bkdata()


class CustomESDataSourceHandler:
    """自定义es数据源"""

    def __init__(self, index_set_id: int = None, sql_list: List[Dict[str, Any]] = None):
        self.index_set_id = index_set_id
        self.sql_list = sql_list or []
        # 没传index_set_id时, 从sql_list里获取
        if not self.index_set_id and self.sql_list:
            self.index_set_id = int(self.sql_list[0]["index"])
        self.data: LogIndexSet = LogIndexSet.objects.filter(pk=self.index_set_id).first()
        self.scenario_id: str = self.data.scenario_id
        self.storage_cluster_id: int = self.data.storage_cluster_id

    def get_instance(self) -> Union[LogCustomESDataSource, ESCustomESDataSource, BkDataCustomESDataSource]:
        """获取处理实例"""
        return {
            Scenario.LOG: LogCustomESDataSource,
            Scenario.ES: ESCustomESDataSource,
            Scenario.BKDATA: BkDataCustomESDataSource,
        }.get(self.scenario_id, LogCustomESDataSource)(index_set_id=self.index_set_id)

    def mapping(self):
        return self.get_instance().mapping()

    def query(self, body: Dict[str, Any]):
        return self.get_instance().query(body=body)

    def msearch(self) -> List[Dict[str, Any]]:
        return self.get_instance().msearch(sql_list=self.sql_list)
