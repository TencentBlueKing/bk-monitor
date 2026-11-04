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

export interface ManageEntity {
  id: string;
  name: string;
  status: string;
  [key: string]: string;
}

export interface ManageModuleColumn {
  colKey: string;
  title: string;
  width?: number;
}

export interface ManageModuleTab {
  id: string;
  title: string;
}

export interface ManageModuleSpec {
  id: string;
  title: string;
  createLabel: string;
  empty: string;
  tabs: ManageModuleTab[];
  columns: ManageModuleColumn[];
  items: Record<string, ManageEntity[]>;
}

export interface ManageModuleSnapshot {
  tab: string;
  filterQuery: string;
  items: ManageEntity[];
}

export const MANAGE_PAGE_SPECS: Record<string, ManageModuleSpec> = {
  'manage-index-set': {
    id: 'manage-index-set',
    title: '索引集',
    createLabel: '新建索引集',
    empty: '暂无索引集',
    tabs: [
      { id: 'list', title: '列表' },
      { id: 'masking', title: '脱敏' },
    ],
    columns: [
      { colKey: 'name', title: '名称' },
      { colKey: 'storage', title: '存储时间', width: 120 },
      { colKey: 'status', title: '状态', width: 120 },
    ],
    items: {
      list: [
        { id: 'idx-1', name: 'nginx-index', storage: '7 天', status: '就绪' },
        { id: 'idx-2', name: 'app-index', storage: '30 天', status: '运行中' },
      ],
      masking: [{ id: 'idx-mask-1', name: 'nginx-index / password', storage: '-', status: '已启用' }],
    },
  },
  'manage-custom-report': {
    id: 'manage-custom-report',
    title: '自定义上报',
    createLabel: '新建上报',
    empty: '暂无自定义上报',
    tabs: [
      { id: 'list', title: '列表' },
      { id: 'detail', title: '详情' },
    ],
    columns: [
      { colKey: 'name', title: '名称' },
      { colKey: 'kind', title: '类型', width: 140 },
      { colKey: 'status', title: '状态', width: 120 },
    ],
    items: {
      list: [
        { id: 'cr-1', name: 'otlp-trace', kind: 'OTLP', status: '运行中' },
        { id: 'cr-2', name: 'json-event', kind: 'JSON', status: '就绪' },
      ],
      detail: [{ id: 'cr-1', name: 'otlp-trace', kind: 'OTLP', status: 'token=demo' }],
    },
  },
  'manage-clean': {
    id: 'manage-clean',
    title: '清洗与脱敏',
    createLabel: '新建清洗',
    empty: '暂无清洗项',
    tabs: [
      { id: 'item', title: '清洗项' },
      { id: 'template', title: '模板' },
      { id: 'masking', title: '脱敏' },
    ],
    columns: [
      { colKey: 'name', title: '名称' },
      { colKey: 'kind', title: '类型', width: 140 },
      { colKey: 'status', title: '状态', width: 120 },
    ],
    items: {
      item: [{ id: 'clean-1', name: 'nginx-json', kind: 'JSON', status: '已应用' }],
      template: [
        { id: 'tpl-1', name: 'json-default', kind: 'JSON', status: '就绪' },
        { id: 'tpl-2', name: 'nginx-grok', kind: 'Grok', status: '就绪' },
      ],
      masking: [{ id: 'mask-1', name: 'phone / password', kind: '脱敏规则', status: '已启用' }],
    },
  },
  'manage-archive': {
    id: 'manage-archive',
    title: '日志归档',
    createLabel: '新建归档',
    empty: '暂无归档配置',
    tabs: [
      { id: 'repo', title: '仓库' },
      { id: 'list', title: '列表' },
      { id: 'restore', title: '回溯' },
    ],
    columns: [
      { colKey: 'name', title: '名称' },
      { colKey: 'repo', title: '仓库', width: 140 },
      { colKey: 'status', title: '状态', width: 120 },
    ],
    items: {
      repo: [{ id: 'repo-1', name: 'cos-cold', repo: 'COS', status: '就绪' }],
      list: [{ id: 'arc-1', name: 'hot-to-cold', repo: 'cos-cold', status: '就绪' }],
      restore: [{ id: 'rst-1', name: 'restore-demo', repo: 'cos-cold', status: '运行中' }],
    },
  },
  'manage-extract': {
    id: 'manage-extract',
    title: '日志提取',
    createLabel: '新建提取',
    empty: '暂无提取任务',
    tabs: [
      { id: 'task', title: '任务' },
      { id: 'link', title: '链路' },
      { id: 'config', title: '配置' },
    ],
    columns: [
      { colKey: 'name', title: '名称' },
      { colKey: 'link', title: '链路', width: 140 },
      { colKey: 'status', title: '状态', width: 120 },
    ],
    items: {
      task: [{ id: 'ext-1', name: 'extract-nightly', link: 'default', status: '运行中' }],
      link: [{ id: 'link-1', name: 'default', link: 'bk-log', status: '就绪' }],
      config: [{ id: 'cfg-1', name: 'extract-permission', link: '-', status: '就绪' }],
    },
  },
  'manage-es': {
    id: 'manage-es',
    title: 'ES 集群',
    createLabel: '新建集群',
    empty: '暂无 ES 集群',
    tabs: [{ id: 'list', title: '集群' }],
    columns: [
      { colKey: 'name', title: '名称' },
      { colKey: 'host', title: '地址', width: 200 },
      { colKey: 'status', title: '状态', width: 120 },
    ],
    items: {
      list: [
        { id: 'es-1', name: 'es-default', host: 'es.example:9200', status: '运行中' },
        { id: 'es-2', name: 'es-backup', host: 'es-bak.example:9200', status: '已停用' },
      ],
    },
  },
  'manage-client-log': {
    id: 'manage-client-log',
    title: '客户端采集',
    createLabel: '新建采集',
    empty: '暂无客户端采集',
    tabs: [
      { id: 'collect', title: '采集' },
      { id: 'search', title: '检索任务' },
    ],
    columns: [
      { colKey: 'name', title: '名称' },
      { colKey: 'version', title: '版本', width: 120 },
      { colKey: 'status', title: '状态', width: 120 },
    ],
    items: {
      collect: [{ id: 'cli-1', name: 'desktop-agent', version: '1.2.0', status: '运行中' }],
      search: [{ id: 'cls-1', name: 'login-task', version: '-', status: '就绪' }],
    },
  },
  'manage-grok': {
    id: 'manage-grok',
    title: 'Grok 管理',
    createLabel: '新建模式',
    empty: '暂无 Grok 模式',
    tabs: [{ id: 'list', title: '模式' }],
    columns: [
      { colKey: 'name', title: '名称' },
      { colKey: 'pattern', title: '模式' },
      { colKey: 'status', title: '状态', width: 120 },
    ],
    items: {
      list: [{ id: 'grok-1', name: 'nginx-combined', pattern: '%{IP:client} %{WORD:method}', status: '就绪' }],
    },
  },
};

