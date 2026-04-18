# Design: DataLink 组件名称复用与稳定映射

## 现状

`DataLink.apply_data_link` 当前流程：

1. 创建/获取 `BkBaseResultTable`；
2. 调 `compose_configs` 派发到对应 strategy 的 `compose_*_configs`；
3. compose 内部按固定 name 直接执行 `update_or_create` 写本地表，并渲染下发 payload；
4. 调 `apply_data_link_with_retry` 下发 BKBase。

核心问题不在 BKBase API，而在 compose 阶段已经把"固定 name"固化进了本地 ORM 与下发配置。

如果只在 compose 完成后再重写 payload 里的 `metadata.name`，会留下两个问题：

- 本地组件表中已经提前创建了"新 name"记录；
- 本地记录与 BKBase 实际配置 name 不一致，后续状态刷新、删除、排障都会偏移。

因此，复用决策必须在 `update_or_create` 之前生效，而不是在最终 payload 上做补丁。

## 总体思路

只在 `apply_data_link` 入口与收尾两端做最小框架性改动，所有匹配规则下沉到 compose：

```
apply_data_link
├── ExistingComponentContext.from_datalink(self)        # 一次性加载现有组件
├── compose_configs(..., existing_context=ctx)          # compose 内通过 ctx.claim 复用
├── leftover 检查 (compose 之后, BKBase 下发之前)        # 按 REUSE_LEFTOVER_POLICY 决定
└── apply_data_link_with_retry(configs)
```

这样做的好处：

- 外层不需要预先知道每个 strategy 会生成几个 slot、按什么键匹配；
- compose 在生成 slot 的循环里就能用最自然的语义键写 predicate；
- "整个 datalink 是否健康"在 compose 之后用 leftover 一次性判定，不需要 cardinality 多态枚举；
- 每个 strategy 接入是独立的，可按 strategy 灰度上线/回滚。

## 核心抽象

### 1. 全局组件 kind 列表

新增一份"DataLink 组件模型全集"的常量：

```python
ALL_DATA_LINK_COMPONENT_KINDS: list[type[DataLinkResourceConfigBase]] = [
    ResultTableConfig,
    VMStorageBindingConfig,
    ESStorageBindingConfig,
    DorisStorageBindingConfig,
    ConditionalSinkConfig,
    DataBusConfig,
]
```

`ExistingComponentContext.from_datalink` 只依赖这个全局列表，不再使用 `STRATEGY_RELATED_COMPONENTS[strategy]` 划分加载范围。

`STRATEGY_RELATED_COMPONENTS` 仍可保留供 `delete_data_link` 等其他逻辑使用；但本次复用机制不引用它。

### 2. ExistingComponentContext

```python
class ExistingComponentContext:
    @classmethod
    def from_datalink(cls, datalink: "DataLink") -> "ExistingComponentContext":
        """
        遍历 ALL_DATA_LINK_COMPONENT_KINDS，按
        bk_tenant_id + namespace + data_link_name 加载该 datalink 下所有现有组件。
        """

    def claim(
        self,
        kind: type[DataLinkResourceConfigBase],
        predicate: Callable[[DataLinkResourceConfigBase], bool],
    ) -> DataLinkResourceConfigBase | None:
        """
        在 kind 对应的 pool 中执行 predicate：
        - 恰好 1 条匹配 → 从 pool 中移除并返回；
        - 0 条 → 返回 None；
        - ≥2 条 → 返回 None，且不修改 pool（歧义放弃复用）。
        kind 必须属于 ALL_DATA_LINK_COMPONENT_KINDS，否则直接 raise。
        """

    def leftover(self) -> dict[type, list[DataLinkResourceConfigBase]]:
        """
        返回所有未被 claim 的 existing；只包含非空 kind。
        """
```

约束：

- `claim` 的 kind 参数必填，避免 predicate 跨 kind 误匹配；
- `from_datalink` 是构造 ctx 的唯一入口，外层不需要也不允许手动 `load(kind, ...)`；
- `leftover()` 只返回非空 kind，外层判空即可，不需要再 filter。

### 3. REUSE_LEFTOVER_POLICY

挂在 `DataLink` 类上的集中表：

```python
class DataLink:
    REUSE_LEFTOVER_POLICY: dict[tuple[str, type], Literal["strict", "keep"]] = {
        (BK_LOG, ESStorageBindingConfig):   "keep",
        (BK_LOG, DorisStorageBindingConfig): "keep",
    }

    def _leftover_policy(self, kind) -> Literal["strict", "keep"]:
        return self.REUSE_LEFTOVER_POLICY.get(
            (self.data_link_strategy, kind), "strict"
        )
```

语义：

- `strict`（默认）：该 kind 的 leftover 必须为空，否则 apply 直接报错；
- `keep`：允许 leftover 存在，既不报错也不删除，也不参与本次下发，本地 ORM 记录保持不变。

无论 policy 取值如何，leftover 都不会被本次 apply 改名/改字段/删除。

