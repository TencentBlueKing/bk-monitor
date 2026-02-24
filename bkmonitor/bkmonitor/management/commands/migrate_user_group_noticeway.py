"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import logging

from django.core.management.base import BaseCommand
from django.db import DatabaseError, transaction

from bkmonitor.models.strategy import UserGroup

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    """迁移用户组通知方式命令.

    批量迁移指定业务下用户组的通知方式配置，支持预览和替换两种模式。

    功能特性
    --------
    - **预览模式**：查询包含指定通知方式的用户组，不修改数据
    - **替换模式**：批量替换通知方式，使用事务保证数据一致性
    - **全面覆盖**：支持 alert_notice、action_notice、duty_notice 三种配置
    - **智能匹配**：自动识别嵌套结构中的通知方式配置
    - **安全可靠**：使用数据库事务，失败自动回滚

    数据结构支持
    ------------
    本命令支持以下三种通知配置结构：

    1. **alert_notice**（告警通知配置）：
       - 结构：``[{"time_range": "...", "notify_config": [{"level": X, "notice_ways": [...]}]}]``
       - 包含：level=1（致命）、level=2（预警）、level=3（提醒）

    2. **action_notice**（执行通知配置）：
       - 结构：``[{"time_range": "...", "notify_config": [{"phase": X, "notice_ways": [...]}]}]``
       - 包含：phase=1（失败时）、phase=2（成功时）、phase=3（执行前）

    3. **duty_notice**（值班通知配置）：
       - 结构：``{"plan_notice": {"notice_ways": [...]}, "personal_notice": {"notice_ways": [...]}}``
       - 包含：plan_notice（排班通知）、personal_notice（个人通知）

    处理逻辑
    --------
    - **匹配检测**：递归遍历所有 notify_config，检查 notice_ways 中是否包含指定通知方式
    - **批量替换**：找到匹配后，替换所有出现的通知方式（包括同一配置中的重复项）
    - **隔离性保证**：只替换指定的通知方式，不影响其他通知方式
    - **事务保护**：所有更新操作在同一事务中执行，失败自动回滚

    使用方法
    --------
    ::

        python manage.py migrate_user_group_noticeway --bk_biz_id <业务ID> --from_noticeway <源通知方式> [--to_noticeway <目标通知方式>]

    参数说明
    --------
    :param bk_biz_id: 业务ID（必需）
    :param from_noticeway: 源通知方式（必需），如 'rtx'、'weixin'、'mail' 等
    :param to_noticeway: 目标通知方式（可选），不传则为预览模式

    示例
    ----
    1. **预览模式** - 查询包含 rtx 通知方式的用户组::

        python manage.py migrate_user_group_noticeway --bk_biz_id 2 --from_noticeway rtx

    输出示例::

        【预览模式】查询业务 2 下包含通知方式 'rtx' 的用户组

        📋 找到 3 个包含通知方式 'rtx' 的用户组：

        用户组ID         用户组名称                      匹配字段
        --------------------------------------------------------------------------------
        ***452          da***ng                        alert_notice, action_notice
        ***852          sa***1                         alert_notice, action_notice
        ***719          【A***组                       alert_notice, action_notice

    2. **替换模式** - 将 rtx 替换为 weixin::

        python manage.py migrate_user_group_noticeway --bk_biz_id 2 --from_noticeway rtx --to_noticeway weixin

    输出示例::

        【替换模式】将业务 2 下的通知方式 'rtx' 替换为 'weixin'

        ✅ 成功替换 3 个用户组的通知方式：

        用户组ID         用户组名称                      替换字段
        --------------------------------------------------------------------------------
        ***452          da***ng                        alert_notice, action_notice
        ***852          sa***1                         alert_notice, action_notice
        ***719          【A***组                       alert_notice, action_notice

        💡 替换详情: 'rtx' → 'weixin'

    3. **处理重复通知方式** - 自动替换同一配置中的所有重复项::

        # 假设用户组 1719 的 alert_notice 中 level=1 有 2 个 rtx
        python manage.py migrate_user_group_noticeway --bk_biz_id -42 --from_noticeway rtx --to_noticeway weixin

        # 结果：level=1 的 2 个 rtx 都会被替换为 weixin

    4. **混合通知方式** - 只替换指定的通知方式，不影响其他::

        # 假设 action_notice 中 phase=3 有 ['rtx', 'sms']
        python manage.py migrate_user_group_noticeway --bk_biz_id 2 --from_noticeway rtx --to_noticeway weixin

        # 结果：phase=3 变为 ['weixin', 'sms']，sms 保持不变

    注意事项
    --------
    .. warning::
       - **数据备份**：执行替换操作前，建议先使用预览模式确认影响范围
       - **业务隔离**：只影响指定业务下的用户组，不会跨业务修改
       - **事务保护**：替换失败会自动回滚，不会产生部分更新
       - **日志记录**：所有操作都会记录日志，便于审计和排查

    .. note::
       - 预览模式不会修改任何数据，可以安全执行
       - 替换模式会立即生效，无需重启服务
       - 支持所有蓝鲸监控支持的通知方式类型

    常见场景
    --------
    1. **通知方式下线**：将即将下线的通知方式迁移到新方式
    2. **通知方式重命名**：统一通知方式命名规范
    3. **批量配置调整**：快速调整多个用户组的通知配置
    4. **配置审计**：查询使用特定通知方式的用户组

    技术实现
    --------
    - **性能优化**：使用 ``values()`` 只加载必要字段，减少内存占用
    - **批量更新**：使用 ``update()`` 批量更新，减少数据库交互
    - **早期返回**：找到第一个匹配后立即返回，避免重复记录
    - **字典去重**：使用字典存储匹配结果，确保用户组不重复
    """

    help = "迁移用户组通知方式 - 支持预览和替换"

    def add_arguments(self, parser):
        parser.add_argument("--bk_biz_id", type=int, required=True, help="业务ID")
        parser.add_argument("--from_noticeway", type=str, required=True, help="源通知方式")
        parser.add_argument(
            "--to_noticeway", type=str, required=False, default="", help="目标通知方式(不传则为预览模式)"
        )

    def handle(self, *args, **options):
        bk_biz_id = options["bk_biz_id"]
        from_noticeway = options["from_noticeway"]
        to_noticeway = options["to_noticeway"]

        # 输入验证
        if not from_noticeway or not from_noticeway.strip():
            self.stdout.write(self.style.ERROR("错误: from_noticeway 不能为空"))
            return

        if to_noticeway:
            # 替换模式
            if not to_noticeway.strip():
                self.stdout.write(self.style.ERROR("错误: to_noticeway 不能为空字符串"))
                return
            self.stdout.write(
                self.style.SUCCESS(
                    f"\n【替换模式】将业务 {bk_biz_id} 下的通知方式 '{from_noticeway}' 替换为 '{to_noticeway}'"
                )
            )
            migrate_user_group_noticeway(bk_biz_id, from_noticeway, to_noticeway, preview_mode=False)
        else:
            # 预览模式
            self.stdout.write(
                self.style.WARNING(f"\n【预览模式】查询业务 {bk_biz_id} 下包含通知方式 '{from_noticeway}' 的用户组")
            )
            migrate_user_group_noticeway(bk_biz_id, from_noticeway, "", preview_mode=True)


