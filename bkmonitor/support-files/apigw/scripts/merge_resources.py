#! /usr/bin/env python

from pathlib import Path

import yaml


def merge_resources(resources_dir: Path):
    """
    合并resources目录下的所有yaml文件，除了old目录
    """
    public_dirs = ["internal", "external"]
    verify_dirs = ["app", "user"]

    # 合并所有资源
    merged_data = {}

    for public_dir in public_dirs:
        for verify_dir in verify_dirs:
            for file in resources_dir.glob(f"{public_dir}/{verify_dir}/*.yaml"):
                data: dict[str, dict] = yaml.safe_load(file.read_text())["paths"]
                for _, path_data in data.items():
                    for _, method_data in path_data.items():
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

                        # 设置public
                        method_data["x-bk-apigateway-resource"]["isPublic"] = public_dir == "external"
                        method_data["x-bk-apigateway-resource"]["allowApplyPermission"] = True

                merged_data.update(data)

    # 生成合并后的资源
    resources = {
        "openapi": "3.0.1",
        "info": {"version": "2.0", "title": "API Gateway Resources", "description": ""},
        "paths": merged_data,
    }

    # 写入文件
    with open(resources_dir / "../resources.yaml", "w") as f:
        yaml.dump(resources, f, allow_unicode=True, sort_keys=False)


if __name__ == "__main__":
    support_files_dir = Path(__file__).parent.parent
    merge_resources(support_files_dir / "resources")
