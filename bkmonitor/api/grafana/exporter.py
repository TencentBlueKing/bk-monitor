# -*- coding: utf-8 -*-
from typing import Dict, List, Union


class DashboardExporter:
    def __init__(self, data_source_metas: List[Dict]):
        self.name_data_sources = {}
        self.uid_data_sources = {}
        self.type_data_sources = {}
        for data_source_meta in data_source_metas:
            self.uid_data_sources[data_source_meta["uid"]] = data_source_meta
            self.name_data_sources[data_source_meta["name"]] = data_source_meta
            self.type_data_sources[data_source_meta["type"]] = data_source_meta

        self.variables = {}
        self.requires = {}
        self.inputs = {}

    def templateize_datasource(self, config: Dict, fallback=None, datasource_mapping=None) -> None:
        """
        数据源模板化
        """
        # 如果没有datasource且有默认datasource，则使用默认datasource
        if not config.get("datasource"):
            if fallback:
                config["datasource"] = fallback
            else:
                return

        data_source: Union[str, Dict] = config["datasource"]
        if isinstance(data_source, str):
            name = data_source
            if name.startswith("$"):
                return

            data_source_meta = self.name_data_sources.get(name)
        else:
            uid = data_source.get("uid") or ""
            if uid.startswith("$"):
                return

            data_source_type = data_source.get("type") or ""
            data_source_meta = self.uid_data_sources.get(uid) or self.type_data_sources.get(data_source_type)

        if not data_source_meta:
            return

        self.requires[f"datasource{data_source_meta['type']}"] = {
            "type": "datasource",
            "id": data_source_meta["type"],
            "name": data_source_meta["typeName"],
        }

        ref_name = f"DS_{data_source_meta['name'].replace(' ', '_').upper()}"
        self.inputs[ref_name] = {
            "name": ref_name,
            "label": data_source_meta["name"],
            "description": "",
            "type": "datasource",
            "pluginId": data_source_meta["type"],
            "pluginName": data_source_meta["typeName"],
        }

        if isinstance(data_source, str):
            config["datasource"] = f"${{{ref_name}}}"
        else:
            config["datasource"] = {"type": data_source_meta["type"], "uid": f"${{{ref_name}}}"}

        if datasource_mapping:
            datasource_mapping[ref_name] = data_source_meta["uid"]

    def make_exportable(self, dashboard: Dict, datasource_mapping: Dict = None):
        """
        仪表盘导出处理
        """
        # 变量预处理
        for variable in dashboard.get("templating", {}).get("list", []):
            if variable.get("type") == "query":
                self.templateize_datasource(variable, datasource_mapping=datasource_mapping)
            self.variables[variable["name"]] = variable
            variable["current"] = {}
            variable["refresh"] = variable.get("refresh") or 1
            variable["options"] = []

        # datasource panels提取&处理
        for row in dashboard.get("panels") or []:
            self.templateize_datasource(row, datasource_mapping=datasource_mapping)

            for panel in row.get("panels") or []:
                self.templateize_datasource(panel, datasource_mapping=datasource_mapping)

                for target in panel.get("targets") or []:
                    self.templateize_datasource(target, panel.get("datasource"), datasource_mapping=datasource_mapping)

            for target in row.get("targets") or []:
                self.templateize_datasource(target, row.get("datasource"), datasource_mapping=datasource_mapping)

        # todo: libraryPanel处理
        dashboard["__inputs"] = list(self.inputs.values())
        dashboard["__requires"] = sorted(self.requires.values(), key=lambda x: x["id"])
        dashboard.pop("id", None)
        dashboard.pop("uid", None)
        return dashboard
