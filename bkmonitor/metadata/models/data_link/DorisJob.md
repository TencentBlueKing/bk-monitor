# DataLink 中的 DorisJob 管理方案

**评审稿。** 一个 DataLink 可以挂载多个 Doris 周期 INSERT Job。metadata 保存任务定义和链路归属，Doris FE 负责调度、执行及保存执行记录。第一阶段评审配置模型和管理接口。APM 预计算用于检验设计能否表达实际需求，接入策略、业务 SQL、建表与上线另行交付。

## 组件放在哪里

现有 `DataLink.compose_configs()` 组装 BKBase 资源，`apply_data_link()` 负责下发和清理。现有组件基类的 `delete_config()` 面向 BKBase。建议在同一个 `metadata.models.data_link` 包增加独立 Django 模型 `DorisJobConfig`，通过外键直接关联 DataLink。在链路详情层把 Job 摘要与已有组件并列展示，返回类型标识 `DorisJob`。写操作从 Job 自身的管理入口进入。

| 入口或场景 | 对 DorisJob 的处理 |
| --- | --- |
| 查看链路配置 | 按链路取本地 Job 列表。无需连接 FE 即可展示名称、集群、数据库、周期和上下游组件 |
| 链路重新 apply、BKBase 资源同步、回收缺失组件 | 保持现有流程。Job 不注册到 BKBase kind 映射、策略组件清理列表或 DataBus sinks |
| 停用链路 | 现有 `delete_data_link()` 仅停止 DataBus 并保留关联。建议维持该语义，由管理员按业务窗口单独暂停 Job，允许处理已入库的数据 |
| 物理删除链路 | 有关联 Job 时由外键 PROTECT 阻止删除，先解除纳管或显式删除 Job |
| 一个 Job 汇总多个来源 | 选负责该任务生命周期的链路作为归属；上下游关系单独登记，允许引用同租户其他链路的表组件。启停权限仍由归属链路管理 |

## DorisJob 的周期调谐

DataLink 和 DorisJob 各自推进。现有 `apply_data_link()` 继续负责 BKBase 组件的组装、下发和清理；调用方按原流程回填元数据。DorisJob 管理接口只把本次变更意图写入 metadata。Celery Beat 周期触发独立的 DorisJob 任务，从数据库取待处理记录。链路 apply 成功、失败、重试和停用均无需调用或投递 Job 任务。二者通过 Job 声明的组件关系和依赖就绪条件协调。[链路主流程](./data_link.py) · [现有链路任务](../../task/datalink.py)

### 每一轮怎样执行

1. 周期任务只扫描 `reconcile_status=pending` 的配置。按 Job 串行处理，进入该 Job 的写操作区后重新读取当前状态和动作。重复投递的 worker 看到前一轮已完成即可退出。
2. 调用 `check_dependencies(job, action) -> (ready, reason)`。创建和恢复调度时，按当前 Job 声明的源、目标检查所需 ResultTable / DorisBinding 是否就绪，并检查已指定的物理表是否可用。只检查该输出使用的依赖；未声明的自由 SQL 依赖仍由 Doris 执行时处理。无需前置条件的动作直接返回 ready，例如暂停和删除应能在上游表离线时执行。
3. 依赖未就绪时保留 pending，展示具体原因，结束本轮。下一轮重新检查。例如目标 Binding 第一轮正在创建、第二轮已就绪，则在第二轮执行变更，无需重跑 DataLink。
4. 就绪后执行记录中的动作。在同一次本地状态更新中保存远端 Job ID 或清除绑定、清空动作和原因，并将状态置为 ready（删除远端后为 draft）。下一轮扫描跳过该记录。ready 表示本次管理动作完成；任务是否正在运行、最近一次 INSERT 是否成功，仍由 FE 状态及 Task 记录回答。

### 状态转换与恢复

