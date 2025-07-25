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
export const SPLIT_MIN_WIDTH = 300;
export const SPLIT_MAX_WIDTH = 1200;

export type ContentType = 'component' | 'dashboard' | 'event';
export interface IRelateItem {
  children?: IRelateItem[];
  contentType?: ContentType;
  id: string;
  name: string;
  queryType?: string[];
  sceneType?: SceneType;
}

export type SceneType = 'detail' | 'overview';
// 分屏关联查看选项列表
export const RELATED_MENU_LIST: IRelateItem[] = [
  {
    id: 'scene',
    name: window.i18n.t('场景') as string,
    children: [
      { id: 'host', name: window.i18n.t('主机监控') as string, contentType: 'dashboard', queryType: ['filter'] },
      {
        id: 'kubernetes',
        name: window.i18n.t('容器监控') as string,
        contentType: 'dashboard',
        queryType: ['filter'],
      },
    ],
  },
  {
    id: 'event',
    name: window.i18n.t('事件') as string,
    children: [
      { id: 'alert_event', name: window.i18n.t('告警事件') as string, contentType: 'event', queryType: [] },
      { id: 'action_event', name: window.i18n.t('处理记录') as string, contentType: 'event', queryType: [] },
      {
        id: 'custom_event',
        name: window.i18n.t('自定义事件') as string,
        contentType: 'dashboard',
        queryType: ['input'],
      },
    ],
  },
];

export interface ISplitPanelItem {
  children: SplitPanelModel[];
  id: string;
  name: string;
}

export class SplitPanelModel {
  contentType?: ContentType;
  id: string;
  name: string;
  queryType?: string[];
  sceneType?: SceneType;
  constructor(model: IRelateItem) {
    Object.keys(model).forEach(key => (this[key] = model[key]));
  }
  get defaultParams() {
    // 事件类型的处理记录需默认 参数
    if (this.id === 'action_event') return { activeFilterId: 'action', searchType: 'action' };
    return {};
  }
  get hasFilter() {
    return this.queryType.includes('filter');
  }
  get hasSearchInput() {
    return this.queryType.includes('input');
  }
}

export const SPLIT_PANEL_LIST: ISplitPanelItem[] = RELATED_MENU_LIST.reduce((pre, cur) => {
  pre.push({
    ...cur,
    children: cur.children.map(item => new SplitPanelModel(item)),
  });
  return pre;
}, []);
