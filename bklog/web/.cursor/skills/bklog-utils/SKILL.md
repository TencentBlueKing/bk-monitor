---
name: bklog-utils
description: BKLog 工具函数使用指南。包含项目内封装的通用工具函数、消息提示、日期处理、DOM 操作等。当需要使用工具函数、处理数据格式化或添加通用逻辑时使用。
---

# BKLog 工具函数指南

## 工具函数位置

```
src/common/
├── util.js         # 核心通用工具函数
├── bkmagic.js      # 消息提示封装
├── bus.js          # 事件总线
└── field-resolver.ts # 字段解析

src/global/utils/
├── time.ts         # 时间处理
├── path.ts         # 路径处理
├── task-pool.ts    # 任务池
└── lazy-task-manager.ts # 懒任务管理
```

## 消息提示

```javascript
import { messageSuccess, messageError, messageWarn, messageInfo } from '@/common/bkmagic';

// 成功提示
messageSuccess('操作成功');

// 错误提示
messageError('操作失败', 5000);  // 5秒后消失

// 警告提示
messageWarn('请注意');

// 信息提示
messageInfo('提示信息');

// 也可通过 Vue 实例调用
this.messageSuccess('成功');
```

## 日期时间处理

```javascript
import { formatDate, formatDateNanos, utcFormatDate } from '@/common/util';

// 格式化时间戳
formatDate(1699084800000);  // "2023-11-04 12:00:00"

// 带时区格式化
formatDate(1699084800000, true);  // "2023-11-04 12:00:00+0800"

// 纳秒精度时间格式化
formatDateNanos('2024-04-09T13:02:11.502064896Z');
// "2024-04-09 21:02:11.502064896"

// UTC 格式化
utcFormatDate('2023-11-04T12:00:00Z');
```

## 数据处理

### 深拷贝

```javascript
import { deepClone } from '@/common/util';

const copy = deepClone(originalObject);
```

### 深度比较

```javascript
import { deepEqual } from '@/common/util';

const isEqual = deepEqual(obj1, obj2, ['ignoreKey']);
```

### 表格数据解析

```javascript
import { parseTableRowData, getRowFieldValue } from '@/common/util';

// 获取嵌套字段值
const value = parseTableRowData(row, 'a.b.c', 'text', false, '--');

// 支持虚拟别名字段
const fieldValue = getRowFieldValue(row, fieldConfig);
```

### 大数字处理

```javascript
import { bigNumberToString, parseBigNumberList } from '@/common/util';

// 处理 BigNumber 类型
const str = bigNumberToString(bigNumberValue);

// 批量处理列表
const list = parseBigNumberList(rawList);
```

## 文件操作

```javascript
import { blobDownload, downFile, downJsonFile, formatFileSize } from '@/common/util';

// 下载 Blob 文件
blobDownload(data, 'filename.txt', 'text/plain');

// 下载文件
downFile('https://example.com/file.zip', 'download.zip');

// 下载 JSON
downJsonFile(JSON.stringify(data), 'data.json');

// 格式化文件大小
formatFileSize(1024);  // "1.00KB"
formatFileSize(1048576, true);  // "1MB"（整数不保留小数）
```

## 字符串处理

```javascript
import { 
  escape, 
  base64Encode, 
  base64Decode, 
  getStringLen,
  getCharLength,
  copyMessage,
  xssFilter 
} from '@/common/util';

// 转义特殊字符
escape('hello.*world');  // "hello\\.\\*world"

// Base64 编解码
const encoded = base64Encode('中文');
const decoded = base64Decode(encoded);

// 获取字符串长度（中文算2个）
getStringLen('hello中文');  // 9

// 复制到剪贴板
copyMessage('要复制的文本', '复制成功提示');

// XSS 过滤
const safe = xssFilter('<script>alert(1)</script>');
```

## DOM 操作

```javascript
import { 
  getStyle, 
  getActualTop, 
  getActualLeft,
  getScrollHeight,
  getScrollTop,
  getWindowHeight,
  getTextPxWidth 
} from '@/common/util';

// 获取元素样式
const color = getStyle(element, 'color');

// 获取元素相对页面的位置
const top = getActualTop(element);
const left = getActualLeft(element);

// 计算文本像素宽度
const width = getTextPxWidth('hello', '12px', 'monospace');
```

## 表格相关

```javascript
import { 
  setDefaultTableWidth, 
  calculateTableColsWidth,
  setFieldsWidth,
  clearTableFilter,
  renderHeader 
} from '@/common/util';

// 设置表格默认宽度自适应
setDefaultTableWidth(visibleFields, tableData, cachedWidths);

// 计算列宽度
const [width, minWidth] = calculateTableColsWidth(field, list);

// 清空表格过滤条件
clearTableFilter(tableRef);

// 表头渲染（带 overflow tips）
renderHeader(h, { column });
```

## 其他工具

### 防抖装饰器

```javascript
import { Debounce } from '@/common/util';

class MyClass {
  @Debounce(300)
  handleSearch() {
    // 300ms 防抖
  }
}
```

### Storage 类

```javascript
import { Storage } from '@/common/util';

const storage = new Storage(3600000);  // 1小时过期
storage.set('key', { data: 'value' });
const data = storage.get('key');  // 过期返回 null
storage.remove('key');
```

### 随机数/颜色

```javascript
import { random, randomInt, randomColor } from '@/common/util';

// 随机字符串
random(8);  // "a3b5c7d9"

// 随机整数
randomInt(1, 100);  // 1-100 之间

// 随机颜色
randomColor('3a84ff', 5);  // 基于蓝色生成5个相近颜色
```

### 系统检测

```javascript
import { getOs, getOsCommandLabel, isIPv6 } from '@/common/util';

getOs();  // 'macos' | 'windows' | 'unknown'
getOsCommandLabel();  // 'Cmd' 或 'Ctrl'
isIPv6('::1');  // true
```

## 使用建议

1. **优先使用已有工具**: 先查找 `src/common/util.js` 是否有满足需求的函数
2. **保持单一职责**: 新工具函数应只做一件事
3. **添加 JSDoc 注释**: 说明参数、返回值和用途
4. **考虑边界情况**: 处理 null、undefined、空数组等
