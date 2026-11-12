# 源码入口审查

当前候选图扫描861个脚本/SFC，发现90条路由（88条具名、2条无名），不是历史所说的87条。组件依赖追溯覆盖76条路由；12条为本地router-view布局，2条仅重定向。完整清单见source/route-entries.json。上述数量不是功能通过率。

router/index.js组装retrieve/monitor/dashboard/manage工厂，根路由按外部版菜单选默认入口。manage.js由log_manage_v2决定当前/旧组件和二级导航；/manage按外部版跳转提取或采集。monitor.js的APM/Trace由条件编译区分，不能把未编译分支当作普通主应用页验收。

retrieve入口先走retrieve-hub，再由retrieve_version选分支。Vue2内部retrieve-v3继续复用retrieve-v2的结果面板、趋势、图表等组件。检索行为契约不能只分析retrieve-v3目录。

views/404.vue的template functional是合法Vue2语法。Vue3 compiler-sfc产生兼容警告但仍有template AST；已分类并用专门用例确认事件不丢失。

7条本地未解析import继续保留：4条类型依赖，3条运行时依赖候选。由main.js静态可达图均未覆盖，不足以证明无用：动态注册、构建入口仍需复核。183个动态/条件编译候选也没有移出分母。详细出处及摘要见dependency-review.json、unresolved.json。

行为契约审查仍在进行。3319个事件绑定和19730个分支仅为源码候选数量，不作为已验证业务场景数。
