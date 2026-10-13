from abc import ABC
from collections.abc import Mapping
from typing import Any, ClassVar, Literal
from urllib.parse import urljoin

from typing_extensions import override

from bk_monitor_base.config import Config
from bk_monitor_base.infras.constant import SPACE_UID_HYPHEN
from bk_monitor_base.infras.third_party_api.api_client import BkApiClient, UserParams
from bk_monitor_base.infras.third_party_api.errors import BkApiError
from bk_monitor_base.infras.threading.local import get_local_param, get_request


def get_unify_query_url(space_uid: str, config: Config) -> str:
    """
    根据空间ID获取统一查询的URL

    Args:
        space_uid: 空间UID
        config: 配置对象

    Returns:
        str: 统一查询的URL
    """
    # 获取unify_query模块的配置
    unify_query_config = config.blueking.api_configs.get("unify_query")

    # 如果有自定义URL，直接返回
    if unify_query_config and unify_query_config.custom_api_url:
        return str(unify_query_config.custom_api_url).rstrip("/")

    # 默认URL（从配置中获取，如果没有则使用空字符串）
    default_url = getattr(config, "unify_query_url", "")

    if not space_uid:
        return default_url

    # 获取路由规则（从配置中获取，如果没有则使用空列表）
    space_type, space_id = space_uid.split(SPACE_UID_HYPHEN, 1)
    for routing_rule in config.blueking.unify_query.routing_rules:
        url = routing_rule.url
        if not url:
            continue

        match_keys: dict[Literal["space_type", "space_id", "space_uid"], str] = {
            "space_type": space_type,
            "space_id": space_id,
            "space_uid": space_uid,
        }

        for key, value in match_keys.items():
            match_values: list[str | int] | int | str | None = getattr(routing_rule, key)
            if not match_values:
                continue

            if not isinstance(match_values, list):
                match_values = [str(match_values)]
            match_values = [str(v) for v in match_values]
            if str(value) not in match_values:
                break
        else:
            return str(url)

    return default_url


