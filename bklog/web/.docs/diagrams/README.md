# 前端架构流程图

本目录包含 bklog/web 前端项目的架构流程图，每个 `.mmd` 文件是独立的 Mermaid 流程图文件。

## 文件列表

| 文件名 | 描述 |
|--------|------|
| `A-整体前端架构图.mmd` | 含 `index.html` 静态壳、应用入口、核心基础设施、Store/路由与全局 UI |
| `B-应用启动时序图.mmd` | 从 `index.html` / bootstrap-loading 到 preload、挂载与淡出首屏占位 |
| `C-路由守卫执行流程.mmd` | beforeEach/afterEach 守卫的判断逻辑与处理步骤 |
| `D-Retrieve检索模块初始化数据流.mmd` | V3 页面初始化、字段元数据与首屏查询链路 |
| `E-HTTP请求处理流程.mmd` | 请求发起 → 拦截器 → 响应处理 → 错误处理全流程 |
| `F-Vuex-Store状态流转图.mmd` | preload→Vuex，以及 Worker、IndexedDB 与结果组件边界 |
| `G-检索模块API调用链路图.mmd` | 普通/联合/场景检索及衍生能力 API 依赖关系 |
| `H-Manage管理模块组件结构图.mmd` | 管理模块壳与各子功能模块的组件层级关系 |
| `I-完整页面请求时序图.mmd` | 从静态壳到检索初始化、流式落盘和按键渲染 |
| `J-API-Key映射查找流程.mmd` | 主线程 http.request 映射；V3 主查询 Worker fetch 旁路 |
| `K-分层架构全景图.mmd` | 静态壳→启动编排→视图/状态/Worker/IndexedDB |

| `L-空间切换数据流.mmd` | 用户切换空间时的状态重置与数据重新加载流程 |

## 使用方式

### 方式一：在线预览

1. **Mermaid Live Editor**  
   访问 https://mermaid.live/，将 `.mmd` 文件内容粘贴到编辑器中即可预览

2. **GitHub / GitLab**  
   直接将 `.mmd` 文件内容放入 Markdown 的 \`\`\`mermaid 代码块中即可渲染

### 方式二：本地预览

1. **VS Code 插件**  
   安装 `Mermaid Preview` 或 `Markdown Preview Mermaid Support` 插件

2. **命令行工具**  
   ```bash
   # 安装 mermaid-cli
   npm install -g @mermaid-js/mermaid-cli

   # 生成 PNG 图片
   mmdc -i A-整体前端架构图.mmd -o A-整体前端架构图.png

   # 生成 SVG 图片
   mmdc -i A-整体前端架构图.mmd -o A-整体前端架构图.svg

   # 批量生成所有图片
   for file in *.mmd; do mmdc -i "$file" -o "${file%.mmd}.svg"; done
   ```

### 方式三：集成到文档

```markdown
# 我的文档

## 架构图

\`\`\`mermaid
graph TB
    A[节点A] --> B[节点B]
\`\`\`
```

## 主题配置

每个 `.mmd` 文件都包含了 `%%{init: {...}}%%` 主题配置，你可以根据需要修改颜色主题：

```mermaid
%%{init: {'theme': 'base', 'themeVariables': { 
    'primaryColor': '#e3f2fd',      // 主色
    'primaryTextColor': '#1565c0',  // 主文字色
    'primaryBorderColor': '#1976d2', // 主边框色
    'lineColor': '#42a5f5'          // 连线色
}}}%%
```

## 图例说明

| 形状 | 含义 |
|------|------|
| `([...])` | 开始/结束节点 |
| `[...]` | 普通处理节点 |
| `{...}` | 判断/条件节点 |
| `-->` | 流程方向 |
| `-->|标签|` | 带标签的流程 |
