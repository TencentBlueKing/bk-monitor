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

import { Component, Emit, Prop } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import './relation-select-panel.scss';

interface TreeNode {
  id: string;
  name: string;
  type?: string;
  loading?: string;
  children?: TreeNode[];
}

interface RelationSelectPanelProps {
  data: TreeNode[];
}

@Component
export default class RelationSelectPanel extends tsc<RelationSelectPanelProps> {
  @Prop({ default: () => [] }) data: TreeNode[];

  loadMoreLoading = {};

  isShowCheckbox(data) {
    if (data.type === 'more') return false;
    return true;
  }

  @Emit('showMore')
  handleShowMore(id: string) {
    return id;
  }

  renderLoadMore(item) {
    return (
      <div class='show-more'>
        <bk-spin
          style={{ display: item.loading ? 'inline-block' : 'none' }}
          size='mini'
        />
        <div
          style={{ display: !item.loading ? 'flex' : 'none' }}
          class='content'
          onClick={() => this.handleShowMore(item.id)}
        >
          <span class='dot' />
          <span class='dot' />
          <span class='dot' />
          <span class='text'>{this.$t('点击加载更多')}</span>
        </div>
      </div>
    );
  }

  render() {
    return (
      <div class='relation-select-panel-comp'>
        <div class='tree-panel'>
          <bk-input />
          <bk-big-tree
            class='relation-workload-tree'
            scopedSlots={{
              default: ({ data }) => {
                console.log(data);
                if (data.type === 'more') return this.renderLoadMore(data);
                return (
                  <div class={['bk-tree-node']}>
                    <span
                      style='padding-right: 5px;'
                      class='node-content'
                    >
                      <span class='item-name'>{data.name}</span>
                    </span>
                  </div>
                );
              },
            }}
            data={this.data}
            selectable={true}
            show-checkbox={this.isShowCheckbox}
          />
        </div>
        <div class='selected-panel' />
      </div>
    );
  }
}
