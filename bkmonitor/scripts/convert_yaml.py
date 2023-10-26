# -*- coding: utf-8 -*-
"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2021 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""


__doc__ = """
python convert_yaml.py -s ../docs/api/monitor_v3.yaml -t ./ -f json
"""


import argparse
import json
import os

import yaml


class BasicException(Exception):
    """异常"""

    pass


def parse_fenlei(path):
    return path.split("/")[3]


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="convert yaml to apigw file")
    parser.add_argument("-s", "--source", type=str, help="input yaml file", required=True)
    parser.add_argument("-t", "--target", type=str, help="output dir", required=True)
    parser.add_argument("-n", "--name", type=str, help="output file name", required=False)
    parser.add_argument(
        "-f",
        "--format",
        type=str,
        help="output file format",
        required=True,
        choices=["json", "yaml", "swagger"],
        default="yaml",
    )
    args = parser.parse_args()

    source, target, format, name = args.source, args.target, args.format, args.name
    name = name or "apigw_default"

    print(
        """
        ===========================
        source:         {},
        target:         {},
        format:         {},
        name:         {},
        ===========================
    """.format(
            source, target, format, name
        )
    )

    if format == "swagger":
        template_header = """swagger: '2.0'
basePath: /
info:
  version: '0.1'
  title: API Gateway Resources
  description: ''
schemes:
- http
paths:"""

        each_resource_template = """
  {resource_request_src_path}:
    {resource_request_method}:
      operationId: {resource_name}
      description: {resource_desc}
      tags:
      - {tag_name}
      responses:
        default:
          description: ''
      x-bk-apigateway-resource:
        isPublic: true
        allowApplyPermission: true
        matchSubpath: false
        backend:
          type: HTTP
          method: {resource_backend_request_method}
          path: {resource_request_dest_path}
          matchSubpath: false
          timeout: 0
          upstreams: {{}}
          transformHeaders: {{}}
        authConfig:
          userVerifiedRequired: false
        disabledStages: []"""

        output = open(os.path.join(target, "{}.{}".format(name, format)), "w")
        output.write(template_header)
        with open(source, "rb") as f:
            apis = yaml.load(f, Loader=yaml.FullLoader)
            for api in apis:
                resource = each_resource_template.format(
                    resource_name=api["name"],
                    resource_desc=api["label"],
                    resource_request_src_path=api["path"].replace("/v2/monitor_v3", ""),
                    resource_request_method=str(api.get("method") or api.get("suggest_method")).lower(),
                    resource_backend_request_method=str(api["dest_http_method"]).lower(),
                    resource_request_dest_path=api["dest_path"],
                    tag_name="meta",  # 暂时固定meta，有需要那就改一下这里
                )
                # print(resource)
                output.write(resource)

        exit(0)

    with open(source, "rb") as f:
        apis = yaml.load(f, Loader=yaml.FullLoader)
        data = [
            {
                "resource_classification": parse_fenlei(api["dest_path"]),
                "headers": {},
                "resource_name": api["name"],
                "description": api["label"],
                "timeout": 30,
                "path": api["path"].replace("/v2/monitor_v3", ""),
                "registed_http_method": api.get("suggest_method") or api["dest_http_method"],
                "dest_http_method": api["dest_http_method"],
                "dest_url": "http://{stageVariables.domain}" + api["dest_path"],
            }
            for api in apis
        ]

        output = open(os.path.join(target, "{}.{}".format(name, format)), "w")
        if format == "json":
            json.dump(data, output, indent=2)
        else:
            yaml.dump(data, output)
