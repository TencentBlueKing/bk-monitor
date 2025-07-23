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

export interface ITreeMenuItem {
  id: number;
  title: string;
  icon?: string;
  expend?: boolean;
  level?: number;
  uid: string;
  hasPermission?: boolean;
  isFolder?: boolean;
  isStarred?: boolean;
  editable?: boolean;
  url?: string;
  children?: ITreeMenuItem[];
}
export interface ITreeOptions {
  level?: number;
  expendIcon?: string;
  closeIcon?: string;
}
/**
 * 树形列表数据项抽象类
 */
export class TreeMenuItem {
  addActive = false; /** id */
  children: TreeMenuItem[] = []; /** 名称 */
  edit = false; /** 子项列表 */
  editable = true; /** 传入的icon */
  editValue = ''; /** 是否展开 */
  expend = false; /** 当前项的级别 */
  hasPermission = false; /** 是否有权限 */
  icon = ''; /** 配置 */
  id: number = null; /** 新增按钮处于激活状态 */
  isFolder = false; /** 更多按钮处于激活状态 */
  isStarred = false; /** 编辑状态 */
  level = 0; /** 重命名 */
  moreActive = false; /** 仪表盘、目录的id */
  options: ITreeOptions = {};
  title = '';
  uid = '';
  constructor(data: ITreeMenuItem, options?: ITreeOptions) {
    const { children = [] } = data;
    for (const [key, value] of Object.entries(data)) {
      if (key === 'editable') {
        this.editable = value ?? true;
      } else this[key] = value;
    }
    this.editValue = this.title;
    this.options = options;
    const { level = 0 } = options || {};
    this.level = level;
    this.children = children.map(child => new TreeMenuItem(child, { ...options, level: this.level + 1 }));
  }
  /** 当前展示的icon */
  get curIcon() {
    if (this.icon) {
      return this.icon;
    }
    if (this.isFolder) {
      return this.expend ? this.options.expendIcon : this.options.closeIcon;
    }
    return null;
  }

  /** 是否仪表盘 */
  get isDashboard() {
    return !this.isFolder;
  }

  /** 是否为通用目录 (id = 0 并且uid = '') */
  get isGeneralFolder() {
    return this.id === 0 && !this.uid;
  }

  /** 是否为分组 */
  get isGroup() {
    return this.isFolder;
  }
}
