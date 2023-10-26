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
import json
from urllib import parse

from requests.auth import AuthBase, HTTPBasicAuth
from requests_toolbelt.multipart.encoder import MultipartEncoder


class EncodeWebhook(object):
    def __init__(self, headers):
        self.headers = headers

    @staticmethod
    def encode_authorization(authorize):
        auth_type = authorize.get("auth_type")
        auth_config = authorize.get("auth_config")
        if auth_type == "basic_auth":
            return HTTPBasicAuth(auth_config["username"], auth_config["password"])
        if auth_type == "bearer_token":
            return HTTPBearerToken(auth_config["token"])

    def encode_body(self, body):
        if not body:
            return b""
        data_type = body["data_type"]
        encode_method = getattr(self, "encode_{}_body".format(data_type), None)
        if encode_method is None:
            return b""

        return encode_method(body)

    def encode_raw_body(self, body):
        """
        组装raw格式的headers
        """
        content_type_headers = {
            "json": "application/json",
            "text": "text/plain",
            "javascript": "application/javascript",
            "html": "text/html",
            "xml": "application/xml",
        }

        content_type = body["content_type"]
        self.headers.update({"Content-Type": content_type_headers.get(content_type, "text/plain")})
        if isinstance(body["content"], str):
            return body["content"].encode("utf-8")
        return json.dumps(body["content"])

    def encode_form_data_body(self, body):

        params = body.get("params", [])
        multipart_data = MultipartEncoder(
            fields={item["key"]: item["value"] for item in params if item.get("is_enabled")}
        )
        self.headers.update({"Content-Type": multipart_data.content_type})
        return multipart_data.to_string()

    def encode_x_www_form_urlencoded_body(self, body):
        """
        x-www-form-urlencoded数据格式组装
        """
        params = body.get("params", [])
        self.headers.update({"Content-Type": "application/x-www-form-urlencoded;charset=utf-8"})
        data = parse.urlencode({item["key"]: item["value"] for item in params if item.get("is_enabled")})
        return data.encode("utf-8")


class HTTPBearerToken(AuthBase):
    def __init__(self, token):
        self.token = token

    def __call__(self, r):
        authstr = "Bearer " + self.token
        r.headers["Authorization"] = authstr
        return r
