# -*- coding: utf-8 -*-
"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""
import concurrent.futures

from django.conf import settings
from django.utils.translation import gettext as _

from core.drf_resource import api, resource


def fetch_panel_title_ids(bk_biz_id, dashboard_uid, org=None):
    """
    获取仪表盘的所有Panel信息
    :param bk_biz_id: 业务ID
    :param dashboard_uid: 仪表盘uid
    :param org: bk_biz_id对应 grafana 的 org 信息（如果提供，将不再查询api.grafana.get_organization_by_name
    :return: [{
        "title": panel["title"],
        "id": panel["id"]
    }]
    """
    if bk_biz_id == "-1":
        bk_biz_id = settings.MAIL_REPORT_BIZ
    if org is None:
        org = api.grafana.get_organization_by_name(name=str(bk_biz_id))
    if org.get("data") and org["data"].get("id"):
        org_id = org["data"]["id"]
        dashboard_config = api.grafana.get_dashboard_by_uid(uid=dashboard_uid, org_id=int(org_id))
        if not dashboard_config.get("data"):
            return []

        panel_id_title = []
        panel_queue = dashboard_config["data"].get("dashboard", {}).get("panels", []).copy()
        while panel_queue:
            panel = panel_queue.pop(0)
            if panel.get("panels"):
                panel_queue.extend(panel["panels"])
            elif panel.get("type") == "row" or not panel.get("id"):
                continue
            else:
                title = panel.get("title")
                if not title:
                    title = f"{_('无标题')} #{panel['id']}"
                panel_id_title.append({"title": title, "id": panel["id"]})
        return panel_id_title
    return []


def fetch_biz_panels(bk_biz_id):
    """
    获取业务下所有dashboard信息与其panels信息
    :param bk_biz_id: 业务ID
    :return: panelsID
    """

    def full_panels(db_dict, uid):
        db_dict["bk_biz_id"] = bk_biz_id
        db_dict["panels"] = fetch_panel_title_ids(bk_biz_id, uid, org=org)

    dashboards = resource.grafana.get_dashboard_list(bk_biz_id=bk_biz_id, is_report=True)
    org = api.grafana.get_organization_by_name(name=str(bk_biz_id))
    with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
        futures = []
        for dashboard in dashboards:
            futures.append(executor.submit(full_panels, dashboard, dashboard["uid"]))

        concurrent.futures.wait(futures)
    return dashboards
