from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Literal, NotRequired, TypedDict

from .client import (
    count_instance_associations_client,
    execute_dynamic_group_client,
    find_host_biz_relation_client,
    find_instance_association_client,
    find_object_association_client,
    find_topo_node_path_client,
    get_dynamic_group_client,
    get_mainline_object_topo_client,
    list_biz_hosts_client,
    list_biz_hosts_topo_client,
    list_hosts_without_biz_client,
    list_service_instance_client,
    list_service_template_client,
    list_set_template_client,
    resource_watch_client,
    search_biz_inst_topo_client,
    search_business_client,
    search_cloud_area_client,
    search_dynamic_group_client,
    search_inst_client,
    search_instance_associations_client,
    search_module_client,
    search_object_attribute_client,
    search_objects_client,
    search_set_client,
)
from .entity import (
    Biz,
    BizList,
    Host,
    HostList,
    InstanceAssociationList,
    Module,
    ModuleList,
    ObjectAssociationList,
    ObjectInstList,
    ObjectModel,
    ServiceTemplate,
    Set,
    SetList,
    SetTemplate,
)
from .ip_utils import exploded_ip, is_v6, split_inner_host


class PageParams(TypedDict, total=False):
    """页面参数类型定义

    Attributes:
        start: 起始位置，从0开始
        limit: 每页数量限制，最大200
        sort: 排序字段，可选参数。通过在字段前面增加 -，如 sort:"-field" 可以表示按照字段 field降序
    """

    start: int
    limit: int
    sort: NotRequired[str]


class PropertyRule(TypedDict, total=False):
    """业务属性查询规则

    Attributes:
        field: 字段名
        operator: 操作符，如 equal, in, not_in 等
        value: 字段值
        condition: 聚合条件，如 AND, OR（当rules嵌套时使用）
        rules: 嵌套规则列表（支持最多3层嵌套）
    """

    field: NotRequired[str]
    operator: NotRequired[str]
    value: NotRequired[Any]
    condition: NotRequired[Literal["AND", "OR"]]
    rules: NotRequired[list["PropertyRule"]]


def format_ip_filter_rule(ips: list[str]) -> list[PropertyRule]:
    """
    格式化 IP 过滤规则，区分 IPv4 和 IPv6
    :param ips: IP 列表
    :return: 过滤规则列表
    """
    filter_rules: list[PropertyRule] = []
    ipv4_list = []
    ipv6_list = []
    for ip in ips:
        if is_v6(ip):
            ipv6_list.append(exploded_ip(ip))  # noqa: F821
        else:
            ipv4_list.append(ip)
    if ipv4_list:
        filter_rules.append(PropertyRule(field="bk_host_innerip", operator="in", value=ipv4_list))
    if ipv6_list:
        filter_rules.append(PropertyRule(field="bk_host_innerip_v6", operator="in", value=ipv6_list))
    return filter_rules


class BizPropertyFilter(TypedDict):
    """业务属性组合查询条件

    Attributes:
        condition: 聚合条件，AND 或 OR
        rules: 规则列表，最多20个规则，支持最多3层嵌套，数组类元素个数不超过500个

    Note:
        - rules 数量不超过20个
        - 嵌套层级不超过3层
        - 涉及到的数组类元素个数不超过500个
    """

    condition: Literal["AND", "OR"]
    rules: list[PropertyRule]


class TimeRule(TypedDict):
    """时间查询规则

    Attributes:
        field: 时间字段名，如 create_time, last_time 等
        start: 开始时间，格式: YYYY-MM-DD HH:MM:SS
        end: 结束时间，格式: YYYY-MM-DD HH:MM:SS
    """

    field: str
    start: str
    end: str


class TimeCondition(TypedDict):
    """按时间查询业务的查询条件

    Attributes:
        oper: 操作符，目前只支持 and
        rules: 时间查询条件列表
    """

    oper: Literal["and"]
    rules: list[TimeRule]


class SearchBusinessParams(TypedDict, total=False):
    """查询业务的参数类型定义

    Attributes:
        bk_supplier_account: 开发商账号，可选
        fields: 指定查询的字段，参数为业务的任意属性，如果不填写字段信息，系统会返回业务的所有字段
        condition: 查询条件（历史遗留字段，请勿继续使用，请用biz_property_filter）
        biz_property_filter: 业务属性组合查询条件，与condition两个参数只能有一个生效
        time_condition: 按时间查询业务的查询条件
        page: 分页条件

    Note:
        - 业务分为两类：未归档的业务和已归档的业务
        - 若要查询已归档的业务，请在condition中增加条件 bk_data_status:disabled
        - 若要查询未归档的业务，请不要带字段"bk_data_status"，或者在condition中增加条件 bk_data_status: {"$ne":"disabled"}
        - biz_property_filter 与 condition 两个参数只能有一个生效，参数 condition 不建议继续使用
    """

    bk_supplier_account: NotRequired[str]
    fields: NotRequired[list[str]]
    condition: NotRequired[dict[str, Any]]
    biz_property_filter: NotRequired[BizPropertyFilter]
    time_condition: NotRequired[TimeCondition]
    page: NotRequired[PageParams]


class SetPropertyFilter(TypedDict):
    """集群属性组合查询条件

    Attributes:
        condition: 聚合条件，AND 或 OR
        rules: 规则列表，最多20个规则，支持最多3层嵌套，数组类元素个数不超过500个

    Note:
        - rules 数量不超过20个
        - 嵌套层级不超过3层
        - 涉及到的数组类元素个数不超过500个
    """

    condition: Literal["AND", "OR"]
    rules: list[PropertyRule]


class HostPropertyFilter(TypedDict):
    """主机属性组合查询条件

    Attributes:
        condition: 聚合条件，AND 或 OR
        rules: 规则列表，最多20个规则，支持最多2层嵌套，数组类元素个数不超过500个

    Note:
        - rules 数量不超过20个
        - 嵌套层级最多2层
        - 涉及到的数组类元素个数不超过500个
    """

    condition: Literal["AND", "OR"]
    rules: list[PropertyRule]


class SetCondition(TypedDict):
    """集群查询条件

    Attributes:
        field: 取值为集群的字段
        operator: 取值为：$eq $ne
        value: field配置的集群字段所对应的值
    """

    field: str
    operator: Literal["$eq", "$ne"]
    value: Any


class ModuleCondition(TypedDict):
    """模块查询条件

    Attributes:
        field: 取值为模块的字段
        operator: 取值为：$eq $ne
        value: field配置的模块字段所对应的值
    """

    field: str
    operator: Literal["$eq", "$ne"]
    value: Any


class LabelSelector(TypedDict):
    """Label选择器

    Attributes:
        key: label的key
        operator: 操作符，可选值: =, !=, exists, !, in, notin
        values: label的values列表
    """

    key: str
    operator: Literal["=", "!=", "exists", "!", "in", "notin"]
    values: list[str]


class SearchModuleParams(TypedDict, total=False):
    """查询模块的参数类型定义

    Attributes:
        bk_supplier_account: 开发商账号，可选
        bk_biz_id: 业务ID，必选
        bk_set_id: 集群ID，可选
        fields: 查询字段，字段来自于模块定义的属性字段
        condition: 查询条件，字段来自于模块定义的属性字段
        page: 分页条件

    Note:
        - 当前版本暂不支持 filter 和 time_condition，保持与原接口一致
    """

    bk_supplier_account: NotRequired[str]
    bk_biz_id: int
    bk_set_id: NotRequired[int]
    fields: NotRequired[list[str]]
    condition: NotRequired[dict[str, Any]]
    page: NotRequired[PageParams]


# 默认页面参数
CMDB_API_PAGE_PARAMS: PageParams = {"limit": 100, "start": 0}


def validate_page_params(page: PageParams | None) -> PageParams:
    """验证页面参数

    Args:
        page: 页面参数，如果为None则使用默认值

    Returns:
        验证后的页面参数

    Raises:
        ValueError: 当参数验证失败时抛出
    """
    if page is None:
        return CMDB_API_PAGE_PARAMS.copy()

    # 创建默认参数的副本
    validated_page = CMDB_API_PAGE_PARAMS.copy()

    # 验证并更新start参数
    if "start" in page:
        start = page["start"]
        if start < 0:
            raise ValueError("page['start'] 不能为负数")
        validated_page["start"] = start

    # 验证并更新limit参数
    if "limit" in page:
        limit = page["limit"]
        if limit <= 0:
            raise ValueError("page['limit'] 必须大于0")
        validated_page["limit"] = limit

    # 验证并更新sort参数（可选）
    if "sort" in page:
        sort = page["sort"]
        if not sort.strip():
            raise ValueError("page['sort'] 不能为空字符串")
        validated_page["sort"] = sort.strip()

    return validated_page


