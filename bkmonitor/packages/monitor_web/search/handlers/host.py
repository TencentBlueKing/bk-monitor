import time
import uuid

from django.conf import settings
from django.utils.translation import gettext as _

from api.cmdb.define import Host
from bkmonitor.utils.request import get_request_tenant_id
from core.drf_resource import api, resource
from monitor_web.search.handlers.base import (
    BaseSearchHandler,
    SearchResultItem,
    SearchScope,
)


class HostSearchHandler(BaseSearchHandler):
    SCENE = "host"
    SCENE_TYPE = "detail"
    SCENE_ID = "host"
    DASHBOARD_ID = "host"
    TOKEN_TYPE = "host"  # token鉴权类型

    def get_token_by_create(self, host: Host) -> str | None:
        start_time = int(time.time())
        token_create_params = {
            "bk_biz_id": host.bk_biz_id,
            "type": self.TOKEN_TYPE,
            "expire_time": start_time + 3600 * 24 * 7,
            "expire_period": "1w",
            "lock_search": False,
            "start_time": start_time,
            "end_time": start_time,
            "default_time_range": ["now-7d", "now"],
            "data": {
                "query": {
                    "filter-bk_target_cloud_id": str(host.bk_cloud_id),
                    "filter-bk_target_ip": host.ip,
                    "filter-bk_host_id": host.bk_host_id,
                    "method": "MAX",
                    "interval": "auto",
                    "groups": [],
                    "dashboardId": self.DASHBOARD_ID,
                    "from": "now-1h",
                    "to": "now",
                    "refleshInterval": "-1",
                    "key": uuid.uuid4().hex[:10],
                    "sceneId": self.SCENE_ID,
                    "sceneType": self.SCENE_TYPE,
                    "queryString": "",
                    "preciseFilter": "false",
                },
                "name": "performance-detail",
                "params": {"id": f"{host.ip}-{str(host.bk_cloud_id)}"},
                "path": f"/performance/detail/{host.ip}-{str(host.bk_cloud_id)}",
                "navList": [{"id": "", "name": host.ip}],
                "weWebData": {},
            },
        }
        return_datas = resource.share.create_share_token(token_create_params)
        enabled_token = return_datas.get("token") if int(time.time()) < return_datas.get("expire_time") else None
        return enabled_token

    def get_token_by_fetch(self, host: Host) -> str | None:
        token_fetch_params = {
            "bk_biz_id": host.bk_biz_id,
            "type": self.TOKEN_TYPE,
            "filter_params": {
                "bk_target_cloud_id": str(host.bk_cloud_id),
                "bk_target_ip": host.ip,
                "bk_host_id": host.bk_host_id,
            },
            "scene_params": {"sceneType": self.SCENE_TYPE, "sceneId": self.SCENE_ID, "dashboardId": self.DASHBOARD_ID},
        }
        share_token_list = resource.share.get_share_token_list(token_fetch_params)
        token = next(
            (
                item["token"]
                for item in share_token_list
                if item["status"] == "is_enabled" and int(time.time()) < item["expire_time"]
            ),
            None,
        )
        return token

    def get_enabled_token(self, host: Host) -> str | None:
        enabled_token = self.get_token_by_fetch(host)
        if enabled_token is None:
            enabled_token = self.get_token_by_create(host)
        return enabled_token

    def search(self, query: str, limit: int = 10) -> list[SearchResultItem]:
        params = {
            "bk_tenant_id": get_request_tenant_id(),
            # 使用CMDB搜索时，需要将 . 替换为 \. 否则会被识别为通配符
            "ip": query.replace(".", "\\.").replace("*", ".*"),
            "limit": 500,
        }

        if self.scope == SearchScope.BIZ:
            params["bk_biz_id"] = self.bk_biz_id

        hosts: Host = api.cmdb.get_host_without_biz(params)["hosts"]

        search_results = []

        for host in hosts:
            enabled_token = self.get_enabled_token(host)

            search_results.append(
                SearchResultItem(
                    bk_biz_id=host.bk_biz_id,
                    title=f"{host.bk_cloud_id}:{host.ip}",
                    view="performance-detail",
                    view_args={"params": {"id": f"{host.ip}-{host.bk_cloud_id}"}},
                    temp_share_url=f"{settings.BK_MONITOR_HOST}?bizId={host.bk_biz_id}/#/share/{enabled_token}"
                    if enabled_token
                    else None,
                )
            )

        search_results = self.collect_results_by_biz(
            search_results,
            limit=limit,
            collect_func=lambda bk_biz_id, items: SearchResultItem(
                bk_biz_id=bk_biz_id,
                title=_("搜索到 {count} 主机").format(count=len(items)),
                view="performance",
                view_args={"query": {"queryString": query}},
                is_collected=True,
            ),
        )

        # self.add_permission_for_results(results=search_results, action=ActionEnum.VIEW_HOST)

        return search_results
