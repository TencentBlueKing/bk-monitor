# Grep 语法高亮编辑器

基于 CodeMirror 6 的 grep 命令语法高亮编辑器，支持完整的 grep/egrep 语法解析和高亮显示。

## 功能特性

### 🎨 语法高亮支持

- **命令关键字**: `grep`, `egrep` - 蓝色粗体显示
- **参数选项**: `-i`, `-v`, `-E` 等 - 橙色粗体显示  
- **字符串**: 双引号和单引号字符串 - 绿色显示
- **正则模式**: 未加引号的模式 - 紫色显示
- **管道符**: `|` - 灰色粗体显示
- **转义字符**: `\n`, `\t`, `\"`, `\'`, `\\` - 橙色粗体显示

### 🔧 支持的语法

根据 EBNF 语法定义，支持以下格式：

```ebnf
commands     = command ("|" command)* ;
command      = cmd_prefix (args_pattern) ;  
cmd_prefix   = [ ("grep" | "egrep") ] [ args ] ;
args_pattern = [ args ] pattern | pattern ;
args         = ("-"identifier)+ ;
pattern      = string | raw_pattern ;
string       = double_quoted | single_quoted ;
raw_pattern  = (escape_sequence | non_special_char)+ ;
```

### 📝 使用示例

| 场景 | 语法示例 | 说明 |
|------|----------|------|
| 基础搜索 | `grep "error"` | 简单字符串搜索 |
| 忽略大小写 | `grep -i "WARNING"` | 不区分大小写 |
| 反向匹配 | `grep -v "debug"` | 排除包含 debug 的行 |
| 管道组合 | `grep -i "error" \| grep -v "test"` | 多条件过滤 |
| 转义字符 | `grep "hello\\"world"` | 处理特殊字符 |
| 正则表达式 | `egrep "[0-9]{3}-[A-Z]{2}"` | 使用正则模式 |

## 使用方法

### 基础用法

```vue
<template>
  <GrepCliEditor 
    v-model:value="grepCommand"
    placeholder="输入 grep 命令..."
    height="40px"
    :enable-syntax-highlight="true"
  />
</template>

<script setup>
import { ref } from 'vue';
import GrepCliEditor from './grep-cli-editor';

const grepCommand = ref('grep -i "error" | grep -v "test"');
</script>
```

### 属性配置

| 属性 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `value` | String | `''` | 编辑器内容 |
| `placeholder` | String | `'-- INSERT --'` | 占位符文本 |
| `height` | String | `'36px'` | 编辑器高度 |
| `autoHeight` | Boolean | `false` | 自适应高度 |
| `minHeight` | String | `'36px'` | 最小高度 |
| `maxHeight` | String | `'200px'` | 最大高度 |
| `enableSyntaxHighlight` | Boolean | `true` | 启用语法高亮 |
| `readOnly` | Boolean | `false` | 只读模式 |

### 事件监听

```vue
<GrepCliEditor 
  v-model:value="command"
  @change="handleChange"
  @update:value="handleUpdate"
/>
```

## 高亮规则

### 1. 命令自动补全
- 如果未显式指定 `grep` 或 `egrep`，默认补全为 `grep`
- 支持参数在命令前后的灵活位置

### 2. 参数识别
支持常用的 grep 参数：
- `-i`: 忽略大小写
- `-v`: 反向匹配（排除）
- `-E`: 使用扩展正则表达式

### 3. 字符串处理
- **双引号字符串**: 支持内部转义字符
- **单引号字符串**: 支持内部转义字符  
- **未加引号模式**: 自动识别为正则模式

### 4. 转义字符支持
- 标准转义: `\"`, `\'`, `\\`, `\n`, `\t`, `\r`
- 十六进制转义: `\x1b`, `\xff` 等

### 5. 管道组合
- 支持多级管道操作
- 每个管道段独立解析和高亮

## 文件结构

```
grep/
├── grep-cli-editor.tsx          # 主编辑器组件
├── grep-highlighter.ts          # 语法高亮实现
├── grep-demo.vue               # 演示组件
├── grep-cli-editor.scss        # 样式文件
└── README.md                   # 使用说明
```

## 技术实现

- **编辑器内核**: CodeMirror 6
- **语法分析**: 基于正则表达式的词法分析
- **高亮渲染**: CodeMirror Decoration API
- **框架支持**: Vue 3 + TypeScript

## 演示效果

运行演示组件查看完整的语法高亮效果：

```vue
import GrepDemo from './grep-demo.vue';
```

演示包含了所有支持的语法特性和高亮效果对比。 