def search_business(
    bk_tenant_id: str,
    fields: list[str] | None = None,
    bk_supplier_account: str | None = None,
    condition: dict[str, Any] | None = None,
    biz_property_filter: BizPropertyFilter | None = None,
    time_condition: TimeCondition | None = None,
    page: PageParams | None = None,
    **kwargs: Any,
) -> tuple[int, BizList]:
    """查询业务（权限：业务查询权限）

    Args:
        bk_tenant_id: 租户ID
        fields: 指定查询的字段，参数为业务的任意属性。如果不填写字段信息，系统会返回业务的所有字段
        bk_supplier_account: 开发商账号（可选）
        condition: 查询条件，参数为业务的任意属性。如果不写代表搜索全部数据
                  （历史遗留字段，请勿继续使用，请用biz_property_filter）
        biz_property_filter: 业务属性组合查询条件。与condition两个参数只能有一个生效
        time_condition: 按时间查询业务的查询条件
        page: 分页条件，包含 start（记录开始位置）、limit（每页限制条数，最大200）、
              sort（排序字段，通过在字段前面增加 -，如 sort:"-field" 可以表��按照字段 field 降序）

    Returns:
        tuple[int, BizList]: (业务总数, 业务列表)
    """
    # 验证互斥参数
    if condition is not None and biz_property_filter is not None:
        raise ValueError("condition 和 biz_property_filter 两个参数只能有一个生效")

    # 验证并处理分页参数
    validated_page = validate_page_params(page) if page is not None else None

    # 构建请求参数
    params: dict[str, Any] = {}

    if fields is not None:
        # 确保必需字段存在
        fields.extend(Biz.get_required_fields())
        params["fields"] = fields

    if bk_supplier_account is not None:
        params["bk_supplier_account"] = bk_supplier_account

    if condition is not None:
        params["condition"] = condition

    if biz_property_filter is not None:
        params["biz_property_filter"] = biz_property_filter

    if time_condition is not None:
        params["time_condition"] = time_condition

    if validated_page is not None:
        params["page"] = validated_page

    params.update(kwargs)

    # 调用API
    api_result = search_business_client(
        bk_tenant_id=bk_tenant_id,
        params=params,
    )

    biz_num = api_result.get("data", {}).get("count", 0)
    biz_list = BizList(api_result.get("data", {}).get("info", []))
    return biz_num, biz_list


def search_set(
    bk_tenant_id: str,
    bk_biz_id: int,
    fields: list[str] | None = None,
    bk_supplier_account: str | None = None,
    condition: dict[str, Any] | None = None,
    set_filter: SetPropertyFilter | None = None,
    time_condition: TimeCondition | None = None,
    page: PageParams | None = None,
    **kwargs: Any,
) -> tuple[int, SetList]:
    """查询集群

    Args:
        bk_tenant_id: 租户ID
        bk_biz_id: 业务ID，必选
        fields: 查询字段，所有字段均为set定义的字段，这些字段包括预置字段，也包括用户自定义字段
        bk_supplier_account: 开发商账号（可选）
        condition: 查询条件（历史遗留字段，请勿继续使用，请用filter）
        set_filter: 属性组合查询条件。与condition两个参数只能有一个生效
        time_condition: 按时间查询模型实例的查询条件
        page: 分页条件，包含 start（记录开始位置）、limit（每页限制条数，最大200）、
              sort（排序字段，通过在字段前面增加 -，如 sort:"-field" 可以表示按照字段 field 降序）

    Returns:
        tuple[int, SetList]: (集群总数, 集群列表)
    """
    # 验证互斥参数
    if condition is not None and set_filter is not None:
        raise ValueError("condition 和 set_filter 两个参数只能有一个生效")

    # 验证并处理分页参数
    validated_page = validate_page_params(page) if page is not None else None

    # 构建请求参数
    params: dict[str, Any] = {"bk_biz_id": bk_biz_id}

    if fields is not None:
        # 确保必需字段存在
        fields.extend(Set.get_required_fields())
        params["fields"] = fields

    if bk_supplier_account is not None:
        params["bk_supplier_account"] = bk_supplier_account

    if condition is not None:
        params["condition"] = condition

    if set_filter is not None:
        params["filter"] = set_filter

    if time_condition is not None:
        params["time_condition"] = time_condition

    if validated_page is not None:
        params["page"] = validated_page

    params.update(kwargs)

    # 调用API
    api_result = search_set_client(
        bk_tenant_id=bk_tenant_id,
        params=params,
    )

    set_num = api_result.get("data", {}).get("count", 0)
    set_list = SetList(api_result.get("data", {}).get("info", []))
    return set_num, set_list


def search_module(
    bk_tenant_id: str,
    bk_biz_id: int,
    bk_set_id: int | None = None,
    fields: list[str] | None = None,
    bk_supplier_account: str | None = None,
    condition: dict[str, Any] | None = None,
    page: PageParams | None = None,
    **kwargs: Any,
) -> tuple[int, ModuleList]:
    """查询模块

    Args:
        bk_tenant_id: 租户ID
        bk_biz_id: 业务ID，必选
        bk_set_id: 集群ID，可选。如果不提供，将查询业务下所有集群的模块
        fields: 查询字段，字段来自于模块定义的属性字段
        bk_supplier_account: 开发商账号（可选）
        condition: 查询条件，字段来自于模块定义的属性字段
        page: 分页条件，包含 start（记录开始位置）、limit（每页限制条数）、sort（排序字段）

    Returns:
        tuple[int, ModuleList]: (模块总数, 模块列表)
    """
    # 验证并处理分页参数
    validated_page = validate_page_params(page) if page is not None else None

    # 构建请求参数
    params: dict[str, Any] = {"bk_biz_id": bk_biz_id}

    if fields is not None:
        # 确保必需字段存在
        fields.extend(Module.get_required_fields())
        params["fields"] = fields

    if bk_supplier_account is not None:
        params["bk_supplier_account"] = bk_supplier_account

    if condition is not None:
        params["condition"] = condition

    if validated_page is not None:
        params["page"] = validated_page

    params.update(kwargs)

    # 如果指定了 bk_set_id，直接查询该集群的模块
    if bk_set_id is not None:
        params["bk_set_id"] = bk_set_id
        api_result = search_module_client(
            bk_tenant_id=bk_tenant_id,
            params=params,
        )
        module_num = api_result.get("data", {}).get("count", 0)
        module_list = ModuleList(api_result.get("data", {}).get("info", []))
        return module_num, module_list

    # 如果未指定 bk_set_id，需要遍历所有集群查询模块
    # 使用 ThreadPoolExecutor 进行并发查询以提升性能
    _, set_list = search_set(bk_tenant_id=bk_tenant_id, bk_biz_id=bk_biz_id)
    bk_set_ids = [s.bk_set_id for s in set_list]

    if not bk_set_ids:
        # 如果没有集群，直接返回空列表
        return 0, ModuleList([])

    def fetch_modules_for_set(set_id: int) -> list[Any]:
        """查询单个集群的模块列表"""
        params_copy = params.copy()
        params_copy["bk_set_id"] = set_id
        try:
            api_result = search_module_client(
                bk_tenant_id=bk_tenant_id,
                params=params_copy,
            )
            return api_result.get("data", {}).get("info", [])
        except Exception:
            # 单个集群查询失败不影响其他集群，返回空列表
            return []

    # 使用线程池并发查询，最大并发数为10（可根据实际情况调整）
    all_modules: list[Any] = []
    max_workers = min(10, len(bk_set_ids))  # 最多10个并发线程

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # 提交所有查询任务
        future_to_set_id = {executor.submit(fetch_modules_for_set, set_id): set_id for set_id in bk_set_ids}

        # 收集查询结果
        for future in as_completed(future_to_set_id):
            modules = future.result()
            all_modules.extend(modules)

    module_num = len(all_modules)
    modules = ModuleList(all_modules)
    return module_num, modules


