## ADDED Requirements

### Requirement: Inline unauthorized recovery
首页空间匹配失败 SHALL 保持原 URL 并显示未授权提示，空间下拉仍可操作。

#### Scenario: Invalid space on initial load
- GIVEN 首页 URL 包含无法匹配的 spaceUid 或 bizId，以及 IndexId 和检索参数
- WHEN 首页初始化完成
- THEN URL 保持不变，展示空间未授权提示，且可展开空间列表，不发起无效空间的索引检索请求

### Requirement: Recover original index selection
从空间失败状态切换可用空间 SHALL 使用原始 IndexId 进入现有索引适配流程。

#### Scenario: Original index exists in selected space
- GIVEN 首页显示空间未授权，原 URL 含 IndexId
- WHEN 用户选择包含该索引的可用空间
- THEN 留在首页并检索该索引，更新空间参数且保留其他适用参数

#### Scenario: Original index absent in selected space
- GIVEN 首页空间匹配失败且 URL 含 IndexId
- WHEN 用户切换到不包含该索引的空间
- THEN 复用原有索引适配与回退逻辑，不引入新的选取优先级

### Requirement: Preserve existing authorized behavior
已匹配空间的普通切换 SHALL 保留原有常规和场景化检索行为。

#### Scenario: Normal scene space switch
- GIVEN 已成功进入场景化检索
- WHEN 用户切换空间
- THEN 仍清除旧空间索引和场景条件，按现有规则恢复默认场景

#### Scenario: No available spaces
- GIVEN 空间匹配失败且完整空间列表为空
- WHEN 用户展开下拉
- THEN 显示空列表并保留未授权提示，不转入无限加载或启动检索
