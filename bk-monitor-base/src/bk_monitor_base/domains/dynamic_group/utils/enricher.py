# pyright: reportArgumentType=false
# pyright: reportOperatorIssue=false
# pyright: reportAttributeAccessIssue=false

"""
主机关联关系增强器

为通用模型实例添加关联的主机列表 (ip_list)。

核心功能：
1. 通过 CMDBInstRelate 查询实例与主机的关联关系
2. 通过 CMDBInstance 批量查询主机信息
3. 为每个实例构建 ip_list 字段
"""

import logging
from collections import defaultdict
from functools import reduce
from typing import Any, ClassVar

from bk_monitor_base.domains.cmdb_instance import search_all_inst_relations, search_all_instances

logger = logging.getLogger(__name__)


class HostRelationEnricher:
    """
    主机关联关系增强器

    为通用模型实例添加关联的主机列表 (ip_list)。

    Usage:
        >>> enricher = HostRelationEnricher(
        ...     bk_tenant_id="system",
        ...     bk_obj_id="bk_switch",
        ...     host_related_field="host_connect"
        ... )
        >>> enriched_list = enricher.enrich(inst_list, bk_biz_id=2)
        >>> # 返回: [{"bk_inst_id": 1, "ip_list": [{"bk_host_id": 101, ...}], ...}]
    """

    # 查询主机信息时需要的字段
    HOST_FIELDS: ClassVar[list[str]] = ["bk_host_id", "bk_cloud_id", "bk_host_innerip", "bk_agent_id", "bk_biz_id"]

    def __init__(self, bk_tenant_id: str, bk_obj_id: str, host_related_field: str):
        """
        初始化主机关联关系增强器

        :param bk_tenant_id: 租户ID
        :param bk_obj_id: CMDB 对象ID (如 "bk_switch")
        :param host_related_field: 主机关联字段名，用于构建 bk_obj_asst_id
        """
        self.bk_tenant_id: str = bk_tenant_id
        self.bk_obj_id: str = bk_obj_id
        self.host_related_field: str = host_related_field

    def enrich(
        self,
        inst_list: list[dict[str, Any]],
        bk_biz_id: int | None = None,
    ) -> list[dict[str, Any]]:
        """
        为实例列表添加关联的主机信息 (ip_list)

        :param inst_list: 实例列表，每个实例必须包含 bk_inst_id 字段
        :param bk_biz_id: 业务ID，可选。如果提供且非0，则只返回有关联主机的实例；
                         如果为0或不提供，则也返回无关联主机的实例（ip_list 为空）
        :return: 添加了 ip_list 字段的实例列表
        """
        if not inst_list:
            return []

        # 如果没有配置关联字段，所有实例的 ip_list 都为空
        if not self.host_related_field:
            return [{**inst, "ip_list": []} for inst in inst_list]

        # 1. 获取实例与主机的关联关系
        inst_ids = [inst["bk_inst_id"] for inst in inst_list]
        inst_host_mapping = self._fetch_inst_host_mapping(inst_ids)

        # 2. 批量查询主机信息
        if inst_host_mapping:
            all_host_ids = list(reduce(lambda x, y: x | y, [set(v) for v in inst_host_mapping.values()]))
            host_info_map = self._batch_get_host_info(all_host_ids)
        else:
            host_info_map = {}

        # 3. 构建返回结果
        return_data: list[dict[str, Any]] = []
        inst_id_set = set(inst_ids)

        for inst_id, host_ids in inst_host_mapping.items():
            if inst_id not in inst_id_set:
                continue

            # 找到原始实例数据
            original_inst = next((i for i in inst_list if i["bk_inst_id"] == inst_id), None)
            if not original_inst:
                continue

            ip_list = [host_info_map[hid] for hid in host_ids if hid in host_info_map]

            # 只添加有关联主机的实例（当 bk_biz_id 有值时）
            if ip_list:
                return_data.append({**original_inst, "ip_list": ip_list})

        # 4. 如果没有指定业务ID或业务ID为0，补充无关联实例
        if not bk_biz_id:
            matched_inst_ids = set(inst_host_mapping.keys())
            for inst in inst_list:
                if inst["bk_inst_id"] not in matched_inst_ids:
                    return_data.append({**inst, "ip_list": []})

        return return_data

    def _fetch_inst_host_mapping(self, inst_ids: list[int]) -> dict[int, list[int]]:
        """
        获取实例与主机的关联关系映射

        :param inst_ids: 实例ID列表
        :return: {inst_id: [host_id1, host_id2, ...]}
        """
        # 判断是正向关联还是反向关联
        # 反向关联: host_related_field 以 "host_" 开头，表示主机关联到实例
        # 正向关联: 实例关联到主机
        is_reverse = self.host_related_field.startswith("host_")

        # 构建查询条件：查询与主机 (bk_asst_obj_id=host) 的关联关系
        # bk_obj_asst_id 格式通常为: {bk_obj_id}_{asst_type}_{asst_obj_id}
        # 例如: bk_switch_connect_host 或 host_connect_bk_switch
        if is_reverse:
            # 反向关联：主机 -> 实例
            bk_obj_asst_id = f"host_{self.host_related_field[5:]}_{self.bk_obj_id}"
        else:
            # 正向关联：实例 -> 主机
            bk_obj_asst_id = f"{self.bk_obj_id}_{self.host_related_field}_host"

        try:
            relation_query: dict[str, Any] = {
                "bk_obj_asst_id": bk_obj_asst_id,
                "bk_tenant_id": self.bk_tenant_id,
            }
            if is_reverse:
                relation_query.update(
                    {
                        "bk_obj_id": "host",
                        "bk_asst_obj_id": self.bk_obj_id,
                        "bk_asst_inst_id": [str(inst_id) for inst_id in inst_ids],
                    }
                )
            else:
                relation_query.update(
                    {
                        "bk_obj_id": self.bk_obj_id,
                        "bk_asst_obj_id": "host",
                        "bk_inst_id": [str(inst_id) for inst_id in inst_ids],
                    }
                )

            associations = search_all_inst_relations(
                query=relation_query,
                fields=["bk_inst_id", "bk_asst_inst_id", "bk_asst_obj_id", "bk_obj_id"],
                ignore_partial_error=True,
            )

            if not associations:
                logger.debug(f"No instance associations found for bk_obj_asst_id={bk_obj_asst_id}")
                return {}
        except Exception as e:
            logger.warning(f"Failed to search instance associations: {e}")
            return {}

        inst_host_mapping: dict[int, list[int]] = defaultdict(list)
        inst_id_set = {int(inst_id) for inst_id in inst_ids}
        for assoc_dict in associations:
            if is_reverse:
                host_id = assoc_dict.get("bk_inst_id")
                inst_id = assoc_dict.get("bk_asst_inst_id")
            else:
                inst_id = assoc_dict.get("bk_inst_id")
                host_id = assoc_dict.get("bk_asst_inst_id")

            try:
                parsed_inst_id = int(inst_id) if inst_id is not None else None
                parsed_host_id = int(host_id) if host_id is not None else None
            except (TypeError, ValueError):
                continue

            if parsed_inst_id is not None and parsed_host_id is not None and parsed_inst_id in inst_id_set:
                inst_host_mapping[parsed_inst_id].append(parsed_host_id)

        return dict(inst_host_mapping)

    def _batch_get_host_info(self, host_ids: list[int]) -> dict[int, dict[str, Any]]:
        """
        批量查询主机信息

        :param host_ids: 主机ID列表
        :return: {host_id: {"bk_host_id": ..., "ip": ..., "bk_cloud_id": ..., ...}}
        """
        if not host_ids:
            return {}

        host_info_map: dict[int, dict[str, Any]] = {}

        try:
            host_list = search_all_instances(
                bk_obj_id="host",
                bk_tenant_id=self.bk_tenant_id,
                query={"bk_host_id": host_ids},
                fields=[*self.HOST_FIELDS, "bk_inst_id", "error"],
                ignore_partial_error=True,
            )

            for host_dict in host_list:
                host_id = host_dict.get("bk_host_id")
                if host_id is not None:
                    host_info: dict[str, Any] = {
                        "bk_host_id": host_id,
                        "ip": host_dict.get("bk_host_innerip", ""),
                        "bk_cloud_id": host_dict.get("bk_cloud_id", 0),
                        "bk_agent_id": host_dict.get("bk_agent_id", ""),
                        "bk_biz_id": host_dict.get("bk_biz_id", 0),
                        "bk_inst_id": host_dict.get("bk_inst_id", host_id),
                        "bk_host_innerip": host_dict.get("bk_host_innerip", ""),
                        "error": bool(host_dict.get("error", True)),
                    }
                    host_info_map[host_id] = host_info

        except Exception as e:
            logger.warning(f"Failed to batch get host info: {e}")

        return host_info_map
