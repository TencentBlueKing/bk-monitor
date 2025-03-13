from typing import Dict, List, Optional, Tuple

from monitor_web.models.scene_view import SceneViewModel
from monitor_web.scene_view.builtin import BuiltinProcessor


class CustomMetricV2BuiltinProcessor(BuiltinProcessor):
    """
    仅存储视图配置，不存储和生成任何具体的图表查询配置
    默认视图为自由视图，不创建默认视图
    """

    @classmethod
    def get_auto_view_panels(cls, view: SceneViewModel) -> Tuple[List[Dict], List[Dict]]:
        """
        获取平铺视图配置
        """
        return [], []

    @classmethod
    def create_default_views(cls, bk_biz_id: int, scene_id: str, view_type: str, existed_views):
        """
        不创建默认视图，默认视图为自由视图
        """
        return

    @classmethod
    def is_builtin_scene(cls, scene_id: str) -> bool:
        return scene_id.startswith("custom_metric_v2_")

    @classmethod
    def get_view_config(cls, view: SceneViewModel, *args, **kwargs) -> Dict:
        """
        根据视图对象生成视图配置
        """
        return {
            "id": view.id,
            "name": view.name,
            "mode": SceneViewModel.SceneViewType.auto,
            "variables": [],
            "order": [],
            "panels": [],
            "list": [],
            "options": view.options,
        }

    @classmethod
    def create_or_update_view(
        cls, bk_biz_id: int, scene_id: str, view_type: str, view_id: str, view_config: Dict
    ) -> Optional[SceneViewModel]:
        """
        创建或更新视图
        options: {
            # 显示的指标
            "show_metrics": [],
            # 指标过滤条件，[{"condition": "and", "key": "xxx", "method": "eq", "value": ["v1"]}]
            "condition": [],
            # 聚合维度，[{"field": "xxxx", "split": True}, {"field": "yyy", "split": False}]
            "group_by": [],
            # 限制返回的series数量，top/bottom，limit=0表示不限制
            "limit": {"function": "top", "limit": 0},
            # 对比配置, 对比模式, time: 时间对比, metric: 指标对比。offset: 对比偏移量
            "compare": {"type": "time", "offset": "1d"},
            # 图表配置
            "chart_config": {
                # 是否展示统计信息
                "show_statistic": False,
                # 是否展示峰值和谷值
                "show_peakand_valley": False,
                # 是否展示常用维度
                "show_common_dimensions": False,
                # 图表列数
                "column_number": 1,
            },
        }
        """
        view, _ = SceneViewModel.objects.update_or_create(
            bk_biz_id=bk_biz_id,
            scene_id=scene_id,
            type=view_type,
            id=view_id,
            defaults={
                "name": view_config["name"],
                "mode": SceneViewModel.SceneViewType.auto,
                "options": view_config["options"],
            },
        )
        return view
