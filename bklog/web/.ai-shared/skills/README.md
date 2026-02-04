# BKLog Web Skills（索引）

## 必读（任务开始前）

`bklog-architecture/SKILL.md` → 项目地图 + 模块映射

## 按需读取

- `bklog-components/SKILL.md` → 组件使用
- `bklog-hooks/SKILL.md` → Hooks 使用
- `bklog-api-services/SKILL.md` → API 调用
- `bk-magicbox-vue/SKILL.md` → UI 组件库

## 快速定位

| 问题形态 | 最小入口（先读这些） |
|---------|-----------------------|
| URL/query/分享链接/地址栏参数 | `src/store/url-resolver.ts` + `src/store/default-values.ts` + `src/views/retrieve-v3/use-app-init.tsx` |
| 路由/版本切换/入口组件 | `src/views/retrieve-hub.tsx` + `src/router/retrieve.js` |
| 检索状态/Vuex | `src/store/retrieve.js` + `src/store/index.js` |
| HTTP/拦截器/全局错误 | `src/api/index.js` + `src/services/index.js` |

## 扩展到其他模块（通用定位）

Route(name/path) → View(entry) → Store(module) → Services(key) → API(axios)
ServiceKey(ns/action) → `src/services/index.js` → `src/services/<ns>.{ts,js}`

## 本地辅助定位（零 Token）

`node scripts/ai-locate.js "<关键词>" --rg`
