from bkmonitor.data_migrate.fetcher.base import FetcherResultType
from bkmonitor.models.base import ReportContents, ReportItems
from bkmonitor.models.report import Report, ReportChannel
from constants.report import GRAPH_ID_REGEX


def _parse_graph_biz_ids(graph: str) -> tuple[set[int], bool]:
    """
    从旧版订阅报表的 graph tag 中提取业务 ID。

    返回值：
    - 第一个元素是解析出的数字业务 ID 集合
    - 第二个元素表示该图表是否应视为“全局/跨业务”
      - 包含多个业务
      - 或使用内置业务类型（非数字）
    """
    match = GRAPH_ID_REGEX.match(graph or "")
    if not match:
        return set(), True

    raw_biz_ids = match.group(1).split(",")
    biz_ids = {int(biz_id) for biz_id in raw_biz_ids if biz_id.lstrip("-").isdigit()}
    has_builtin_biz = any(not biz_id.lstrip("-").isdigit() for biz_id in raw_biz_ids)
    is_cross_biz = has_builtin_biz or len(biz_ids) != 1
    return biz_ids, is_cross_biz


def _get_report_item_ids_by_biz(bk_biz_id: int | None) -> list[int]:
    """
    根据旧版订阅报表内容中的 graphs 反推报表归属。

    规则：
    - ``bk_biz_id is None``：返回全部报表
    - 仅关联单一业务：归属该业务
    - 关联多个业务或内置业务：视为全局报表，归属 ``bk_biz_id=0``
    """
    if bk_biz_id is None:
        return list(ReportItems.objects.values_list("id", flat=True))

    report_item_ids: list[int] = []
    report_contents = ReportContents.objects.values("report_item", "graphs")
    report_biz_mapping: dict[int, tuple[set[int], bool]] = {}

    for content in report_contents:
        current_biz_ids: set[int] = set()
        current_is_global = False
        for graph in content["graphs"] or []:
            biz_ids, is_cross_biz = _parse_graph_biz_ids(graph)
            current_biz_ids.update(biz_ids)
            current_is_global = current_is_global or is_cross_biz

        report_item_id = content["report_item"]
        existed_biz_ids, existed_is_global = report_biz_mapping.get(report_item_id, (set(), False))
        merged_biz_ids = existed_biz_ids | current_biz_ids
        merged_is_global = existed_is_global or current_is_global or len(merged_biz_ids) != 1
        report_biz_mapping[report_item_id] = (merged_biz_ids, merged_is_global)

    for report_item_id, (biz_ids, is_global) in report_biz_mapping.items():
        if is_global and bk_biz_id == 0:
            report_item_ids.append(report_item_id)
            continue
        if not is_global and biz_ids == {bk_biz_id}:
            report_item_ids.append(report_item_id)

    return report_item_ids


def get_report_fetcher(bk_biz_id: int | None) -> list[FetcherResultType]:
    """
    获取报表相关迁移 ORM 查询配置。

    包含两类报表：
    - 旧版仪表盘订阅报表：通过 ``ReportContents.graphs`` 反推业务归属
    - 新版订阅报表：``Report`` 直接按业务过滤，``ReportChannel`` 再通过 ``report_id`` 关联
    """
    report_item_ids = _get_report_item_ids_by_biz(bk_biz_id)
    report_filters = None if bk_biz_id is None else {"bk_biz_id": bk_biz_id}
    report_ids = Report.objects.filter(**(report_filters or {})).values_list("id", flat=True)
    return [
        (ReportItems, {"id__in": report_item_ids}, None),
        (ReportContents, {"report_item__in": report_item_ids}, None),
        (Report, report_filters, None),
        (ReportChannel, {"report_id__in": report_ids}, None),
    ]
