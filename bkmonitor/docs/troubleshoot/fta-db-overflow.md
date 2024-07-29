# 告x警处理模型关联字段防止21亿溢出处理

## 1. 问题描述
action_instance表记录随着时间增长， 自增id会逐渐超过int上限。虽然主键id设置成了bigint，但关联此id的字段声明还是int
关联此id的表：
- converge_relation.related_id
- action_instance.parent_action_id

当关联id超过21亿时，会导致数据溢出。

## 解决方案
针对存量表，直接修改字段，会造成请求卡住，服务中断。因此当前方案选择: 
- 备份当前表
- 新建新表接收新数据写入
- 按需将旧数据导入新表

### converge_relation表

1. 重命名存量表
```sql
# 展示当前表结构
SHOW CREATE TABLE converge_relation;
# 重命名表
RENAME TABLE `converge_relation` to `converge_relation_backup`;
```

2. 新建表承接最新数据
```sql
# 下面示例： 不建议直接复制粘贴使用
# 注意，这里表结构可以参考上面的show  create table 命令的输出
# 创建新表改动的地方： AUTO_INCREMENT=2151576812 从21.5亿开始自增。避免和原表id重复

CREATE TABLE `converge_relation` (
  `id` bigint(20) NOT NULL AUTO_INCREMENT,
  `converge_id` bigint(20)  NOT NULL,
  `related_id` bigint(20)  NOT NULL,
  `related_type` varchar(64) NOT NULL,
  `is_primary` tinyint(1) NOT NULL,
  `alerts` longtext NOT NULL,
  `converge_status` varchar(32) NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `converge_relation_converge_id_related_id_r_6fcb6f9d_uniq` (`converge_id`,`related_id`,`related_type`),
  KEY `converge_relation_converge_id_2e295c9e` (`converge_id`),
  KEY `converge_relation_related_id_c6fc11de` (`related_id`),
  KEY `converge_relation_related_type_1957ed0b` (`related_type`)
) ENGINE=InnoDB AUTO_INCREMENT=2151576812 DEFAULT CHARSET=utf8mb4;
```

3. 按需导入部分最近数据, 这里id范围按需处理，建议根据converge_relation_backup的 最大id往前推10w条
```sql
INSERT INTO converge_relation 
SELECT * FROM converge_relation_backup 
WHERE related_id != 2147483647 AND id > xxxxxxxxxx;
```


### alarm_action表

```sql
# 参考converge_relation表的操作


RENAME TABLE `action_instance` TO `action_instance_backup`；

CREATE TABLE `action_instance` (
  `id` bigint(20) NOT NULL AUTO_INCREMENT,
  `is_enabled` tinyint(1) NOT NULL,
  `is_deleted` tinyint(1) NOT NULL,
  `create_user` varchar(32) NOT NULL,
  `create_time` datetime(6) NOT NULL,
  `update_user` varchar(32) NOT NULL,
  `update_time` datetime(6) NOT NULL,
  `signal` varchar(64) NOT NULL,
  `strategy_id` int(11) NOT NULL,
  `alerts` longtext NOT NULL,
  `alert_level` int(11) NOT NULL,
  `status` varchar(64) NOT NULL,
  `failure_type` varchar(64) DEFAULT NULL,
  `ex_data` longtext NOT NULL,
  `end_time` datetime(6) DEFAULT NULL,
  `action_plugin` longtext NOT NULL,
  `action_config` longtext NOT NULL,
  `bk_biz_id` varchar(64) NOT NULL,
  `is_parent_action` tinyint(1) NOT NULL,
  `parent_action_id` bigint(20) NOT NULL,
  `sub_actions` longtext NOT NULL,
  `assignee` longtext NOT NULL,
  `inputs` longtext NOT NULL,
  `outputs` longtext NOT NULL,
  `execute_times` int(11) NOT NULL,
  `generate_uuid` varchar(32) NOT NULL,
  `dimensions` longtext NOT NULL,
  `dimension_hash` varchar(64) NOT NULL,
  `action_config_id` int(11) NOT NULL,
  `is_polled` tinyint(1) NOT NULL,
  `need_poll` tinyint(1) NOT NULL,
  `strategy` longtext NOT NULL,
  `strategy_relation_id` int(11) NOT NULL,
  `real_status` varchar(64) NOT NULL,
  PRIMARY KEY (`id`),
  KEY `action_instance_is_parent_action_aa294f47` (`is_parent_action`),
  KEY `action_instance_generate_uuid_a272b9ad` (`generate_uuid`),
  KEY `action_instance_create_time_signal_160f6297_idx` (`create_time`,`signal`),
  KEY `action_instance_status_signal_update_time_86f01fbd_idx` (`status`,`signal`,`update_time`),
  KEY `action_instance_create_time_status_65063f7f_idx` (`create_time`,`status`),
  KEY `action_instance_need_poll_63db9df0` (`need_poll`),
  KEY `idx_update_time` (`update_time`),
  KEY `idx_need_poll_is_polled` (`need_poll`,`is_polled`),
  KEY `strategy_relation_id` (`strategy_relation_id`)
) ENGINE=InnoDB AUTO_INCREMENT=2151576812 DEFAULT CHARSET=utf8mb4；
```