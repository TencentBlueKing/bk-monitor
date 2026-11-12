# P0已有改动处置

当前V2的main、router、url-resolver、event、HTTP、store和retrieve组件内已有埋点；V3若干文件已有testid/可访问性改动。已在source-manifest和preexisting-source.diff冻结，暂不回滚。

旧埋点不是可信观测基准：store.dispatch关闭开关后仍改变返回链/after订阅，异步activeSpanStack无法保证并发因果，HTTP观测还曾新增Traceparent。P4只在通过探针校准后替换必要观测点；冻结的原始差异保持可追溯。

V3既有testid保留为定位候选，不因存在testid标功能通过。未改变任何既有业务资源。

许可证CLI第一次ensure对短头脚本发生正文丢失，本轮测试项数量检查发现异常；已恢复并改用标准头+mark，mark前后校验正文摘要。新增empty-test-files-cannot-pass防止空测试退出0误判。
