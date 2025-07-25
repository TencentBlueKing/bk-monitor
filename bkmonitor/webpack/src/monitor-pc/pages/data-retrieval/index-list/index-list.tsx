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
import { Component, Emit, Prop, Ref } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import EmptyStatus from '../../../components/empty-status/empty-status';

import type { EmptyStatusOperationType, EmptyStatusType } from '../../../components/empty-status/types';

import './index-list.scss';

export interface IIndexListItem {
  children?: IIndexListItem[];
  id: string;
  name: string;
}
interface IEvents {
  onEmptyStatusOperation: EmptyStatusOperationType;
  onSelect: IIndexListItem;
}

interface IProps {
  emptyStatusType?: EmptyStatusType;
  height?: number;
  list: IIndexListItem[];
  tipsPlacement?: string;
  type?: 'list' | 'tree';
}
@Component
export default class IndexList extends tsc<IProps, IEvents> {
  @Ref() indexTree: any;

  @Prop({ type: Array, default: () => [] }) list: IProps['list'];
  @Prop({ type: String, default: 'list' }) type: IProps['type'];
  @Prop({ type: Number }) height: IProps['height'];
  /** 溢出提示的位置 */
  @Prop({ type: String, default: 'right' }) tipsPlacement: string;
  @Prop({ type: String, default: 'empty' }) emptyStatusType: EmptyStatusType;

  selectNodeId = '';

  /**
   * 选中节点
   * @param item
   */
  @Emit('select')
  handleSelectItem(item): IIndexListItem {
    return item;
  }

  /** 搜索过滤节点 */
  handleFilterItem(str) {
    this.indexTree?.filter(str);
    this.selectNodeId = '';
    // 搜索默认选中第一个过滤节点
    if (this.indexTree?.visibleNodes?.length > 1 && str) {
      this.selectNodeId = this.indexTree.visibleNodes[1].id;
    }
    this.indexTree.setSelected(this.selectNodeId, {
      emitEvent: !this.selectNodeId,
    });
  }

  handleSelectNode() {
    const node = this.indexTree?.getNodeById(this.selectNodeId);
    this.handleSelectItem(node);
  }

  @Emit('emptyStatusOperation')
  handleEmptyOperation(type: EmptyStatusOperationType) {
    return type;
  }
  render() {
    const scopedSlots = {
      default: ({ data }: { data: IIndexListItem }) => (
        <span
          class='index-list-item-text'
          v-bk-overflow-tips={{ placement: this.tipsPlacement }}
        >
          {data.name}
        </span>
      ),
    };
    return (
      <bk-big-tree
        ref='indexTree'
        height={this.height}
        class={['index-list-tree-wrap', this.type]}
        data={this.list}
        expand-on-click={false}
        padding={this.type === 'list' ? 10 : 26}
        scopedSlots={scopedSlots}
        default-expand-all
        selectable
        on-select-change={this.handleSelectItem}
      >
        <EmptyStatus
          slot='empty'
          type={this.emptyStatusType}
          onOperation={this.handleEmptyOperation}
        />
      </bk-big-tree>
    );
  }
}
