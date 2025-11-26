import copy
import json
import uuid
from io import BytesIO

from blueapps.conf import settings
from django.core.cache import cache
from django.utils import timezone

from apps.constants import UserOperationActionEnum, UserOperationTypeEnum
from apps.decorators import user_operation_record
from apps.feature_toggle.handlers.toggle import FeatureToggleObject
from apps.feature_toggle.plugins.constants import UNIFY_QUERY_SEARCH
from apps.log_search.constants import (
    DEFAULT_INDEX_SET_FIELDS_CONFIG_NAME,
    ExportStatus,
    ExportType,
    SearchScopeEnum,
)
from apps.log_search.exceptions import BaseSearchIndexSetException
from apps.log_search.handlers.index_set import (
    IndexSetFieldsConfigHandler,
    IndexSetHandler,
)
from apps.log_search.handlers.search.aggs_handlers import AggsViewAdapter
from apps.log_search.handlers.search.favorite_handlers import FavoriteHandler
from apps.log_search.handlers.search.search_handlers_esquery import SearchHandler
from apps.log_search.models import (
    AsyncTask,
    IndexSetFieldsConfig,
    LogIndexSet,
    UserIndexSetFieldsConfig,
)
from apps.log_search.utils import create_download_response
from apps.log_unifyquery.handler.base import UnifyQueryHandler
from apps.models import model_to_dict
from apps.utils.local import get_request_username
from bkm_search_module.api import AbstractBkApi
from bkm_search_module.constants import ScopeType
from bkm_space.utils import bk_biz_id_to_space_uid, space_uid_to_bk_biz_id


