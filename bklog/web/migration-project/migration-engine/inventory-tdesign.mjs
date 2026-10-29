/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 *
 * Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
 *
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) is licensed under the MIT License.
 *
 * License for 蓝鲸智云PaaS平台 (BlueKing PaaS):
 *
 * ---------------------------------------------------
 * Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated
 * documentation files (the "Software"), to deal in the Software without restriction, including without limitation
 * the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and
 * to permit persons to whom the Software is furnished to do so, subject to the following conditions:
 *
 * The above copyright notice and this permission notice shall be included in all copies or substantial portions of
 * the Software.
 *
 * THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO
 * THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
 * AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF
 * CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS
 * IN THE SOFTWARE.
 */

import { readdir, readFile, mkdir, writeFile } from 'node:fs/promises';
import { dirname, resolve, relative } from 'node:path';
import { fileURLToPath } from 'node:url';
const here = dirname(fileURLToPath(import.meta.url));
const root = resolve(here, '../../src');
const mappings = {
  alert: 'Alert',
  badge: 'Badge',
  'big-tree': 'Tree',
  checkbox: 'Checkbox',
  'checkbox-group': 'CheckboxGroup',
  col: 'Col',
  collapse: 'Collapse',
  'collapse-item': 'CollapsePanel',
  container: 'Layout',
  'date-picker': '@blueking/date-picker (保留)',
  button: 'Button',
  dialog: 'Dialog',
  'dropdown-menu': 'Dropdown',
  exception: 'Empty + 业务异常页',
  form: 'Form',
  'form-item': 'FormItem',
  input: 'Input / Textarea / InputNumber',
  navigation: 'Layout + Menu',
  'navigation-menu': 'Menu',
  'navigation-menu-group': 'MenuGroup',
  'navigation-menu-item': 'MenuItem',
  option: 'Option',
  'option-group': 'OptionGroup',
  pagination: 'Pagination',
  popover: 'Popup',
  popconfirm: 'Popconfirm',
  process: 'Steps + 业务进度状态',
  progress: 'Progress',
  radio: 'Radio',
  'radio-group': 'RadioGroup',
  'radio-button': 'RadioButton',
  'round-progress': 'Progress',
  row: 'Row',
  'search-select': 'SelectInput + 业务查询编辑器',
  select: 'Select',
  sideslider: 'Drawer',
  slider: 'Slider',
  steps: 'Steps',
  switcher: 'Switch',
  tag: 'Tag',
  tab: 'Tabs',
  'tab-panel': 'TabPanel',
  table: 'Table / EnhancedTable',
  'table-column': 'columns + cell / title 函数',
  'table-setting-content': 'Popup + CheckboxGroup + 字段配置',
  'tag-input': 'TagInput',
  'time-picker': 'TimePicker',
  timeline: 'Timeline',
  transfer: 'Transfer',
  tree: 'Tree',
  upload: 'Upload',
  swiper: 'Swiper',
  rate: 'Rate',
  'animate-number': 'Statistic',
  'virtual-scroll': '虚拟滚动业务适配',
  spin: 'Loading',
  loading: 'Loading',
  tooltips: 'Tooltip / Popup',
  notify: 'NotifyPlugin',
  message: 'MessagePlugin',
  'info-box': 'DialogPlugin',
  'resize-layout': '业务可拖拽布局',
  'overflow-tips': 'Tooltip',
  clickoutside: '业务外部点击指令',
  divider: 'Divider',
};
const entries = new Map();
const imports = [];
function add(name, file, kind, attrs = '') {
  const record = entries.get(name) || {
    source: name,
    target: mappings[name] || '待源码分析，禁止占位替换',
    status: '待分析',
    occurrences: 0,
    files: new Set(),
    props: new Set(),
    events: new Set(),
    slots: new Set(),
    kinds: new Set(),
  };
  record.occurrences++;
  record.files.add(file);
  record.kinds.add(kind);
  for (const m of attrs.matchAll(/(?:^|\s)([:@#]?[\w.-]+)(?:\s*=|\s|$)/g)) {
    const k = m[1];
    if (k.startsWith('@')) record.events.add(k.slice(1));
    else if (k.startsWith('#')) record.slots.add(k.slice(1));
    else record.props.add(k.replace(/^:/, ''));
  }
  entries.set(name, record);
}
async function walk(dir) {
  for (const item of await readdir(dir, { withFileTypes: true })) {
    const path = resolve(dir, item.name);
    if (item.isDirectory()) await walk(path);
    else if (/\.(?:vue|[jt]sx?)$/.test(item.name)) {
      const content = await readFile(path, 'utf8');
      const file = relative(root, path);
      for (const match of content.matchAll(/<bk-([a-z][\w-]*)\b([^>]*?)>/g))
        add(match[1], file, 'template/JSX', match[2]);
      for (const match of content.matchAll(/\bv-bk([a-z]+)\b/g)) add(match[1], file, 'directive');
      for (const match of content.matchAll(/\bimport\s+([^;]*?)\s+from\s+['"](bk-magic-vue[^'"]*)['"]/g)) {
        // Start at the closest import to avoid crossing unrelated statements.
        const spec = match[1];
        imports.push({ file, module: match[2], specifiers: spec.trim() });
        for (const name of spec.matchAll(/\bbk([A-Z]\w*)\b/g))
          add(
            name[1].replace(/[A-Z]/g, (c, i) => (i ? '-' : '') + c.toLowerCase()),
            file,
            'import',
          );
      }
    }
  }
}
await walk(root);
const components = [...entries.values()]
  .map(e => ({
    ...e,
    files: [...e.files].sort(),
    props: [...e.props].sort(),
    events: [...e.events].sort(),
    slots: [...e.slots].sort(),
    kinds: [...e.kinds],
  }))
  .sort((a, b) => b.files.length - a.files.length);
const output = resolve(here, '../artifacts/tdesign/source-inventory.json');
await mkdir(dirname(output), { recursive: true });
await writeFile(
  output,
  JSON.stringify(
    {
      source: 'bklog/web/src',
      generatedAt: new Date().toISOString(),
      scope: '源码静态候选，属性/事件/插槽需结合AST和运行时复核，计数不代表验收',
      componentCount: components.length,
      importFileCount: new Set(imports.map(x => x.file)).size,
      imports,
      components,
    },
    null,
    2,
  ) + '\n',
);
console.log(
  JSON.stringify(
    {
      output,
      components: components.length,
      importFiles: new Set(imports.map(x => x.file)).size,
      top: components.slice(0, 12).map(x => ({ source: x.source, files: x.files.length, target: x.target })),
    },
    null,
    2,
  ),
);
