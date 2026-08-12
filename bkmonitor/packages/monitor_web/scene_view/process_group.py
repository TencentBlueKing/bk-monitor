"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""


def _port_sort_key(port) -> tuple:
    try:
        return 0, int(port)
    except (TypeError, ValueError):
        return 1, str(port)


def _process_sort_key(process: dict) -> tuple:
    ports = process.get("ports") or []
    primary_port = process.get("port")
    if primary_port in (None, "") and ports:
        primary_port = min(ports, key=_port_sort_key)
    return (
        _port_sort_key(primary_port),
        str(process.get("protocol") or ""),
        str(process.get("bindIp") or ""),
        str(process.get("id") or ""),
    )


def group_process_configs(processes: list[dict]) -> list[dict]:
    """按 display_name 合并 CMDB 进程配置，并保留组内全部端口绑定。"""
    process_groups: dict[str, list[dict]] = {}

    for process in processes:
        process_groups.setdefault(process["name"], []).append(process)

    groups = []
    for name, process_configs in process_groups.items():
        # 兼容字段统一取排序后的代表配置，避免端口与启动命令来自不同 CMDB 记录。
        representative = min(process_configs, key=_process_sort_key)
        group = {**representative, "id": name, "portBindings": []}
        if group.get("port") in (None, "") and group.get("ports"):
            group["port"] = min(group["ports"], key=_port_sort_key)
        binding_keys: set[tuple] = set()

        for process in process_configs:
            ports = process.get("ports") or ([] if process.get("port") in (None, "") else [process["port"]])
            for port in ports:
                binding_key = (process.get("protocol"), process.get("bindIp"), port)
                if binding_key in binding_keys:
                    continue
                binding_keys.add(binding_key)
                group["portBindings"].append(
                    {"protocol": process.get("protocol"), "bindIp": process.get("bindIp"), "port": port}
                )

        group["portBindings"].sort(
            key=lambda item: (_port_sort_key(item["port"]), str(item["protocol"]), item["bindIp"] or "")
        )
        groups.append(group)
    return groups