def list_biz_hosts(
    bk_tenant_id: str,
    bk_biz_id: int,
    page: PageParams | None = None,
    fields: list[str] | None = None,
    bk_set_ids: list[int] | None = None,
    set_cond: list[SetCondition] | None = None,
    bk_module_ids: list[int] | None = None,
    module_cond: list[ModuleCondition] | None = None,
    host_property_filter: HostPropertyFilter | None = None,
    **kwargs: Any,
) -> tuple[int, HostList]:
    """查询业务下的主机（支持多种过滤条件）

    根据业务ID查询业务下的主机，可附带其他的过滤信息，如集群id、模块id等。

    Args:
        bk_tenant_id: 租户ID
        bk_biz_id: 业务ID（必选）
        page: 分页参数，{"start": 0, "limit": 100, "sort": "bk_host_id"}，默认 {"start": 0, "limit": 100}
        fields: 主机属性列表，控制返回结果的主机里有哪些字段，能够加速接口请求和减少网络流量传输
        bk_set_ids: 集群ID列表，最多200条，与set_cond只能使用其中一个
        set_cond: 集群查询条件，与bk_set_ids只能使用其中一个
        bk_module_ids: 模块ID列表，最多500条，与module_cond只能使用其中一个
        module_cond: 模块查询条件，与bk_module_ids只能使用其中一个
        host_property_filter: 主机属性组合查询条件，支持AND和OR组合，最多嵌套2层
        **kwargs: 其他额外参数

    Returns:
        tuple[int, HostList]: (主机总数, 主机列表)
    """
    # 验证互斥参数
    if bk_set_ids is not None and set_cond is not None:
        raise ValueError("bk_set_ids和set_cond只能使用其中一个")

    if bk_module_ids is not None and module_cond is not None:
        raise ValueError("bk_module_ids和module_cond只能使用其中一个")

    # 验证列表长度限制
    if bk_set_ids is not None and len(bk_set_ids) > 200:
        raise ValueError("bk_set_ids最多200条")

    if bk_module_ids is not None and len(bk_module_ids) > 500:
        raise ValueError("bk_module_ids最多500条")

    # 设置默认分页参数
    if page is None:
        page = CMDB_API_PAGE_PARAMS.copy()

    # 验证页面参数
    validated_page = validate_page_params(page)

    # 期望返回的host对象一定有bk_host_id, bk_host_name, bk_host_innerip
    # 为none时会返回所有字段，传参时入参必须包含这三个字段
    if fields is not None:
        fields.extend(Host.get_required_fields())

    # 构建请求参数
    params: dict[str, Any] = {
        "bk_biz_id": bk_biz_id,
        "fields": fields,
        "page": validated_page,
    }

    # 添加可选参数
    if bk_set_ids is not None:
        params["bk_set_ids"] = bk_set_ids

    if set_cond is not None:
        params["set_cond"] = set_cond

    if bk_module_ids is not None:
        params["bk_module_ids"] = bk_module_ids

    if module_cond is not None:
        params["module_cond"] = module_cond

    if host_property_filter is not None:
        params["host_property_filter"] = host_property_filter

    # 添加其他额外参数
    params.update(kwargs)

    # 调用API
    api_result = list_biz_hosts_client(
        bk_tenant_id=bk_tenant_id,
        params=params,
    )

    host_num = api_result.get("data", {}).get("count", 0)
    host_data = api_result.get("data", {}).get("info", [])

    # CMDB API 不返回 bk_biz_id 字段，但 Host 模型需要，所以手动添加
    for host in host_data:
        if "bk_biz_id" not in host:
            host["bk_biz_id"] = bk_biz_id

    host_list = HostList(host_data)
    return host_num, host_list


def search_object_attribute(
    bk_tenant_id: str,
    bk_obj_id: str,
    bk_biz_id: int | None = None,
    **kwargs: Any,
) -> list[dict[str, Any]]:
    """根据模型id查询对象模型属性（权限：模型查看权限）

    Args:
        bk_tenant_id: 租户ID
        bk_obj_id: 模型ID（必选）
        bk_biz_id: 业务ID（可选），设置后查询结果包含业务自定义字段
        **kwargs: 其他额外参数

    Returns:
        list[dict[str, Any]]: 对象属性列表，每个属性包含：
            - bk_property_id: 属性ID
            - bk_property_name: 属性名称
            - bk_property_type: 属性类型（singlechar/longchar/int/enum/date/time/objuser等）
            - bk_obj_id: 模型ID
            - isrequired: 是否必填
            - isreadonly: 是否只读
            - editable: 是否可编辑
            - option: 用户自定义内容
            - unit: 单位
            - placeholder: 占位符
            - bk_property_group: 字段分栏名
    """
    params: dict[str, Any] = {"bk_obj_id": bk_obj_id}

    if bk_biz_id is not None:
        params["bk_biz_id"] = bk_biz_id

    params.update(kwargs)

    api_result = search_object_attribute_client(
        bk_tenant_id=bk_tenant_id,
        params=params,
    )
    return api_result.get("data", [])


def find_host_biz_relation(
    bk_tenant_id: str,
    bk_host_ids: list[int],
    bk_biz_id: int | None = None,
    batch_size: int = 500,
    max_workers: int = 5,
    **kwargs: Any,
) -> list[dict[str, Any]]:
    """根据主机ID查询业务相关信息（自动分批并发）

    根据主机ID列表查询主机与业务、集群、模块的关联关系。
    自动将大列表分批处理，每批不超过500个（CMDB API限制），并发请求以提升性能。

    Args:
        bk_tenant_id: 租户ID
        bk_host_ids: 主机ID列表（无数量限制，自动分批处理）
        bk_biz_id: 业务ID（可选，用于过滤特定业务下的关系）
        batch_size: 每批数量，默认500（CMDB API 限制最大500）
        max_workers: 并发线程数，默认5

    Returns:
        主机业务关系列表，每个元素包含：
            - bk_biz_id: 业务ID
            - bk_host_id: 主机ID
            - bk_module_id: 模块ID
            - bk_set_id: 集群ID
            - bk_supplier_account: 开发商账户

    Note:
        - 一个主机可能属于多个模块，因此返回结果中同一个 bk_host_id 可能出现多次
        - 当 bk_host_ids 为空时，直接返回空列表
    """
    if not bk_host_ids:
        return []

    # 将 bk_host_ids 分批，每批最多 batch_size 个
    batches = [bk_host_ids[i : i + batch_size] for i in range(0, len(bk_host_ids), batch_size)]

    # 如果只有一批，直接请求，无需并发
    if len(batches) == 1:
        params: dict[str, Any] = {"bk_host_id": batches[0]}
        if bk_biz_id is not None:
            params["bk_biz_id"] = bk_biz_id
        params.update(kwargs)
        result = find_host_biz_relation_client(
            bk_tenant_id=bk_tenant_id,
            params=params,
        )
        return result.get("data", [])

    # 多批时使用 ThreadPoolExecutor 并发请求
    def fetch_batch(batch_host_ids: list[int]) -> list[dict[str, Any]]:
        """查询单批主机的业务关系"""
        _params: dict[str, Any] = {"bk_host_id": batch_host_ids}
        if bk_biz_id is not None:
            _params["bk_biz_id"] = bk_biz_id
        _params.update(kwargs)
        try:
            _result = find_host_biz_relation_client(
                bk_tenant_id=bk_tenant_id,
                params=_params,
            )
            return _result.get("data", [])
        except Exception:
            # 单批查询失败不影响其他批次，返回空列表
            return []

    all_relations: list[dict[str, Any]] = []
    workers = min(max_workers, len(batches))

    with ThreadPoolExecutor(max_workers=workers) as executor:
        future_to_batch = {executor.submit(fetch_batch, batch): batch for batch in batches}

        for future in as_completed(future_to_batch):
            relations = future.result()
            all_relations.extend(relations)

    return all_relations


def list_hosts_without_biz(
    bk_tenant_id: str,
    page: PageParams | None = None,
    fields: list[str] | None = None,
    bk_biz_id: int | None = None,
    host_property_filter: HostPropertyFilter | None = None,
    **kwargs: Any,
) -> tuple[int, HostList]:
    """没有业务信息的主机查询（权限：主机池主机查看权限）

    Args:
        bk_tenant_id: 租户ID
        page: 分页参数，包含 start（记录开始位置）、limit（每页限制条数，最大500）
        fields: 主机属性列表（可选），控制返回结果的主机里有哪些字段，不填默认返回所有字段
        bk_biz_id: 业务ID（可选）
        host_property_filter: 主机属性组合查询条件（可选），支持AND和OR组合，最多嵌套2层
        **kwargs: 其他额外参数

    Returns:
        tuple[int, HostList]: (主机总数, 主机列表)
    """
    if page is None:
        page = CMDB_API_PAGE_PARAMS.copy()

    validated_page = validate_page_params(page)

    if fields is not None:
        fields.extend(Host.get_required_fields())

    params: dict[str, Any] = {"page": validated_page}

    if fields is not None:
        params["fields"] = fields
    if bk_biz_id is not None:
        params["bk_biz_id"] = bk_biz_id
    if host_property_filter is not None:
        params["host_property_filter"] = host_property_filter

    params.update(kwargs)

    api_result = list_hosts_without_biz_client(
        bk_tenant_id=bk_tenant_id,
        params=params,
    )
    host_num = api_result.get("data", {}).get("count", 0)
    host_data = api_result.get("data", {}).get("info", [])

    # 补充必要字段空值
    for host in host_data:
        host["bk_host_innerip"] = host.get("bk_host_innerip") or ""
        host["bk_host_innerip_v6"] = host.get("bk_host_innerip_v6") or ""
        host["bk_host_name"] = host.get("bk_host_name") or ""
        host["bk_cloud_id"] = host.get("bk_cloud_id") or 0

    if host_data:
        host_ids = [host["bk_host_id"] for host in host_data]
        relation_result = find_host_biz_relation(bk_tenant_id=bk_tenant_id, bk_host_ids=host_ids)
        host_id_to_biz: dict[int, int] = {r["bk_host_id"]: r["bk_biz_id"] for r in relation_result}
        for host in host_data:
            bk_host_id = host["bk_host_id"]
            if bk_host_id in host_id_to_biz:
                host["bk_biz_id"] = host_id_to_biz[bk_host_id]

    host_list = HostList(host_data)
    return host_num, host_list


