import copy
import json
import logging
import math
from abc import ABC
from collections.abc import Mapping
from concurrent.futures import Future, ThreadPoolExecutor, as_completed
from enum import Enum
from string import Formatter
from typing import Any, ClassVar, Literal, Protocol, TypedDict, cast, runtime_checkable

import requests

from bk_monitor_base.config import Config, get_config

from .errors import BkApiError
from .user.api import get_tenant_admin_username

logger = logging.getLogger(__name__)


class BkApiMode(Enum):
    """
    蓝鲸API模式
    """

    ESB = "esb"
    APIGW = "apigw"


@runtime_checkable
class BkApiClientProtocol(Protocol):
    """协议类：定义必需的类属性"""

    # 模块名称
    module_name: ClassVar[str]

    # 操作名称
    action: ClassVar[str]

    # 请求方法
    method: ClassVar[str]

    # 操作子路径
    esb_path: ClassVar[str]
    apigw_path: ClassVar[str]

    # 基础路径
    esb_base_url: ClassVar[str]
    apigw_base_url: ClassVar[str]

    # 仅当esb与apigw请求方法不一致时才需要单独定义
    esb_method: ClassVar[str | None]
    apigw_method: ClassVar[str | None]

    # 请求控制参数
    timeout: ClassVar[int]
    verify: ClassVar[bool]


class BkUsername(TypedDict):
    bk_username: str


class AccessToken(TypedDict):
    access_token: str


class BkToken(TypedDict):
    bk_token: str


# 用户参数
UserParams = BkUsername | AccessToken | BkToken


