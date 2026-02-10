# 前端架构流程图

本目录包含 bklog/web 前端项目的架构流程图，每个 `.mmd` 文件是独立的 Mermaid 流程图文件。

## 文件列表

| 文件名 | 描述 |
|--------|------|
| `A-整体前端架构图.mmd` | 展示应用入口层、核心基础设施、Store/路由模块、全局 UI 组件的整体关系 |
| `B-应用启动时序图.mmd` | 从浏览器加载到应用渲染的完整启动时序 |
| `C-路由守卫执行流程.mmd` | beforeEach/afterEach 守卫的判断逻辑与处理步骤 |
| `D-Retrieve检索模块初始化数据流.mmd` | 检索页面从 URL 解析到查询执行的完整链路 |
| `E-HTTP请求处理流程.mmd` | 请求发起 → 拦截器 → 响应处理 → 错误处理全流程 |
| `F-Vuex-Store状态流转图.mmd` | 组件与 Store 之间 dispatch/commit/mapState 的数据流动 |
| `G-检索模块API调用链路图.mmd` | 从 Preload 到检索查询再到衍生能力的 API 依赖关系 |
| `H-Manage管理模块组件结构图.mmd` | 管理模块壳与各子功能模块的组件层级关系 |
| `I-完整页面请求时序图.mmd` | 以检索页为例的用户访问全流程时序图 |
| `J-API-Key映射查找流程.mmd` | http.request 如何通过 services 映射到实际接口 |
| `K-分层架构全景图.mmd` | 从用户交互层到后端 API 的完整分层结构 |
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
