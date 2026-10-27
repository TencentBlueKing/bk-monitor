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

export interface ManageNavItem {
  id: string;
  title: string;
  path: string;
  icon: string;
}

export interface ManageNavGroup {
  id: string;
  title: string;
  keyword: string;
  children: ManageNavItem[];
}

export interface ManageNavSnapshot {
  collapsed: boolean;
  collapsedGroups: string[];
}

export const MANAGE_NAV_GROUPS: ManageNavGroup[] = [
  {
    id: 'access',
    title: '数据接入',
    keyword: '接入',
    children: [
      { id: 'manage-collection', title: '采集项', path: '/manage/collection', icon: 'bklog-rizhicaiji' },
      { id: 'manage-custom-report', title: '自定义上报', path: '/manage/custom-report', icon: 'bklog-rizhitiqupeizhi' },
    ],
  },
  {
    id: 'index-set',
    title: '索引集',
    keyword: '索引',
    children: [
      { id: 'manage-index-set', title: '索引集', path: '/manage/index-set', icon: 'bklog-all2' },
    ],
  },
  {
    id: 'clean',
    title: '清洗',
    keyword: '清洗',
    children: [
      { id: 'manage-clean', title: '清洗模板', path: '/manage/clean', icon: 'bklog-rizhitiqupeizhi' },
    ],
  },
  {
    id: 'archive',
    title: '归档',
    keyword: '归档',
    children: [
      { id: 'manage-archive', title: '日志归档', path: '/manage/archive', icon: 'bklog-download' },
    ],
  },
  {
    id: 'extract',
    title: '提取',
    keyword: '提取',
    children: [
      { id: 'manage-extract', title: '日志提取', path: '/manage/extract', icon: 'bklog-rizhitiqupeizhi' },
    ],
  },
  {
    id: 'es',
    title: 'ES',
    keyword: 'ES',
    children: [
      { id: 'manage-es', title: 'ES 集群', path: '/manage/es', icon: 'bklog-shezhi' },
    ],
  },
  {
    id: 'client',
    title: '客户端',
    keyword: '客户端',
    children: [
      { id: 'manage-client-log', title: '客户端采集', path: '/manage/client-log', icon: 'bklog-host' },
      { id: 'manage-grok', title: 'Grok 管理', path: '/manage/grok', icon: 'bklog-set-icon' },
    ],
  },
];

export class ManageNavController {
  private snapshot: ManageNavSnapshot = { collapsed: false, collapsedGroups: [] };

  getState(): ManageNavSnapshot {
    return { collapsed: this.snapshot.collapsed, collapsedGroups: [...this.snapshot.collapsedGroups] };
  }

  getGroups(): ManageNavGroup[] {
    return MANAGE_NAV_GROUPS.map(group => ({
      ...group,
      children: group.children.map(item => ({ ...item })),
    }));
  }

  getActiveId(path: string): string {
    const items = MANAGE_NAV_GROUPS.flatMap(group => group.children);
    const matched = items.find(item => path === item.path || path.startsWith(`${item.path}/`));
    return matched?.id ?? '';
  }

  isGroupCollapsed(id: string): boolean {
    return this.snapshot.collapsedGroups.includes(id);
  }

  toggleGroup(id: string): ManageNavSnapshot {
    const next = new Set(this.snapshot.collapsedGroups);
    if (next.has(id)) {
      next.delete(id);
    } else {
      next.add(id);
    }
    this.snapshot = { ...this.snapshot, collapsedGroups: [...next] };
    return this.getState();
  }

  toggleCollapsed(): ManageNavSnapshot {
    this.snapshot = { ...this.snapshot, collapsed: !this.snapshot.collapsed };
    return this.getState();
  }
}
