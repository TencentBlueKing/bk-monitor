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
import { Component, Emit, Prop, Watch } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import TreeList, { type IMoreData } from './tree-list';
import { type ITreeMenuItem, TreeMenuItem } from './utils';

interface IProps {
  data: ITreeMenuItem[];
  defaultExpend?: boolean;
  expendIcon?: string;
  closeIcon?: string;
  checked?: string;
}
interface IEvents {
  onSelected: TreeMenuItem;
  onMore: IMoreData;
  onRename: TreeMenuItem;
}

@Component
export default class TreeMenu extends tsc<IProps, IEvents> {
  @Prop({ type: Array, default: () => [] }) data: ITreeMenuItem[];
  /** 是否默认打开分组 */
  @Prop({ type: Boolean, default: false }) defaultExpend: boolean;
  /** 展开icon */
  @Prop({ type: String, default: 'icon-mc-open-folder' }) expendIcon: string;
  /** 收起icon */
  @Prop({ type: String, default: 'icon-mc-full-folder' }) closeIcon: string;
  /** 选中 */
  @Prop({ type: String, default: '' }) checked: string;

  localData: TreeMenuItem[] = [];
  /** 当前选中项 */
  localChecked: string = null;
  initialized = false;

  @Watch('checked', { immediate: true })
  checkedChange(val: string) {
    this.localChecked = val;
    this.localData.some(item => {
      if (item.children?.some(set => set.uid === val)) {
        item.expend = true;
        setTimeout(() => {
          document.getElementById(val)?.scrollIntoView({ block: 'center' });
        }, 320);
        return true;
      }
      return false;
    });
  }

  @Watch('data', { immediate: true })
  handleDataChange(data: ITreeMenuItem[]) {
    if (data) {
      this.initialized = true;
      this.localData = this.handleTreeData(data);
      this.checkedChange(this.checked);
    }
  }

  /** 生成列表渲染所需的数据 */
  handleTreeData(data: ITreeMenuItem[], level = 0): TreeMenuItem[] {
    return data.map(item => {
      const newItem = new TreeMenuItem(
        {
          ...item,
          expend: !this.initialized
            ? this.defaultExpend
            : (this.localData?.find(set => set.id === item.id)?.expend ?? false),
          level,
        },
        {
          expendIcon: this.expendIcon,
          closeIcon: this.closeIcon,
        }
      );
      return newItem;
    });
  }

  @Emit('selected')
  handleSelectedItem(item: TreeMenuItem) {
    this.localChecked = item.uid;
    return item;
  }
  @Emit('more')
  handleMore(data: IMoreData) {
    return data;
  }
  @Emit('rename')
  handleRename(item: TreeMenuItem) {
    return item;
  }
  render() {
    return (
      <TreeList
        checked={this.localChecked}
        list={this.localData}
        onMore={this.handleMore}
        onRename={this.handleRename}
        onSelected={this.handleSelectedItem}
      />
    );
  }
}