def list_service_instance(
    bk_tenant_id: str,
    bk_biz_id: int,
    page: PageParams | None = None,
    bk_module_id: int | None = None,
    bk_host_ids: list[int] | None = None,
    selectors: list[LabelSelector] | None = None,
    search_key: str | None = None,
    **kwargs: Any,
) -> tuple[int, list[Any]]:
    """根据业务id查询服务实例列表

    Args:
        bk_tenant_id: 租户ID
        bk_biz_id: 业务ID（必选）
        page: 分页参数，包含 start（记录开始位置）、limit（每页限制条数，最大500）
        bk_module_id: 模块ID（可选）
        bk_host_ids: 主机ID列表（可选），最多支持1000个主机id
        selectors: label过滤功能（可选），operator可选值: =, !=, exists, !, in, notin
        search_key: 名字过滤参数（可选），可填写进程名称包含的字符用于模糊搜索
        **kwargs: 其他额外参数

    Returns:
        tuple[int, list[Any]]: (服务实例总数, 服务实例列表)
            服务实例包含：id、name、bk_biz_id、bk_module_id、bk_host_id、creator、modifier、create_time、last_time
    """
    if page is None:
        page = CMDB_API_PAGE_PARAMS.copy()

    validated_page = validate_page_params(page)

    params: dict[str, Any] = {"bk_biz_id": bk_biz_id, "page": validated_page}

    if bk_module_id is not None:
        params["bk_module_id"] = bk_module_id
    if bk_host_ids is not None:
        params["bk_host_ids"] = bk_host_ids
    if selectors is not None:
        params["selectors"] = selectors
    if search_key is not None:
        params["search_key"] = search_key

    params.update(kwargs)

    api_result = list_service_instance_client(
        bk_tenant_id=bk_tenant_id,
        params=params,
    )
    instance_num = api_result.get("data", {}).get("count", 0)
    instances = api_result.get("data", {}).get("info", [])
    return instance_num, instances


def search_dynamic_group(
    bk_tenant_id: str,
    bk_biz_id: int,
    page: PageParams | None = None,
    condition: dict[str, Any] | None = None,
    disable_counter: bool | None = None,
    **kwargs: Any,
) -> tuple[int, list[Any]]:
    """查询动态分组列表（版本：v3.9.6，权限：业务访问权限）

    Args:
        bk_tenant_id: 租户ID
        bk_biz_id: 业务ID（必选）
        page: 分页参数，包含 start（记录开始位置）、limit（每页限制条数，最大200）、sort（排序字段，默认按创建时间排序）
        condition: 查询条件（可选），支持的字段包括 create_user、modify_user、name
        disable_counter: 是否不返回总记录条数（可选），默认返回
        **kwargs: 其他额外参数

    Returns:
        tuple[int, list[Any]]: (动态分组总数, 动态分组列表)
            动态分组包含：bk_biz_id、id、name、bk_obj_id（host/set）、info、create_user、create_time、modify_user、last_time
    """
    if page is None:
        page = CMDB_API_PAGE_PARAMS.copy()

    validated_page = validate_page_params(page)

    params: dict[str, Any] = {"bk_biz_id": bk_biz_id, "page": validated_page}

    if condition is not None:
        params["condition"] = condition
    if disable_counter is not None:
        params["disable_counter"] = disable_counter

    params.update(kwargs)

    api_result = search_dynamic_group_client(
        bk_tenant_id=bk_tenant_id,
        params=params,
    )
    group_num = api_result.get("data", {}).get("count", 0)
    groups = api_result.get("data", {}).get("info", [])
    return group_num, groups


def execute_dynamic_group(
    bk_tenant_id: str,
    bk_biz_id: int,
    dynamic_group_id: int,
    fields: list[str] | None = None,
    **kwargs: Any,
) -> list[dict[str, Any]]:
    """执行动态分组，并拉取全部命中数据。

    Args:
        bk_tenant_id: 租户ID
        bk_biz_id: 业务ID
        dynamic_group_id: 动态分组ID
        fields: 返回字段列表, 默认返回 bk_host_id, bk_cloud_id, bk_host_innerip, bk_host_name

    Returns:
        动态分组命中的数据列表（由 CMDB 响应的 `data.info` 合并而来）。
    """

    if not fields:
        fields = ["bk_host_id", "bk_cloud_id", "bk_host_innerip", "bk_host_name"]

    _, data, _ = execute_dynamic_group_client.batch_request(
        bk_tenant_id=bk_tenant_id,
        params={
            "bk_biz_id": bk_biz_id,
            "id": dynamic_group_id,
            "fields": fields,
            **kwargs,
        },
        # CMDB 使用 page.start/page.limit 的 offset 分页模式
        pagination_mode="offset",
        first_page_or_start_value=0,
        page_or_offset_key="page.start",
        page_size_or_limit_key="page.limit",
        # CMDB 统一响应格式：{"data": {"count": int, "info": []}}
        total_key="data.count",
        data_list_key="data.info",
    )
    return data


class DynamicGroupConfig(TypedDict):
    """动态分组条件"""

    bk_biz_id: int
    name: str
    id: str
    bk_obj_id: Literal["host", "set"]
    info: dict[str, Any]


def get_dynamic_group(
    bk_tenant_id: str,
    bk_biz_id: int,
    dynamic_group_id: int,
    **kwargs: Any,
) -> DynamicGroupConfig:
    """获取动态分组配置

    Args:
        bk_tenant_id: 租户ID
        bk_biz_id: 业务ID
        dynamic_group_id: 动态分组ID

    Returns:
        动态分组配置
    """

    result = get_dynamic_group_client(
        bk_tenant_id=bk_tenant_id,
        params={"bk_biz_id": bk_biz_id, "id": dynamic_group_id, **kwargs},
    )
    return result["data"]


class InstTopoItem(TypedDict):
    """实例拓扑结果"""

    bk_obj_id: str
    bk_obj_name: str
    bk_inst_id: int
    bk_inst_name: str
    child: list["InstTopoItem"]


def search_biz_inst_topo(
    bk_tenant_id: str,
    bk_biz_id: int,
    **kwargs: Any,
) -> list[InstTopoItem]:
    """查询业务实例拓扑

    Args:
        bk_tenant_id: 租户ID
        bk_biz_id: 业务ID（必选）
        **kwargs: 其他额外参数

    Returns:
        list[Any]: 业务实例拓扑列表，每个节点包含：
            - bk_inst_id: 实例ID
            - bk_inst_name: 实例名称
            - bk_obj_id: 模型ID
            - bk_obj_name: 模型名称
            - default: 业务类型（0-普通集群，1-内置模块集合）
            - child: 子节点列表
    """
    api_result = search_biz_inst_topo_client(
        bk_tenant_id=bk_tenant_id,
        params={"bk_biz_id": bk_biz_id, **kwargs},
    )
    return api_result.get("data", [])


def get_mainline_object_topo(
    bk_tenant_id: str,
    **kwargs: Any,
) -> list[Any]:
    """获取主线对象拓扑

    Args:
        bk_tenant_id: 租户ID
    Returns:
        主线对象拓扑
    """

    api_result = get_mainline_object_topo_client(bk_tenant_id=bk_tenant_id, params={**kwargs})
    return api_result.get("data", [])


def resource_watch(
    bk_tenant_id: str,
    bk_resource: str,
    bk_cursor: str,
    bk_event_types: list[str],
    bk_fields: list[str],
    **kwargs: Any,
) -> dict[str, Any]:
    """资源变更事件监听

    Args:
        bk_tenant_id: 租户ID
        bk_resource: 资源类型
        bk_cursor: 事件游标
        bk_event_types: 事件类型列表
        bk_fields: 返回字段列表
    Returns:
        资源变更事件
    """

    api_result = resource_watch_client(
        bk_tenant_id=bk_tenant_id,
        params={
            "bk_resource": bk_resource,
            "bk_cursor": bk_cursor,
            "bk_event_types": bk_event_types,
            "bk_fields": bk_fields,
            **kwargs,
        },
    )
    return api_result.get("data", {})