本次唯一需要声明 `keep` 的就是 `BK_LOG` 的 ES/Doris binding：当对应开关被关闭时本次 compose 不会生成它们，旧 binding 允许留在原地。

### 4. 灰度开关

```python
# settings
DATA_LINK_COMPONENT_REUSE_STRATEGIES: set[str] = set()
```

`apply_data_link` 入口：

```python
if self.data_link_strategy in settings.DATA_LINK_COMPONENT_REUSE_STRATEGIES:
    # 新路径：from_datalink → compose(ctx=…) → leftover 检查 → BKBase 下发
else:
    # 老路径：原 compose → BKBase 下发
```

每个 strategy 独立加入开关，独立灰度、独立回滚。

## 执行流程

```python
def apply_data_link(self, *args, **kwargs):
    self._ensure_bkbase_result_table(...)

    if self.data_link_strategy in settings.DATA_LINK_COMPONENT_REUSE_STRATEGIES:
        ctx = ExistingComponentContext.from_datalink(self)
        configs = self.compose_configs(*args, existing_context=ctx, **kwargs)
        self._check_leftover_or_raise(ctx)
    else:
        configs = self.compose_configs(*args, **kwargs)

    return self.apply_data_link_with_retry(configs)


def _check_leftover_or_raise(self, ctx: ExistingComponentContext) -> None:
    leftover_map = ctx.leftover()
    violations = {
        kind: items
        for kind, items in leftover_map.items()
        if self._leftover_policy(kind) == "strict"
    }
    if violations:
        raise ComponentReuseError(self, violations)
```

要点：

- leftover 检查必须在 `apply_data_link_with_retry(configs)` **之前**完成，避免本地检查失败但云端已被部分下发；
- 多 kind 的 strict 违规一次性聚合到一个错误中抛出，错误信息包含 `data_link_name / strategy / kind / leftover 标识`；
- compose 自身抛异常时 leftover 检查不会执行，这没问题，apply 本身已失败。

## compose 分支接入

每个接入新模式的 `compose_*_configs` 需要：

1. 函数签名增加 `existing_context: ExistingComponentContext | None = None` 参数；
2. 在每个 `update_or_create` 之前插入：

   ```python
   existing = existing_context and existing_context.claim(
       ResultTableConfig,
       lambda c: c.table_id == usage_monitor_table_id,
   )
   name = existing.name if existing else usage_vmrt_name
   ```

3. 用 `name` 替换原本的固定 `name=usage_vmrt_name` 走 `update_or_create`；
4. 后续 `compose_config(...)` 等渲染逻辑保持不变 —— 它们已经通过 ORM 实例的 `name` 字段来生成 payload。

predicate 选择建议（不作为框架约束，仅供 review/编写时参考）：

| kind | 推荐稳定语义键 |
| --- | --- |
| `ResultTableConfig` | `table_id` |
| `VMStorageBindingConfig` | `table_id` |
| `ESStorageBindingConfig` | `table_id` |
| `DorisStorageBindingConfig` | `table_id` |
| `ConditionalSinkConfig` | `name == self.data_link_name`（单实例） |
| `DataBusConfig` | `data_id_name`（单实例时也可直接 `name == self.data_link_name`） |

predicate 必须只依赖 ORM 字段，不得依赖 queryset 顺序、pk、`update_at` 等不稳定来源，确保重复 apply 给出一致结果。

## 涉及的 compose 分支

按现状，以下分支需要按 strategy 接入新模式：

- `compose_standard_time_series_configs` (`BK_STANDARD_V2_TIME_SERIES`)
- `compose_bk_plugin_time_series_config` (`BK_EXPORTER_TIME_SERIES` / `BK_STANDARD_TIME_SERIES`)
- `compose_bcs_federal_proxy_time_series_configs`
- `compose_bcs_federal_subset_time_series_configs`
- `compose_basereport_time_series_configs`
- `compose_base_event_configs`
- `compose_system_proc_configs`
- `compose_log_configs`（同时声明 `BK_LOG` 的 ES/Doris binding 为 `keep`）
- `compose_custom_event_configs`

接入顺序建议从单实例链路（`BK_STANDARD_V2_TIME_SERIES`）做起，最后再做 `BASEREPORT_TIME_SERIES_V1` 这类多 slot 链路。

## 与 delete_data_link 的关系

`delete_data_link` 仍按现有逻辑全量删除当前 `data_link_name` 关联的组件，与本次复用机制独立。被 `keep` 策略保留下来的历史 binding，会在 `delete_data_link` 时一起被清理，符合预期。

## 测试策略

至少补充以下测试（按已开启灰度的 strategy 分别覆盖）：

1. **迁移后 name 不一致但可复用**
   - 单实例链路（如 `BK_STANDARD_V2_TIME_SERIES`），既有组件 name 与当前规则不同；
   - 重复 apply 不应新增第二套组件；下发 payload 中 name 与本地一致。

2. **多组件稳定复用**
   - `BASEREPORT_TIME_SERIES_V1`：既有组件按 `table_id` 与本次 slot 对齐；
   - 连续两次 apply，claim 结果完全一致。