class BkApiClient(BkApiClientProtocol, ABC):
    """
    API客户端基类
    """

    verify: ClassVar[bool] = False
    timeout: ClassVar[int] = 60
    esb_method: ClassVar[str | None] = None
    apigw_method: ClassVar[str | None] = None

    def __init_subclass__(cls) -> None:
        """
        子类定义检查
        """
        super().__init_subclass__()

        # 抽象类跳过校验
        if getattr(cls, "abstract_class", False):
            return

        if not hasattr(cls, "module_name") or not cls.module_name:
            raise NotImplementedError("必须定义 module_name 属性")

        if getattr(cls, "method", None) not in {"GET", "POST", "DELETE"}:
            raise NotImplementedError("必须定义 method 属性，并且值必须是 'GET'、'POST' 或 'DELETE'")

        if not getattr(cls, "esb_base_url", None) and not getattr(cls, "apigw_base_url", None):
            raise NotImplementedError("必须定义 esb_base_url 或 apigw_base_url 属性")

        if getattr(cls, "esb_base_url", None) and not getattr(cls, "esb_path", None):
            raise NotImplementedError("在 esb_base_url 定义时，必须定义 esb_path 属性")

        if getattr(cls, "apigw_base_url", None) and not getattr(cls, "apigw_path", None):
            raise NotImplementedError("在 apigw_base_url 定义时，必须定义 apigw_path 属性")

    def __init__(
        self,
        *,
        bk_app_code: str | None = None,
        bk_app_secret: str | None = None,
        bk_api_url: str | None = None,
        config: Config | None = None,
    ) -> None:
        self.config: Config = config or get_config()

        if bk_app_code and bk_app_secret and bk_api_url:
            self.bk_app_code = bk_app_code
            self.bk_app_secret = bk_app_secret
            self.bk_api_url = bk_api_url
        else:
            self.bk_app_code: str = self.config.blueking.app_code
            self.bk_app_secret: str = self.config.blueking.app_secret
            self.bk_api_url: str = str(self.config.blueking.api_url)

        # 解析路径中的参数
        self.esb_path_keys: list[str] = self._parse_path_format_keys(self.esb_path) if self.esb_path else []
        self.apigw_path_keys: list[str] = self._parse_path_format_keys(self.apigw_path) if self.apigw_path else []

        self.session: requests.Session = requests.Session()

    def _parse_path_format_keys(self, path: str) -> list[str]:
        """
        解析路径中的参数
        """
        keys: set[str] = set()
        for v in Formatter().parse(path):
            # 跳过空值
            if v[1] is None:
                continue

            # 路径参数必须具名
            if v[1] == "":
                raise ValueError(
                    f"parse path template error: module: {self.module_name} action: {self.action} path: {path}, path template field cannot be empty"
                )
            keys.add(v[1])
        return list(keys)

    def _format_path(self, path: str, keys: list[str], params: dict[str, Any]) -> str:
        """
        路径渲染
        """
        # 如果没有需要替换的参数，直接返回原始路径
        if not keys:
            return path

        # 收集路径参数
        context: dict[str, Any] = {}
        for key in keys:
            # 检查是否缺少路径参数
            if key not in params:
                raise BkApiError(
                    module=self.module_name,
                    action=self.action,
                    method=self.method,
                    url=path,
                    message=f"Missing path parameter: {key}",
                )

            # 默认会将路径参数从params中移除
            context[key] = params.pop(key)
        return path.format(**context)

    def get_headers(self, bk_tenant_id: str, user_params: UserParams) -> dict[str, str]:
        """
        获取请求头
        """
        auth_params: dict[str, Any] = {
            "bk_app_code": self.bk_app_code,
            "bk_app_secret": self.bk_app_secret,
            **user_params,
        }

        # 非多租户情况下，网关请求默认使用 default
        if not self.config.blueking.enable_multi_tenancy:
            bk_tenant_id = "default"

        return {
            "X-Bk-Tenant-Id": bk_tenant_id,
            "Content-Type": "application/json",
            "X-Bkapi-Authorization": json.dumps(auth_params),
        }

    def handle_response(self, response: requests.Response) -> Any:
        """响应结果处理

        Args:
            response (requests.Response): 请求响应对象
        """

        request_url = response.request.url or ""

        # 检查响应状态
        try:
            response.raise_for_status()
        except requests.HTTPError:
            logger.error(
                f"BkApiError [Module: {self.module_name}][Action: {self.action}][Status Code: {response.status_code}] get error: {response.text}",
                extra=dict(module_name=self.module_name, url=request_url),
            )
            raise BkApiError(
                module=self.module_name,
                action=self.action,
                status_code=response.status_code,
                method=self.method,
                url=request_url,
                message=response.text,
            )

        # 尝试解析响应内容
        try:
            result: dict[str, Any] = response.json()
        except requests.JSONDecodeError as e:
            logger.error(
                f"BkApiError [Module: {self.module_name}][Action: {self.action}] get error: {str(e)}",
                extra=dict(module_name=self.module_name, url=request_url),
            )
            raise BkApiError(
                module=self.module_name, action=self.action, method=self.method, url=request_url, message=str(e)
            )

        # 如果响应结果没有result字段，直接返回
        if "result" not in result:
            return result

        # 如果有result字段，且result为True，则返回结果
        if result["result"]:
            return result

        # 如果有result字段，且result为False，则抛出错误
        msg = result.get("message", "") or result.get("bk_error_msg", "") or str(result)
        request_id: Any | str = result.pop("request_id", "") or response.headers.get("x-bkapi-request-id", "")
        logger.error(
            f"BkApiError [Module: {self.module_name}][Action: {self.action}]({request_id}) get error: {msg}",
            extra=dict(module_name=self.module_name, url=request_url),
        )
        raise BkApiError(
            module=self.module_name,
            action=self.action,
            method=self.method,
            url=request_url,
            message=msg,
            third_api_error_code=str(result.get("code", "")) or None,
        )

    def handle_params(self, params: dict[str, Any]) -> dict[str, Any]:
        """处理请求参数"""
        return params

    @staticmethod
    def _get_nested_value(data: dict[str, Any] | list[Any], key_path: str, default: Any = None) -> Any:
        """从嵌套字典中提取值，支持键路径（如 'data.list'）

        Args:
            data: 数据（通常是字典，但也可能是其他类型）
            key_path: 键路径，支持点号分隔的嵌套键
            default: 默认值

        Returns:
            提取的值，如果不存在则返回默认值
        """
        # 这里用 Mapping 做类型收敛，避免静态检查出现 Unknown 推断
        if not isinstance(data, Mapping):
            return default

        keys = key_path.split(".")
        value: Any = data
        for key in keys:
            if not isinstance(value, Mapping):
                return default

            mapping = cast(Mapping[str, Any], value)
            if key not in mapping:
                return default
            value = mapping[key]
        return value

    @staticmethod
    def _set_nested_value(data: dict[str, Any], key_path: str, value: Any) -> None:
        """向嵌套字典写入值，支持点号路径（如 'pagination.page'）。

        说明：
            该方法用于“写入”场景，与 `_get_nested_value` 对应。
            当中间节点不存在时会自动创建 dict；若中间节点已存在但不是 dict，
            为避免隐式覆盖导致请求参数异常，将抛出 ValueError。

        Args:
            data: 目标字典（会被原地修改）
            key_path: 键路径，使用 "." 分隔
            value: 要写入的值

        Raises:
            ValueError: key_path 为空、包含空 key，或中间节点类型冲突。
        """
        if not key_path:
            raise ValueError("key_path cannot be empty")

        keys = key_path.split(".")
        if any(not k for k in keys):
            raise ValueError(f"invalid key_path: {key_path}")

        current: dict[str, Any] = data
        for key in keys[:-1]:
            existed = current.get(key)
            if existed is None:
                current[key] = {}
                existed = current[key]
            if not isinstance(existed, dict):
                raise ValueError(f"cannot set nested value, key '{key}' is not a dict in key_path: {key_path}")
            current = cast(dict[str, Any], existed)
        current[keys[-1]] = value

    @classmethod
    def _set_value_by_key_path(cls, data: dict[str, Any], key_path: str, value: Any) -> None:
        """根据 key_path 写入值，兼容扁平 key 与点号嵌套 key。

        Args:
            data: 目标字典（会被原地修改）
            key_path: 键名或点号路径（如 "page" 或 "pagination.page"）
            value: 写入的值
        """
        if "." in key_path:
            cls._set_nested_value(data, key_path, value)
        else:
            data[key_path] = value

    @staticmethod
    def _split_request_data(
        data: dict[str, Any],
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        """切分请求参数为文件/非文件类型"""
        file_data: dict[str, Any] = {}
        non_file_data: dict[str, Any] = {}
        for request_param, param_value in list(data.items()):
            if hasattr(param_value, "read"):
                # 一般认为含有read属性的为文件类型
                file_data[request_param] = param_value
            else:
                non_file_data[request_param] = param_value
        return non_file_data, file_data

    def _get_api_mode(self) -> BkApiMode:
        """
        获取API模式

        Returns:
            BkApiMode: API模式
        """
        # 如果启用多租户，必须使用apigw
        if self.config.blueking.enable_multi_tenancy:
            return BkApiMode.APIGW

        module_config = self.config.blueking.api_configs.get(self.module_name)
        mode = BkApiMode(module_config.mode) if module_config else None

        # 如果未指定模式，则根据URL自动判断，优先使用esb
        if mode is None:
            if self.esb_base_url:
                mode = BkApiMode.ESB
            else:
                mode = BkApiMode.APIGW

        return mode

    def get_api_mode(self) -> BkApiMode:
        """返回当前客户端使用的 API 模式。"""
        return self._get_api_mode()

    def _get_api_url(self, params: dict[str, Any]) -> str:
        """
        获取API URL
        """
        api_config = self.config.blueking.api_configs.get(self.module_name)

        # 获取自定义API地址
        custom_base_url: str | None = (
            str(api_config.custom_api_url) if api_config and api_config.custom_api_url else None
        )

        # 判断使用esb还是apigw
        url_parts: list[str] = []
        if self._get_api_mode() == BkApiMode.ESB:
            if custom_base_url:
                url_parts.append(custom_base_url.rstrip("/"))
            else:
                url_parts.extend([self.bk_api_url.rstrip("/"), self.esb_base_url.strip("/")])
            url_parts.append(self.esb_path)
            path_keys = self.esb_path_keys
        else:
            if custom_base_url:
                url_parts.append(custom_base_url.rstrip("/"))
            else:
                url_parts.extend([self.bk_api_url.rstrip("/"), self.apigw_base_url.strip("/")])
            url_parts.append(self.apigw_path)
            path_keys = self.apigw_path_keys

        # url拼接
        api_url = "/".join(part for part in url_parts if part)

        # 路径参数渲染
        return self._format_path(api_url, path_keys, params)

    def request(
        self,
        *,
        bk_tenant_id: str,
        user_params: UserParams,
        params: Mapping[str, Any],
        stream: bool = False,
        verify: bool | None = None,
        timeout: int | None = None,
    ) -> Any:
        """
        发送请求

        Args:
            bk_tenant_id: 蓝鲸租户ID
            user_params: 用户自定义请求参数
            params: 请求参数
            stream: 是否以流式方式请求
            verify: 是否验证SSL证书
            timeout: 请求超时时间
        """
        params = self.handle_params(copy.deepcopy(dict(params)))
        headers = self.get_headers(bk_tenant_id=bk_tenant_id, user_params=user_params)

        # 设置请求超时时间和ssl验证
        if timeout is None:
            timeout = self.timeout
        if verify is None:
            verify = self.verify

        # 请求参数
        kwargs: dict[str, Any] = {
            "method": self.method.lower(),
            "url": self._get_api_url(params),
            "verify": verify,
            "stream": stream,
            "timeout": timeout,
            "headers": headers,
        }

        # 按照请求方法设置参数
        if self.method.upper() == "GET":
            kwargs.update({"params": params})
        elif self.method.upper() == "POST":
            # 处理文件和非文件数据
            no_file_data, file_data = self._split_request_data(params)
            if file_data:
                kwargs.update({"files": file_data, "data": no_file_data})
            else:
                kwargs.update({"json": no_file_data})
        else:
            raise ValueError(f"unsupported request method: {self.method}")

        # 发送请求
        response = self.session.request(**kwargs)

        # 处理响应
        return self.handle_response(response)

    def batch_request(
        self,
        *,
        bk_tenant_id: str,
        user_params: UserParams | None = None,
        params: Mapping[str, Any] | None = None,
        batch_size: int = 500,
        concurrent_count: int = 5,
        pagination_mode: Literal["page", "offset"],
        first_page_or_start_value: int,
        page_or_offset_key: str,
        page_size_or_limit_key: str,
        total_key: str,
        data_list_key: str,
        verify: bool | None = None,
        timeout: int | None = None,
        total_limit: int | None = None,
        ignore_partial_error: bool = False,
    ) -> tuple[bool, list[Any], int]:
        """批量请求

        批量请求接口，用于需要分页请求的情况。

        支持两种分页模式(pagination_mode):
            page模式: page/page_size: 页数/单页数量
            offset模式: offset/limit: 偏移量/限制数量

        使用前需要确认以下信息:
            1. 分页参数的key名是什么, 可以调整page_or_offset_key和page_size_or_limit_key
            2. 分页参数的起始值是多少, 0还是1, 可以调整first_page_or_start_value
            3. 返回数据中如何提取总数的key名和数据列表的key名是什么, 可以调整total_key和data_list_key

        Args:
            bk_tenant_id: 蓝鲸租户ID
            user_params: 用户自定义请求参数
            params: 请求参数
            batch_size: 分页大小
            concurrent_count: 并发数
            total_limit: 限制返回的最大记录数，如果为 None，则返回所有记录
            pagination_mode: 分页模式(page/offset), page是指page/page_size, offset是指offset/limit
            first_page_or_start_value: 首次请求的页数或起始值
            page_or_offset_key: 页数/偏移量键，支持点号路径（如 "pagination.page"）
            page_size_or_limit_key: 单页数量/limit键，支持点号路径（如 "pagination.page_size"）
            total_key: 总数键
            data_list_key: 数据列表键
            verify: 是否验证SSL证书
            timeout: 请求超时时间
            ignore_partial_error: 是否忽略部分错误，如果不忽略，则会抛出异常

        Returns:
            1. 是否完全成功（所有请求都成功）
            2. 合并后的数据列表
            3. 总数

        Examples:
            >>> client = MyApiClient()
            >>> data = client.batch_request(
            ...     bk_tenant_id="system",
            ...     params={"filter": "active"},
            ...     pagination_mode="page",
            ...     first_page_or_start_value=1,
            ...     page_or_offset_key="page",
            ...     page_size_or_limit_key="page_size",
            ...     total_key="total",
            ...     data_list_key="list",
            ... )
            >>> print(f"获取到 {len(data)} 条记录")
        """
        # 参数处理和默认值设置
        if user_params is None:
            user_params = {"bk_username": get_tenant_admin_username(bk_tenant_id=bk_tenant_id)}

        if params is None:
            params = {}

        if batch_size <= 0:
            raise ValueError(f"batch_size must be positive, got {batch_size}")
        if concurrent_count <= 0:
            raise ValueError(f"concurrent_count must be positive, got {concurrent_count}")

        mode = (pagination_mode or "").lower()
        if mode not in {"page", "offset"}:
            raise ValueError(f"unsupported pagination_mode: {pagination_mode}")

        # 深拷贝参数避免修改原始参数
        base_params = copy.deepcopy(dict(params))

        # 首次请求：直接按 batch_size 拉取第一页数据，并同时获取总数
        # 这样在数据量不大的情况下，可以只用一次请求完成。
        first_params = copy.deepcopy(base_params)
        self._set_value_by_key_path(first_params, page_or_offset_key, first_page_or_start_value)
        self._set_value_by_key_path(first_params, page_size_or_limit_key, batch_size)

        try:
            first_response = self.request(
                bk_tenant_id=bk_tenant_id,
                user_params=user_params,
                params=first_params,
                verify=verify,
                timeout=timeout,
            )
        except Exception as e:
            logger.error(
                f"BkApiError [Module: {self.module_name}][Action: {self.action}] batch_request first request failed: {str(e)}",
                extra=dict(module_name=self.module_name),
            )
            raise

        # 从响应中提取第一页数据
        first_data_list = self._get_nested_value(first_response, data_list_key, [])
        if not isinstance(first_data_list, list):
            first_data_list = []

        # 从响应中提取总数（如果缺失则为 None）
        total = self._get_nested_value(first_response, total_key, None)

        if total is None:
            # 无法获知总数：退化为仅返回第一页数据（并应用 total_limit）
            data = cast(list[Any], first_data_list if total_limit is None else first_data_list[:total_limit])
            # total_key 缺失时，为了保持返回值稳定，这里使用当前返回的数据量作为 total
            return True, data, len(data)

        raw_total = int(total)
        if raw_total <= 0:
            # 总数为0：直接返回第一页数据（通常为空），避免额外请求
            return True, [], 0

        # 计算实际需要返回的数据量
        actual_total = min(raw_total, total_limit) if total_limit is not None else raw_total
        if actual_total <= 0:
            return True, [], raw_total

        total_pages = math.ceil(actual_total / batch_size)

        def _build_remaining_request_index_list() -> list[int]:
            """构建需要额外请求的页码/offset 列表（按顺序，已排除第一页）。"""
            if total_pages <= 1:
                return []
            if mode == "page":
                # page 模式下：第一页为 first_page_or_start_value，后续从 +1 开始
                return [first_page_or_start_value + i for i in range(1, total_pages)]
            # offset 模式下：第一页从 first_page_or_start_value 开始，后续按 batch_size 增加
            start_offset = first_page_or_start_value
            return [start_offset + i * batch_size for i in range(1, total_pages)]

        first_index = first_page_or_start_value
        remaining_indices = _build_remaining_request_index_list()
        request_indices_in_order = [first_index, *remaining_indices]

        # 单页：直接返回首次请求的数据即可
        if total_pages <= 1:
            return True, cast(list[Any], first_data_list[:actual_total]), raw_total

        # 并发请求所有页面
        all_data: list[Any] = []
        overall_success = True

        # 使用线程池并发请求剩余页面（第一页已由首次请求获得）
        with ThreadPoolExecutor(max_workers=concurrent_count) as executor:
            futures: dict[Future[Any], int] = {}

            for index in remaining_indices:
                page_params = copy.deepcopy(base_params)
                self._set_value_by_key_path(page_params, page_or_offset_key, index)
                self._set_value_by_key_path(page_params, page_size_or_limit_key, batch_size)

                future = executor.submit(
                    self.request,
                    bk_tenant_id=bk_tenant_id,
                    user_params=user_params,
                    params=page_params,
                    verify=verify,
                    timeout=timeout,
                )
                futures[future] = index

            # 收集结果，使用字典按页面顺序存储（包含第一页）
            page_results: dict[int, list[Any]] = {first_index: first_data_list}
            for future in as_completed(futures):
                index = futures[future]
                try:
                    response = future.result()
                    data_list = self._get_nested_value(response, data_list_key, [])
                    if isinstance(data_list, list):
                        page_results[index] = data_list
                except Exception as e:
                    if not ignore_partial_error:
                        # 不忽略部分失败：直接抛出，交由上层处理
                        raise

                    overall_success = False
                    logger.warning(
                        f"BkApiError [Module: {self.module_name}][Action: {self.action}] batch_request index {index} failed: {str(e)}",
                        extra=dict(module_name=self.module_name, index=index, pagination_mode=mode),
                    )
                    # 单个页面失败不中断整个流程，继续处理其他页面

            # 按页面顺序合并结果
            for index in request_indices_in_order:
                if index in page_results:
                    all_data.extend(page_results[index])

        # 应用 total_limit 限制
        all_data = all_data[:actual_total]

        return overall_success, all_data, raw_total

    def __call__(
        self,
        *,
        bk_tenant_id: str,
        user_params: UserParams | None = None,
        params: Mapping[str, Any] | None = None,
    ) -> Any:
        """
        发起请求
        """

        # 如果未提供用户参数，则使用租户管理员用户名
        user_params = user_params or {"bk_username": get_tenant_admin_username(bk_tenant_id=bk_tenant_id)}

        # 发送请求
        response = self.request(bk_tenant_id=bk_tenant_id, user_params=user_params, params=params or {})
        return response
