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
import { defineComponent } from 'vue';

import { Input, Popover, Tree } from 'bkui-vue';
import { Search } from 'bkui-vue/lib/icon';

import './aggregation-select.scss';

export default defineComponent({
  name: 'AggregationSelect',
  props: {
    checkedIds: {
      type: Array,
      required: true,
    },
    treeData: {
      type: Array,
      required: true,
    },
    autoAggregate: {
      type: Boolean,
      default: true,
    },
    aggregateConfig: {
      type: Object,
      default: undefined,
    },
  },
  emits: ['update:autoAggregate', 'update:checkedIds'],
  setup(props, { emit }) {
    /** 聚合规则选择 */
    const handleNodeCheck = checkedData => {
      emit(
        'update:checkedIds',
        checkedData.filter(item => !item.children).map(item => item.id)
      );
    };
    return {
      handleNodeCheck,
    };
  },
  render() {
    return (
      <div class='aggregation-select'>
        <Popover
          extCls='aggregation-select-popover'
          v-slots={{
            default: () => (
              <div class='aggregation-select-trigger'>
                <i class='icon-monitor icon-menu-set trigger-icon'></i>
                {this.$t('聚合规则')}
              </div>
            ),
            content: () => (
              <div class='aggregation-select-content'>
                <div class='panel-header'>
                  <div
                    class={{
                      'panel-btn': true,
                      'is-active': this.autoAggregate,
                    }}
                    onClick={() => this.$emit('update:autoAggregate', true)}
                  >
                    {this.$t('自动聚合')}
                  </div>
                  <div
                    class={{
                      'panel-btn': true,
                      'is-active': !this.autoAggregate && !this.checkedIds.length,
                    }}
                    onClick={() => this.$emit('update:autoAggregate', false)}
                  >
                    {this.$t('不聚合')}
                  </div>
                </div>
                <div class='panel-search'>
                  <Input
                    v-slots={{
                      prefix: () => <Search class='input-icon' />,
                    }}
                    behavior='simplicity'
                    placeholder={this.$t('请输入关键字')}
                  ></Input>
                </div>
                <Tree
                  checked={this.checkedIds}
                  children={'children'}
                  data={this.treeData}
                  expandAll={true}
                  indent={36}
                  label='name'
                  levelLine={false}
                  nodeKey='id'
                  showCheckbox={true}
                  showNodeTypeIcon={false}
                  onNodeChecked={this.handleNodeCheck}
                ></Tree>
              </div>
            ),
          }}
          arrow={false}
          renderType='shown'
          trigger='click'
        ></Popover>
      </div>
    );
  },
});
