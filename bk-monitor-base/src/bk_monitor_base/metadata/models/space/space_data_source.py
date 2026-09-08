import logging

from bk_monitor_base.metadata import models
from bk_monitor_base.metadata.models.space import constants

logger = logging.getLogger("metadata")


def get_biz_data_id() -> dict[int, list[int]]:
    """获取业务对应的数据源关联关系"""
    platform_biz_id = 0
    # 同时排除掉小于 0 的数据
    result_table_dict = {
        rt.table_id: rt.bk_biz_id for rt in models.ResultTable.objects.exclude(bk_biz_id__lte=platform_biz_id)
    }
    # 过滤数据源数据
    data_id_dict = {
        ds_rt.table_id: ds_rt.bk_data_id
        for ds_rt in models.DataSourceResultTable.objects.filter(table_id__in=result_table_dict.keys())
    }
    biz_data_id_dict = {}
    # 匹配数据，格式{biz_id: [data_id]}
    for rt, biz in result_table_dict.items():
        data_id = data_id_dict.get(rt)
        if not data_id:
            logger.warning("result table: %s not found data id", rt)
            continue
        if biz in biz_data_id_dict:
            biz_data_id_dict[biz].append(data_id)
        else:
            biz_data_id_dict[biz] = [data_id]

    return biz_data_id_dict


def get_real_biz_id(data_name: str, is_in_ts_group: bool, is_in_event_group: bool, space_uid: str | None = None) -> int:
    # 平台业务ID，赋值为 0
    platform_biz_id = 0
    # 如果 space_uid 有值，则直接取里面的 space_id 作为业务 id
    if space_uid:
        real_biz_id = space_uid.split("__", -1)[-1]
    # 如果在tsgroup中，获取拆分后的第一个值
    elif is_in_ts_group:
        real_biz_id = data_name.split("_")[0]
    # 如果在eventgroup中，获取拆分后的最后一个值
    elif is_in_event_group:
        real_biz_id = data_name.split("_")[-1]
    else:
        real_biz_id = platform_biz_id
    # 转换为整数，如果异常，则为平台级业务
    try:
        real_biz_id = int(real_biz_id)
    except Exception:
        real_biz_id = platform_biz_id
    return real_biz_id


def get_real_zero_biz_data_id() -> dict[str, list[int]] | list[int]:
    """获取数据源归属的业务
    1. 查询数据源对应的rt，如果bk_biz_id为0，则为所属业务
    2. 如果为0，则需要查询 tsgroup 或者 eventgroup, 并且设置为平台级ID
        - 如果在 tsgroup 中，则需要按照 data_name 以"_"拆分，取最后一个为业务ID
        - 如果在 eventgroup 中，则需要按照 data_name 以"_"拆分，去第一个为业务ID
    """
    # 平台业务ID，赋值为 0
    platform_biz_id = 0
    # 获取业务ID为 0 的结果表
    result_table_list = models.ResultTable.objects.filter(bk_biz_id=platform_biz_id).values_list("table_id", flat=True)
    # 过滤数据源数据
    data_id_list = models.DataSourceResultTable.objects.filter(table_id__in=result_table_list).values_list(
        "bk_data_id", flat=True
    )
    # 这里通过 etl_conf 过滤指定的类型
    data_sources = models.DataSource.objects.filter(
        bk_data_id__in=data_id_list, etl_config__in=constants.SPACE_DATASOURCE_ETL_LIST
    ).values("bk_data_id", "data_name", "space_uid")
    # 查询 tsgroup 和 eventgroup, 是否有对应的数据源ID
    ts_data_id_list = models.TimeSeriesGroup.objects.filter(bk_data_id__in=data_id_list).values_list(
        "bk_data_id", flat=True
    )
    event_data_id_list = models.EventGroup.objects.filter(bk_data_id__in=data_id_list).values_list(
        "bk_data_id", flat=True
    )
    # 如果在 ts group 中，则通过data name 拆分，获取biz_id
    biz_data_id_dict = {}
    for ds in data_sources:
        bk_data_id = ds["bk_data_id"]
        is_in_ts_group = bk_data_id in ts_data_id_list
        is_in_event_group = bk_data_id in event_data_id_list
        real_biz_id = get_real_biz_id(ds["data_name"], is_in_ts_group, is_in_event_group, ds["space_uid"])
        # 组装数据
        if real_biz_id in biz_data_id_dict:
            biz_data_id_dict[real_biz_id].append(bk_data_id)
        else:
            biz_data_id_dict[real_biz_id] = [bk_data_id]
    return biz_data_id_dict, list(data_id_list)