def migrate_user_group_noticeway(
    bk_biz_id: int, from_noticeway: str, to_noticeway: str = "", preview_mode: bool = True
) -> None:
    """迁移用户组通知方式。

    :param bk_biz_id: 业务ID。
    :param from_noticeway: 源通知方式。
    :param to_noticeway: 目标通知方式。空字符串表示预览模式。
    :param preview_mode: 是否为预览模式。
    :raises django.db.DatabaseError: 数据库操作失败时。
    """
    # 查询该业务下的所有用户组,一次性加载所有需要的字段
    user_groups = list(
        UserGroup.objects.filter(bk_biz_id=bk_biz_id).values(
            "id", "name", "alert_notice", "action_notice", "duty_notice"
        )
    )

    if not user_groups:
        print(f"\n⚠️  业务 {bk_biz_id} 下没有找到任何用户组")
        return

    # 使用字典存储匹配的用户组信息，提高查找效率
    matched_groups_dict = {}
    # 待更新的用户组(用于批量更新)
    groups_to_update = []

    for user_group_data in user_groups:
        group_id = user_group_data["id"]
        group_name = user_group_data["name"]

        # 检查三个通知配置字段
        alert_notice_matched = check_and_collect_matched(
            group_id,
            group_name,
            "alert_notice",
            user_group_data["alert_notice"],
            from_noticeway,
            matched_groups_dict,
        )
        action_notice_matched = check_and_collect_matched(
            group_id,
            group_name,
            "action_notice",
            user_group_data["action_notice"],
            from_noticeway,
            matched_groups_dict,
        )
        duty_notice_matched = check_and_collect_matched(
            group_id,
            group_name,
            "duty_notice",
            user_group_data["duty_notice"],
            from_noticeway,
            matched_groups_dict,
        )

        # 如果非预览模式,准备更新
        if not preview_mode and (alert_notice_matched or action_notice_matched or duty_notice_matched):
            updated_data = {"id": group_id}
            if alert_notice_matched:
                updated_data["alert_notice"] = replace_noticeway(
                    user_group_data["alert_notice"], from_noticeway, to_noticeway
                )
            if action_notice_matched:
                updated_data["action_notice"] = replace_noticeway(
                    user_group_data["action_notice"], from_noticeway, to_noticeway
                )
            if duty_notice_matched:
                updated_data["duty_notice"] = replace_noticeway_in_dict(
                    user_group_data["duty_notice"], from_noticeway, to_noticeway
                )
            groups_to_update.append(updated_data)

    # 转换为列表用于输出
    matched_groups = list(matched_groups_dict.values())

    # 如果非预览模式,使用事务批量更新
    if not preview_mode and groups_to_update:
        try:
            with transaction.atomic():
                for group_data in groups_to_update:
                    group_id = group_data.pop("id")
                    UserGroup.objects.filter(id=group_id).update(**group_data)
                logger.info(
                    f"successfully migrated notice way from '{from_noticeway}' to '{to_noticeway}' "
                    f"for {len(groups_to_update)} user groups in business {bk_biz_id}"
                )
        except DatabaseError as e:
            error_msg = f"failed to migrate notice way: {e}"
            logger.exception(error_msg)
            print(f"\n❌ 更新失败: {e}")
            raise

    # 输出结果
    if preview_mode:
        print_preview_result(matched_groups, from_noticeway)
    else:
        print_replace_result(matched_groups, from_noticeway, to_noticeway)


