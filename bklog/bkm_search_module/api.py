# -*- coding: utf-8 -*-
import abc

from django.conf import settings
from django.utils.module_loading import import_string

from bkm_search_module import types


class AbstractBkApi(metaclass=abc.ABCMeta):
    @staticmethod
    def list_index_set(scope_list: types.ScopeList):
        """索引集列表"""
        raise NotImplementedError

    @staticmethod
    def search_condition(index_set_id: int):
        """获取查询条件"""
        raise NotImplementedError

    @staticmethod
    def search_condition_options(index_set_id: int, fields: list):
        """获取查询条件选项"""
        raise NotImplementedError

    @staticmethod
    def search_history(index_set_id: int):
        """获取查询历史"""
        raise NotImplementedError

    @staticmethod
    def search_inspect(query_string: str):
        """检索语句语法检测"""
        raise NotImplementedError

    @staticmethod
    def search(index_set_id: int, params: dict):
        """日志检索"""
        raise NotImplementedError

    @staticmethod
    def search_fields(index_set_id: int, params: dict):
        """字段配置"""
        raise NotImplementedError

    @staticmethod
    def create_fields_config(index_set_id: int, params: dict):
        """创建索引集表格配置"""
        raise NotImplementedError

    @staticmethod
    def update_fields_config(index_set_id: int, params: dict):
        """更新索引集表格配置"""
        raise NotImplementedError

    @staticmethod
    def list_fields_config(index_set_id: int):
        """获取索引集表格配置列表"""
        raise NotImplementedError

    @staticmethod
    def delete_fields_config(config_id: int):
        """删除索引集表格配置列表"""
        raise NotImplementedError

    @staticmethod
    def save_user_config(index_set_id: int, config_id: int):
        """更新用户表格配置"""
        raise NotImplementedError

    @staticmethod
    def context(index_set_id: int, params: dict):
        """上下文"""
        raise NotImplementedError

    @staticmethod
    def tail_f(index_set_id: int, params: dict):
        """实时日志"""
        raise NotImplementedError

    @staticmethod
    def date_histogram(index_set_id: int, params: dict):
        """趋势柱状图"""
        raise NotImplementedError

    @staticmethod
    def export(index_set_id: int, cache_key: str):
        """日志下载"""
        raise NotImplementedError

    @staticmethod
    def download_url(index_set_id: int, params: dict):
        """获取日志下载连接"""
        raise NotImplementedError


class BkApiProxy:
    def __init__(self):
        self._api = None

    def __getattr__(self, action):
        if self._api is None:
            self.init_api()
        func = getattr(self._api, action)
        return func

    def init_api(self):
        api_class = getattr(settings, "BKM_SEARCH_MODULE_BKAPI_CLASS", "bkm_search_module.api.AbstractBkApi")
        self._api = import_string(api_class)


BkApi: AbstractBkApi = BkApiProxy()
