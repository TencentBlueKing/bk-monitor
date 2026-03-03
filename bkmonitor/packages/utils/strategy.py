from bkmonitor.action.serializers import UserGroupDetailSlz, UserGroupSlz
from bkmonitor.models import StrategyActionConfigRelation, UserGroup


def fill_user_groups(configs: list[dict], with_detail: bool = False) -> None:
    """策略配置补充告警组信息

    Args:
        configs: 策略配置列表
        with_detail: 是否显示告警组详情
    """
    strategy_ids = [config["id"] for config in configs]
    action_relations = StrategyActionConfigRelation.objects.filter(strategy_id__in=strategy_ids)
    user_group_ids = []
    for action_relation in action_relations:
        user_group_ids.extend(action_relation.validated_user_groups)
    if with_detail:
        user_groups_slz = UserGroupDetailSlz(UserGroup.objects.filter(id__in=user_group_ids), many=True).data
    else:
        user_groups_slz = UserGroupSlz(UserGroup.objects.filter(id__in=user_group_ids), many=True).data
    user_groups = {group["id"]: dict(group) for group in user_groups_slz}

    for config in configs:
        for action in config["actions"] + [config["notice"]]:
            user_group_list = []
            for user_group_id in action["user_groups"]:
                if user_group_id and user_group_id in user_groups:
                    user_group_list.append(user_groups[user_group_id])
            action["user_group_list"] = user_group_list
