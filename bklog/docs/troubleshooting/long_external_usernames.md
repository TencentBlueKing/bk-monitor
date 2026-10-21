# 长外部用户名被截断的影响与修复

本文基于仓库代码与迁移静态评估，未连接生产数据库，也未验证生产部署版本、表大小、字符集、行格式和迁移耗时。下文的表数量是代码模型的完整范围；TGPA、版本日志等可选应用是否安装、对应表是否存在，需按目标部署核对。

## 根因与修复边界

原公共基类 `OperateRecordModel.created_by / updated_by` 和 `SoftDeleteModel.deleted_by` 的长度均为 32。用户名超过字段长度时，MySQL 非严格模式可能截断后返回成功及 warning。后续使用完整用户名精确查询，便不能命中已经截断的记录。

`FavoriteGroup.get_or_create_private_group` 正是这条链路：用完整用户名查询个人组，未找到便插入；插入时再次截断，撞上旧记录的联合唯一键；Django 使用原始查询条件重查仍然找不到，最终抛出异常。该问题不需要以唯一键缺少 `source_type` 为前提。

修复将上述字段与独立声明的短用户名字段统一扩为 64，保留精确身份匹配。长度选择与外部授权模型 `ExternalPermission.authorized_user` 及认证依赖 `blueapps.account.User.username` 的现有 64 字符容量一致；场景检索相关用户字段也已经是 64。已有 255、256 字符用户名字段保持原容量。该修复不保证支持超过 64 字符的用户标识。