class BkApi(AbstractBkApi):
    @staticmethod
    def list_index_set(scope_list: list = None):
        """
        检索-索引集列表
        """
        if not scope_list:
            return []

        space_uid_list = list()
        for _scope in scope_list:
            if _scope["scopeType"] == ScopeType.SPACE.value:
                space_uid_list.append(_scope["scopeId"])
            else:
                space_uid_list.append(bk_biz_id_to_space_uid(_scope["scopeId"]))

        if not space_uid_list:
            return []

        res = list(
            LogIndexSet.objects.filter(space_uid__in=space_uid_list, is_active=True).values(
                "index_set_id", "index_set_name"
            )
        )

        return res

    @staticmethod
    def search_condition(index_set_id: int):
        """检索条件"""
        search_handler = SearchHandler(index_set_id=index_set_id, search_dict={})
        search_handler_result = search_handler.fields(scope="default")
        fields = search_handler_result.get("fields")
        res = [
            {"id": _field["field_name"], "name": _field["field_alias"]}
            for _field in fields
            if _field["field_name"] != "log"
        ]
        return res

    @staticmethod
    def search_condition_options(index_set_id: int, fields: list):
        """检索条件选项"""

        data = {"fields": fields}

        index_set_instance = LogIndexSet.objects.filter(index_set_id=index_set_id).first()
        space_uid = index_set_instance.space_uid

        space_uids = IndexSetHandler.get_all_related_space_uids(space_uid)

        if space_uids:
            paternal_space_uid = space_uids[0]
            paternal_bk_biz_id = space_uid_to_bk_biz_id(paternal_space_uid)
            data["bk_biz_id"] = paternal_bk_biz_id

        if FeatureToggleObject.switch(UNIFY_QUERY_SEARCH, data.get("bk_biz_id")):
            data["index_set_ids"] = [index_set_id]
            data.setdefault("agg_fields", data.pop("fields", []))
            terms_data = UnifyQueryHandler(data).terms()
        else:
            terms_data = AggsViewAdapter().terms(index_set_id=index_set_id, query_data=data)

        result = terms_data.get("aggs_items", {})
        res = dict()

        for _k, _v in result.items():
            _value_list = list()
            _id = 1
            for _value in _v:
                _value_list.append({"id": str(_id), "name": _value})
                _id += 1
            res[_k] = _value_list

        return res

    @staticmethod
    def search_history(index_set_id: int):
        """查询历史"""
        data = SearchHandler.search_history(index_set_id)

        res_data = [
            {
                "id": _data["id"],
                "start_time": _data["params"]["start_time"],
                "end_time": _data["params"]["end_time"],
                "query_string": _data["query_string"],
                "conditions": _data["params"]["addition"],
            }
            for _data in data
        ]

        return res_data

    @staticmethod
    def search_inspect(query_string: str):
        """检索语句语法检测"""

        data = FavoriteHandler().inspect(keyword=query_string)

        res_data = {
            "is_legal": data["is_legal"],
            "is_resolved": data["is_resolved"],
            "message": data["message"],
            "query_string": data["keyword"],
        }

        return res_data

    @staticmethod
    def search(index_set_id: int, params: dict):
        """日志检索"""
        addition = list()

        condition = params.get("condition", {})

        if condition:
            for _k, _v in condition.items():
                addition.append({"field": _k, "operator": "=", "value": str(_v)})

        search_dict = {
            "keyword": params.get("query_string"),
            "start_time": params.get("start_time"),
            "end_time": params.get("end_time"),
            "begin": params.get("begin"),
            "size": params.get("size"),
            "addition": addition,
        }

        result = SearchHandler(index_set_id=index_set_id, search_dict=search_dict).search()

        res_data = {
            "total": result.get("total", 0),
            "list": result.get("list", []),
            "origin_log_list": result.get("origin_log_list", []),
        }

        return res_data

    @staticmethod
    def search_fields(index_set_id: int, params: dict):
        """字段配置"""
        search_dict = {"start_time": params.get("start_time"), "end_time": params.get("end_time")}
        search_handler = SearchHandler(index_set_id=index_set_id, search_dict=search_dict)
        search_handler_result = search_handler.fields(scope="default")

        res_data = {
            "fields": search_handler_result["fields"],
            "time_field": search_handler_result["time_field"],
            "time_field_type": search_handler_result["time_field_type"],
            "time_field_unit": search_handler_result["time_field_unit"],
        }
        return res_data

    @staticmethod
    def create_fields_config(index_set_id: int, params: dict):
        """创建索引集表格配置"""
        SearchHandler(index_set_id, {}).verify_sort_list_item(params["sort_list"])
        data = IndexSetFieldsConfigHandler(index_set_id=index_set_id).create_or_update(
            name=params["name"], display_fields=params["display_fields"], sort_list=params["sort_list"]
        )
        return data

    @staticmethod
    def update_fields_config(index_set_id: int, params: dict):
        """更新索引集表格配置"""
        SearchHandler(index_set_id, {}).verify_sort_list_item(params["sort_list"])
        data = IndexSetFieldsConfigHandler(index_set_id=index_set_id, config_id=params["config_id"]).create_or_update(
            name=params["name"], display_fields=params["display_fields"], sort_list=params["sort_list"]
        )
        return data

    @staticmethod
    def list_fields_config(index_set_id: int):
        """获取索引集表格配置列表"""
        config_dict = dict()
        fields_config_objs = IndexSetFieldsConfig.objects.filter(index_set_id=index_set_id).all()
        for _obj in fields_config_objs:
            if _obj.scope not in config_dict:
                config_dict[_obj.scope] = list()
            config_dict[_obj.scope].append(model_to_dict(_obj))

        if SearchScopeEnum.SEARCH_CONTEXT.value not in config_dict:
            # 获取上下文配置
            search_handler_esquery = SearchHandler(index_set_id, {"start_time": "", "end_time": ""})
            fields = search_handler_esquery.fields(scope=SearchScopeEnum.SEARCH_CONTEXT.value)

            obj, __ = IndexSetFieldsConfig.objects.get_or_create(
                index_set_id=index_set_id,
                name=DEFAULT_INDEX_SET_FIELDS_CONFIG_NAME,
                scope=SearchScopeEnum.SEARCH_CONTEXT.value,
                defaults={"display_fields": fields["display_fields"], "sort_list": fields["sort_list"]},
            )

            config_dict[SearchScopeEnum.SEARCH_CONTEXT.value] = model_to_dict(obj)

        # 构建返回数据
        res_data = dict()
        for _k, _v in config_dict.items():
            _v.sort(key=lambda c: c["name"] == DEFAULT_INDEX_SET_FIELDS_CONFIG_NAME, reverse=True)
            if _k not in res_data:
                res_data[_k] = {"item": _v}

            # 获取config_id
            res_data[_k]["config_id"] = UserIndexSetFieldsConfig.get_config(
                index_set_id=index_set_id, username=get_request_username(), scope=_k
            ).id

        return res_data

    @staticmethod
    def delete_fields_config(config_id: int):
        """删除索引集表格配置列表"""
        IndexSetFieldsConfig.delete_config(config_id)

    @staticmethod
    def save_user_config(index_set_id: int, config_id: int):
        """保存用户索引集配置"""
        IndexSetHandler(index_set_id=index_set_id).config(config_id=config_id)
        return {"success": True}

    @staticmethod
    def context(index_set_id: int, params: dict):
        """上下文"""
        search_dict = {
            "begin": params["begin"],
            "size": params["size"],
            "zero": params["zero"],
            "serverIp": params["location"]["serverIp"],
            "path": params["location"]["path"],
            "gseIndex": params["location"]["gseIndex"],
            "iterationIndex": params["location"]["iterationIndex"],
            "search_type_tag": "context",
            "dtEventTimeStamp": params["location"]["dtEventTimeStamp"],
        }

        search_handler = SearchHandler(index_set_id=index_set_id, search_dict=search_dict)

        result = search_handler.search_context()

        return result

    @staticmethod
    def tail_f(index_set_id: int, params: dict):
        """实时日志"""
        search_dict = {
            "size": params["size"],
            "zero": params["zero"],
            "serverIp": params["location"]["serverIp"],
            "path": params["location"]["path"],
            "gseIndex": params["location"]["gseIndex"],
            "iterationIndex": params["location"]["iterationIndex"],
            "dtEventTimeStamp": params["location"]["dtEventTimeStamp"],
        }

        search_handler = SearchHandler(index_set_id=index_set_id, search_dict=search_dict)

        result = search_handler.search_tail_f()

        res_data = {"total": result.get("total"), "list": result.get("list")}

        return res_data

    @staticmethod
    def date_histogram(index_set_id: int, params: dict):
        """趋势柱状图"""
        query_data = {
            "keyword": params.get("query_string"),
            "start_time": params.get("start_time"),
            "end_time": params.get("end_time"),
            "begin": params.get("begin"),
            "size": params.get("size"),
            "addition": [] if not params.get("conditions") else [params.get("conditions")],
            "interval": params.get("interval"),
            "fields": [],
        }

        result = AggsViewAdapter().date_histogram(index_set_id=index_set_id, query_data=query_data)

        buckets = result.get("aggs", {}).get("group_by_histogram", {}).get("buckets", [])

        return buckets

    @staticmethod
    def export(index_set_id: int, cache_key: str):
        """日志下载"""
        search_dict = dict()

        cache_result = cache.get(cache_key)
        if cache_result:
            search_dict = json.loads(cache_result)

        request_data = copy.deepcopy(search_dict)

        tmp_index_obj = LogIndexSet.objects.filter(index_set_id=index_set_id).first()
        if tmp_index_obj:
            index_set_data_obj_list = tmp_index_obj.get_indexes(has_applied=True)
            if len(index_set_data_obj_list) > 0:
                index_list = [x.get("result_table_id", "unknow") for x in index_set_data_obj_list]
                index = "_".join(index_list).replace(".", "_")
            else:
                raise BaseSearchIndexSetException(BaseSearchIndexSetException.MESSAGE.format(index_set_id=index_set_id))
        else:
            raise BaseSearchIndexSetException(BaseSearchIndexSetException.MESSAGE.format(index_set_id=index_set_id))

        output = BytesIO()
        export_fields = search_dict.get("export_fields", [])
        search_handler = SearchHandler(
            index_set_id, search_dict=search_dict, export_fields=export_fields, export_log=True
        )
        result = search_handler.search()
        result_list = result.get("origin_log_list")
        for item in result_list:
            json_data = json.dumps(item, ensure_ascii=False).encode("utf8")
            output.write(json_data + b"\n")
        file_name = f"bk_log_search_{index}.log"
        response = create_download_response(output, file_name)
        AsyncTask.objects.create(
            request_param=request_data,
            scenario_id=search_dict["scenario_id"],
            index_set_id=index_set_id,
            result=True,
            completed_at=timezone.now(),
            export_status=ExportStatus.SUCCESS,
            start_time=search_dict["start_time"],
            end_time=search_dict["end_time"],
            export_type=ExportType.SYNC,
            bk_biz_id=None,
        )

        # add user_operation_record
        operation_record = {
            "username": get_request_username(),
            "space_uid": tmp_index_obj.space_uid,
            "record_type": UserOperationTypeEnum.EXPORT,
            "record_object_id": index_set_id,
            "action": UserOperationActionEnum.START,
            "params": request_data,
        }
        user_operation_record.delay(operation_record)

        return response

    @staticmethod
    def download_url(index_set_id: int, params: dict):
        """获取日志下载链接"""

        addition = list()

        condition = params.get("condition", {})

        if condition:
            for _k, _v in condition.items():
                addition.append({"field": _k, "operator": "=", "value": str(_v)})

        search_dict = {
            "keyword": params.get("query_string"),
            "start_time": params.get("start_time"),
            "end_time": params.get("end_time"),
            "begin": params.get("begin"),
            "size": params.get("size"),
            "addition": addition,
            "export_fields": params.get("export_fields", []),
        }
        # 设置请求参数缓存
        cache_key = str(uuid.uuid4())
        cache.set(cache_key, json.dumps(search_dict), 60)

        host = str(settings.BK_BKLOG_HOST)
        if host.endswith("/"):
            host = host[0:-1]

        return {"export_url": host + f"/api/v1/search_module/index_set/{index_set_id}/export/?cache_key={cache_key}"}
