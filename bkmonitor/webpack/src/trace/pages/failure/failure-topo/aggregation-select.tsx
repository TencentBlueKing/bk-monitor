/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 *
 * Copyright (C) 2017-2025 Tencent.  All rights reserved.
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
import { type PropType, computed, defineComponent, ref, watch } from 'vue';

import { Input, Popover, Switcher, Tree } from 'bkui-vue';
import { Search } from 'bkui-vue/lib/icon';
import { useI18n } from 'vue-i18n';

import ExceptionComp from '../../../components/exception';

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
    isAutoAggregate: {
      type: Boolean,
      default: true,
    },
    /** 菜单接口返回的动态聚合开关列表 */
    aggregateSwitches: {
      type: Array as PropType<{ [k: string]: any; default: boolean; key: string; name: string }[]>,
      default: () => [],
    },
  },
  emits: [
    'update:isAutoAggregate',
    'update:checkedIds',
    'update:aggregateCluster',
    'update:aggregateVersion',
    'update:aggregateCall',
    'reset:checkedIds',
  ],
  setup(props, { emit }) {
    const { t } = useI18n();
    const isMac = /Macintosh|Mac/.test(navigator.userAgent);
    /** 支持搜索, 当前声明2个原因为 当前版本输入框组件不绑定值不支持清除配置，所以需要一个值来缓存搜索值
     *  而搜索的触发方式需要按回车才能搜索，所以需要分开，后续更新版本后修改为一个即可
     */
    const searchValue = ref('');
    const treeSearchValue = ref('');
    // 从属关系聚合
    const aggregateCluster = ref(false);
    // 部署版本聚合
    const aggregateVersion = ref(false);
    // 调用关系聚合
    const aggregateCall = ref(true);

    const handleRelationChange = () => {
      emit('update:aggregateCluster', aggregateCluster.value);
    };
    const handleVersionChange = () => {
      emit('update:aggregateVersion', aggregateVersion.value);
    };
    const handleCallChange = () => {
      emit('update:aggregateCall', aggregateCall.value);
    };

    /** 菜单接口是否返回了 aggregate_version 开关 */
    const showVersionSwitch = computed(() => props.aggregateSwitches?.some(sw => sw.key === 'aggregate_version'));

    /** 当菜单接口返回 aggregate_switches 后，用 default 值初始化版本聚合开关状态 */
    watch(
      () => props.aggregateSwitches,
      switches => {
        const versionSwitch = switches?.find(sw => sw.key === 'aggregate_version');
        aggregateVersion.value = versionSwitch?.default ?? false;
      },
      { immediate: true }
    );

    /** 重置到默认选中状态 */
    const handleReset = () => {
      emit('reset:checkedIds');
      searchValue.value = '';
      treeSearchValue.value = '';
    };

    /** 聚合规则选择 */
    const handleNodeCheck = checkedData => {
      emit(
        'update:checkedIds',
        checkedData.map(item => item.id)
      );
    };

    return {
      isMac,
      aggregateCluster,
      aggregateVersion,
      aggregateCall,
      showVersionSwitch,
      handleRelationChange,
      handleVersionChange,
      handleCallChange,
      handleReset,
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
              <div class={{ 'aggregation-select-content-wrap': true, 'non-mac': !this.isMac }}>
                <div class='panel-header'>
                  <div
                    class={{
                      'panel-btn': true,
                      'is-active': this.isAutoAggregate,
                    }}
                    onClick={() => this.$emit('update:isAutoAggregate', true)}
                  >
                    {this.t('自动聚合')}
                  </div>
                  <div
                    class={{
                      'panel-btn': true,
                      'is-active': !this.isAutoAggregate,
                    }}
                    onClick={() => this.$emit('update:isAutoAggregate', false)}
                  >
                    {this.t('手动聚合')}
                  </div>
                </div>

                {!this.isAutoAggregate && (
                  <>
                    <div class='info-tips'>
                      <i class='icon-monitor icon-tips' />
                      <span>{this.t('如果同时开启多聚合规则，将按顺序执行')}</span>
                    </div>

                    <div class='switcher-list'>
                      <div class='switcher-item'>
                        <div class='switcher-item-header'>
                          <div class='switcher-label'>
                            <span class='label-num'>{'\u2460'}</span>
                            {this.t('按 <从属关系> 聚合')}
                          </div>
                          <div class='switcher-action'>
                            {this.aggregateCluster && (
                              <span
                                class='reset-btn'
                                onClick={this.handleReset}
                              >
                                {this.t('重置')}
                              </span>
                            )}
                            <Switcher
                              v-model={this.aggregateCluster}
                              size='small'
                              theme='primary'
                              onChange={this.handleRelationChange}
                            />
                          </div>
                        </div>

                        {this.aggregateCluster && (
                          <div class='switcher-item-content'>
                            <div class='content-search'>
                              <Input
                                v-model={this.searchValue}
                                v-slots={{
                                  suffix: () => <Search class='search-icon' />,
                                }}
                                behavior='simplicity'
                                placeholder={this.t('搜索')}
                                size='small'
                                clearable
                                onClear={() => (this.treeSearchValue = '')}
                                onEnter={value => (this.treeSearchValue = value)}
                              />
                            </div>
                            <div class='content-tree'>
                              {this.treeData.length > 0 ? (
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
                                  expandAll={true}
                                  indent={36}
                                  label='name'
                                  levelLine={false}
                                  nodeKey='id'
                                  showCheckbox={true}
                                  showNodeTypeIcon={false}
                                  onNodeChecked={this.handleNodeCheck}
                                />
                              ) : (
                                <ExceptionComp
                                  class='tree-empty'
                                  imgHeight={'auto'}
                                  isDarkTheme={true}
                                  isError={false}
                                  title={this.t('暂无可聚合节点')}
                                />
                              )}
                            </div>
                          </div>
                        )}
                      </div>

                      {this.showVersionSwitch && (
                        <div class='switcher-item'>
                          <div class='switcher-item-header'>
                            <div class='switcher-label'>
                              <span class='label-num'>{'\u2461'}</span>
                              {this.t('按 <部署版本> 聚合')}
                            </div>
                            <Switcher
                              v-model={this.aggregateVersion}
                              size='small'
                              theme='primary'
                              onChange={this.handleVersionChange}
                            />
                          </div>
                        </div>
                      )}

                      <div class='switcher-item'>
                        <div class='switcher-item-header'>
                          <div class='switcher-label'>
                            <span class='label-num'>{this.showVersionSwitch ? '\u2462' : '\u2461'}</span>
                            {this.t('按 <调用关系> 聚合')}
                          </div>
                          <Switcher
                            v-model={this.aggregateCall}
                            size='small'
                            theme='primary'
                            onChange={this.handleCallChange}
                          />
                        </div>
                      </div>
                    </div>
                  </>
                )}
              </div>
            ),
          }}
          arrow={false}
          placement='bottom-start'
          renderType='shown'
          trigger='click'
        />
      </div>
    );
  },
});
