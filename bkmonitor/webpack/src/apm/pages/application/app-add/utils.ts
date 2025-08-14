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

import { deepClone } from 'monitor-common/utils/utils';

export interface ICardItem {
  checked: boolean;
  descData?: IDescData;
  hidden: boolean;
  id: string;
  img: string;
  theme: ThemeType;
  title: string;
}
export interface IDescData {
  heat: number;
  isOfficial: boolean;
  name: string;
}
export interface IListDataItem {
  children?: IListDataItem[];
  list?: ICardItem[];
  multiple?: boolean;
  title: string;
  other?: {
    checked: boolean;
    title: string;
    value: string;
  };
}
export type ThemeType = 'lang' | 'plugin' | 'system';
export class SystemData {
  /** 语言数据 */
  lang: IListDataItem = {
    title: window.i18n.tc('支持语言'),
    multiple: false,
    list: [],
  };
  /** 接入流程md文档 */
  mdData: Record<string, Record<string, string>> = null;
  /** 插件数据 */
  plugin: IListDataItem = {
    title: window.i18n.tc('支持插件'),
    list: [],
  };
  /** 环境数据 */
  system = {
    title: window.i18n.tc('支持环境'),
    children: [
      {
        title: window.i18n.tc('容器环境'),
        list: [],
      },
      {
        title: window.i18n.tc('物理环境'),
        list: [],
      },
    ],
  };
  constructor(systemData) {
    systemData && this.initData(systemData);
  }
  /** 新建应用的环境数据 */
  get addAppSystemData() {
    return [this.plugin, this.lang, this.system];
  }

  /** 筛选被选中的数据 */
  get getCheckedList(): IListDataItem[] {
    return this.handleCheckedList();
  }

  /** 新建服务所需的环境数据 */
  get serviceSystemData() {
    return [this.lang, this.system];
  }

  /** 获取对应插件的的文档 */
  getMdDataFromPluginId(pluginId: string) {
    return this.mdData[pluginId];
  }

  /** 获取当前语言环境的md */
  getMdString(pluginId: string, langIds?: string[], systemIds?: string[]): string {
    const currentMdData = this.getMdDataFromPluginId(pluginId);
    let deploymentIds = systemIds || [];
    let languageIds = langIds || [];
    if (!langIds && !systemIds) {
      const data = this.getSystemIds();
      deploymentIds = data.deploymentIds;
      languageIds = data.languageIds;
    }
    const mdList = [];
    languageIds.forEach(lang => {
      deploymentIds.forEach(system => {
        const srcMd = currentMdData[lang]?.[system];
        const md = srcMd ? `#### ${pluginId} ${lang} ${system}\n\n${srcMd}` : '';
        mdList.push(md);
      });
    });
    return mdList.join('\n');
  }

  /** 处理环境选中值 */
  getSystemIds() {
    /** 获取已经选中的环境配置 */
    const fn = list =>
      list.reduce((total, item) => {
        if (item.list) total.push(...item.list);
        if (item.children) total.push(...fn(item.children));
        return total;
      }, []);
    const list = fn(this.addAppSystemData);
    const checkedList = list.filter(item => item.checked);
    const languageIds = [];
    const deploymentIds = [];
    let pluginId = '';
    checkedList.forEach(item => {
      if (item.checked && item.theme === 'lang') {
        languageIds.push(item.id);
      } else if (item.checked && item.theme === 'system') {
        deploymentIds.push(item.id);
      } else if (item.checked && item.theme === 'plugin') {
        pluginId = item.id;
      }
    });
    return {
      pluginId,
      deploymentIds,
      languageIds,
    };
  }

  /** 处理选中的数据 */
  handleCheckedList(list: IListDataItem[] = this.addAppSystemData) {
    const fn = (list: IListDataItem[]) =>
      list.map(row => {
        if (row.children) {
          return {
            ...row,
            children: fn(row.children),
          };
        }
        row.list = row.list.filter(item => item.checked);

        return row;
      });
    return fn(deepClone(list));
  }

  /** 选中插件 */
  handleCheckedPlugin(id: ICardItem['id']) {
    this.plugin.list.forEach(plugin => {
      if (plugin.id === id) plugin.checked = true;
    });
  }

  /** 批量修改整行卡片的选中状态 */
  handleRowChecked(row: IListDataItem, bool = false) {
    row.list.forEach(item => (item.checked = bool));
    if (row.other) {
      row.other.checked = bool;
      row.other.value = '';
    }
  }

  initData(data) {
    /** 插件列表 */
    this.plugin.list = data.plugins.map((plugin): ICardItem => {
      const { name, author, id, is_official, popularity, icon } = plugin;
      return {
        id,
        title: name,
        img: icon,
        theme: 'plugin',
        descData: {
          name: author,
          isOfficial: is_official,
          heat: popularity,
        },
        checked: false,
        hidden: false,
      };
    });
    /** 语言列表 */
    this.lang.list = data.languages.map((lang): ICardItem => {
      const { id, name, icon } = lang;
      return {
        id,
        title: name || id,
        img: icon || '',
        theme: 'lang',
        checked: false,
        hidden: false,
      };
    });
    /** 容器环境 */
    data.deployments.forEach(item => {
      const { id, name, icon } = item;
      const cardItem: ICardItem = {
        id,
        title: name,
        img: icon || '',
        theme: 'system',
        checked: false,
        hidden: false,
      };
      if (item.category.id === 'container') {
        this.system.children[0].list.push(cardItem);
      }
      if (item.category.id === 'host') {
        this.system.children[1].list.push(cardItem);
      }
    });
    /** 帮助文档 */
    this.mdData = data.help_md;
  }

  /** 校验数据 */
  validate(list?: IListDataItem[]): boolean {
    const localCheckList = this.handleCheckedList(list);
    return localCheckList.every(
      row =>
        !!row.list?.length ||
        (row.other?.checked && !!row.other?.value) ||
        row.children?.some?.(child => !!child.list.length)
    );
  }
}
