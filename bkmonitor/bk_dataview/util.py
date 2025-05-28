import math

from bk_dataview.models import Dashboard
import json


def get_dashboard_data_view_size(uid: str, panel_id: str) -> dict:
    """
    获取仪表盘某张图表的大小信息(转换后)
    转换比例：
    图数量   1      2     3
    h：    37.11  36.85  36
    w：    66.79  66.58  66
    当前策略为取单图最大比例
    """
    # 获取指定仪表盘的data信息
    json_data = Dashboard.objects.filter(uid=uid).values("data")
    # 解析data信息， 获取图表大小信息
    data = json.loads(json_data)
    if isinstance(panel_id, str):
        panel_id = int(panel_id)
    panel = next((p for p in data.get("panels", []) if p.get("id") == panel_id), {})
    grid_pos = panel.get("gridPos", {})
    actual_size = {"w": math.ceil(grid_pos.get("w", 0)) * 66.79, "h": math.ceil(grid_pos.get("h", 0) * 37.11)}
    return actual_size
