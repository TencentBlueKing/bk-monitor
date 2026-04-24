# 品牌资产

`bkmonitor-admin` 暂时复用 bkmonitor 现有的灰色监控平台图标，避免在第一期引入新的品牌符号。后续如果需要正式设计，可以在不改业务代码的前提下替换 `BrandLogo` 使用的静态资产。

## 资产

- `public/logo-mark.png`：复用自 bkmonitor 的灰色监控图标，适合 favicon、侧边栏、README 和本地开发入口。

## 使用原则

- 第一阶段不再额外生成 SVG 或横向组合标识。
- UI 内统一使用 `logo-mark.png`，旁边保留 `bkmonitor-admin` 文本。
- 如果后续替换正式 logo，优先保持方形图标的路径和尺寸稳定，减少前端改动面。

## 使用建议

- 深色侧边栏中使用方形图标，配合产品名文字。
- README 或文档中只展示图标，不使用横向组合 logo。