export class ManageModuleController {
  private spec: ManageModuleSpec;
  private snapshot: ManageModuleSnapshot;

  constructor(moduleId: string) {
    this.spec = MANAGE_PAGE_SPECS[moduleId] ?? MANAGE_PAGE_SPECS['manage-index-set'];
    this.snapshot = {
      tab: this.spec.tabs[0].id,
      filterQuery: '',
      items: this.spec.items[this.spec.tabs[0].id].map(item => ({ ...item })),
    };
  }

  getSpec(): ManageModuleSpec {
    return this.spec;
  }

  getState(): ManageModuleSnapshot {
    return { ...this.snapshot, items: this.snapshot.items.map(item => ({ ...item })) };
  }

  getVisibleItems(): ManageEntity[] {
    const query = this.snapshot.filterQuery.toLowerCase();
    return this.snapshot.items.filter(item => (
      !query
      || item.name.toLowerCase().includes(query)
      || Object.values(item).some(value => String(value).toLowerCase().includes(query))
    ));
  }

  setTab(tab: string): ManageModuleSnapshot {
    const next = this.spec.tabs.some(item => item.id === tab) ? tab : this.spec.tabs[0].id;
    this.snapshot = {
      tab: next,
      filterQuery: '',
      items: (this.spec.items[next] ?? []).map(item => ({ ...item })),
    };
    return this.getState();
  }

  setFilterQuery(value: string): ManageModuleSnapshot {
    this.snapshot = { ...this.snapshot, filterQuery: String(value ?? '').trim() };
    return this.getState();
  }

  save(name: string): ManageModuleSnapshot {
    const trimmed = String(name ?? '').trim();
    if (!trimmed) {
      return this.getState();
    }
    if (this.snapshot.items.some(item => item.name === trimmed)) {
      return this.getState();
    }
    this.snapshot = {
      ...this.snapshot,
      items: [{ id: `new-${Date.now()}`, name: trimmed, status: '就绪' }, ...this.snapshot.items],
    };
    return this.getState();
  }

  remove(id: string): ManageModuleSnapshot {
    this.snapshot = { ...this.snapshot, items: this.snapshot.items.filter(item => item.id !== id) };
    return this.getState();
  }
}
