import inspect
import re
import time

from django.core.management.base import BaseCommand
from django.conf import settings
from apps.iam import Permission

import bk_dataview.grafana.client as grafana_client
from apps.iam.handlers import ActionEnum
from apps.iam.management.commands.iam_upgrade_action_v2 import (
    Command as IamMigrateCommand,
)

ACTIONS_TO_MIGRATE = [
    ActionEnum.VIEW_DASHBOARD,
    ActionEnum.MANAGE_DASHBOARD,
]


class Command(BaseCommand):
    help = "export config json for Migrate grafana 8.x(bk-log) configuration to grafana 9.x(bk-monitor)"

    def add_arguments(self, parser):
        """添加命令行参数"""
        parser.add_argument(
            "--grafana_url", type=str, help="URL of the Grafana instance where the configuration will be written"
        )
        parser.add_argument(
            "--selected_biz",
            type=str,
            default="all",
            help="Comma-separated list of biz_ids for migration. Default is 'all', which includes every biz_id",
        )
        parser.add_argument("--app_code", type=str, default="bk_monitorv3", help="app_code for migrate permission")
        parser.add_argument(
            "--stats_only",
            action="store_true",
            help="Only get migration statistics without performing actual migration",
        )

    def handle(self, *args, **options):
        start_time = time.time()
        """ 执行命令 """
        self.stdout.write("[migrate_grafana] #### START ####")
        # 获取命令行参数
        grafana_url = options["grafana_url"]
        selected_biz = options["selected_biz"]
        stats_only = options["stats_only"]
        # app_code = options["app_code"]

        # 从 bk_log 获取 grafana 配置数据
        grafana_data, extract_failed_biz, migration_stats = self.get_grafana_config(grafana_client, selected_biz)

        # 如果只是获取统计信息，则显示后退出
        if stats_only:
            self.show_migration_stats(migration_stats)
            end_time = time.time()
            self.stdout.write(f"[migrate_grafana] #### STATS ONLY MODE END ####, Cost: {end_time - start_time} s")
            return

        # 转换 bk-log grafana 配置数据
        biz_to_org_mapping, convert_failed_biz = self.convert_bklog_grafana_config(grafana_url, grafana_data)
        # 写入配置数据到新 Grafana,由用户进行指定
        write_failed_biz = self.write_config_to_grafana(grafana_url, grafana_data, biz_to_org_mapping)

        # 迁移权限 - 先不迁移权限
        # self.migrate_permissions(app_code)

        # 集中展示错误信息
        self.show_error_info(extract_failed_biz, convert_failed_biz, write_failed_biz, migration_stats)

        end_time = time.time()
        self.stdout.write(f"[migrate_grafana] #### END ####, Cost: {end_time - start_time} s")

    # 通用函数
    @staticmethod
    def record_error(failed_biz, biz_id, err_msg):
        if biz_id not in failed_biz:
            failed_biz[biz_id] = []
        failed_biz[biz_id].append(err_msg)

    @staticmethod
    def show_error(error_msg):
        current_frame = inspect.currentframe()
        caller_frame = current_frame.f_back if current_frame else None
        line_number = caller_frame.f_lineno if caller_frame else None
        print(f"ERROR on line {line_number}: {error_msg}")

    # 数据获取
    def get_grafana_config(self, bklog_grafana_client, selected_biz):
        """获取 bk-log grafana 配置数据"""
        self.stdout.write("START get config from bk_log")
        orgs_resp = bklog_grafana_client.get_all_organization()
        if orgs_resp.status_code != 200:
            self.show_error(f"failed: get config from bk_log: {orgs_resp.json()}")
            raise ValueError("Failed to get orgs from bk_log")

        orgs = self.filter_orgs_by_biz(selected_biz, orgs_resp.json())
        all_data, failed_biz, migration_stats = self.extract_grafana_config(orgs)

        self.stdout.write("END get config from bk_log")
        return all_data, failed_biz, migration_stats

    def filter_orgs_by_biz(self, selected_biz, orgs):
        """根据命令行参数,选择需要迁移的业务"""
        if selected_biz == "all":
            self.stdout.write("selected_biz is 'all': get all biz from bk_log")
            return orgs
        self.stdout.write(f"get selected biz from bk_log: {selected_biz}")
        selected_biz_ids = selected_biz.split(",")

        return [org for org in orgs if org["name"] in selected_biz_ids]

    def extract_grafana_config(self, orgs):
        """提取 bk_log grafana 配置数据"""
        # 完整的 bk_log grafana 配置数据
        all_data = []
        # 提取失败的业务及其失败原因
        failed_biz = {}
        # 统计信息
        migration_stats = {
            "total_biz": 0,  # 只统计有仪表盘的业务
            "total_dashboards": 0,
            "biz_details": [],
        }

        for org in orgs:
            org_id, org_name = org["id"], org["name"]
            is_legal_org_name = self.check_org_name(org_id, org_name, failed_biz)
            if not is_legal_org_name:
                continue

            # 获取当前业务下所有 dashboard
            dashboards_resp = grafana_client.search_dashboard(org_id=org["id"])
            if dashboards_resp.status_code != 200:
                self.show_error(f"FAILED to get dashboards for org {org_name}: {dashboards_resp.json()}")
                self.record_error(failed_biz, org_name, f"failed to get dashboards: {dashboards_resp.json()}")
                continue

            org_data = self.process_dashboards(dashboards_resp.json(), org_id, org_name, failed_biz)

            # 统计当前业务信息
            biz_dashboard_count = sum(len(folder["dashboards"]) for folder in org_data["folders"])

            # 只处理有仪表盘的业务
            if biz_dashboard_count > 0:
                biz_folder_count = len(org_data["folders"])
                migration_stats["total_biz"] += 1
                migration_stats["total_dashboards"] += biz_dashboard_count
                migration_stats["biz_details"].append(
                    {"biz_id": org_name, "dashboard_count": biz_dashboard_count, "folder_count": biz_folder_count}
                )

                all_data.append(org_data)
                self.stdout.write(
                    f"process org_id {org_id} -- org_name(biz_id) {org_name} SUCCESS: {biz_dashboard_count} dashboards"
                )
            else:
                self.stdout.write(f"SKIP org_id {org_id} -- org_name(biz_id) {org_name}: no dashboards")

        return all_data, failed_biz, migration_stats

    def check_org_name(self, org_id, org_name, failed_biz):
        if not re.match(r"^-?\d+$", org_name):
            self.show_error(f"SKIP process org_id {org_id} -- org_name(biz_id) {org_name}: invalid biz_id")
            self.record_error(failed_biz, org_name, "org_name is illegal")
            return False
        else:
            self.stdout.write(f"START process org_id {org_id} -- org_name(biz_id) {org_name}")
            return True

    def process_dashboards(self, dashboards, org_id, org_name, failed_biz):
        """遍历单一业务下所有 dashboard, 处理结构信息"""
        org_data = {"biz_id": org_name, "folders": []}
        folder_item = {}

        for dashboard in dashboards:
            folder_title = dashboard.get("folderTitle", "General")

            if folder_title not in folder_item:
                folder_item[folder_title] = {"folder_title": folder_title, "dashboards": []}

            dashboard_detail_resp = grafana_client.get_dashboard_by_uid(org_id=org_id, dashboard_uid=dashboard["uid"])
            if dashboard_detail_resp.status_code != 200:
                self.show_error(f"failed to get dashboard info in biz {org_name}: {dashboard_detail_resp.json()}")
                self.record_error(failed_biz, org_name, f"failed to get dashboard info: {dashboard_detail_resp.json()}")
                continue

            dashboard_detail = dashboard_detail_resp.json()
            panel_info = dashboard_detail["dashboard"]["panels"]

            dashboard_data = {
                "dashboard_title": dashboard["title"],
                "panels": panel_info,
                "refresh": dashboard_detail.get("dashboard", {}).get("refresh", ""),
                "tags": dashboard_detail.get("dashboard", {}).get("tags", []),
                "timezone": dashboard_detail.get("dashboard", {}).get("timezone", "browser"),
                "templating": dashboard_detail.get("dashboard", {}).get("templating", []),
                "time": dashboard_detail.get("dashboard", {}).get("time", {}),
                "timepicker": dashboard_detail.get("dashboard", {}).get("timepicker", {}),
            }
            folder_item[folder_title]["dashboards"].append(dashboard_data)

        for folder in folder_item.values():
            org_data["folders"].append(folder)

        return org_data

    # 数据转换
    def convert_bklog_grafana_config(self, grafana_url, grafana_data):
        """转换 bk-log grafana 配置数据, 支持平滑迁移到 bk-monitor"""
        failed_biz = {}
        orgs_resp = grafana_client.get_all_organization(grafana_url)
        if orgs_resp.status_code != 200:
            self.show_error(f"failed to convert orgs for bk_log: {orgs_resp.json()}")
            raise ValueError(f"Failed to get orgs from {grafana_url}")

        orgs = orgs_resp.json()
        biz_to_org_mapping = {str(org["name"]): org["id"] for org in orgs}

        self.stdout.write("START change datasource to bk_log_search")
        for data in grafana_data:
            biz_id = data["biz_id"]
            self.update_datasource_in_data(grafana_url, biz_id, data, biz_to_org_mapping, failed_biz)

        self.stdout.write("END change the datasource to bk_log_search")

        return biz_to_org_mapping, failed_biz

    def update_datasource_in_data(self, grafana_url, biz_id, data, biz_to_org_mapping, failed_biz):
        """更新数据源信息,处理组织创建逻辑"""
        bk_log_datasource_uid = self.ensure_datasource(grafana_url, biz_id, biz_to_org_mapping, failed_biz)
        if not bk_log_datasource_uid:
            self.show_error(f"failed to get datasource for biz_id {biz_id}, will use default datasource")
            return

        for folder in data["folders"]:
            for dashboard in folder["dashboards"]:
                for panel in dashboard["panels"]:
                    self.update_panel_datasource(panel, bk_log_datasource_uid)

                for template in dashboard["templating"].get("list", []):
                    self.update_template_datasource(template, bk_log_datasource_uid)

    def ensure_datasource(self, grafana_url, biz_id, biz_to_org_mapping, failed_biz):
        """确保数据源存在及获取 uid, 以及必要时新建组织"""
        if biz_id in biz_to_org_mapping:
            # 业务已创建,导入数据源
            org_id = biz_to_org_mapping[biz_id]
            datasource_uid = self.get_datasource_uid(grafana_url, org_id, failed_biz, biz_id)
            return datasource_uid
        else:
            org_id = self.create_organization(grafana_url, biz_id, failed_biz)
            biz_to_org_mapping[biz_id] = org_id
            return None if org_id is None else self.get_datasource_uid(grafana_url, org_id, failed_biz, biz_id)

    def get_datasource_uid(self, grafana_url, org_id, failed_biz, biz_id):
        """获取指定组织的数据源 uid"""
        bk_monitor_ds_resp = grafana_client.get_all_datasources(org_id, grafana_url)
        if bk_monitor_ds_resp.status_code != 200:
            self.show_error(f"failed to get datasources for org {org_id}: {bk_monitor_ds_resp.json()}")
            self.record_error(failed_biz, biz_id, f"failed to get datasources: {bk_monitor_ds_resp.json()}")
            return None

        for ds in bk_monitor_ds_resp.json():
            if ds["type"] == "bk_log_datasource":
                return ds["uid"]
        return None

    def create_organization(self, grafana_url, biz_id, failed_biz):
        """必要时创建新组织并返回组织 id"""
        resp = grafana_client.create_organization(biz_id, grafana_url)
        if resp.status_code == 200:
            if (
                "message" in resp.json()
                and "message" in resp.json()
                and resp.json()["message"] == "Organization created"
            ):
                self.stdout.write(f"create organization success for biz_id {biz_id}")
                return resp.json()["orgId"]
        else:
            self.show_error(f"failed create organization for biz_id {biz_id}: {resp.json()}")
            self.record_error(failed_biz, biz_id, f"failed create organization: {resp.json()}")
            return None

    def update_template_datasource(self, template, bk_log_datasource_uid):
        """更新模板变量的数据源信息"""
        datasource_config = {
            "type": "bk_log_datasource",
            "uid": bk_log_datasource_uid,
        }

        if "datasource" in template:
            template["datasource"] = datasource_config

    def update_panel_datasource(self, panel, bk_log_datasource_uid):
        """为单一面板更新数据源信息"""
        if "collapsed" in panel and "panels" in panel:
            for collapsed_panel in panel["panels"]:
                self.update_panel_datasource(collapsed_panel, bk_log_datasource_uid)

        datasource_config = {
            "type": "bk_log_datasource",
            "uid": bk_log_datasource_uid,
        }

        if "datasource" in panel:
            panel["datasource"] = datasource_config

        has_target_datasource = False
        for target in panel.get("targets", []) or []:
            # 处理两种旧结构：datasource 或 datasourceId
            if "datasource" in target or "datasourceId" in target:
                if "datasourceId" in target:
                    target.pop("datasourceId", None)
                target["datasource"] = datasource_config
                has_target_datasource = True

        if "datasource" not in panel and not has_target_datasource:
            self.show_error(f"panel {panel.get('title', 'unknown')} has no datasource")

    def write_config_to_grafana(self, grafana_url, grafana_data, biz_to_org_mapping):
        """写入配置数据到 Grafana"""
        failed_biz = {}
        self.stdout.write("START write config to grafana")
        for data in grafana_data:
            biz_id = data["biz_id"]
            org_id = biz_to_org_mapping.get(biz_id, None)
            if not org_id:
                self.show_error(f"write failed for biz_id {biz_id}: need to be created")
                self.record_error(failed_biz, biz_id, "biz need to be created")
                continue

            self.stdout.write(f"start write config to org {org_id} biz {biz_id}")
            self.process_folders_and_dashboards(grafana_url, biz_id, org_id, data, failed_biz)
            self.stdout.write(f"end write config to org {org_id} biz {biz_id}")

        self.stdout.write("END write config to grafana")

        return failed_biz

    def process_folders_and_dashboards(self, grafana_url, biz_id, org_id, data, failed_biz):
        """处理 folder 和 dashboard 的配置与创建"""
        folders = data["folders"]
        all_folders = self.get_all_folders(grafana_url, org_id, biz_id)

        for folder in folders:
            folder_title, folder_uid = self.ensure_folder(grafana_url, biz_id, org_id, folder, all_folders, failed_biz)
            if not folder_uid:
                continue

            # 针对 General 文件夹特殊处理: 其无 uid
            if folder_uid == "1":
                folder_uid = None

            for dashboard in folder["dashboards"]:
                self.create_dashboard(grafana_url, biz_id, org_id, dashboard, folder_title, folder_uid, failed_biz)

    def get_all_folders(self, grafana_url, org_id, biz_id):
        all_folders_resp = grafana_client.get_folders(org_id, grafana_url)
        if all_folders_resp.status_code == 200:
            all_folders = all_folders_resp.json()
            return [folder["title"] for folder in all_folders]
        else:
            self.show_error(f"write failed for biz_id {biz_id}: failed to get all folders")
            raise ValueError(f"Failed to get all folders for org {org_id} -- biz {biz_id}")

    def ensure_folder(self, grafana_url, biz_id, org_id, folder, all_folders, failed_biz):
        """确保文件夹存在并返回"""
        folder_title = folder["folder_title"]
        parent_uid = folder.get("parent_uid", None)

        if folder_title == "General":
            folder_title = "[bklog] 迁移目录"

        resp = grafana_client.create_folder(org_id, folder_title, parent_uid, grafana_url)
        if resp.status_code == 200:
            folder_uid = resp.json()["uid"]
            self.stdout.write(f"create folder success in org {org_id} with folder_title {folder_title}")
            return folder_title, folder_uid
        elif not folder_title.endswith("_bklog") and f"{folder_title}_bklog" not in all_folders:
            folder_title = folder_title + "_bklog"
            resp_copy = grafana_client.create_folder(org_id, folder_title, parent_uid, grafana_url)
            if resp_copy.status_code == 200:
                folder_uid = resp_copy.json()["uid"]
                self.stdout.write(f"create folder success in org {org_id} with folder_title {folder_title}")
                return folder_title, folder_uid
            else:
                self.show_error(
                    f"create folder failed in org {org_id} with folder_title {folder_title}: {resp_copy.json()}"
                )
                self.record_error(failed_biz, biz_id, f"create folder failed: {resp_copy.json()}")
                return "", None
        else:
            self.show_error(f"folder_title {folder_title} and {folder_title}_bklog both already exists in org {org_id}")
            self.record_error(
                failed_biz,
                biz_id,
                f"folder_title {folder_title} and {folder_title}_bklog both already exists in org {org_id}",
            )
            return "", None

    def create_dashboard(self, grafana_url, biz_id, org_id, dashboard, folder_title, folder_uid, failed_biz):
        """创建仪表盘"""
        dashboard_info = {
            "title": f"[bklog] {dashboard['dashboard_title']}",
            "tags": dashboard["tags"],
            "timezone": dashboard["timezone"],
            "refresh": dashboard["refresh"],
            "templating": dashboard["templating"],
            "time": dashboard["time"],
            "timepicker": dashboard["timepicker"],
        }
        resp = grafana_client.create_dashboard(org_id, dashboard_info, dashboard["panels"], folder_uid, grafana_url)
        if resp.status_code == 200:
            self.stdout.write(
                f"create dashboard success {dashboard_info['title']} in org {org_id} with folder_title {folder_title}"
            )
        else:
            self.show_error(
                f"create dashboard failed {dashboard_info['title']} in "
                f"org {org_id} with folder_title {folder_title}: {resp.json()}"
            )
            self.record_error(failed_biz, biz_id, f"create dashboard failed: {resp.json()}")

    # 权限迁移
    def migrate_permissions(self, app_code):
        """迁移权限信息"""
        self.stdout.write("START migrate permissions")
        migrate_command = IamMigrateCommand()
        migrate_command.iam_client = Permission.get_iam_client(settings.BK_APP_TENANT_ID)
        policies_by_actions = {}
        for action in ACTIONS_TO_MIGRATE:
            polices = migrate_command.query_polices(action.id)
            policies_by_actions[action.id] = polices

        for action in ACTIONS_TO_MIGRATE:
            polices = policies_by_actions[action.id]
            total = len(polices)
            self.stdout.write(f"start migrate action: {action.id}, policy count: {total}")

            progress = 0
            resources = []

            for police in polices:
                resource = migrate_command.policy_to_resource(action, police)
                resources.append(resource)

            for resource in resources:
                resource["system"] = app_code
                resp = migrate_command.grant_resource(resource)
                if resp is not None:
                    progress += 1
            self.stdout.write(f"migrate action: {action.id}, progress: {progress}/{total}")

        self.stdout.write("END migrate permissions")

    # 统计展示
    def show_migration_stats(self, migration_stats):
        """展示迁移规模统计信息"""
        if not migration_stats:
            return

        self.stdout.write("")
        self.stdout.write("========== MIGRATION SCALE STATISTICS ==========")
        self.stdout.write(f"📊 Total businesses to migrate: {migration_stats['total_biz']}")
        self.stdout.write(f"📈 Total dashboards to migrate: {migration_stats['total_dashboards']}")
        self.stdout.write("")
        self.stdout.write("📋 Business details:")
        for detail in migration_stats["biz_details"]:
            self.stdout.write(
                f"   • Business {detail['biz_id']}: {detail['dashboard_count']} dashboards, {detail['folder_count']} folders"
            )
        self.stdout.write("")
        self.stdout.write("💡 Migration complexity assessment:")
        if migration_stats["total_dashboards"] <= 100:
            self.stdout.write("   - Small scale migration (≤100 dashboards)")
        elif migration_stats["total_dashboards"] <= 500:
            self.stdout.write("   - Medium scale migration (101-500 dashboards)")
        elif migration_stats["total_dashboards"] <= 1000:
            self.stdout.write("   - Large scale migration (501-1000 dashboards)")
        else:
            self.stdout.write("   - Very large scale migration (>1000 dashboards)")
        self.stdout.write("================================================")
        self.stdout.write("")

    # 错误打印
    def show_error_info(self, extract_failed_biz, convert_failed_biz, write_failed_biz, migration_stats):
        """集中展示错误信息"""
        if extract_failed_biz:
            self.stdout.write("------------ FAILED INFO: get config ------------")
            for biz in extract_failed_biz:
                self.stdout.write(f"get grafana config failed for biz_id {biz}: {extract_failed_biz[biz]}")
            self.stdout.write("---------------------------------------------------")

        if convert_failed_biz:
            self.stdout.write("------------ FAILED INFO: convert config ------------")
            for biz in convert_failed_biz:
                self.stdout.write(f"convert grafana config failed for biz_id {biz}: {convert_failed_biz[biz]}")
            self.stdout.write("---------------------------------------------------")

        if write_failed_biz:
            self.stdout.write("------------ FAILED INFO: write config ------------")
            for biz in write_failed_biz:
                self.stdout.write(f"write grafana config failed for biz_id {biz}: {write_failed_biz[biz]}")
            self.stdout.write("---------------------------------------------------")

        # 展示迁移规模统计
        self.show_migration_stats(migration_stats)