def search_inst(
    bk_tenant_id: str,
    bk_obj_id: str,
    page: PageParams | None = None,
    condition: dict[str, list[dict[str, Any]]] | None = None,
    time_condition: TimeCondition | None = None,
    fields: dict[str, list[str]] | None = None,
    **kwargs: Any,
) -> tuple[int, ObjectInstList]:
    """根据关联关系实例查询模型实例（权限：模型实例查询权限）

    该接口只适用于自定义层级模型和通用模型实例上，不适用于业务、集群、模块、主机等模型实例

    Args:
        bk_tenant_id: 租户ID
        bk_obj_id: 模型ID
        page: 分页参数, {"start": 0, "limit": 200, "sort": "bk_inst_id"}
        condition: 具有关联关系的模型实例查询条件。key为模型ID，value为条件列表。
                   每个条件包含 field（模型字段名）、operator（$regex/$eq/$ne）、value（字段值）
                   示例: {"user": [{"field": "operator", "operator": "$regex", "value": "admin"}]}
        time_condition: 按时间查询模型实例的查询条件。
                        包含 oper（操作符，目前只支持and）和 rules（时间查询条件列表）
                        每个rule包含 field（字段名）、start（起始时间 yyyy-MM-dd hh:mm:ss）、end（结束时间）
        fields: 指定查询模型实例返回的字段。key为模型ID，value为该查询模型要返回的模型属性字段列表
                示例: {"bk_switch": ["bk_asset_id", "bk_inst_id", "bk_inst_name", "bk_obj_id"]}
        **kwargs: 其他可选参数

    Returns:
        tuple[int, ObjectInstList]: (实例总数, 实例列表)
    """
    if page is None:
        page = CMDB_API_PAGE_PARAMS.copy()

    # 验证页面参数
    validated_page = validate_page_params(page)

    # 构建请求参数
    params: dict[str, Any] = {"bk_obj_id": bk_obj_id, "page": validated_page}

    if condition is not None:
        params["condition"] = condition

    if time_condition is not None:
        params["time_condition"] = time_condition

    if fields is not None:
        params["fields"] = fields

    params.update(kwargs)

    api_result = search_inst_client(
        bk_tenant_id=bk_tenant_id,
        params=params,
    )
    inst_num = api_result.get("data", {}).get("count", 0)
    inst_list = api_result.get("data", {}).get("info", [])
    # 为每个实例添加bk_obj_id字段
    for inst in inst_list:
        inst["bk_obj_id"] = bk_obj_id

    return inst_num, ObjectInstList(inst_list)


def list_biz_all_hosts(
    bk_tenant_id: str,
    bk_biz_id: int,
    fields: list[str] | None = None,
    bk_set_ids: list[int] | None = None,
    set_cond: list[SetCondition] | None = None,
    bk_module_ids: list[int] | None = None,
    module_cond: list[ModuleCondition] | None = None,
    host_property_filter: HostPropertyFilter | None = None,
    **kwargs: Any,
) -> tuple[int, HostList]:
    """获取业务下所有主机（自动翻页）

    基于 list_biz_hosts 接口实现，自动处理分页获取所有结果。

    Args:
        bk_tenant_id: 租户ID
        bk_biz_id: 业务ID
        fields: 主机属性列表，控制返回结果的主机里有哪些字段
        bk_set_ids: 集群ID列表，最多200条。与set_cond互斥，只能使用其中一个
        set_cond: 集群查询条件。与bk_set_ids互斥，只能使用其中一个
                  每个条件包含 field（集群字段）、operator（$eq/$ne）、value（字段值）
        bk_module_ids: 模块ID列表，最多500条。与module_cond互斥，只能使用其中一个
        module_cond: 模块查询条件。与bk_module_ids互斥，只能使用其中一个
                     每个条件包含 field（模块字段）、operator（$eq/$ne）、value（字段值）
        host_property_filter: 主机属性组合查询条件，支持AND/OR组合，最多嵌套2层
        **kwargs: 其他可选参数

    Returns:
        tuple[int, HostList]: (主机总数, 主机列表)

    Note:
        - bk_set_ids 和 set_cond 只能使用其中一个
        - bk_module_ids 和 module_cond 只能使用其中一个
    """
    params: dict[str, Any] = {"bk_biz_id": bk_biz_id}

    if fields is not None:
        params["fields"] = fields

    if bk_set_ids is not None:
        params["bk_set_ids"] = bk_set_ids

    if set_cond is not None:
        params["set_cond"] = set_cond

    if bk_module_ids is not None:
        params["bk_module_ids"] = bk_module_ids

    if module_cond is not None:
        params["module_cond"] = module_cond

    if host_property_filter is not None:
        params["host_property_filter"] = host_property_filter

    params.update(kwargs)

    _, data, _ = list_biz_hosts_client.batch_request(
        bk_tenant_id=bk_tenant_id,
        params=params,
        batch_size=500,
        pagination_mode="offset",
        first_page_or_start_value=0,
        page_or_offset_key="page.start",
        page_size_or_limit_key="page.limit",
        total_key="data.count",
        data_list_key="data.info",
    )
    return len(data), HostList(data)


def list_all_hosts(
    bk_tenant_id: str,
    fields: list[str] | None = None,
    bk_biz_id: int | None = None,
    host_property_filter: HostPropertyFilter | None = None,
    **kwargs: Any,
) -> tuple[int, HostList]:
    """获取所有主机（自动翻页）

    基于 list_hosts_without_biz 接口实现，自动处理分页获取所有结果。
    主机池主机查询接口，可查询没有业务信息的主机。

    Args:
        bk_tenant_id: 租户ID
        fields: 主机属性列表，控制返回结果的主机里有哪些字段，不填默认返回所有字段
        bk_biz_id: 业务ID（可选）
        host_property_filter: 主机属性组合查询条件，支持AND/OR组合，最多嵌套2层
        **kwargs: 其他可选参数

    Returns:
        tuple[int, HostList]: (主机总数, 主机列表)

    Note:
        - 权限：主机池主机查看权限
        - 返回的主机会额外附加 bk_biz_id 字段（通过 find_host_biz_relation 接口获取）
    """
    params: dict[str, Any] = {}

    if fields is not None:
        params["fields"] = fields

    if bk_biz_id is not None:
        params["bk_biz_id"] = bk_biz_id

    if host_property_filter is not None:
        params["host_property_filter"] = host_property_filter

    params.update(kwargs)

    _, host_data, _ = list_hosts_without_biz_client.batch_request(
        bk_tenant_id=bk_tenant_id,
        params=params,
        batch_size=500,
        pagination_mode="offset",
        first_page_or_start_value=0,
        page_or_offset_key="page.start",
        page_size_or_limit_key="page.limit",
        total_key="data.count",
        data_list_key="data.info",
    )

    if host_data:
        host_ids = [host["bk_host_id"] for host in host_data]
        relation_result = find_host_biz_relation(bk_tenant_id=bk_tenant_id, bk_host_ids=host_ids)
        host_id_to_biz: dict[int, int] = {r["bk_host_id"]: r["bk_biz_id"] for r in relation_result}
        for host in host_data:
            bk_host_id = host["bk_host_id"]
            if bk_host_id in host_id_to_biz:
                host["bk_biz_id"] = host_id_to_biz[bk_host_id]

    return len(host_data), HostList(host_data)


def search_all_inst_by_bk_obj_id(
    bk_tenant_id: str,
    bk_obj_id: str,
    condition: dict[str, list[dict[str, Any]]] | None = None,
    time_condition: TimeCondition | None = None,
    fields: dict[str, list[str]] | None = None,
    **kwargs: Any,
) -> tuple[int, ObjectInstList]:
    """根据对象ID获取所有实例（自动翻页）

    基于 search_inst 接口实现，自动处理分页获取所有结果。
    该接口只适用于自定义层级模型和通用模型实例上，不适用于业务、集群、模块、主机等模型实例。

    Args:
        bk_tenant_id: 租户ID
        bk_obj_id: 模型ID
        condition: 具有关联关系的模型实例查询条件。key为模型ID，value为条件列表。
                   每个条件包含 field（模型字段名）、operator（$regex/$eq/$ne）、value（字段值）
                   示例: {"user": [{"field": "operator", "operator": "$regex", "value": "admin"}]}
        time_condition: 按时间查询模型实例的查询条件。
                        包含 oper（操作符，目前只支持and）和 rules（时间查询条件列表）
                        每个rule包含 field（字段名）、start（起始时间 yyyy-MM-dd hh:mm:ss）、end（结束时间）
        fields: 指定查询模型实例返回的字段。key为模型ID，value为该查询模型要返回的模型属性字段列表
                示例: {"bk_switch": ["bk_asset_id", "bk_inst_id", "bk_inst_name", "bk_obj_id"]}
        **kwargs: 其他可选参数

    Returns:
        tuple[int, ObjectInstList]: (实例总数, 实例列表)

    Note:
        - 权限：模型实例查询权限
        - 返回的实例会额外附加 bk_obj_id 字段
    """
    params: dict[str, Any] = {"bk_obj_id": bk_obj_id}

    if condition is not None:
        params["condition"] = condition

    if time_condition is not None:
        params["time_condition"] = time_condition

    if fields is not None:
        params["fields"] = fields

    params.update(kwargs)

    _, data, _ = search_inst_client.batch_request(
        bk_tenant_id=bk_tenant_id,
        params=params,
        batch_size=500,
        pagination_mode="offset",
        first_page_or_start_value=0,
        page_or_offset_key="page.start",
        page_size_or_limit_key="page.limit",
        total_key="data.count",
        data_list_key="data.info",
    )
    # 为每个实例添加bk_obj_id字段
    for inst in data:
        inst["bk_obj_id"] = bk_obj_id
    return len(data), ObjectInstList(data)