| 事件 | 本地状态与后续行为 |
| --- | --- |
| 保存模板或自由配置草稿 | draft。发布请求在一次本地写入中设为 pending，动作置为 create |
| 对已绑定 Job 提交启停或删除请求 | pending，动作分别为 pause、resume 或 drop；返回已受理状态。再次提交同一待处理动作复用原请求 |
| 依赖在准备或 FE 暂时不可达 | 保留 pending 和原因，下轮继续。查询错误不能当作远端对象不存在 |
| 动作已经完成 | create / pause / resume 转 ready，drop 转 draft；显式接管成功直接转 ready。后续周期对这些记录均不执行 DDL |
| 同名冲突、SQL 错误或权限不足 | failed，保留动作和错误，周期扫描跳过。修正问题或显式接管后再推进；retry 将失败动作放回 pending |
| worker 中断或 FE 成功但本地写回失败 | 已提交的 pending 记录会被下轮发现。执行前观察目标：已绑定 Job 已处于请求的启停状态，或待删除的旧 Job 已确认不存在时，只补写本地结果。创建时发现未绑定的同名 Job 则进入 failed，供管理员接管 |
| 依赖组件删除、链路停用或重复 apply | 删除已声明的必要组件时，待创建或恢复的 Job 记录缺失依赖并转 failed，避免级联删除引用后意外放行。单纯停用 DataBus 或重复 apply 保留 Job 原有意图；需要停止调度时显式请求 pause |

管理接口和 worker 共用单 Job 写操作的串行边界，防止旧动作回写覆盖新请求。等待期间可撤销尚未执行的动作（有远端绑定回 ready，无绑定回 draft）；正在执行的动作先完成，再受理后续操作。每轮按当前持久化状态选择工作，不要求调用方收到 Celery 消息后再次触发。首期对 ready 记录按需查询 FE 运行详情，集群外手工改动可通过显式管理动作处理。

## 建议字段

| 字段 | Django 类型 / 初值 | 用途及变更语义 |
| --- | --- | --- |
| id | BigAutoField | metadata 的组件 ID，管理接口使用此 ID |
| data_link | ForeignKey(DataLink, PROTECT)，related_name=doris_jobs | 指向主键 data_link_name。租户、namespace、DataID 均从所属链路读取 |
| cluster_id | IntegerField，必填 | 使用现有 ClusterInfo.cluster_id，按链路租户及 TYPE_DORIS 解析连接。凭据由 ClusterInfo 提供 |
| database | CharField(255)，必填 | 创建 Job 时使用的 Doris 数据库上下文。任务 SQL 建议显式写出源表、目标表的库名 |
| name | CharField(255)，必填 | Doris Job 原名；按集群管理名称。集群、库、名称在绑定后固定，迁移或改名作为新 Job 处理 |
| interval_minutes | PositiveIntegerField，必填 | 首期只支持正整数分钟周期，映射为 EVERY n MINUTE |
| insert_sql | TextField，必填 | 保存单条 INSERT 任务体。服务负责组装 CREATE JOB，时间窗口、聚合及目标表由任务定义表达 |
| reconcile_status | CharField，默认 draft，索引 | draft / pending / ready / failed，Celery 仅扫描 pending |
| pending_action | CharField，可空 | create / pause / resume / drop；随请求写入，成功后清空 |
| status_reason | TextField，可空 | 等待的依赖或最近一次管理动作的错误 |
| doris_job_id | BigIntegerField，可空 | 创建成功或显式接管后保存 FE 返回的 Id；执行记录按此 ID 查询。空值表示尚未绑定远端对象 |
| create_time / last_modify_time | DateTimeField，自动维护 | 本地配置创建和修改时间 |

