from django.db import migrations
from apps.log_search.constants import FavoriteGroupType


def forwards_func(apps, schema_editor):
    favorite_group_model = apps.get_model("log_search", "FavoriteGroup")
    favorite_model = apps.get_model("log_search", "Favorite")
    # 获取所有私有分组和未分组
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
                target_group_id = checked_groups[key]
                print(f"group: {group.name} has data, moving to group_id: {target_group_id}")

                existing_favorites = favorite_model.objects.filter(group_id=target_group_id)
                existing_favorite_names = set(existing_favorites.values_list("name", flat=True))
                for item in items:
                    # 数据库唯一约束，需要生成唯一的收藏名称
                    unique_name = get_unique_favorite_name(item.name, existing_favorite_names)
                    if unique_name != item.name:
                        print(f"Renaming favorite {item.name} (id: {item.id}) to {unique_name}")
                        existing_favorite_names.add(unique_name)
                    item.name = unique_name
                    item.group_id = target_group_id
                    item.save(update_fields=["name", "group_id"])
            groups_to_delete.append(group.id)
        else:
            # 记录第一个遇到的分组ID
            checked_groups[key] = group.id
    favorite_group_model.objects.filter(id__in=groups_to_delete).delete()
    print(f"Deleted {len(groups_to_delete)} groups\n")


def get_unique_favorite_name(base_name, favorite_names):
    """
    生成唯一的收藏名称，名称重复时添加后缀，否则保持不变
    """
    candidate_name = base_name
    suffix_num = 1
    while candidate_name in favorite_names:
        candidate_name = f"{base_name}_{suffix_num}"
        suffix_num += 1
    return candidate_name


class Migration(migrations.Migration):
    dependencies = [
        ("log_search", "0089_logindexset_query_alias_settings"),
    ]

    operations = [
        migrations.RunPython(forwards_func),
    ]