字段容量不等同于入库前校验：Django `save()` 不自动调用 `full_clean()`。本次没有统一调整数据库 `sql_mode`；开启严格模式应另行评估已有写入兼容性。参见 [Django 模型校验](https://docs.djangoproject.com/en/4.2/ref/models/instances/#validating-objects) 与 [MySQL 5.7 字符串类型](https://docs.oracle.com/cd/E17952_01/mysql-5.7-en/char.html)。

## 影响范围

公共基类覆盖 **54 张表、8 个 app、143 列**，即 54 个 `created_by`、54 个 `updated_by`、35 个 `deleted_by`。加上 5 个独立字段，共为 **59 张表、11 个 app、148 列**。

| app | 具体模型数 | 继承公共基类的具体模型 |
| --- | ---: | --- |
| feature_toggle | 1 | FeatureToggle |
| log_clustering | 9 | SampleSet、AiopsModel、AiopsModelExperiment、AiopsSignatureAndPattern、ClusteringRemark、ClusteringConfig、SignatureStrategySettings、NoticeGroup、ClusteringSubscription |
| log_commons | 4 | ApiAuthToken、ExternalPermission、ExternalPermissionApplyRecord、TokenAccessRecord |
| log_databus | 16 | CollectorConfig、ContainerCollectorConfig、BcsRule、BcsStorageClusterConfig、ItsmEtlConfig、DataLinkConfig、StorageCapacity、StorageUsed、BKDataClean、CleanTemplate、CleanStash、ArchiveConfig、RestoreConfig、CollectorPlugin、FieldDateFormat、GrokInfo |
| log_desensitize | 3 | DesensitizeRule、DesensitizeConfig、DesensitizeFieldConfig |
| log_extract | 3 | Strategies、Tasks、ExtractLink |
| log_measure | 1 | AccessIndexSet |
| log_search | 17 | ProjectInfo、AccessSourceConfig、LogIndexSet、LogIndexSetData、UserIndexSetConfig、UserIndexSetSearchHistory、ResourceChange、FavoriteSearch、Favorite、FavoriteGroup、FavoriteUnionSearch、AsyncTask、EmailTemplate、SpaceType、Space、StorageClusterRecord、UserCustomConfig |

默认表名为 `<app>_<小写模型名>`；例外为 `ExternalPermission → external_permission`、`ExternalPermissionApplyRecord → external_permission_apply_record`、`TokenAccessRecord → token_access_record`、`AsyncTask → export_task`。`CollectorBase` 是抽象类，不单独计表。

以下独立字段不会随公共基类扩容自动变更，需要各自迁移：

| 表 | 字段 | 原长度 | 主要影响 |
| --- | --- | ---: | --- |
| log_search_usermetaconf | username | 32 | 用户功能指引；`(username, type)` 唯一键及 `get_or_create` |
| log_search_userindexsetfieldsconfig | username | 32 | 用户展示字段配置；精确查询、`update_or_create` 及联合唯一键 |
| tgpa_tgpareportsyncrecord | created_by | 32 | TGPA 上报同步记录创建人 |
| log_audit_useroperationrecord | created_by | 32 | 操作审计中的操作者 |
| version_log_versionlogvisited | username | 50 | 用户名主键；版本访问记录的精确查询及 `update_or_create` |

## 高风险调用链

| 功能 | 代码入口 | 截断的影响 |
| --- | --- | --- |
| 个人收藏组与收藏 | `apps/log_search/models.py` 的 `FavoriteGroup.get_or_create_private_group`、`Favorite.get_user_favorite`；`handlers/search/favorite_handlers.py` 的创建及归属检查 | 个人组查询后新建撞唯一键；收藏不可见、创建冲突或修改归属校验失败 |
| 日志提取 | `apps/log_extract/handlers/tasks.py` 的 `list`、创建任务、`get_polling_result` | 写入完整外部用户名后被截断；列表、轮询用完整用户名查询不到 |
| 异步导出 | `AsyncTask.check_running_count_by_user`；`apps/log_search/handlers/search/async_export_handlers.py` 及 `apps/log_unifyquery/handler/scene_async_export.py` 的历史查询；下载接口 | 历史和下载归属查询失败；按用户统计运行任务漏计，影响并发限制 |
| 检索历史 | `apps/log_search/decorators.py` 的 `search_history_record`；`search_handlers_esquery.py` 的历史查询及删除 | 外部用户历史保存后无法用完整用户名读取或删除 |
| 用户字段配置与指引 | `UserIndexSetFieldsConfig.get_config`、`IndexSetHandler.config`、`MetaHandler.get_user_guide` | 个人设置无法命中；查不到再创建时可能冲突 |
| Token 复用与访问记录 | `apps/log_commons/token.py` 的 `get_or_create_token`、`record_access` | Token 按创建人查不到后反复创建；访问记录可能重复。`TokenAccessRecord` 的 `(token, created_by)` 是普通索引，不保证报唯一键冲突 |
| 索引集访问统计 | `AccessIndexSet` 的联合唯一键 | 用户身份维度被截断，可能混淆统计或触发冲突 |
| IAM 资源归属 | `apps/iam/views/resources.py` 的采集项及索引集资源提供逻辑 | `CollectorConfig / LogIndexSet.created_by` 用作 owner、approver，不只是展示信息 |
| 下游账号及通知 | `apps/log_databus/tasks/bkdata.py`、`handlers/collector/base.py`；`apps/log_clustering/utils/monitor.py` | 创建人、修改人被用作 BKBase 维护人及平台账号，聚类创建人被用作通知接收人 |

其余审计字段的直接影响是操作者信息不完整；不能因此认定所有创建人、修改人字段都仅用于审计。未发现 `deleted_by` 用于身份查询、唯一键或授权条件。

## MySQL 5.7 迁移限制

扩容后，涉及用户名字段的主要联合索引最大长度估算如下。字符部分按该列使用相同字符集估算，整数按 4 字节计算；目标库仍需检查实际列定义及索引前缀。

| 索引 | utf8 最大字节数 | utf8mb4 最大字节数 |
| --- | ---: | ---: |
| Favorite：name、space_uid、group_id、source_app_code、created_by | 1825 | 2432 |
| FavoriteGroup：name、space_uid、created_by、source_app_code、source_type | 1296 | 1728 |
| export_task_user_run_idx：created_by、export_type、export_status | 768 | 1024 |
| UserIndexSetFieldsConfig 的五列唯一键 | 436 | 580 |
| UserMetaConf：username、type | 384 | 512 |
| TokenAccessRecord：token、created_by | 288 | 384 |

MySQL 5.7 在 16KB 页、启用 `innodb_large_prefix` 且使用 `DYNAMIC / COMPRESSED` 行格式时，索引键长度上限是 3072 字节。`COMPACT / REDUNDANT` 或关闭 `innodb_large_prefix` 时，上限可能只有 767；8KB、4KB 页还会降低大索引上限。特别是 `export_task_user_run_idx` 在 utf8 下由 672 扩至 768 字节，会跨过旧 767 字节边界。不能只根据 MySQL 版本号认定索引可扩容。参见 [MySQL 5.7 InnoDB 限制](https://docs.oracle.com/cd/E17952_01/mysql-5.7-en/innodb-limits.html)。

`VARCHAR` 的长度头也影响 DDL：utf8mb4 的 32→64 字符等于 128→256 最大字节数，长度头从 1 字节变成 2 字节。MySQL 5.7 此时不能使用 `ALGORITHM=INPLACE`，需要 `COPY`；50→64 也会从 200 跨至 256 字节。因此扩容可能重建表并阻塞写入，大表尤其需要评估窗口和临时空间，不能承诺仅改元数据或无锁执行。utf8 的 32→64 为 96→192 字节，没有该长度头边界，但实际执行方式仍以目标库 DDL 为准。参见 [MySQL 5.7 Online DDL 列操作](https://docs.oracle.com/cd/E17952_01/mysql-5.7-en/innodb-online-ddl-operations.html)。

本次是标准 Django `AlterField` 迁移，同一张表的多个字段可能生成多条 `ALTER TABLE`。应检查 `sqlmigrate` 的实际输出并据此评估 DDL 次数、表复制及锁定耗时，不能按每表只重建一次估算。

## 只读上线前检查

### 本地执行验证记录（2026-10-21）

已在本地 MySQL 8.0.40 开发库实际应用本次全部 11 个迁移。执行前核对待执行计划仅包含这 11 个迁移；执行后核对 `django_migrations` 为 11/11 已应用，并通过 `information_schema.COLUMNS` 确认 59 张表的 148 个目标列全部为 64 字符。

在开发库事务中验证了 33、64 字符用户名完整保存、重复读取个人收藏组复用同一条记录，以及前 32 字符相同的用户仍有独立分组。验证事务已回滚，没有保留测试分组。此前 39 项目标测试也已通过。

上述验证库启用了 `STRICT_TRANS_TABLES`；本记录不代表已经验证 MySQL 5.7 的 DDL 行为、生产环境非严格模式或生产数据恢复。

### 目标环境检查

在应用实际写入的数据库上执行；若存在路由或多个数据库，应分别检查相应库。以下 SQL 均为只读，不包含业务用户名、任务 ID 或补数操作。

```sql
SELECT VERSION() AS mysql_version,
       DATABASE() AS current_database,
       @@SESSION.sql_mode AS session_sql_mode,
       @@GLOBAL.sql_mode AS global_sql_mode;

SHOW VARIABLES WHERE Variable_name IN (
    'innodb_page_size', 'innodb_large_prefix',
    'innodb_default_row_format', 'innodb_file_format'
);
```

检查本次目标列的实际容量、字符集、表行格式及估算大小。`TABLE_ROWS`、数据和索引大小属于估算值；不存在的可选应用表不会返回行。完整安装且表结构与代码一致时，本查询对应 148 列。

```sql
SELECT c.TABLE_NAME, c.COLUMN_NAME, c.COLUMN_TYPE,
       c.CHARACTER_MAXIMUM_LENGTH, c.CHARACTER_SET_NAME, c.COLLATION_NAME,
       CASE WHEN c.CHARACTER_MAXIMUM_LENGTH >= 64 THEN 'ready' ELSE 'expand' END AS capacity,
       t.ENGINE, t.ROW_FORMAT, t.TABLE_ROWS,
       ROUND(t.DATA_LENGTH / 1024 / 1024, 2) AS data_mb,
       ROUND(t.INDEX_LENGTH / 1024 / 1024, 2) AS index_mb
FROM information_schema.COLUMNS AS c
JOIN information_schema.TABLES AS t
  ON t.TABLE_SCHEMA = c.TABLE_SCHEMA AND t.TABLE_NAME = c.TABLE_NAME
WHERE c.TABLE_SCHEMA = DATABASE()
  AND (
    (c.COLUMN_NAME IN ('created_by', 'updated_by', 'deleted_by') AND c.TABLE_NAME IN (
      'feature_toggle_featuretoggle',
      'log_clustering_sampleset', 'log_clustering_aiopsmodel',
      'log_clustering_aiopsmodelexperiment', 'log_clustering_aiopssignatureandpattern',
      'log_clustering_clusteringremark', 'log_clustering_clusteringconfig',
      'log_clustering_signaturestrategysettings', 'log_clustering_noticegroup',
      'log_clustering_clusteringsubscription',
      'log_commons_apiauthtoken', 'external_permission',
      'external_permission_apply_record', 'token_access_record',
      'log_databus_collectorconfig', 'log_databus_containercollectorconfig',
      'log_databus_bcsrule', 'log_databus_bcsstorageclusterconfig',
      'log_databus_itsmetlconfig', 'log_databus_datalinkconfig',
      'log_databus_storagecapacity', 'log_databus_storageused',
      'log_databus_bkdataclean', 'log_databus_cleantemplate', 'log_databus_cleanstash',
      'log_databus_archiveconfig', 'log_databus_restoreconfig',
      'log_databus_collectorplugin', 'log_databus_fielddateformat', 'log_databus_grokinfo',
      'log_desensitize_desensitizerule', 'log_desensitize_desensitizeconfig',
      'log_desensitize_desensitizefieldconfig',
      'log_extract_strategies', 'log_extract_tasks', 'log_extract_extractlink',
      'log_measure_accessindexset',
      'log_search_projectinfo', 'log_search_accesssourceconfig', 'log_search_logindexset',
      'log_search_logindexsetdata', 'log_search_userindexsetconfig',
      'log_search_userindexsetsearchhistory', 'log_search_resourcechange',
      'log_search_favoritesearch', 'log_search_favorite', 'log_search_favoritegroup',
      'log_search_favoriteunionsearch', 'export_task', 'log_search_emailtemplate',
      'log_search_spacetype', 'log_search_space', 'log_search_storageclusterrecord',
      'log_search_usercustomconfig',
      'tgpa_tgpareportsyncrecord', 'log_audit_useroperationrecord'
    ))
    OR (c.COLUMN_NAME = 'username' AND c.TABLE_NAME IN (
      'log_search_usermetaconf', 'log_search_userindexsetfieldsconfig',
      'version_log_versionlogvisited'
    ))
  )
ORDER BY c.TABLE_NAME, c.ORDINAL_POSITION;
```

核对主要联合索引是否与部署版本一致，并查看是否存在前缀索引：

```sql
SELECT TABLE_NAME, INDEX_NAME, NON_UNIQUE,
       GROUP_CONCAT(
         CONCAT(COLUMN_NAME, IF(SUB_PART IS NULL, '', CONCAT('(', SUB_PART, ')')))
         ORDER BY SEQ_IN_INDEX SEPARATOR ', '
       ) AS index_columns
FROM information_schema.STATISTICS
WHERE TABLE_SCHEMA = DATABASE()
  AND TABLE_NAME IN (
    'log_search_favorite', 'log_search_favoritegroup', 'export_task',
    'log_search_usermetaconf', 'log_search_userindexsetfieldsconfig',
    'log_measure_accessindexset', 'token_access_record',
    'version_log_versionlogvisited'
  )
GROUP BY TABLE_NAME, INDEX_NAME, NON_UNIQUE
ORDER BY TABLE_NAME, INDEX_NAME;
```

## 上线顺序与历史数据恢复

1. 核对目标部署版本、应用安装范围、实际写库和迁移状态，执行上述只读结构检查；结合表大小、字符集、索引限制及复制配置评估 DDL 窗口。不要用本地库状态代替生产检查。
2. 按项目约定加载目标环境配置，在包含本次迁移的发布版本中先查看 `manage.py migrate --plan`。迁移覆盖全部 11 个 app；可选应用应在对应安装它们的部署中确认迁移执行。安排扩列先于恢复相关写入，并按既有发布流程执行迁移、发布应用和 worker。
3. 复查实际列长度已至少 64，迁移状态完整，再用获授权的测试账号验证新建、重复读取个人组、收藏创建及回显、提取与导出历史。本文不代表这些生产步骤已经执行。
4. 单独审核历史数据修复清单。必须由完整用户名、已确认的记录、业务或空间、来源应用等证据建立归属，检查目标记录和唯一键冲突后再制定补数；不能用相同的前 32 个字符自动猜测用户身份。
5. 收藏必须同时核对个人组与收藏条目：`FavoriteGroup.created_by`、`Favorite.created_by` 以及条目的 `group_id`。只扩字段会允许创建一个完整用户名的新个人组，旧组中的收藏仍可能不可见。如果完整用户名的新组已经存在，直接回填旧组的 `created_by` 可能撞上现有唯一键；应先核对新旧组、关联条目及各自唯一键，再制定人工可审核的合并方案。不要自动合并、删除，也不要直接批量改名可能由多个同前缀账号共用的旧记录。
6. 提取、导出、历史、个人配置和审计等记录分别按业务证据恢复。扩列本身无法推导被截掉的字符，不能在结构迁移中自动补全。恢复后再验证列表、归属和配额行为。

扩列后若已有超过旧长度的数据，回滚应用时应保留扩容后的列；直接缩列可能造成再次截断或迁移失败。
