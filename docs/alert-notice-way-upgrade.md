# 告警通知类型升级说明

升级后，告警中心按非父通知记录统计通知渠道，包含同一告警各轮通知产生的记录。渠道出现表示产生过通知记录，发送结果仍以通知详情为准。原有 `ALERT_NOTICE_WAY_BY_RECORDS` 配置不再生效。

正常升级不回填历史记录，也不需要为历史索引补 mapping。升级前未写入 `notice_way` 的记录不会计入通知类型筛选或统计。正向筛选可能漏命中，通知分布可能少计；使用相同通知条件的导出、趋势查询也只覆盖已索引的渠道。

告警列表接口会标记结果不完整，通知类型排除筛选会拒绝不完整结果。设置 `allow_partial=false` 的请求如果使用通知筛选或请求通知分布，也会报结果不完整。不使用通知条件且不需要聚合统计的调用可传 `show_aggs=false`。

告警产生、通知发送、通知详情与原始记录不受此历史缺字段影响。上线后确认当前动作写索引的 `notice_way` mapping 为 `keyword`，并用升级后实际产生的通知记录验证筛选和统计。

## 按需回填

只有需要用通知类型查询旧记录的环境才执行。在部署环境的 `manage.py` 所在目录执行，将示例索引名替换为需要覆盖的物理索引；多个索引以逗号分隔。范围按索引选取，包含所选索引中的历史通知记录。

```sh
indices=bkfta_action_20260101_0
python manage.py init_action_notice_way_mapping --indices "$indices"
# 上一步若显示待补 mapping，先对同一范围补齐。
python manage.py init_action_notice_way_mapping --indices "$indices" --apply
python manage.py backfill_action_notice_way --indices "$indices"
# 确认待回填量后，按集群负载调整限速。
python manage.py backfill_action_notice_way --indices "$indices" --apply --wait --requests-per-second 100
python manage.py backfill_action_notice_way --indices "$indices"
```

不带 `--apply` 的回填命令刷新搜索视图并统计缺字段的非父通知记录，不改写文档。以同一范围内待回填数为零作为验收；可限速重跑，已补齐字段的文档不会再次更新。等待超时不会取消 ES 任务，请按命令输出的任务 ID 查看状态，待任务结束后再复验。