class HostTopoModuleItem(TypedDict):
    """主机拓扑模块结果"""

    bk_module_id: int
    bk_module_name: str


class HostTopoSetItem(TypedDict):
    """主机拓扑结果"""

    bk_set_id: int
    bk_set_name: str
    module: list[HostTopoModuleItem]


class HostTopoHostItem(TypedDict):
    """主机拓扑主机结果"""

    bk_host_id: int


class HostTopoItem(TypedDict):
    """主机"""

    host: HostTopoHostItem
    topo: list[HostTopoSetItem]


def list_biz_hosts_topo(
    bk_tenant_id: str,
    bk_biz_id: int,
    page: PageParams | None = None,
    fields: list[str] | None = None,
    **kwargs: Any,
) -> tuple[int, list[HostTopoItem]]:
    """查询业务下的主机拓扑

    Args:
        bk_tenant_id: 租户ID
        bk_biz_id: 业务ID
        fields: 查询字段, 不传默认只返回bk_host_id
        page: 分页参数, {"start": 0, "limit": 100, "sort": "bk_host_id"}
    Returns:
        主机拓扑列表
    """
    if page is None:
        page = CMDB_API_PAGE_PARAMS.copy()

    # 验证页面参数
    validated_page = validate_page_params(page)

    api_result = list_biz_hosts_topo_client(
        bk_tenant_id=bk_tenant_id,
        params={"bk_biz_id": bk_biz_id, "page": validated_page, "fields": fields, **kwargs},
    )
    host_num = api_result.get("data", {}).get("count", 0)
    hosts = api_result.get("data", {}).get("info", [])
    return host_num, hosts


def list_biz_all_hosts_topo(
    bk_tenant_id: str,
    bk_biz_id: int,
    fields: list[str] | None = None,
    **kwargs: Any,
) -> tuple[int, list[HostTopoItem]]:
    """获取业务下所有主机拓扑（自动翻页）"""
    params = {"bk_biz_id": bk_biz_id, "fields": fields}
    params.update(kwargs)

    _, data, _ = list_biz_hosts_topo_client.batch_request(
        bk_tenant_id=bk_tenant_id,
        params=params,
        batch_size=500,
        pagination_mode="offset",
        first_page_or_start_value=0,
        page_or_offset_key="page.start",
        page_size_or_limit_key="page.limit",
        total_key="data.count",
        data_list_key="data.info",
    )
    return len(data), data


def search_objects(
    bk_tenant_id: str,
    creator: str | None = None,
    modifier: str | None = None,
    bk_classification_id: str | None = None,
    bk_obj_id: str | None = None,
    bk_obj_name: str | None = None,
    obj_sort_number: int | None = None,
    **kwargs: Any,
) -> list[ObjectModel]:
    """根据可选条件查询模型（权限：模型查看权限）

    Args:
        bk_tenant_id: 租户ID
        creator: 本条数据创建者
        modifier: 本条数据的最后修改人员
        bk_classification_id: 对象模型的分类ID，只能用英文字母序列命名
        bk_obj_id: 对象模型的ID，只能用英文字母序列命名
        bk_obj_name: 对象模型的名字，用于展示，可以使用人类可以阅读的任何语言
        obj_sort_number: 对象模型在所属模型分组下的排序序号
        **kwargs: 其他可选参数

    Returns:
        list[ObjectModel]: 对象模型列表，每个对象包含以下字段：
            - id: 数据记录的ID
            - creator: 本条数据创建者
            - modifier: 本条数据的最后修改人员
            - bk_classification_id: 对象模型的分类ID
            - bk_obj_id: 对象模型的ID
            - bk_obj_name: 对象模型的名字
            - bk_supplier_account: 开发商账号
            - bk_ispaused: 是否停用
            - ispre: 是否预定义
            - bk_obj_icon: 对象模型的ICON信息
            - position: 用于前端展示的坐标
            - description: 数据的描述信息
            - obj_sort_number: 对象模型在所属模型分组下的排序序号
    """
    params: dict[str, Any] = {}

    if creator is not None:
        params["creator"] = creator

    if modifier is not None:
        params["modifier"] = modifier

    if bk_classification_id is not None:
        params["bk_classification_id"] = bk_classification_id

    if bk_obj_id is not None:
        params["bk_obj_id"] = bk_obj_id

    if bk_obj_name is not None:
        params["bk_obj_name"] = bk_obj_name

    if obj_sort_number is not None:
        params["obj_sort_number"] = obj_sort_number

    params.update(kwargs)

    api_result = search_objects_client(
        bk_tenant_id=bk_tenant_id,
        params=params,
    )

    return [ObjectModel(**i) for i in api_result.get("data", [])]


class FindTopoNodePathParams(TypedDict):
    """拓扑节点路径节点"""

    bk_obj_id: str
    bk_inst_id: int


class FindTopoNodePathNode(TypedDict):
    """拓扑节点路径节点"""

    bk_obj_id: str
    bk_inst_id: int
    bk_inst_name: str


class FindTopoNodePathResult(FindTopoNodePathNode):
    """拓扑节点路径结果"""

    bk_paths: list[list[FindTopoNodePathNode]]


def find_topo_node_path(
    bk_tenant_id: str, bk_biz_id: int, bk_nodes: list[FindTopoNodePathParams], **kwargs: Any
) -> list[FindTopoNodePathResult]:
    """查询拓扑节点路径

    Args:
        bk_tenant_id: 租户ID
        bk_biz_id: 业务ID
        bk_nodes: 节点列表(最大支持1000个节点)
    Returns:
        拓扑节点路径结果
    """

    if not bk_nodes:
        return []

    result = find_topo_node_path_client(
        bk_tenant_id=bk_tenant_id, params={"bk_biz_id": bk_biz_id, "bk_nodes": bk_nodes, **kwargs}
    )
    return result.get("data") or []


def list_service_template(
    bk_tenant_id: str,
    bk_biz_id: int,
    service_template_ids: list[int] | None = None,
    service_category_id: int | None = None,
    search: str | None = None,
    is_exact: bool | None = None,
    **kwargs: Any,
) -> list[ServiceTemplate]:
    """获取服务模板列表

    Args:
        bk_tenant_id: 租户ID
        bk_biz_id: 业务ID
        service_template_ids: 服务模板ID列表
        service_category_id: 服务分类ID
        search: 搜索关键词
        is_exact: 是否精确搜索, 默认为False, 与search搭配使用

    Returns:
        服务模板列表
    """
    params: dict[str, Any] = {"bk_biz_id": bk_biz_id}
    if service_category_id:
        params["service_category_id"] = service_category_id
    if service_template_ids:
        params["service_template_ids"] = service_template_ids
    if search:
        params["search"] = search
    if is_exact is not None:
        params["is_exact"] = is_exact

    params.update(kwargs)

    # CMDB 使用 page.start/page.limit 的 offset 分页模式，统一响应格式：{"data": {"count": int, "info": []}}
    _, data, _ = list_service_template_client.batch_request(
        bk_tenant_id=bk_tenant_id,
        params=params,
        batch_size=500,
        pagination_mode="offset",
        first_page_or_start_value=0,
        page_or_offset_key="page.start",
        page_size_or_limit_key="page.limit",
        total_key="data.count",
        data_list_key="data.info",
    )

    templates: list[ServiceTemplate] = []
    for item in data:
        if "bk_biz_id" not in item:
            item["bk_biz_id"] = bk_biz_id
        templates.append(ServiceTemplate(**item))
    return templates