class UnifyQueryApiClient(BkApiClient, ABC):
    """统一查询 API Client

    UnifyQuery 是一个特殊的API，它不走标准的ESB/APIGW网关，而是直接请求独立部署的服务。
    因此需要重写部分方法来适配其特殊的请求逻辑。
    """

    abstract_class: ClassVar[bool] = True

    module_name: ClassVar[str] = "unify_query"

    # UnifyQuery 不使用标准的ESB/APIGW路径，这里设置为空
    esb_base_url: ClassVar[str] = ""
    esb_path: ClassVar[str] = ""
    apigw_base_url: ClassVar[str] = ""
    apigw_path: ClassVar[str] = ""

    # UnifyQuery 使用自定义的路径
    unify_query_path: ClassVar[str] = ""

    @override
    def _get_api_url(self, params: dict[str, Any]) -> str:
        """
        获取API URL（重写以支持UnifyQuery的自定义路由逻辑）

        Args:
            params: 请求参数

        Returns:
            str: 完整的API URL
        """
        # 从参数中提取space_uid
        space_uid = ""
        if "space_uid" in params:
            space_uid = params.get("space_uid", "")

        # TODO: 后续可能存在多业务查询的情况，此时需要根据第一个业务ID获取空间UID

        # 获取UnifyQuery的基础URL
        base_url = get_unify_query_url(space_uid, self.config)

        # 拼接完整URL
        if not base_url:
            raise BkApiError(
                module=self.module_name,
                action=self.action,
                method=self.method,
                url="",
                message="UnifyQuery URL not configured",
            )

        # 使用unify_query_path而不是apigw_path
        path = self.unify_query_path.lstrip("/")

        # 路径参数渲染
        path_keys = self._parse_path_format_keys(path)
        rendered_path = self._format_path(path, path_keys, params)

        return urljoin(base_url.rstrip("/") + "/", rendered_path)

    @override
    def get_headers(self, bk_tenant_id: str, user_params: UserParams) -> dict[str, str]:
        """
        获取请求头（重写以支持UnifyQuery的自定义请求头）

        Args:
            bk_tenant_id: 租户ID
            user_params: 用户参数

        Returns:
            dict: 请求头字典
        """
        headers: dict[str, str] = {"Content-Type": "application/json"}

        # 设置租户ID
        if bk_tenant_id:
            headers["X-Bk-Tenant-Id"] = bk_tenant_id

        # 设置查询来源
        request = get_request()
        source = "backend"

        if request and hasattr(request, "user") and hasattr(request.user, "username"):
            username = request.user.username
            if username:
                source = f"username:{username}"
        elif get_local_param("strategy_id", None):
            source = f"strategy:{get_local_param('strategy_id')}"

        headers["Bk-Query-Source"] = source

        return headers

    @override
    def handle_params(self, params: dict[str, Any]) -> dict[str, Any]:
        """
        处理请求参数（重写以支持UnifyQuery的特殊参数处理）

        Args:
            params: 原始请求参数

        Returns:
            dict: 处理后的请求参数
        """
        # 调用父类方法
        params = super().handle_params(params)

        # 从参数中提取space_uid用于设置请求头
        space_uid = params.get("space_uid", "")

        # 将space_uid存储到params中，供_get_api_url使用
        if space_uid:
            params["_space_uid"] = space_uid

        return params

    @override
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
        发送请求（重写以支持UnifyQuery的特殊请求逻辑）

        Args:
            bk_tenant_id: 租户ID
            user_params: 用户参数
            params: 请求参数
            stream: 是否流式请求
            verify: 是否验证SSL
            timeout: 超时时间

        Returns:
            Any: 响应结果
        """
        import copy

        params = self.handle_params(copy.deepcopy(dict(params)))

        # 提取space_uid用于设置请求头
        space_uid = params.pop("_space_uid", "")

        # 获取请求头
        headers = self.get_headers(bk_tenant_id=bk_tenant_id, user_params=user_params)

        # 设置空间相关的请求头
        if space_uid is None:
            # 跨业务查询
            headers["X-Bk-Scope-Skip-Space"] = self.config.blueking.app_code
        elif space_uid:
            headers["X-Bk-Scope-Space-Uid"] = space_uid

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
            kwargs["params"] = params
        elif self.method.upper() in ["POST", "PUT", "PATCH"]:
            kwargs["json"] = params
        elif self.method.upper() in ["DELETE", "HEAD"]:
            kwargs["params"] = params
        else:
            raise ValueError(f"unsupported request method: {self.method}")

        # 发送请求
        response = self.session.request(**kwargs)

        # 处理响应
        return self.handle_response(response)


class PromqlToStruct(UnifyQueryApiClient):
    """
    PromQL转结构化查询参数
    """

    action: ClassVar[str] = "promql_to_struct"
    method: ClassVar[str] = "POST"
    unify_query_path: ClassVar[str] = "/query/ts/promql_to_struct"


class StructToPromql(UnifyQueryApiClient):
    """
    结构化查询参数转PromQL
    """

    action: ClassVar[str] = "struct_to_promql"
    method: ClassVar[str] = "POST"
    unify_query_path: ClassVar[str] = "/query/ts/struct_to_promql"


class QueryDataByPromql(UnifyQueryApiClient):
    """使用PromQL查询数据"""

    action: ClassVar[str] = "query_data_by_promql"
    method: ClassVar[str] = "POST"
    unify_query_path: ClassVar[str] = "/query/ts/promql"


class GetDimensionData(UnifyQueryApiClient):
    """
    获取维度数据
    """

    action: ClassVar[str] = "get_dimension_data"
    method: ClassVar[str] = "POST"
    unify_query_path: ClassVar[str] = "/query/ts/info/{info_type}"


# 实例化客户端对象
promql_to_struct_client = PromqlToStruct()
struct_to_promql_client = StructToPromql()
query_data_by_promql_client = QueryDataByPromql()
get_dimension_data_client = GetDimensionData()