def check_and_collect_matched(
    group_id: int,
    group_name: str,
    field_name: str,
    config_data,
    from_noticeway: str,
    matched_groups_dict: dict,
) -> bool:
    """检查配置中是否包含指定通知方式,并收集匹配信息。

    :param group_id: 用户组ID。
    :param group_name: 用户组名称。
    :param field_name: 字段名称。
    :param config_data: 配置数据,可能是列表、字典或None。
    :param from_noticeway: 源通知方式。
    :param matched_groups_dict: 匹配的用户组字典(key为group_id)。
    :return: 是否匹配。
    """
    # 空值检查
    if config_data is None:
        return False

    if isinstance(config_data, list):
        # alert_notice 和 action_notice 是列表结构
        # 结构: [{"time_range": "...", "notify_config": [{"level/phase": X, "notice_ways": [...]}]}]
        for item in config_data:
            if not isinstance(item, dict):
                continue
            # 获取 notify_config 列表
            notify_config_list = item.get("notify_config", [])
            if not isinstance(notify_config_list, list):
                continue
            # 遍历 notify_config 中的每个配置项
            for notify_config in notify_config_list:
                if not isinstance(notify_config, dict):
                    continue
                # 检查 notice_ways
                notice_ways = notify_config.get("notice_ways", [])
                if isinstance(notice_ways, list):
                    for notice_way_config in notice_ways:
                        if isinstance(notice_way_config, dict) and notice_way_config.get("name") == from_noticeway:
                            add_matched_group(matched_groups_dict, group_id, group_name, field_name)
                            # 找到匹配后直接返回，无需继续遍历
                            return True
    elif isinstance(config_data, dict):
        # duty_notice 是字典结构
        # 检查直接包含 notice_ways 的情况
        if "notice_ways" in config_data and isinstance(config_data["notice_ways"], list):
            for notice_way_config in config_data["notice_ways"]:
                if isinstance(notice_way_config, dict) and notice_way_config.get("name") == from_noticeway:
                    add_matched_group(matched_groups_dict, group_id, group_name, field_name)
                    return True

        # 检查 duty_notice 中的嵌套结构（plan_notice 和 personal_notice）
        for sub_key in ["plan_notice", "personal_notice"]:
            if sub_key in config_data and isinstance(config_data[sub_key], dict):
                sub_config = config_data[sub_key]
                if "notice_ways" in sub_config and isinstance(sub_config["notice_ways"], list):
                    for notice_way_config in sub_config["notice_ways"]:
                        if isinstance(notice_way_config, dict) and notice_way_config.get("name") == from_noticeway:
                            add_matched_group(matched_groups_dict, group_id, group_name, field_name)
                            return True

    return False