def list_set_template(
    bk_tenant_id: str,
    bk_biz_id: int,
    set_template_ids: list[int] | None = None,
    **kwargs: Any,
) -> list[SetTemplate]:
    """获取集群模板列表

    Args:
        bk_tenant_id: 租户ID
        bk_biz_id: 业务ID
        set_template_ids: 集群模板ID列表

    Returns:
        集群模板列表
    """
    params: dict[str, Any] = {"bk_biz_id": bk_biz_id}
    if set_template_ids:
        params["set_template_ids"] = set_template_ids

    params.update(kwargs)

    # CMDB 使用 page.start/page.limit 的 offset 分页模式，统一响应格式：{"data": {"count": int, "info": []}}
    _, data, _ = list_set_template_client.batch_request(
        bk_tenant_id=bk_tenant_id,
        params=params,
        batch_size=500,
        pagination_mode="offset",
        first_page_or_start_value=0,
        page_or_offset_key="page.start",
        page_size_or_limit_key="page.limit",
        total_key="data.count",
        data_list_key="data.info",
    )

    templates: list[SetTemplate] = []
    for item in data:
        if "bk_biz_id" not in item:
            item["bk_biz_id"] = bk_biz_id
        templates.append(SetTemplate(**item))
    return templates


class CloudArea(TypedDict):
    """云区域"""

    # 云区域ID
    bk_cloud_id: int
    # 云区域名称
    bk_cloud_name: str
    # 云区域供应商
    bk_cloud_vendor: str
    # 云区域状态
    bk_status: str
    # 云区域状态详情
    bk_status_detail: str
    # 云区域账号ID
    bk_accound_id: int
    # 云区域供应商账号
    bk_supplier_account: str
    # 云区域VPC ID
    bk_vpc_id: str
    # 云区域VPC名称
    bk_vpc_name: str
    # 区域
    bk_region: str


def search_cloud_area(bk_tenant_id: str, **kwargs: Any) -> list[CloudArea]:
    """查询云区域

    Args:
        bk_tenant_id: 租户ID

    Returns:
        云区域
    """
    api_result = search_cloud_area_client(bk_tenant_id=bk_tenant_id, params={**kwargs})
    inst_list = api_result.get("data", {}).get("info", [])
    return inst_list


def get_host_by_template(
    bk_tenant_id: str,
    bk_biz_id: int,
    bk_obj_id: str,
    template_ids: list[int],
    fields: list[str] | None = None,
    **kwargs: Any,
) -> list[HostTopoItem]:
    """
    获取模板下的主机

    Args:
        bk_tenant_id: 租户ID
        bk_biz_id: 业务ID
        bk_obj_id: 模板类型，SERVICE_TEMPLATE 或 SET_TEMPLATE
        template_ids: 模板ID列表
        fields: 查询字段列表

    Returns:
        主机列表
    """
    from bk_monitor_base.infras.declaratives.constants import TargetNodeType

    # 按模板查询节点
    if bk_obj_id == TargetNodeType.SERVICE_TEMPLATE:
        # 服务模板：获取模块
        # 需要先获取所有模块，然后按 service_template_id 过滤
        _, all_modules = search_module(bk_tenant_id=bk_tenant_id, bk_biz_id=bk_biz_id)
        # 过滤出匹配的模块
        template_ids_set = set(template_ids)
        modules = [m for m in all_modules if getattr(m, "service_template_id", None) in template_ids_set]
        topo_nodes = {"module": [m.bk_module_id for m in modules]}
    elif bk_obj_id == TargetNodeType.SET_TEMPLATE:
        # 集群模板：获取集群
        # 需要先获取所有集群，然后按 set_template_id 过滤
        _, all_sets = search_set(bk_tenant_id=bk_tenant_id, bk_biz_id=bk_biz_id)
        # 过滤出匹配的集群
        template_ids_set = set(template_ids)
        sets = [s for s in all_sets if getattr(s, "set_template_id", None) in template_ids_set]
        topo_nodes = {"set": [s.bk_set_id for s in sets]}
    else:
        topo_nodes = {}

    return get_host_by_topo_node(
        bk_tenant_id=bk_tenant_id,
        bk_biz_id=bk_biz_id,
        topo_nodes=topo_nodes,
        fields=fields,
        **kwargs,
    )


def get_host_by_topo_node(
    bk_tenant_id: str,
    bk_biz_id: int,
    topo_nodes: dict[str, list[int]] | None = None,
    fields: list[str] | None = None,
    **kwargs: Any,
) -> list[HostTopoItem]:
    """
    根据拓扑节点批量查询主机

    Args:
        bk_tenant_id: 租户ID
        bk_biz_id: 业务ID
        topo_nodes: 拓扑节点，格式为 {"module": [1, 2], "set": [3, 4]}
        fields: 查询字段列表

    Returns:
        主机列表
    """

    # 如果节点只有module和set，可以直接拼接过滤条件
    filter_params: dict[str, Any] = {}
    if topo_nodes:
        bk_module_ids = topo_nodes.pop("module", [])
        bk_set_ids = topo_nodes.pop("set", [])
        if bk_module_ids:
            filter_params["module_property_filter"] = {
                "condition": "AND",
                "rules": [{"field": "bk_module_id", "operator": "in", "value": bk_module_ids}],
            }
        if bk_set_ids:
            filter_params["set_property_filter"] = {
                "condition": "AND",
                "rules": [{"field": "bk_set_id", "operator": "in", "value": bk_set_ids}],
            }

    # 获取业务下所有主机
    _, hosts = list_biz_all_hosts_topo(
        bk_tenant_id=bk_tenant_id, bk_biz_id=bk_biz_id, fields=fields, **filter_params, **kwargs
    )

    # TODO: 支持非模块和集群的拓扑节点过滤
    return hosts


class HostIPParams(TypedDict):
    ip: str
    bk_cloud_id: NotRequired[int]


def get_host_by_ip(
    bk_tenant_id: str,
    bk_biz_id: int,
    ips: list[HostIPParams] | None = None,
    bk_host_ids: list[int] | None = None,
    fields: list[str] | None = None,
    **kwargs: Any,
) -> list[Host]:
    """通过IP获取主机信息

    Args:
        bk_tenant_id: 租户ID
        bk_biz_id: 业务ID
        ips: IP列表，每个元素包含 {"ip": str, "bk_cloud_id": int | None}
        bk_host_ids: 主机ID列表

    Returns:
        主机信息列表
    """
    # 如果ips和bk_host_ids都为空，则返回空列表
    if not ips and not bk_host_ids:
        return []

    # 如果fields为空，则使用默认字段；否则补齐 Host 模型构建所需字段
    if fields is None:
        query_fields: list[str] = ["bk_host_innerip", "bk_host_innerip_v6", "bk_cloud_id", "bk_host_name", "bk_host_id"]
    else:
        required_fields = [field for field in Host.get_required_fields() if field != "bk_biz_id"]
        query_fields = list(dict.fromkeys([*fields, *required_fields]))

    # 处理请求参数
    cloud_dict: dict[int, list[str]] = defaultdict(list)
    for h in ips or []:
        cloud_dict[h.get("bk_cloud_id", -1)].append(h["ip"])

    conditions: list[dict[str, Any]] = []

    # 添加主机IP和云区域搜索条件
    for bk_cloud_id, ip_list in cloud_dict.items():
        ipv6_ips = []
        ipv4_ips = []
        for ip in ip_list:
            if is_v6(ip):
                ipv6_ips.append(ip)
            else:
                ipv4_ips.append(ip)

        ipv4_condition: dict[str, Any] = {
            "condition": "AND",
            "rules": [{"field": "bk_host_innerip", "operator": "in", "value": ipv4_ips}],
        }
        ipv6_condition: dict[str, Any] = {
            "condition": "AND",
            "rules": [{"field": "bk_host_innerip_v6", "operator": "in", "value": ipv6_ips}],
        }
        if bk_cloud_id != -1:
            ipv4_condition["rules"].append({"field": "bk_cloud_id", "operator": "equal", "value": bk_cloud_id})
            ipv6_condition["rules"].append({"field": "bk_cloud_id", "operator": "equal", "value": bk_cloud_id})

        if ipv4_ips:
            conditions.append(ipv4_condition)
        if ipv6_ips:
            conditions.append(ipv6_condition)

    # 构建主机ID查询条件
    if bk_host_ids:
        conditions.append(
            {"condition": "AND", "rules": [{"field": "bk_host_id", "operator": "in", "value": bk_host_ids}]}
        )

    if len(conditions) == 1:
        condition_params = conditions[0]
    else:
        condition_params = {"condition": "OR", "rules": conditions}

    _, host_list = list_biz_all_hosts_topo(
        bk_tenant_id=bk_tenant_id,
        bk_biz_id=bk_biz_id,
        host_property_filter=condition_params,
        fields=query_fields,
        **kwargs,
    )

    hosts: list[dict[str, Any]] = []
    for record in host_list:
        host: dict[str, Any] = dict(record["host"])

        host["bk_host_innerip"] = split_inner_host(host.get("bk_host_innerip", ""))
        host["bk_host_innerip_v6"] = split_inner_host(host.get("bk_host_innerip_v6", ""))
        host.setdefault("bk_host_name", "")
        host.setdefault("bk_host_id", 0)
        if not host["bk_host_innerip"] and not host["bk_host_innerip_v6"]:
            continue
        host["ip"] = host["bk_host_innerip"]
        host["bk_biz_id"] = bk_biz_id
        hosts.append(host)

    return HostList(hosts)


