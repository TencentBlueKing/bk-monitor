# 检索试点与共享模型修复记录

本批仅证明两个限定契约：行展开/KV筛选/JSON切换/恢复；初始化显示字段名称与顺序。不是完整检索模块或全业务验收。

## 数据与执行证据

修订1完整捕获包含52个NDJSON事件（meta、50行、done），19个只读请求记录含一次真实客户端取消。V2自回放通过后，V3同数据、同绝对时间和固定Date时钟回归通过；客户端取消真实观察到，没有使用后端兜底。

修订2补齐显示字段断言，20个只读请求记录自回放通过。V2初始显示12项字段及别名顺序；V3修复前为空，修复后与V2一致。具体捕获、回放、对照运行与完整性摘要位于runs/pilot；完整日志、截图及UI JSON保存在0700的本地临时目录，响应文件0600。

## 修复1：展开字段搜索框

Vue2 expand-view.vue 的ext-cls用于业务样式。原兼容适配未转成class，导致搜索宽度130而V2为200，标签栏高度32而V2为23。替换为直接使用TDesign Input，使用Vue3具名value模型，保留handleSearch、handleClearSearch、handleInputChange和原有模式/草稿逻辑；业务样式恢复到相同几何。回车筛选、字段值与响应一致、JSON切换、草稿保留、删空恢复及收起均通过。

名称比较曾将KV/JSON之间的模板空白判为差异，已只规范可访问名称空白，输入/数据值仍严格比较。负向用例保证值中的空格不被吞掉。之前定位失败和Vite依赖预构建引发重新初始化的运行均保留无效状态。

## 修复2：原生模型契约及显示字段消失

真实Vue兼容运行时复现：全局COMPONENT_V_MODEL为suppress-warning时，组件仅MODE:3仍会把modelValue/onUpdate:modelValue转换为value/onModelCompat:input。该设置抑制告警但没有关闭旧语义。

显示字段父组件已有visibleFields与dragVisibleFields各12项，Draggable实际却接到旧value，原生modelValue为空，导致没有渲染。另有模块反复Object.assign同一Draggable兼容配置，覆盖先前修复，使结果取决于模块加载顺序。

新增preserveVue3ComponentModel统一边界，合并已有配置并显式COMPONENT_V_MODEL:false；用于TDesign组件和全部四个Vue3 Draggable导入点。原v-model数组替换及onEnd回调保留，没有保留临时list变更方案。全局旧组件模型语义没有关闭，实际Vue VNode负向测试确认旧组件仍保持原协议。

8项离线原生模型契约通过，覆盖Checkbox、CheckboxGroup、RadioGroup、Input trim/Enter、Select、Switch、TagInput与重置。新夹具在packages/web-v3/fixtures，不依赖被gitignore忽略的历史测试文件。旧夹具曾因bkTooltips导出删除而无法初始化，已记为工具问题；新用例要求成功初始化、精确用例数和源码未变，空运行不能通过。

## 现存问题与边界

- 初始严格类型检查仍有1677条错误；不能宣称项目类型检查通过。
- 两个旧测试的baselineUrl导出丢失已恢复为带当前源码指纹校验的V2引用；四个相关测试文件合计12项通过，只作补充，不代替浏览器证据。
- 尚未验证搜索清空图标、搜索图标点击、字段拖拽持久化、字段统计/添加/移除等完整分支。
- 当前截图仍有导航、其他控件与整体布局待复核；所选语义/几何通过不表示全屏视觉通过。
- AI自动新增会话依然阻止，AI功能未验收。
- 管理种子正在执行，只读菜单/停用类型预览后取消，不提交对现有采集项的任何操作。
