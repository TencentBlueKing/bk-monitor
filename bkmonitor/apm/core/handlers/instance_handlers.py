# -*- coding: utf-8 -*-
import json
import logging

from django.conf import settings

from apm.constants import APM_TOPO_INSTANCE, DEFAULT_TOPO_INSTANCE_EXPIRE

logger = logging.getLogger("apm_topo")


class InstanceHandler:
    def __init__(self):
        self.redis_client = self.get_redis_client()

    @staticmethod
    def get_redis_client():
        from metadata.utils.redis_tools import RedisTools

        return RedisTools().client

    def get_cache_data(self, name: str) -> dict:
        """
        获取应用 topoinstance 缓存数据
        """
        json_res = self.redis_client.get(name)
        if json_res:
            return json.loads(json_res)
        return {}

    @staticmethod
    def get_topo_instance_cache_key(bk_biz_id, app_name):
        """
        组装 key 值
        """
        return APM_TOPO_INSTANCE.format(settings.PLATFORM, settings.ENVIRONMENT, bk_biz_id, app_name)

    def refresh_data(self, name: str, update_map: dict):
        """
        更新、删除数据
        """
        if not update_map:
            return

        # 连续7天无数据, key 过期
        self.redis_client.set(name, json.dumps(update_map), ex=DEFAULT_TOPO_INSTANCE_EXPIRE)
        logger.info(f"[InstanceDiscover] {name} update {len(update_map)}")

