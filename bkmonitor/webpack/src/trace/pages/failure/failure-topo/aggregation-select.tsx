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
import { defineComponent, ref } from 'vue';

import { Input, Popover, Switcher, Tree } from 'bkui-vue';
import { Search } from 'bkui-vue/lib/icon';
import { useI18n } from 'vue-i18n';

import Collapse from '../components/collapse';

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
  emits: ['update:autoAggregate', 'update:checkedIds', 'update:aggregateCluster'],
  setup(props, { emit }) {
    const { t } = useI18n();
    /** 支持搜索, 当前声明2个原因为 当前版本输入框组件不绑定值不支持清除配置，所以需要一个值来缓存搜索值
     *  而搜索的触发方式需要按回车才能搜索，所以需要分开，后续更新版本后修改为一个即可
     */
    const searchValue = ref('');
    const treeSearchValue = ref('');
    const aggregateCluster = ref(true);
    const handleChange = () => {
      emit('update:aggregateCluster', aggregateCluster.value);
    };
    /** 聚合规则选择 */
    const handleNodeCheck = checkedData => {
      emit(
        'update:checkedIds',
        checkedData.map(item => item.id)
      );
    };

    return {
      handleChange,
      aggregateCluster,
      treeSearchValue,
      searchValue,
      handleNodeCheck,
      t,
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
                <i class='icon-monitor icon-shezhi1 trigger-icon' />
                {this.t('聚合规则')}
              </div>
            ),
            content: () => (
              <div class='aggregation-select-content-wrap'>
                <Collapse title={this.t('按调用关系聚合')}>
                  <div class='aggregation-select-switcher'>
                    <Switcher
                      v-model={this.aggregateCluster}
                      v-bk-tooltips={{
                        content: this.t('如果同时开启了 按从属关系聚合，将先进行从属边的聚合，再进行调用边的聚合'),
                      }}
                      theme='primary'
                      onChange={this.handleChange}
                    />
                  </div>
                </Collapse>
                <Collapse title={this.t('按从属关系聚合')}>
                  <div class='aggregation-select-content'>
                    <div class='panel-header'>
                      <div
                        class={{
                          'panel-btn': true,
                          'is-active': this.autoAggregate,
                        }}
                        onClick={() => this.$emit('update:autoAggregate', true)}
                      >
                        {this.t('自动聚合')}
                      </div>
                      <div
                        class={{
                          'panel-btn': true,
                          'is-active': !this.autoAggregate && !this.checkedIds.length,
                        }}
                        onClick={() => this.$emit('update:autoAggregate', false)}
                      >
                        {this.t('不聚合')}
                      </div>
                    </div>
                    <div class='panel-search'>
                      <Input
                        v-model={this.searchValue}
                        v-slots={{
                          prefix: () => <Search class='input-icon' />,
                        }}
                        behavior='simplicity'
                        placeholder={this.t('请输入关键字')}
                        clearable
                        onClear={() => (this.treeSearchValue = '')}
                        onEnter={value => (this.treeSearchValue = value)}
                      />
                    </div>
                    <Tree
                      search={{
                        value: this.treeSearchValue,
                        match: 'fuzzy',
                        resultType: 'tree',
                        showChildNodes: false,
                      }}
                      checked={this.checkedIds}
                      // biome-ignore lint/correctness/noChildrenProp: <explanation>
                      children={'children'}
                      data={this.treeData}
                      empty-text={this.t('没有数据')}
                      expandAll={true}
                      indent={36}
                      label='name'
                      levelLine={false}
                      nodeKey='id'
                      showCheckbox={true}
                      showNodeTypeIcon={false}
                      onNodeChecked={this.handleNodeCheck}
                    />
                  </div>
                </Collapse>
              </div>
            ),
          }}
          arrow={false}
          renderType='shown'
          trigger='click'
        />
      </div>
    );
  },
});