3. **部分命中 + 部分新建**
   - 部分 slot 的 existing 已存在并能命中，部分缺失；
   - 命中 slot 复用既有 name，缺失 slot 按 generated name 新建。

4. **歧义放弃复用**
   - 同一 predicate 命中多条 existing；
   - 该 slot 走新建，多余 existing 保留进入 leftover。

5. **strict leftover 触发报错**
   - 单实例 kind 在 datalink 下出现 ≥2 条 existing；
   - apply 在下发前直接 raise，包含 kind 与 existing 标识；
   - 不调用 BKBase 下发接口（mock 验证）。

6. **多 strict 违规一次性聚合**
   - 多个 kind 同时违规；
   - 单次 raise 中包含全部 kind 的违规信息。

7. **`BK_LOG` keep 策略生效**
   - 关闭 Doris 开关后 apply，旧 Doris binding 保留在 ORM；
   - 不报错、不进入下发 payload、不被删除或修改。

8. **claim 误用保护**
   - compose 调 `claim` 传入未注册 kind；
   - ctx 直接 raise，确保编程错误尽早暴露。

9. **历史 strategy 创建的组件被纳入 ctx**
   - 构造一条属于 `ALL_DATA_LINK_COMPONENT_KINDS` 但不属于当前 strategy 默认 kind 的 existing；
   - 当前 strategy 不会 claim 它，最终进入 leftover；按默认 `strict` 报错。

10. **灰度开关关闭时回退到老路径**
    - `DATA_LINK_COMPONENT_REUSE_STRATEGIES` 不包含该 strategy；
    - apply 行为与改造前完全一致；ctx 不被构造，leftover 检查不执行。

## 复用后元数据回填

复用能力只解决 "apply 过程中选对 name" 一半的问题；剩下一半是 apply 成功之后，下游元数据（`BkBaseResultTable` / `AccessVMRecord` / 状态刷新任务）必须按实名回填，否则依旧会按旧生成名错查一通。相关修改集中在四处：

```
apply_data_link (reuse ok)
   └─► compose 已经把 RT/Binding/DataBus 的实名（可能是 legacy 名）落入 *Config 表
       │
       ├─► sync_metadata
       │     ├─ ResultTableConfig.objects.get(data_link_name, table_id)   → bkbase_rt_name
       │     ├─ DataBusConfig.objects.get(data_link_name)                 → bkbase_data_name
       │     └─ bkbase_table_id = f"{rt.datalink_biz_ids.data_biz_id}_{rt.name}"
       │        ↓
       │     BkBaseResultTable(data_link_name=...)
       │        ↓
       ├─► create_bkbase_data_link
       │     └─ AccessVMRecord.vm_result_table_id = BkBaseResultTable.bkbase_table_id
       │
       └─► _refresh_data_link_status（周期任务）
             ├─ DataIdConfig: 先按 bkbase_data_name；miss 则 fallback 到 DataLink.bk_data_id
             └─ 各 kind 组件: 按 (bk_tenant_id, namespace, data_link_name) 过滤后逐个刷新
```

不变式：

- `BkBaseResultTable.bkbase_rt_name == ResultTableConfig.name`（本次 apply 真正使用的 RT 名，可能是 legacy）。
- `BkBaseResultTable.bkbase_table_id == f"{rt.datalink_biz_ids.data_biz_id}_{rt.name}"`；业务 id 与 compose 中 `monitor_biz_id` 同源，多租户下跟随 tenant。
- `BkBaseResultTable.bkbase_data_name == DataBusConfig.data_id_name`（若链路未来演进出多 databus 会立刻 `MultipleObjectsReturned`，比静默写错名好）。
- `AccessVMRecord.vm_result_table_id == BkBaseResultTable.bkbase_table_id`；读取失败才 fallback 用 `get_tenant_datalink_biz_id(bk_tenant_id, bk_biz_id).data_biz_id` 兜底。
- `_refresh_data_link_status` 不再要求 RT/Binding/DataBus 三者同名。

兼容性处理：

- `sync_metadata` 查不到 `ResultTableConfig` / `DataBusConfig` 时 warning + skip，不再猜名写入；已命中 `MultipleObjectsReturned` 走 error + skip。
- `_refresh_data_link_status` 中 `DataIdConfig` 按 `bkbase_data_name` 查不到时 fallback 按 `DataLink.bk_data_id` 再查一次，兜住历史脏数据；两个 key 都 miss 时只跳过数据源状态刷新，不影响组件循环。

顺带清理：

- `BkBaseResultTable.component_id` property（把 `bkbase_rt_name` 错当作 DataBus name 使用，仅 1 个单测引用）本次一并删除。

## 非本次处理

- 清理历史重复组件 / 孤儿组件回收；
- 跨 datalink 误关联自动修复；
- DataId 侧的迁移命名兼容；
- 直接对 BKBase 现网组件做全量扫描比对；
- 多进程/多节点并发执行 `apply_data_link` 的并发安全性。
