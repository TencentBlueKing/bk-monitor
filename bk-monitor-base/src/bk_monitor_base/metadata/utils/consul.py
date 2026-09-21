import os
from typing import Any

import consul

from bk_monitor_base.metadata.config import settings


def is_file_exists(file_path: str | None) -> bool:
    """
    判断一个文件是否存在
    :param file_path: 文件路径
    :return: True | False
    """
    if file_path is None:
        return False

    return os.path.isfile(file_path) and os.path.exists(file_path)


class BKConsul(consul.Consul):
    def __init__(
        self,
        using_settings: bool = True,
        scheme: str = "http",
        verify: Any = None,
        cert: Any = None,
        port: int = 8500,
        **kwargs: Any,
    ):
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
            super().__init__(scheme=scheme, verify=verify, cert=cert, port=port, **kwargs)
            return

        # 判断是否存在consul的证书认证配置
        host = settings.metadata.consul_client_host
        port = settings.metadata.consul_client_port
        client_cert = settings.metadata.consul_client_cert_file
        client_key = settings.metadata.consul_client_key_file
        server_cert = settings.metadata.consul_server_ca_cert
        https_port = settings.metadata.consul_https_port

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

        super().__init__(scheme=scheme, verify=verify, cert=cert, port=port, **kwargs)
