class TopoHostError(Exception):
    """拓扑主机相关异常的基类

    CMDB接口 find_host_by_topo异常时抛出，
    例如：
    - 拓扑实例在CMDB被删除后，获取不存在的CMDB实例，接口抛出异常

    """

    pass


class BizHostError(Exception):
    """拓扑主机相关异常的基类

    CMDB接口 list_biz_hosts异常时抛出，

    """

    pass