class ObjectAssociationCondition(TypedDict, total=False):
    """对象关联关系查询条件"""

    bk_asst_id: str
    bk_obj_id: str
    bk_asst_obj_id: str


def find_object_association(
    bk_tenant_id: str,
    condition: ObjectAssociationCondition | None = None,
    **kwargs: Any,
) -> ObjectAssociationList:
    """查询模型之间的关联关系

    根据条件查询CMDB中模型之间的关联关系。支持通过关联类型ID、源模型ID、目标模型ID进行查询。

    Args:
        bk_tenant_id: 租户ID
        condition: 查询条件，包含以下可选字段：
            - bk_asst_id: 模型的关联类型唯一id
            - bk_obj_id: 源模型id，与目标模型id必填一个
            - bk_asst_obj_id: 目标模型id，与源模型id必填一个
        **kwargs: 其他额外参数

    Returns:
        ObjectAssociationList: 对象关联关系列表
    """
    params: dict[str, Any] = {}

    if condition:
        params["condition"] = condition

    params.update(kwargs)

    api_result = find_object_association_client(
        bk_tenant_id=bk_tenant_id,
        params=params,
    )

    association_list = api_result.get("data", [])
    return ObjectAssociationList(association_list)


class InstanceAssociationRule(TypedDict, total=False):
    """实例关联查询规则"""

    field: str
    operator: str
    value: Any


class InstanceAssociationCondition(TypedDict, total=False):
    """实例关联查询条件"""

    condition: str
    rules: list[InstanceAssociationRule]


def count_instance_associations(
    bk_tenant_id: str,
    bk_obj_id: str,
    bk_biz_id: int | None = None,
    conditions: InstanceAssociationCondition | None = None,
    **kwargs: Any,
) -> int:
    """查询模型实例关系数量

    统计满足条件的模型实例关联关系数量。支持复杂的组合查询条件，条件可以嵌套使用AND/OR逻辑。

    Args:
        bk_tenant_id: 租户ID
        bk_obj_id: 模型ID（必选）
        bk_biz_id: 业务ID，针对主线模型查询时需要提供（可选）
        conditions: 组合查询条件，支持AND和OR两种方式，可以嵌套，最多嵌套3层，每层OR条件最大支持20个。
                   不指定该参数表示匹配全部（即conditions为null）
        **kwargs: 其他额外参数

    Returns:
        int: 满足条件的实例关联关系数量
    """
    params: dict[str, Any] = {"bk_obj_id": bk_obj_id}

    if bk_biz_id is not None:
        params["bk_biz_id"] = bk_biz_id

    if conditions is not None:
        params["conditions"] = conditions

    params.update(kwargs)

    api_result = count_instance_associations_client(
        bk_tenant_id=bk_tenant_id,
        params=params,
    )

    return api_result.get("data", {}).get("count", 0)


def search_instance_associations(
    bk_tenant_id: str,
    bk_obj_id: str,
    page: PageParams,
    bk_biz_id: int | None = None,
    conditions: InstanceAssociationCondition | None = None,
    fields: list[str] | None = None,
    **kwargs: Any,
) -> InstanceAssociationList:
    """通用模型实例关系查询

    查询满足条件的模型实例关联关系列表。支持复杂的组合查询条件、字段过滤和分页。

    Args:
        bk_tenant_id: 租户ID
        bk_obj_id: 模型ID（必选）
        page: 分页设置（必选），包含：
            - start: 记录开始位置
            - limit: 每页限制条数，最大500
            - sort: 检索排序（可选），遵循MongoDB语义格式{KEY}:{ORDER}，默认按照创建时间排序
        bk_biz_id: 业务ID，针对主线模型查询时需要提供（可选）
        conditions: 组合查询条件，支持AND和OR两种方式，可以嵌套，最多嵌套3层，每层OR条件最大支持20个。
                   不指定该参数表示匹配全部（即conditions为null）
        fields: 指定需要返回的字段，不具备的字段将被忽略，不指定则返回全部字段
               （返回全部字段会对性能产生影响，建议按需返回）
        **kwargs: 其他额外参数

    Returns:
        InstanceAssociationList: 满足条件的实例关联关系列表

    Notes:
        - conditions.condition: 规则操作符，可选值为 "AND" 或 "OR"
        - conditions.rules: 所选业务的范围条件规则列表，每个规则包含：
            - field: 条件字段，可选值 id, bk_inst_id, bk_obj_id, bk_asst_inst_id,
                    bk_asst_obj_id, bk_obj_asst_id, bk_asst_id
            - operator: 操作符，可选值 equal, not_equal, in, not_in, less, less_or_equal,
                       greater, greater_or_equal, between, not_between等
            - value: 条件字段期望的值，不同的operator对应不同的value格式，数组类型值最大支持500个元素
        - rules 中可以嵌套 condition 对象，形成复杂的查询条件
        - 版本要求：v3.10.1+
        - 权限要求：模型实例查询权限

    Examples:
        # 简单查询：查询特定关联类型的实例
        associations = search_instance_associations(
            bk_tenant_id="0",
            bk_obj_id="bk_switch",
            page={"start": 0, "limit": 100},
            conditions={
                "condition": "AND",
                "rules": [
                    {
                        "field": "bk_obj_asst_id",
                        "operator": "equal",
                        "value": "bk_switch_connect_host"
                    }
                ]
            },
            fields=["bk_inst_id", "bk_asst_inst_id", "bk_asst_obj_id"]
        )

        # 复杂查询：嵌套条件查询
        associations = search_instance_associations(
            bk_tenant_id="0",
            bk_obj_id="bk_switch",
            page={"start": 0, "limit": 500},
            conditions={
                "condition": "AND",
                "rules": [
                    {
                        "field": "bk_obj_asst_id",
                        "operator": "equal",
                        "value": "bk_switch_connect_host"
                    },
                    {
                        "condition": "OR",
                        "rules": [
                            {
                                "field": "bk_inst_id",
                                "operator": "in",
                                "value": [2, 4, 6]
                            },
                            {
                                "field": "bk_asst_id",
                                "operator": "equal",
                                "value": 3
                            }
                        ]
                    }
                ]
            },
            fields=["bk_inst_id", "bk_asst_inst_id", "bk_asst_obj_id", "bk_asst_id", "bk_obj_asst_id"]
        )

        # 查询所有实例关联关系（不带条件）
        associations = search_instance_associations(
            bk_tenant_id="0",
            bk_obj_id="bk_switch",
            page={"start": 0, "limit": 100}
        )
    """
    params: dict[str, Any] = {
        "bk_obj_id": bk_obj_id,
        "page": page,
    }

    if bk_biz_id is not None:
        params["bk_biz_id"] = bk_biz_id

    if conditions is not None:
        params["conditions"] = conditions

    if fields is not None:
        params["fields"] = fields

    params.update(kwargs)

    api_result = search_instance_associations_client(
        bk_tenant_id=bk_tenant_id,
        params=params,
    )

    return InstanceAssociationList(api_result.get("data", {}).get("info", []))


class FindInstanceAssociationCondition(TypedDict, total=False):
    """查询模型实例关联关系的条件"""

    bk_obj_asst_id: str
    bk_asst_id: NotRequired[str]
    bk_asst_obj_id: NotRequired[str]


def find_instance_association(
    bk_tenant_id: str,
    bk_obj_id: str,
    condition: FindInstanceAssociationCondition,
    **kwargs: Any,
) -> InstanceAssociationList:
    """查询模型的实例关联关系

    根据条件查询指定模型的实例关联关系。需要提供模型关联关系的唯一ID，可选择性地提供关联类型ID和目标模型ID进行进一步过滤。

    Args:
        bk_tenant_id: 租户ID
        bk_obj_id: 源模型ID（必选，v3.10+）
        condition: 查询条件（必选），包含：
            - bk_obj_asst_id: 模型关联关系的唯一id（必选）
            - bk_asst_id: 关联类型的唯一id（可选）
            - bk_asst_obj_id: 目标模型id（可选）
        **kwargs: 其他额外参数

    Returns:
        InstanceAssociationList: 实例关联关系列表
    """
    params: dict[str, Any] = {
        "bk_obj_id": bk_obj_id,
        "condition": condition,
    }

    params.update(kwargs)

    api_result = find_instance_association_client(
        bk_tenant_id=bk_tenant_id,
        params=params,
    )

    return InstanceAssociationList(api_result.get("data", []))