列表通过外键索引查询。建议同一个 ClusterInfo 的 `(cluster_id, name)` 只能由一条配置占用，与 Doris 的 Job 名称唯一语义对应。共用物理 FE 的多个集群登记仍可能遇到远端重名，按创建冲突处理。运行状态与最近失败原因在查看运行详情时读取；Task 历史沿用 Doris 的保留策略。字段里无需复制状态、连接参数或 DataLink 身份字段。[Doris 3.x Job 定义](https://doris.apache.org/docs/3.x/sql-manual/sql-statements/job/CREATE-JOB/)

## 上下游表关系

按 **源表组件 → DorisJob → 目标表组件** 记录直接依赖。一个 Job 可以有多个 source 和多个 target；同一张表也可以供多个 Job 读取，或由多个 Job 写入。链路归属回答“谁管理 Job”，表关系回答“它从哪里读、写到哪里”。上游数和下游数互相独立，查询经过 Job 节点，无须生成每一对源表和目标表的组合。

建议增加本地模型 `DorisJobTableRelation`，每行表示一个方向上的一个组件引用。

| 字段 | 类型 | 用途 |
| --- | --- | --- |
| job | ForeignKey(DorisJobConfig, CASCADE) | 配置移除时一并移除关系 |
| direction | CharField，source / target | 相对于 Job 的读写方向；同一表可以分别出现在两个方向 |
| result_table_config | ForeignKey(ResultTableConfig, CASCADE)，可空 | 引用逻辑结果表组件，例如需要从链路结果表详情反查生产者或消费者 |
| doris_binding | ForeignKey(DorisStorageBindingConfig, CASCADE)，可空 | 引用具体 DorisBinding，例如同一逻辑表在存储轮换前后有多个绑定，要区分任务实际使用哪一个 |

每条引用通过请求中的 `kind + id` 选择一个外键。声明逻辑依赖时选 ResultTable；依赖特定存储绑定时选 DorisBinding。一个方向可混用两类组件。服务从被引用对象读取名称、租户、namespace 等展示信息。Binding 的 `physical_tables` 可以包含多张物理表，因此 Binding 级引用只表示依赖该绑定；具体读写的物理表以任务 SQL 为准。尚未登记为这两类组件的物理表仍可出现在 SQL 中，组件拓扑只能展示已登记的关系。

例如，周期任务读取请求明细和服务维表，写入一张按天分区的汇总表。它可以声明两个 source（明细的 DorisBinding、维表的 ResultTable）和一个 target（汇总表的 DorisBinding）。如果目标表同时需要从逻辑结果表和实际绑定两个入口反查，可在 target 中显式登记这两个组件。这样有两条目标组件关系，实际写入仍是一张表。

**多个独立目标表。** 关系模型允许登记多个目标。执行层沿用一个配置对应一个 FE Job、一条 INSERT 的约定。若业务分别向服务汇总表、接口汇总表执行两条 INSERT，在同一 DataLink 下声明两个 DorisJob，各自挂真实的源表和目标表。这样既能从链路看到全部输出，又能按目标定位执行失败的 Job。若将来需要把多条 INSERT 当作一个可统一启停的任务，需另行设计对多个远端 Job 的编排和部分成功语义。

## 两种配置入口

两种入口都生成前述 `DorisJobConfig` 草稿及其表关系，沿用相同的发布、启停和查询方法。

| 入口 | 调用方提供 | 保存结果 |
| --- | --- | --- |
| 模板配置 | 模板 key、按槽位命名的 `sources` 和 `targets`、本次参数，以及归属链路和执行集群等公共配置 | 按模板生成具体 INSERT、周期和直接表关系；每个输出返回独立草稿 ID |
| 自由配置 | Job 名称、数据库、周期、完整 `insert_sql`，以及显式声明的 `sources` 和 `targets` | 原样保存任务体，按声明记录表关系；适用于临时任务、已有任务接管和模板未覆盖的 SQL |

**模板定义。** 建议首期把模板随 metadata 代码维护，用稳定的 key 查找。每份模板声明源槽位、目标槽位、业务参数及默认值，以及每个输出对应的 INSERT 模板。一个输出声明任务名称后缀、使用哪些源槽位、写入哪个目标槽位。周期可以由模板给默认值，也可以在本次配置中指定。模板的管理与 Job 发布是两个独立动作。

**组件与物理表。** 槽位名如 `events` 或 `daily`，用于在 SQL 中引用输入。每个槽位可以同时携带组件引用和本次使用的物理库表。当已有 DorisBinding 提供唯一可用的物理表时可直接取用；有多个用途时由调用方选择对应物理表。只提供逻辑 ResultTable 且无法确定实际库表时，预览返回待补充的槽位。未登记为组件的库表也可以作为模板输入，此时预览显示物理表，拓扑只记录能够关联到组件的槽位。渲染由服务按库名、表名分别引用标识符，业务参数按模板声明的类型生成 SQL 字面值。

以下为配置请求示例，组件 ID、物理表和模板名称仅用于说明。

```json
{
  "template_key": "daily_rollup",
  "name": "request_rollup",
  "sources": {
    "events": {"kind": "DorisBinding", "id": 11, "database": "raw", "table": "requests"},
    "services": {"kind": "ResultTable", "id": 12, "database": "dim", "table": "services"}
  },
  "targets": {
    "by_service": {"kind": "DorisBinding", "id": 21, "database": "agg", "table": "requests_by_service"},
    "by_app": {"kind": "DorisBinding", "id": 22, "database": "agg", "table": "requests_by_app"}
  },
  "params": {"lookback_days": 1},
  "interval_minutes": 60
}
```

在该示例模板中，`by_service` 输出只读取 `events`，`by_app` 输出读取 `events` 和 `services`。一次保存生成 `request_rollup_by_service` 和 `request_rollup_by_app` 两份草稿，各有自己的 INSERT 和表关系。反查 `services` 只会找到后一个 Job。两份草稿在同一个本地事务中创建，随后可分别发布；查看运行状态或修复一次发布失败时，使用对应的 Job ID。

**模板实例的保存与编辑。** 建议在 Job 配置上增加两个可空字段：`template_key`（CharField）记录来源，`template_inputs`（JSONField）保留本次输出标识、槽位实参和业务参数，供回显和重新预览。自由配置时两个字段为空。已保存的 `insert_sql` 和周期是发布依据；更新模板只影响下一次渲染。修改已有实例时按组件 ID 选择草稿、重新预览并保存；对已发布的 Job 沿用显式替换流程。也可以将草稿切换为自由配置：保留渲染后的 SQL、周期和已有表关系，清除模板来源后直接编辑。单独修订拓扑只更新关系，模板回显的输入仍代表上次渲染；下次显式套用模板时应展示将被替换的 SQL 和表关系。

## 管理方法

以下是 metadata 服务方法的建议契约。调用方传入当前租户，服务按租户定位链路和 Job。配置或执行 SQL 仅面向具有相应集群管理权限的操作人，沿用已有 FE 连接配置。写接口提供具名动作，参数只接受该动作所需的字段。FE 账号须具备目标版本执行 Job DDL 的权限。

| 方法 | 输入与结果 | 对 Doris 的影响 |
| --- | --- | --- |
| list_templates() | 返回可用模板的 key、源和目标槽位、参数及周期默认值 | 无 |
| preview_template(link, template_key, sources, targets, params, options) | 返回各输出的名称、物理库表、渲染 SQL、周期和直接组件关系，供检查 | 无，不落库 |
| save_from_template(link, template_key, sources, targets, params, options) | 按预览相同的规则生成并一次保存各输出草稿，返回输出名到组件 ID 的映射；编辑时显式指定对应草稿 ID | 无 |
| save_config(link, fields, sources, targets, id=None) | 在同一 metadata 事务中保存草稿及两组组件引用，返回组件 ID | 无 |
| list_configs(link) | 返回配置摘要及按方向分组的组件引用 | 无 |
| set_table_relations(id, sources, targets) | 整体替换两组关系，空数组清空该方向。草稿和已接管 Job 均可单独修订拓扑 | 无 |
| list_jobs_by_table(kind, component_id, direction=None) | 反查直接引用该组件的 Job 及归属链路；source 查消费者，target 查生产者，省略方向则返回双方及各自方向 | 无 |
| publish_jobs(link, job_ids) | 将选中的草稿记录为 pending/create；已绑定且完成的配置返回已有结果 | 无，等待周期调谐 |
| reconcile_pending_jobs() | Celery 周期入口，按配置 ID 分别处理 pending 动作，一项失败不影响其他 Job | 依赖就绪后执行对应 DDL |
| check_dependencies(job, action) | 返回是否就绪和等待原因 | 按动作读取所需组件或库表 |
| retry_job(id) / cancel_pending(id) | 重新排入失败动作，或撤销待执行动作 | 无 |
| adopt_job(link, cluster_id, database, remote_id, fields, sources, targets) | 将现有周期 INSERT Job 绑定到链路；先展示远端实际 SQL 和周期，仅支持能完整表达为本模型的任务 | 仅读取。由管理员指定已存在的 Job，核对名称、ID、库上下文、任务体和周期后记录实际定义，关联调用方提供的上下游组件。无法确定上下文时由管理员显式提供并核实 |
| get_status(id) | 返回当前远端状态、名称及可见的最近错误；区分草稿、远端缺失及查询错误 | 查 jobs("type"="insert")，精确定位 Job |
| list_tasks(id, page, page_size) | 返回开始/结束时间、执行结果及错误 | 复用现有 insert 类型任务查询，按当前远端 Job ID 分页 |
| pause_job(id) / resume_job(id) | 记录 pending/pause 或 pending/resume，返回受理状态 | 周期任务调用 Doris PAUSE / RESUME。暂停可能影响正在执行的 Task |
| drop_job(id) | 记录 pending/drop；远端删除成功后回到草稿 | 周期任务执行 DROP JOB。业务表和已写入的数据保留 |
| detach_config(id) | 删除本地配置和链路关联；可用于废弃草稿或移交已有任务 | 无。已发布 Job 继续按原计划运行 |

**关系维护。** 保存时按当前租户和调用人可见范围解析组件 ID。接管存量任务时允许两组关系为空，后续可补录。单独编辑关系只修改 metadata，SQL 和调度保持原样；修改 SQL 涉及读写表变化时，在保存新草稿时一并更新关系。删除远端 Job 并保留草稿时也保留上下游配置；解除纳管时随本地 Job 删除关系。组件本身被删除时只清理指向它的引用，远端 Job 继续运行；以新组件替换旧组件后通过关系编辑入口重新关联。

**修改 SQL 或周期。** 首期采用显式操作序列。请求暂停并等待调谐完成，查看在途 Task 和最后成功窗口，保留旧配置以备恢复。请求删除，待状态回到 draft 后编辑并重新发布。重新创建会获得新的 Job ID，切换前可用旧 ID 查看仍保留的历史。新定义发布失败时草稿可继续修正，旧调度已经停止。恢复旧调度需用保留的旧定义重新发布。该流程不会自行补算切换期间的窗口，业务负责人应根据目标表写入语义决定是否补算。

**存量与重试。** 本地草稿遇到远端同名 Job 时返回冲突，展示远端 ID，由管理员选择接管；不覆盖同名对象。FE 创建成功而本地写入失败也走相同入口。接管属于已有草稿时绑定原记录。对已绑定记录的远端写操作先按名称定位实际 ID，遇到同名新对象则停止，避免误操作。删除返回超时后重新查询，只有能确认旧 Job 已不存在才清空绑定；连接或权限异常保留原配置。建议同一配置的管理写操作在服务层按记录串行执行，跨库失败按上述流程恢复。

## 链路详情示例

同一条 APM 入库链路可挂载按服务汇总和按接口汇总两个 Job，各自保存周期和 INSERT 定义。管理员从链路详情进入指定 Job，可以单独暂停接口汇总，查看上一次执行失败的原因；服务汇总与 DataBus 消费继续运行。链路重新下发时两个 Job 仍保留原 ID。这个例子只要求建立配置关联，组件本身无须理解 APM 指标名、分位数算法或维度。

## 实现时的验收点

1. 链路详情能列出多个 Job；跨租户查询和写操作遵循原有资源权限。普通链路列表和 BKBase apply 无需连接 FE。
2. 验证创建、启停、删除、解除纳管；重复提交、同名冲突、FE 请求超时分别返回可操作的结果。接管一条既有 Job 后远端 ID 和执行记录保持连续。
3. 验证停用链路、重建 BKBase 关系及清理缺失组件均不会意外删除 Job；显式删除一条 Job 后，其他 Job 和物理表仍可访问。
4. 用目标 Doris 版本实测 `jobs`、`tasks` 返回字段、名称大小写、调度周期展示、执行中的暂停行为和账号权限，再确定接管入口可直接回填的字段。
5. 一个 Job 声明两条 source 和两条 target，验证两个方向均能独立增删、按组件 ID 反查。覆盖同表既读又写、不同 Job 共享一张表、历史与当前 DorisBinding 同时存在、跨链路同租户引用。验证单独修改关系不会触发 FE DDL。
6. 用两源两目标模板预览并保存，核对各输出实际使用的源、目标与 SQL。更新模板后已存草稿及运行中 Job 保持原定义；已有草稿能重新渲染，也能切换为自由配置。验证自由配置可在没有模板的情况下独立保存和发布。
7. 用连续三轮检验调谐：首轮依赖未就绪，DDL 次数为零；次轮依赖就绪，成功执行一次并转 ready；第三轮跳过该 Job。覆盖重复投递、FE 成功后本地写回失败、failed 修正后重试，以及上游表离线时仍可暂停和删除。
8. 单独运行或重试 DataLink apply，确认不会创建 Job 或改变既有 Job 状态；反向验证 Celery 延迟或 Job 失败不会阻塞链路下发。

对应代码入口：[DataLink 编排](./data_link.py)、[BKBase 组件基类](./data_link_configs.py)、[已有集群 Job 与 Task 查询](../../../kernel_api/rpc/functions/admin/doris_jobs.py)。现有集群查询面向列表；运行详情需要增加按指定 ID 或名称精确过滤的查询，避免拉全量再筛选。
