# data_migrate

用于基于 Django ORM 做业务数据目录化导入导出。

当前公开入口：

- `apply_auto_increment_from_directory`
- `export_biz_data_to_directory`
- `import_biz_data_from_directory`
- `replace_tenant_id_in_directory`
- `sanitize_cluster_info_in_directory`

代码导出位置见 [__init__.py](/Users/unique0lai/Documents/Codes/bk-monitor/bk-monitor/worktrees/data-migrate/bkmonitor/bkmonitor/data_migrate/__init__.py)。

同时提供了 management command：

- `python manage.py data_migrate apply-sequences ...`
- `python manage.py data_migrate export ...`
- `python manage.py data_migrate import ...`
- `python manage.py data_migrate replace-tenant-id ...`
- `python manage.py data_migrate sanitize-cluster-info ...`

## 使用方式

### 导出

```bash
python manage.py data_migrate export \
  --directory /tmp \
  --bk-biz-ids 2 3 0
```

说明：

- `bk_biz_ids` 为要导出的业务 ID 列表
- `0` 代表全局数据
- command 会先在系统临时目录生成导出目录，再打成 zip 包
- 最终只把 zip 文件输出到 `--directory` 指定目录下
- 可选参数：
  - `--format`
  - `--indent`
- 不允许显式指定 `using`，统一走项目默认数据库路由

### 导入

```bash
python manage.py data_migrate import \
  --directory /tmp/bkmonitor-data-export
```

说明：

- `import` 读取的是已经解压好的导出目录，不直接读取 zip 文件

可选参数：

- `--disable-atomic`
  - 是否按单个文件事务导入

### 恢复自增游标

```bash
python manage.py data_migrate apply-sequences \
  --directory /tmp/bkmonitor-data-export
```

说明：

- 读取的是已经解压好的导出目录中的 `sequences.json`
- 不执行数据导入
- 适合在确认导入完成后单独恢复游标

### 执行 handler

```bash
python manage.py data_migrate replace-tenant-id \
  --directory /tmp/bkmonitor-data-export \
  --biz-tenant-id-map '{"*":"tenant-a","2":"tenant-b"}'
```

说明：

- handler 读取和修改的是已经解压好的导出目录中的 fixture 文件
- 当前已实现第一个 handler：按业务替换 `bk_tenant_id`
- 只有记录字段里真实存在 `bk_tenant_id` 时才会替换
- 全局目录视为 `bk_biz_id=0`
- 支持 `"*"` 语法批量匹配普通业务
- `"*"` 不会覆盖全局目录 `bk_biz_id=0`
- 如果同时配置具体业务和 `"*"`，具体业务优先
- 执行历史会追加记录到 `manifest.json` 的 `handlers` 字段中

### 脱敏 ClusterInfo 连接配置

```bash
python manage.py data_migrate sanitize-cluster-info \
  --directory /tmp/bkmonitor-data-export
```

说明：

- 只处理 `metadata.ClusterInfo` 的导出记录
- 会把 `domain_name`、`port`、`username`、`password` 以及 SSL/SASL 相关连接字段改成假数据
- 目的是避免迁移后继续连接旧环境的存储集群
- 这个 handler 也是目录级原地修改，可在 export 后、import 前单独执行
- 同样要求先解压 zip，再对目录执行

## 导出目录结构

`export` 命令最终输出的是一个 zip 包，zip 解压后的目录结构如下：

```text
export_root/
  manifest.json
  sequences.json
  global/
    *.json
  biz/
    2/
      *.json
    3/
      *.json
```

各文件含义：

- `manifest.json`
  - 导出清单
  - 记录导出格式、业务列表、全局文件列表、每个业务的模块文件列表
  - 如果执行过 handler，还会记录 `handlers` 历史
- `sequences.json`
  - 顶层自增游标信息
  - 记录涉及模型的当前游标、预留后游标、导出数据中的最大主键
- `global/*.json`
  - 全局数据模块
- `biz/<bk_biz_id>/*.json`
  - 单个业务下的模块化 fixture 文件

## `bk_biz_id=0` 的含义

`0` 不代表普通业务，而是“全局数据”。

当前导出时：

- 普通业务数据写入 `biz/<bk_biz_id>/`
- 全局数据写入 `global/`

是否属于全局数据，由各 fetcher 自己定义。不是所有带 `bk_biz_id` 的表都允许导出 `0`。

## 自增游标恢复逻辑

导出时会生成顶层 `sequences.json`，记录每个自增主键模型的：

- `current_start`
- `reserved_start`
- `exported_max_pk`

推荐流程：

1. 先执行 `import`
2. 再单独执行 `apply-sequences`
3. 由 `sequences.json` 将每个模型的自增游标推进到一个安全值

最终恢复值会至少不小于：

- 导出时记录的 `reserved_start`
- `exported_max_pk + 1`

这样可以降低导入后再次写入或二次导入时的主键冲突风险。

## 当前约束

- 目前处于开发阶段，接口以目录版为准
- 单文件导入导出接口已经移除
- 导出内容依赖 `fetcher/` 下各模块的 ORM 查询定义
- metadata 相关数据不是全量导出，而是先按业务收敛 `table_id / data_id / cluster_id` 再分层补齐
- handler 设计为目录级原地处理，适合在 export 后、import 前任意阶段执行