def add_matched_group(matched_groups_dict: dict, group_id: int, group_name: str, field_name: str) -> None:
    """添加匹配的用户组信息。

    :param matched_groups_dict: 匹配的用户组字典(key为group_id)。
    :param group_id: 用户组ID。
    :param group_name: 用户组名称。
    :param field_name: 字段名称。
    """
    if group_id in matched_groups_dict:
        # 用户组已存在，添加字段（避免重复）
        if field_name not in matched_groups_dict[group_id]["fields"]:
            matched_groups_dict[group_id]["fields"].append(field_name)
    else:
        # 新用户组
        matched_groups_dict[group_id] = {"id": group_id, "name": group_name, "fields": [field_name]}


def replace_noticeway(config_list: list, from_noticeway: str, to_noticeway: str) -> list:
    """替换列表结构中的通知方式。

    :param config_list: 配置列表。
    :param from_noticeway: 源通知方式。
    :param to_noticeway: 目标通知方式。
    :return: 替换后的配置列表。
    """
    if not isinstance(config_list, list):
        return config_list

    # 结构: [{"time_range": "...", "notify_config": [{"level/phase": X, "notice_ways": [...]}]}]
    for item in config_list:
        if not isinstance(item, dict):
            continue
        # 获取 notify_config 列表
        notify_config_list = item.get("notify_config", [])
        if not isinstance(notify_config_list, list):
            continue
        # 遍历 notify_config 中的每个配置项
        for notify_config in notify_config_list:
            if not isinstance(notify_config, dict):
                continue
            # 替换 notice_ways 中的通知方式
            notice_ways = notify_config.get("notice_ways", [])
            if isinstance(notice_ways, list):
                for notice_way_config in notice_ways:
                    if isinstance(notice_way_config, dict) and notice_way_config.get("name") == from_noticeway:
                        notice_way_config["name"] = to_noticeway
    return config_list


def replace_noticeway_in_dict(config_dict: dict, from_noticeway: str, to_noticeway: str) -> dict:
    """替换字典结构中的通知方式。

    :param config_dict: 配置字典。
    :param from_noticeway: 源通知方式。
    :param to_noticeway: 目标通知方式。
    :return: 替换后的配置字典。
    """
    if not isinstance(config_dict, dict):
        return config_dict

    # 处理直接包含 notice_ways 的情况
    if "notice_ways" in config_dict and isinstance(config_dict["notice_ways"], list):
        for notice_way_config in config_dict["notice_ways"]:
            if isinstance(notice_way_config, dict) and notice_way_config.get("name") == from_noticeway:
                notice_way_config["name"] = to_noticeway

    # 处理 duty_notice 中的嵌套结构（plan_notice 和 personal_notice）
    for sub_key in ["plan_notice", "personal_notice"]:
        if sub_key in config_dict and isinstance(config_dict[sub_key], dict):
            sub_config = config_dict[sub_key]
            if "notice_ways" in sub_config and isinstance(sub_config["notice_ways"], list):
                for notice_way_config in sub_config["notice_ways"]:
                    if isinstance(notice_way_config, dict) and notice_way_config.get("name") == from_noticeway:
                        notice_way_config["name"] = to_noticeway

    return config_dict


def print_preview_result(matched_groups: list, from_noticeway: str) -> None:
    """打印预览结果。

    :param matched_groups: 匹配的用户组列表。
    :param from_noticeway: 源通知方式。
    """
    if not matched_groups:
        print(f"\n✅ 未找到包含通知方式 '{from_noticeway}' 的用户组")
        return

    print(f"\n📋 找到 {len(matched_groups)} 个包含通知方式 '{from_noticeway}' 的用户组：\n")
    print(f"{'用户组ID':<15} {'用户组名称':<30} {'匹配字段'}")
    print("-" * 80)
    for group in matched_groups:
        fields_str = ", ".join(group["fields"])
        print(f"{group['id']:<15} {group['name']:<30} {fields_str}")


def print_replace_result(matched_groups: list, from_noticeway: str, to_noticeway: str) -> None:
    """打印替换结果。

    :param matched_groups: 匹配的用户组列表。
    :param from_noticeway: 源通知方式。
    :param to_noticeway: 目标通知方式。
    """
    if not matched_groups:
        print(f"\n✅ 未找到包含通知方式 '{from_noticeway}' 的用户组，无需替换")
        return

    print(f"\n✅ 成功替换 {len(matched_groups)} 个用户组的通知方式：\n")
    print(f"{'用户组ID':<15} {'用户组名称':<30} {'替换字段'}")
    print("-" * 80)
    for group in matched_groups:
        fields_str = ", ".join(group["fields"])
        print(f"{group['id']:<15} {group['name']:<30} {fields_str}")

    print(f"\n💡 替换详情: '{from_noticeway}' → '{to_noticeway}'")
