from typing import Any, Dict, List
from urllib import parse

from django.db.models import Q
from django.http import HttpResponse

from bkmonitor.data_source import conditions_to_q, filter_dict_to_conditions
from bkmonitor.data_source.unify_query.builder import QueryConfigBuilder
from metadata.models import ResultTable


def generate_file_download_response(file_content: str, file_name: str) -> HttpResponse:
    """生成一个带有文件内容和文件名的 HTTP 响应"""
    # 对文件名进行 URL 编码
    file_name = parse.quote(file_name, encoding="utf8")
    file_name = parse.unquote(file_name, encoding="ISO8859_1")
    response = HttpResponse(file_content)
    response["Content-Type"] = "application/x-msdownload"
    response["Content-Disposition"] = f'attachment; filename="{parse.quote(file_name, encoding="utf8")}"'
    return response


def get_q_from_query_config(query_config: Dict[str, Any]) -> QueryConfigBuilder:
    return (
        QueryConfigBuilder((query_config["data_type_label"], query_config["data_source_label"]))
        .table(query_config["table"])
        .time_field("time")
        .group_by(*query_config.get("group_by", []))
        .conditions(query_config.get("where", []))
        .filter(conditions_to_q(filter_dict_to_conditions(query_config.get("filter_dict") or {}, [])))
        .query_string(query_config.get("query_string") or "")
    )


def get_data_labels_map(bk_biz_id: int, tables: List[Dict[str, Any]]) -> Dict[str, str]:
    data_labels_map = {}
    for table in tables:
        data_labels = (
            ResultTable.objects.filter(bk_biz_id__in=[0, bk_biz_id])
            .filter(Q(table_id=table) | Q(data_label=table))
            .values("table_id", "data_label")
        )
        for data_label_entry in data_labels:
            data_labels_map[data_label_entry["table_id"]] = data_label_entry["data_label"]
            data_labels_map[data_label_entry["data_label"]] = data_label_entry["data_label"]
    return data_labels_map
