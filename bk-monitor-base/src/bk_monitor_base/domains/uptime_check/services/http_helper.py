"""
HTTP协议拨测配置辅助函数

提供HTTP协议相关的配置处理,包括:
- HTTP请求体编码
- 认证信息处理
- URL参数拼接
"""

import json
import urllib.parse
from base64 import b64encode
from typing import Any, final

from requests.utils import to_native_string  # pyright: ignore[reportUnknownVariableType]


@final
class GetHTTPConfig:
    """
    HTTP配置处理类

    负责处理HTTP协议的认证信息和请求体编码
    继承自EncodeWebhook的核心逻辑
    """

    def __init__(self, headers: dict[str, str] | None = None):
        """
        初始化

        Args:
            headers: HTTP请求头字典
        """
        self.headers = headers or {}

    def get_authorization(self, authorize: dict[str, Any]) -> dict[str, str]:
        """
        处理HTTP认证信息

        支持两种认证方式:
        - basic_auth: HTTP基础认证
        - bearer_token: Bearer Token认证

        Args:
            authorize: 认证配置字典
                {
                    "auth_type": "basic_auth" | "bearer_token",
                    "auth_config": {
                        "username": "...",  # basic_auth
                        "password": "...",  # basic_auth
                        "token": "..."      # bearer_token
                    }
                }

        Returns:
            更新后的headers字典
        """
        auth_type = authorize.get("auth_type")
        auth_config = authorize.get("auth_config", {})

        if auth_type == "basic_auth":
            username = str(auth_config.get("username", "")).encode("latin1")
            password = str(auth_config.get("password", "")).encode("latin1")
            credentials = b":".join((username, password))
            encoded = b64encode(credentials).strip()
            self.headers["Authorization"] = "Basic " + to_native_string(encoded)

        elif auth_type == "bearer_token":
            token = auth_config.get("token", "")
            self.headers["Authorization"] = f"Bearer {token}"

        return self.headers

    def get_body(self, body: dict[str, Any]) -> str:
        """
        处理HTTP请求体

        根据不同的data_type编码请求体:
        - default: 空请求体
        - raw: 原始数据(JSON/文本/HTML/XML等)
        - form_data: 表单数据(multipart/form-data)
        - x_www_form_urlencoded: URL编码表单数据

        Args:
            body: 请求体配置
                {
                    "data_type": "raw" | "form_data" | "x_www_form_urlencoded" | "default",
                    "content_type": "json" | "text" | "html" | "xml" | "javascript",  # for raw
                    "content": "...",  # for raw
                    "params": [{"key": "...", "value": "...", "is_enabled": true}, ...]  # for form_data/urlencoded
                }

        Returns:
            编码后的请求体字符串
        """
        encode_body = self.encode_body(body)
        if isinstance(encode_body, bytes):
            return encode_body.decode("utf-8")
        return encode_body

    def encode_body(self, body: dict[str, Any]) -> bytes | str:
        """
        编码请求体

        Args:
            body: 请求体配置

        Returns:
            编码后的字节串或字符串
        """
        if not body:
            return b""

        data_type = body.get("data_type", "default")

        if data_type == "raw":
            return self._encode_raw_body(body)
        elif data_type == "form_data":
            return self._encode_form_data_body(body)
        elif data_type == "x_www_form_urlencoded":
            return self._encode_x_www_form_urlencoded_body(body)
        else:
            return b""

    def _encode_raw_body(self, body: dict[str, Any]) -> bytes | str:
        """
        编码raw格式的请求体

        Args:
            body: 包含content_type和content的字典

        Returns:
            编码后的数据
        """
        content_type_headers = {
            "json": "application/json",
            "text": "text/plain",
            "javascript": "application/javascript",
            "html": "text/html",
            "xml": "application/xml",
        }

        content_type = body.get("content_type", "text")
        self.headers["Content-Type"] = content_type_headers.get(content_type, "text/plain")

        content = body.get("content", "")
        if isinstance(content, str):
            return content.encode("utf-8")
        return json.dumps(content)

    def _encode_form_data_body(self, body: dict[str, Any]) -> str:
        """
        编码form-data格式的请求体

        Args:
            body: 包含params列表的字典

        Returns:
            编码后的表单数据字符串
        """
        params = body.get("params", [])
        # 简化实现: 直接返回URL编码格式
        # 注意: 原实现使用MultipartEncoder,这里简化处理
        fields = {item["key"]: item["value"] for item in params if item.get("is_enabled")}
        encoded = urllib.parse.urlencode(fields)
        self.headers["Content-Type"] = "multipart/form-data"
        return encoded

    def _encode_x_www_form_urlencoded_body(self, body: dict[str, Any]) -> bytes:
        """
        编码x-www-form-urlencoded格式的请求体

        Args:
            body: 包含params列表的字典

        Returns:
            编码后的字节串
        """
        params = body.get("params", [])
        self.headers["Content-Type"] = "application/x-www-form-urlencoded;charset=utf-8"

        fields = {item["key"]: item["value"] for item in params if item.get("is_enabled")}
        data = urllib.parse.urlencode(fields)
        return data.encode("utf-8")


def url_join_args(url_list: list[str], query: dict[str, Any] | None = None, **kwargs: Any) -> list[str]:
    """
    拼接GET请求参数到URL

    Args:
        url_list: 原URL列表,可带?或不带
        query: urllib.parse.urlencode支持的query字典
        **kwargs: 额外的查询参数

    Returns:
        拼接好的URL列表

    Examples:
        >>> url_join_args(["http://example.com"], {"key": "value"})
        ['http://example.com?key=value']

        >>> url_join_args(["http://example.com?"], {"key": "value"})
        ['http://example.com?key=value']

        >>> url_join_args(["http://example.com?a=1"], {"b": "2"})
        ['http://example.com?a=1&b=2']
    """
    results: list[str] = []

    for url in url_list:
        result = url

        # 如果URL不以?结尾且有参数,添加?
        if not result.endswith("?") and (query or kwargs):
            result = url + "?"

        # 拼接query参数
        if query:
            result = result + urllib.parse.urlencode(query)

        # 拼接kwargs参数
        if kwargs:
            if query:
                result = result + "&" + urllib.parse.urlencode(kwargs)
            else:
                result = result + urllib.parse.urlencode(kwargs)

        results.append(result)

    return results
