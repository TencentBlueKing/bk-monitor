#!/usr/bin/env python

from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List

import yaml


@dataclass
class EsbApi:
    api_type: str
    comp_codename: str
    dest_http_method: str
    dest_path: str
    is_hidden: bool
    label: str
    label_en: str
    name: str
    path: str
    method: str


def read_esb_yaml(file_path: str) -> List[EsbApi]:
    """
    读取esb的yaml文件
    :param file_path: esb的yaml文件路径
    :return: EsbApiDefine列表
    """
    with open(file_path, "r") as f:
        data: List[Dict] = yaml.safe_load(f)

    return [EsbApi(**item) for item in data]


def convert_esb_to_apigw(esb_apis: List[EsbApi]) -> Dict[str, Dict]:
    """
    将esb的api转换为apigw的api,按tag分组生成多份配置
    :param esb_apis: esb的api列表
    :return: 按tag分组的多份apigw配置,格式为 {tag: config}
    """
    # 定义路径关键字到tag的映射
    path_to_tag = {
        "user_group": "user_group",
        "notice_group": "notice_group",
        "duty_rule": "duty_rule",
        "alarm_strategy": "alarm_strategy",
        "shield": "shield",
        "event": "event",
        "action": "action",
        "alert": "alert",
        "collect": "collect",
        "uptime_check": "uptime_check",
        "/meta/": "metadata",
        "custom_report": "custom_report",
        "custom_event": "custom_event",
        "custom_time_series": "custom_time_series",
        "custom_metric": "custom_metric",
        "apm": "apm",
        "application_web": "apm",
        "calendar": "calendar",
        "grafana": "dashboard",
        "as_code": "as_code",
        "mail_report": "render_image",
        "render_image": "render_image",
        "new_report": "render_image",
    }

    # 按tag分组存储paths
    tag_paths = defaultdict(dict)

    for api in esb_apis:
        path_key = api.path.rstrip("/") + "/"
        method = api.method.lower() if api.method else api.dest_http_method.lower()

        # 根据dest_path确定tag
        tag = "others"
        for key, value in path_to_tag.items():
            if key in api.dest_path:
                tag = value
                break

        # TODO: 包含占位符的path处理

        # 将API添加到对应tag的paths中
        tag_paths[tag][path_key] = {
            method: {
                "operationId": api.name,
                "description": api.label,
                "tags": [tag],
                "x-bk-apigateway-resource": {
                    "isPublic": not api.is_hidden,
                    "allowApplyPermission": True,
                    "matchSubpath": False,
                    "backend": {"type": "HTTP", "method": method, "path": api.dest_path, "matchSubpath": False},
                    "authConfig": {
                        "appVerifiedRequired": True,
                        "userVerifiedRequired": False,
                        "resourcePermissionRequired": True,
                    },
                    "descriptionEn": api.label_en,
                },
            }
        }

    # 为每个tag生成完整的配置
    configs = {}
    for tag, paths in tag_paths.items():
        configs[tag] = {
            "swagger": "2.0",
            "basePath": "/",
            "info": {"version": "1.0", "title": "API Gateway Resources", "description": ""},
            "schemes": ["http"],
            "paths": paths,
        }

    return configs


def write_apigw_configs(configs: Dict[str, Dict], output_dir: Path):
    """
    将apigw的配置写入文件
    :param configs: apigw的配置
    :param output_dir: 输出目录
    """
    # 创建输出目录
    output_dir.mkdir(parents=True, exist_ok=True)

    # 按分类写入文件
    for tag, config in configs.items():
        with open(output_dir / f"{tag}.yaml", "w+") as f:
            yaml.dump(config, f, allow_unicode=True, sort_keys=False)


if __name__ == "__main__":
    support_files_dir = Path(__file__).parent.parent

    esb_yaml_path = support_files_dir.parent.parent / "docs" / "api" / "monitor_v3.yaml"
    esb_apis = read_esb_yaml(esb_yaml_path)
    configs = convert_esb_to_apigw(esb_apis)

    write_apigw_configs(configs, support_files_dir / "resources")
