# -*- coding: utf-8 -*-
import logging

from bkm_search_module import types
from bkm_search_module.api import BkApi
from bkm_search_module.models import SearchModuleUserConfig

logger = logging.getLogger("bkm_search_module")


class SearchModuleHandler:
    @staticmethod
    def list_index_set(scope_list: types.ScopeList):
        """索引集列表"""
        return BkApi.list_index_set(scope_list=scope_list)

    @staticmethod
    def search_condition(index_set_id: int):
        """获取查询条件"""
        return BkApi.search_condition(index_set_id=index_set_id)

    @staticmethod
    def search_condition_options(index_set_id: int, fields: list):
        """获取查询条件选项"""
        return BkApi.search_condition_options(index_set_id=index_set_id, fields=fields)

    @staticmethod
    def search_history(index_set_id: int):
        """获取查询历史"""
        return BkApi.search_history(index_set_id=index_set_id)

    @staticmethod
    def search_inspect(query_string: str):
        """检索语句语法检测"""
        return BkApi.search_inspect(query_string=query_string)

    @staticmethod
    def update_or_create_config(username: str, config: dict):
        """创建、更新用户配置"""
        SearchModuleUserConfig.objects.update_or_create(username=username, defaults={"config": config})
        return {"success": True}

    @staticmethod
    def retrieve_user_config(username: str):
        """获取用户配置"""
        obj = SearchModuleUserConfig.objects.filter(username=username).first()

        return {"config": obj.config} if obj else {"config": None}

    @staticmethod
    def search(index_set_id: int, params: dict):
        """日志检索"""
        return BkApi.search(index_set_id=index_set_id, params=params)

    @staticmethod
    def search_fields(index_set_id: int, params: dict):
        """字段配置"""
        return BkApi.search_fields(index_set_id=index_set_id, params=params)

    @staticmethod
    def create_fields_config(index_set_id: int, params: dict):
        """创建索引集表格配置"""
        return BkApi.create_fields_config(index_set_id=index_set_id, params=params)

    @staticmethod
    def update_fields_config(index_set_id: int, params: dict):
        """更新索引集表格配置"""
        return BkApi.update_fields_config(index_set_id=index_set_id, params=params)

    @staticmethod
    def list_fields_config(index_set_id: int):
        """获取索引集表格配置列表"""
        return BkApi.list_fields_config(index_set_id=index_set_id)

    @staticmethod
    def delete_fields_config(config_id: int):
        """删除索引集表格配置列表"""
        return BkApi.delete_fields_config(config_id=config_id)

    @staticmethod
    def save_user_config(index_set_id: int, config_id: int):
        """更新用户表格配置"""
        return BkApi.save_user_config(index_set_id=index_set_id, config_id=config_id)

    @staticmethod
    def context(index_set_id: int, params: dict):
        """上下文"""
        return BkApi.context(index_set_id=index_set_id, params=params)

    @staticmethod
    def tail_f(index_set_id: int, params: dict):
        """实时日志"""
        return BkApi.tail_f(index_set_id=index_set_id, params=params)

    @staticmethod
    def date_histogram(index_set_id: int, params: dict):
        """趋势柱状图"""
        return BkApi.date_histogram(index_set_id=index_set_id, params=params)

    @staticmethod
    def export(index_set_id: int, cache_key: str):
        """日志下载"""
        return BkApi.export(index_set_id=index_set_id, cache_key=cache_key)

    @staticmethod
    def download_url(index_set_id: int, params: dict):
        """获取日志下载连接"""
        return BkApi.download_url(index_set_id=index_set_id, params=params)
