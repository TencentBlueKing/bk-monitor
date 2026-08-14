# @blueking/ai-ui-sdk 使用问题记录

## 问题1：package.json 需要补全 typesVersions 属性

### 背景

SDK 的 `package.json` 已配置 `exports.types` 来导出子路径类型，但当前项目使用 `moduleResolution: "node"`，该模式**不支持 `exports` 的子路径类型解析**，导致子路径导入（如 `@blueking/ai-ui-sdk/components`）无法识别类型。

因此需要同时补充 `typesVersions` 配置，作为 `node` 模式下的兼容兜底：

```json
{
  "types": "dist/main.d.ts",
  "typesVersions": {
    "*": {
      "components": ["./dist/components.d.ts"],
      "enums": ["./dist/enums.d.ts"]
    }
  },
  "exports": {
    "./components": {
      "types": "./dist/components.d.ts",
      "import": "./dist/components.ts.js",
      "require": "./dist/components.ts.js"
    },
    "./enums": {
      "types": "./dist/enums.d.ts",
      "import": "./dist/enums.ts.js",
      "require": "./dist/enums.ts.js"
    }
  }
}
```

### 原理

| `moduleResolution`                      | 生效机制        | 说明                                                          |
| --------------------------------------- | --------------- | ------------------------------------------------------------- |
| `"node"` (`node10`)                     | `typesVersions` | `exports` 被忽略，由 `typesVersions` 兜底映射子路径到 `.d.ts` |
| `"node16"` / `"nodenext"` / `"bundler"` | `exports.types` | 优先遵循 `exports` 规范                                       |

### 结论

当前项目 `moduleResolution: "node"` 下，子路径导入的类型能正常解析，**依赖的是 `typesVersions` 的兼容配置**，而非 `exports`。

---
