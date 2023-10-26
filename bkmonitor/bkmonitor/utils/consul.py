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


import os

import consul
from django.conf import settings


def get_settings(config_name):
    """
    获取一个指定的settings内容，如果为空字符串时，会将该配置以None方式返回
    :param config_name: 配置名
    :return: None | str
    """

    value = getattr(settings, config_name, None)
    if value == "":
        return None

    return value


def is_file_exists(file_path):
    """
    判断一个文件是否存在
    :param file_path: 文件路径
    :return: True | False
    """
    if file_path is None:
        return False

    return os.path.isfile(file_path) and os.path.exists(file_path)


class BKConsul(consul.Consul):
    def __init__(self, using_settings=True, scheme="http", verify=None, cert=None, port=8500, **kwargs):
        """
        可以自动适配django配置中的consul配置客户端
        :param using_settings: 是否使用settings中的配置，默认使用
        :param scheme: 请求scheme
        :param verify: server端认证信息，应该传入为对方签发证书的CA的证书
        :param cert: client端认证信息，应该传入(客户端证书，客户端私钥)
        :param port: 服务端端口
        :param kwargs: 其他额外参数
        """
        # 如果不需要使用tls，直接返回
        if not using_settings:
            super(BKConsul, self).__init__(scheme=scheme, verify=verify, cert=cert, port=port, **kwargs)
            return

        # 判断是否存在consul的证书认证配置
        host = get_settings("CONSUL_CLIENT_HOST")
        port = get_settings("CONSUL_CLIENT_PORT")
        client_cert = get_settings("CONSUL_CLIENT_CERT_FILE")
        client_key = get_settings("CONSUL_CLIENT_KEY_FILE")
        server_cert = get_settings("CONSUL_SERVER_CA_CERT")
        https_port = get_settings("CONSUL_HTTPS_PORT")

        client_cert = client_cert if is_file_exists(client_cert) else None
        client_key = client_key if is_file_exists(client_key) else None
        server_cert = server_cert if is_file_exists(server_cert) else None
        https_port = https_port if https_port else None

        # 需要客户端key及证书同时不为None，同时外部也没有指定，那配置方可以生效
        if (client_cert is not None and client_key is not None) and cert is None:
            cert = (client_cert, client_key)

        # 需要外部未有传入verify配置而且settings中存在
        if verify is None and server_cert is not None:
            verify = server_cert

        kwargs["host"] = host
        # 如果有任何一个证书的配置，则将scheme改为https
        if cert is not None:
            scheme = "https"
            # 如果有scheme的切换，那么应该需要考虑端口变更
            port = https_port
            # python 默认的 SSL/TLS 认证库在使用自签名证书时，可能不支持 `127.0.0.1`作为 SNI
            # 需要转换为 `localhost`
            if kwargs.get("host") == "127.0.0.1":
                kwargs["host"] = "localhost"

        super(BKConsul, self).__init__(scheme=scheme, verify=verify, cert=cert, port=port, **kwargs)
