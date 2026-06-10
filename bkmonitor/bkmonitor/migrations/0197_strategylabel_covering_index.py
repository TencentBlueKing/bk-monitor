# Generated manually: 为 StrategyLabel 增加覆盖索引 (strategy_id, label_name)
# 优化 get_strategy_label_list 标签计数查询：WHERE strategy_id IN (...) GROUP BY label_name。
# 原 index_together(label_name, strategy_id) 的 leading 列非过滤列 strategy_id，无法 seek。

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("bkmonitor", "0196_add_issue_merge_relation"),
    ]

    operations = [
        migrations.AddIndex(
            model_name="strategylabel",
            index=models.Index(fields=["strategy_id", "label_name"], name="idx_strlabel_sid_lname"),
        ),
    ]
