# -*- coding: utf-8 -*-
from django.core.management.base import BaseCommand
from bkmonitor.models.strategy import DutyArrange, UserGroup


class Command(BaseCommand):
    help = "删除告警组中的指定用户，仅处理直接通知的用户"

    def add_arguments(self, parser):
        parser.add_argument("--user_id", type=str, help="要删除用户ID")

    def handle(self, *args, **options):
        user_id = options["user_id"]
        delete_user(user_id)


def delete_user(user_id):
    """
    删除用户
    """
    duty_arranges = DutyArrange.objects.all().only("users", "user_group_id")

    # 初始化处理容器
    update_list = []
    related_group = set()  # 使用集合自动去重

    # 遍历处理每个排班记录
    for duty_arrange in duty_arranges:
        try:
            original_length = len(duty_arrange.users)
            users = [user for user in duty_arrange.users if user.get("id") != user_id]

            # 检测到数据变更
            if len(users) < original_length:
                duty_arrange.users = users
                update_list.append(duty_arrange)
                related_group.add(duty_arrange.user_group_id)  # 集合添加
        except Exception as e:
            print(f"duty_arrange异常:{str(e)}")
            continue

    if update_list:
        DutyArrange.objects.bulk_update(update_list, ["users"])

    if related_group:
        related_groups = UserGroup.objects.filter(id__in=related_group).values("name", "bk_biz_id")

        # 结构化日志输出
        print("更新的用户组有：")
        print("用户组名称,业务ID\n")
        for group in related_groups:
            print(f"{group['name']},{group['bk_biz_id']}")

    else:
        print(f"用户ID：`{user_id}`不存在")
