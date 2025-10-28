from django.conf import settings
from pypinyin import lazy_pinyin

from bkm_ipchooser import constants, types
from bkm_ipchooser.api import BkApi
from bkm_ipchooser.query import resource
from bkmonitor.utils.tenant import bk_biz_id_to_bk_tenant_id


class BaseHandler:
    @staticmethod
    def get_meta_data(bk_biz_id: int) -> types.MetaData:
        return {"scope_type": constants.ScopeType.BIZ.value, "scope_id": str(bk_biz_id), "bk_biz_id": bk_biz_id}

    @classmethod
    def format_hosts(cls, hosts: list[types.HostInfo], bk_biz_id: int) -> list[types.FormatHostInfo]:
        """
        格式化主机信息
        :param hosts: 尚未进行格式化处理的主机信息
        :return: 格式化后的主机列表
        """
        biz_id__info_map: dict[int, dict] = {
            biz_info["bk_biz_id"]: biz_info for biz_info in resource.ResourceQueryHelper.fetch_biz_list()
        }

        # TODO: 暂不支持 >1000
        resp = BkApi.search_cloud_area(
            {"bk_tenant_id": bk_biz_id_to_bk_tenant_id(bk_biz_id), "page": {"start": 0, "limit": 1000}}
        )

        if resp.get("info"):
            cloud_id__info_map: dict[int, dict] = {
                cloud_info["bk_cloud_id"]: cloud_info["bk_cloud_name"] for cloud_info in resp["info"]
            }
        else:
            # 默认存在直连区域
            cloud_id__info_map = {
                constants.DEFAULT_CLOUD: {
                    "bk_cloud_id": constants.DEFAULT_CLOUD,
                    "bk_cloud_name": constants.DEFAULT_CLOUD_NAME,
                }
            }

        formatted_hosts: list[types.HostInfo] = []
        for host in hosts:
            bk_cloud_id = host["bk_cloud_id"]

            # 补充展示字段display_name
            display_name = ""
            for field in settings.HOST_DISPLAY_FIELDS:
                if not host.get(field):
                    continue

                if field == "bk_host_innerip_v6":
                    value = host[field]
                else:
                    value = host[field]
                display_name = value
                break
            if not display_name:
                display_name = host["bk_host_innerip"] or host["bk_host_name"] or host["bk_host_innerip_v6"]

            formatted_hosts.append(
                {
                    "meta": BaseHandler.get_meta_data(bk_biz_id),
                    "host_id": host["bk_host_id"],
                    "ip": host["bk_host_innerip"],
                    "ipv6": host.get("bk_host_innerip_v6", ""),
                    "outer_ip": host.get("bk_host_outerip", ""),
                    "outer_ipv6": host.get("bk_host_outerip_v6", ""),
                    "cloud_id": host["bk_cloud_id"],
                    "cloud_vendor": host.get("bk_cloud_vendor", ""),
                    "agent_id": host.get("bk_agent_id", ""),
                    "host_name": host["bk_host_name"],
                    "os_name": host["bk_os_name"],
                    "os_type": host["bk_os_type"],
                    "alive": host.get("status"),
                    "cloud_area": {"id": bk_cloud_id, "name": cloud_id__info_map.get(bk_cloud_id, bk_cloud_id)},
                    "biz": {
                        "id": bk_biz_id,
                        "name": biz_id__info_map.get(bk_biz_id, {}).get("bk_biz_name", bk_biz_id),
                    },
                    # 暂不需要的字段，留作扩展
                    "bk_mem": host.get("bk_mem", ""),
                    "bk_disk": host.get("bk_disk", ""),
                    "bk_cpu": host.get("bk_cpu", ""),
                    "display_name": display_name,
                    "country": host.get("bk_state_name", ""),
                    "city": host.get("bk_province_name", ""),
                    "carrieroperator": host.get("bk_isp_name", ""),
                }
            )

        return formatted_hosts

    @classmethod
    def format_host_id_infos(cls, hosts: list[types.HostInfo], bk_biz_id: int) -> list[types.FormatHostInfo]:
        """
        格式化主机信息
        :param hosts: 尚未进行格式化处理的主机信息
        :return: 格式化后的主机列表
        """

        formatted_hosts: list[types.HostInfo] = []
        for host in hosts:
            formatted_hosts.append(
                {
                    "meta": BaseHandler.get_meta_data(bk_biz_id),
                    "host_id": host["bk_host_id"],
                    "ip": host["bk_host_innerip"],
                    "ipv6": host.get("bk_host_innerip_v6"),
                    "cloud_id": host["bk_cloud_id"],
                }
            )

        return formatted_hosts

    @classmethod
    def sort_by_name(cls, datas: list[dict]):
        # 按照名称排序
        # 用在 动态拓扑, 服务模板, 集群模板
        datas.sort(key=lambda g: lazy_pinyin(g["name"]))

    @classmethod
    def fill_meta(self, datas: list[dict], meta: dict):
        for data in datas:
            data["meta"] = meta
