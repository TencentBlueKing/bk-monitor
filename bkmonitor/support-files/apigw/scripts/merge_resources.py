#! /usr/bin/env python

import json
from pathlib import Path

import yaml

# 开启个人令牌而公开的内部接口在文档中心统一归入该分组
PERSONAL_TOKEN_TAG = "用户态接口"


def check_unique_operation_ids(merged_data: dict):
    """校验合并后所有资源的 operationId 全局唯一。

    apigateway 要求 operationId 全局唯一，重复会在 sync_apigw 阶段被网关以
    `40002 校验失败` 拒绝，进而导致 migrate Job 的 init 容器退出、CrashLoopBackOff。
    在合并阶段提前 fail-fast，把问题暴露在本地/CI，而非部署时。
    """
    seen: dict[str, str] = {}
    for path, path_data in merged_data.items():
        for method, method_data in path_data.items():
            operation_id = method_data.get("operationId")
            if not operation_id:
                continue
            origin = f"{method.upper()} {path}"
            if operation_id in seen:
                raise ValueError(
                    f"duplicate operationId '{operation_id}': {seen[operation_id]} vs {origin}; "
                    f"apigateway requires globally-unique operationId"
                )
            seen[operation_id] = origin


def check_openapi_schema_types(node, location: str = "$.paths"):
    """校验合并后所有 Schema 的 type 为字符串。

    resources.yaml 声明 OpenAPI 3.0.1，数组形式的 type（Draft7 / OpenAPI 3.1）会被网关以
    `40002 校验失败` 拒绝；可空字段须写成 `nullable: true`。
    """
    if isinstance(node, dict):
        if isinstance(node.get("type"), list):
            raise ValueError(f"{location}: OpenAPI 3.0 schema type must be a string, got {node['type']}")
        for key, value in node.items():
            check_openapi_schema_types(value, f"{location}.{key}")
    elif isinstance(node, list):
        for index, value in enumerate(node):
            check_openapi_schema_types(value, f"{location}[{index}]")


def _schema_type(schema: dict) -> str:
    schema_type = schema.get("type") or " / ".join(
        dict.fromkeys(filter(None, map(_schema_type, schema.get("oneOf") or schema.get("anyOf") or [])))
    )
    if schema_type == "array" and schema.get("items"):
        return f"array[{_schema_type(schema['items'])}]"
    return schema_type


def _schema_description(schema: dict, description: str = "") -> str:
    parts = [description or schema.get("description", "")]
    if "enum" in schema:
        parts.append("可选值：" + "、".join(f"`{json.dumps(value, ensure_ascii=False)}`" for value in schema["enum"]))
    if "default" in schema:
        parts.append(f"默认值：`{json.dumps(schema['default'], ensure_ascii=False)}`")
    return " ".join(filter(None, parts)).replace("|", "\\|").replace("\n", " ")


def _schema_rows(schema: dict, prefix: str = "") -> list[tuple[str, str, bool, str]]:
    rows = []
    required = set(schema.get("required") or [])
    for name, prop in (schema.get("properties") or {}).items():
        field = f"{prefix}{name}"
        rows.append((field, _schema_type(prop), name in required, _schema_description(prop)))
        rows.extend(_schema_rows(prop, f"{field}."))
        if prop.get("items"):
            rows.extend(_schema_rows(prop["items"], f"{field}[]."))
    return rows


def render_resource_doc(path: str, method: str, operation: dict) -> str:
    """按资源的 OpenAPI 定义生成文档中心的 Markdown 文档。"""
    rows = [
        (
            param["name"],
            _schema_type(param["schema"]),
            param.get("required", False),
            _schema_description(param["schema"], param.get("description", "")),
        )
        for param in operation.get("parameters", [])
    ]
    body_schema = operation.get("requestBody", {}).get("content", {}).get("application/json", {}).get("schema", {})
    rows.extend(_schema_rows(body_schema))

    lines = [
        "### 功能描述",
        "",
        operation.get("description", ""),
        "",
        f"`{method.upper()} {path}`",
        "",
        "### 请求参数",
        "",
    ]
    if rows:
        lines += ["| 参数 | 类型 | 必填 | 说明 |", "|---|---|---|---|"]
        lines += [
            f"| {field} | {schema_type} | {'是' if required else '否'} | {desc} |"
            for field, schema_type, required, desc in rows
        ]
    else:
        lines.append("无")
    if body_schema.get("oneOf") or body_schema.get("anyOf"):
        lines += ["", "部分参数存在组合约束（如二选一必填），以参数说明为准。"]
    lines += ["", "### 返回结果", "", "沿用网关标准的 result、code、message、data 响应结构。", ""]
    return "\n".join(lines)


def merge_resources(resources_dir: Path):
    """
    合并resources目录下的所有yaml文件，除了old目录
    """
    public_dirs = ["internal", "external"]
    verify_dirs = ["app", "user"]

    # 合并所有资源
    merged_data = {}
    personal_token_operations = []

    for public_dir in public_dirs:
        for verify_dir in verify_dirs:
            for file in resources_dir.glob(f"{public_dir}/{verify_dir}/*.yaml"):
                data: dict[str, dict] = yaml.safe_load(file.read_text())["paths"]
                for path, path_data in data.items():
                    for method, method_data in path_data.items():
                        # 覆盖 authConfig
                        method_data["x-bk-apigateway-resource"].setdefault("authConfig", {})
                        auth_config = method_data["x-bk-apigateway-resource"]["authConfig"]
                        auth_config.update(
                            {
                                "appVerifiedRequired": auth_config.get("appVerifiedRequired", True),
                                "userVerifiedRequired": verify_dir == "user",
                                "resourcePermissionRequired": auth_config.get("resourcePermissionRequired", True),
                            }
                        )

                        # 补充标签
                        method_data["tags"] = method_data.get("tags") or [file.name.split(".")[0]]

                        # 设置public；开启个人令牌的内部接口须对用户可见，才能在授权范围中选择
                        personal_token_public = public_dir == "internal" and bool(
                            auth_config.get("oauth2PersonalClientEnabled")
                        )
                        method_data["x-bk-apigateway-resource"]["isPublic"] = (
                            public_dir == "external" or personal_token_public
                        )
                        if personal_token_public:
                            method_data["tags"] = [PERSONAL_TOKEN_TAG]
                            personal_token_operations.append((path, method, method_data))
                        method_data["x-bk-apigateway-resource"]["allowApplyPermission"] = True

                merged_data.update(data)

    # 写入前校验 operationId 全局唯一，避免重复定义被带到部署时才由网关报错
    check_unique_operation_ids(merged_data)
    check_openapi_schema_types(merged_data)

    # 生成合并后的资源
    resources = {
        "openapi": "3.0.1",
        "info": {"version": "2.0", "title": "API Gateway Resources", "description": ""},
        "paths": merged_data,
    }

    # 写入文件
    with open(resources_dir / "../resources.yaml", "w") as f:
        yaml.dump(resources, f, allow_unicode=True, sort_keys=False)

    # 开启个人令牌而公开的接口没有手写文档时，按 OpenAPI 定义生成，供 sync_resource_docs_by_archive 同步
    docs_dir = resources_dir / "../docs/zh"
    docs_dir.mkdir(parents=True, exist_ok=True)
    for path, method, method_data in personal_token_operations:
        doc_file = docs_dir / f"{method_data['operationId']}.md"
        if not doc_file.exists():
            doc_file.write_text(render_resource_doc(path, method, method_data), encoding="utf-8")


if __name__ == "__main__":
    support_files_dir = Path(__file__).parent.parent
    merge_resources(support_files_dir / "resources")
