from django.db import migrations
from apps.log_search.constants import FavoriteGroupType


def forwards_func(apps, schema_editor):
    favorite_group_model = apps.get_model("log_search", "FavoriteGroup")
    favorite_model = apps.get_model("log_search", "Favorite")

    groups = favorite_group_model.objects.filter(
        group_type__in=[FavoriteGroupType.PRIVATE.value, FavoriteGroupType.UNGROUPED.value]
    ).order_by("created_at")

    checked_groups = {}
    groups_to_delete = []
    for group in groups:
        if group.group_type == FavoriteGroupType.UNGROUPED.value:
            # 未分组的唯一性判断不包含 created_by 字段
            key = f"{group.source_app_code}_{group.space_uid}_{group.group_type}"
        else:
            key = f"{group.source_app_code}_{group.space_uid}_{group.group_type}_{group.created_by}"
        if key in checked_groups:
            # 如果已经存在相同的分组，检查是否有数据，有则将数据转移到第一个遇到的分组
            items = favorite_model.objects.filter(group_id=group.id)
            if items:
                print(f"group: {group.name} has data, moving to group_id: {checked_groups[key]}")
                for item in items:
                    item.group_id = checked_groups[key]
                    try:
                        item.save(update_fields=["group_id"])
                    except Exception as e:
                        print(f"Error moving item: {item.id} - {item.name}, error: {e}")
            groups_to_delete.append(group.id)
        else:
            # 记录第一个遇到的分组ID
            checked_groups[key] = group.id
    favorite_group_model.objects.filter(id__in=groups_to_delete).delete()
    print(f"Deleted {len(groups_to_delete)} groups\n")


class Migration(migrations.Migration):
    dependencies = [
        ("log_search", "0089_logindexset_query_alias_settings"),
    ]

    operations = [
        migrations.RunPython(forwards_func),
    ]
