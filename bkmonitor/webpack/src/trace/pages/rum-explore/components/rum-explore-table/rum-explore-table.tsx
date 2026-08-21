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
import { type PropType, computed, defineComponent, onBeforeUnmount, onMounted, shallowRef } from 'vue';

import { PrimaryTable } from '@blueking/tdesign-ui';
import { Exception, Loading } from 'bkui-vue';
import { useI18n } from 'vue-i18n';

import ExploreFieldSetting from '../../../trace-explore/components/explore-field-setting/explore-field-setting';
import StatisticsList from '../../../trace-explore/components/statistics-list';
import { useFieldStatisticsPopover } from '../../composables/use-field-statistics-popover';
import { statisticsApi } from '../../services/rum-search';
import { useRumTableColumns } from './use-rum-table-columns';

import type { IDimensionFieldTreeItem } from '../../../trace-explore/typing';
import type { IRumCommonParams, IRumField, IRumSortInfo, IRumSpanRecord } from '../../typings';

import './rum-explore-table.scss';

export default defineComponent({
  name: 'RumExploreTable',
  props: {
    data: {
      type: Array as PropType<IRumSpanRecord[]>,
      default: () => [],
    },
    /** 当前展示的列 */
    displayFields: {
      type: Array as PropType<string[]>,
      default: () => [],
    },
    /** 可作为列的字段全集，供字段设置使用 */
    displayableFields: {
      type: Array as PropType<IRumField[]>,
      default: () => [],
    },
    loading: {
      type: Boolean,
      default: false,
    },
    /** 触底加载中 */
    scrollLoading: {
      type: Boolean,
      default: false,
    },
    sort: {
      type: Object as PropType<IRumSortInfo>,
      default: () => ({ sortBy: '', descending: null }),
    },
    /** 统计分析的查询上下文 */
    commonParams: {
      type: Object as PropType<IRumCommonParams>,
      default: () => ({}),
    },
    timeRange: {
      type: Array as PropType<string[]>,
      default: () => [],
    },
  },
  emits: {
    conditionChange: (_condition: { key: string; method: string; value: string }) => true,
    displayFieldChange: (_fields: string[]) => true,
    sortChange: (_sort: IRumSortInfo) => true,
    scrollToEnd: () => true,
    clearFilter: () => true,
  },
  setup(props, { emit }) {
    const { t } = useI18n();
    const tableWrapRef = shallowRef<HTMLElement>(null);

    const { activeFieldName, selectField, showPopover, statisticsListRef, destroyPopover, openPopover } =
      useFieldStatisticsPopover('bottom');

    const fieldMap = computed(() => new Map(props.displayableFields.map(field => [field.name, field])));

    const { columns } = useRumTableColumns({
      displayFields: computed(() => props.displayFields),
      fieldMap,
      onCellFilter: (field, value) => emit('conditionChange', { key: field.name, method: 'equal', value }),
      onFieldAnalysis: (trigger, field) => openPopover(trigger, field as unknown as IDimensionFieldTreeItem),
    });

    /** 最右侧固定的字段设置齿轮列 */
    const settingColumn = computed(() => ({
      colKey: '__col_setting__',
      width: 32,
      minWidth: 32,
      fixed: 'right' as const,
      align: 'center' as const,
      resizable: false,
      thClassName: '__table-custom-setting-col__',
      title: () => (
        <ExploreFieldSetting
          class='table-field-setting'
          sourceList={props.displayableFields}
          targetList={props.displayFields}
          onConfirm={fields => emit('displayFieldChange', fields)}
        />
      ),
      cell: () => undefined,
    }));

    function handleScroll(event: Event) {
      const target = event.target as HTMLElement;
      if (target.scrollHeight - target.scrollTop - target.clientHeight > 40) return;
      emit('scrollToEnd');
    }

    let scrollContainer: HTMLElement | null = null;

    onMounted(() => {
      scrollContainer = tableWrapRef.value?.querySelector('.t-table__content');
      scrollContainer?.addEventListener('scroll', handleScroll);
    });

    onBeforeUnmount(() => {
      scrollContainer?.removeEventListener('scroll', handleScroll);
      destroyPopover();
    });

    return {
      t,
      activeFieldName,
      columns,
      selectField,
      settingColumn,
      showPopover,
      statisticsApi,
      statisticsListRef,
      tableWrapRef,
      destroyPopover,
      handleSortChange: (sort: IRumSortInfo) => emit('sortChange', sort),
      handleConditionChange: (condition: { key: string; method: string; value: string }) =>
        emit('conditionChange', condition),
    };
  },
  render() {
    return (
      <div
        ref='tableWrapRef'
        class='rum-explore-table'
      >
        <PrimaryTable
          v-slots={{
            empty: () => (
              <Exception
                description={this.t('搜索结果为空')}
                scene='part'
                type='search-empty'
              >
                <span
                  class='clear-filter-btn'
                  onClick={() => this.$emit('clearFilter')}
                >
                  {this.t('清空检索条件')}
                </span>
              </Exception>
            ),
          }}
          lastFullRow={
            this.data.length
              ? () => (
                  <Loading
                    style={{ display: this.scrollLoading ? 'inline-flex' : 'none' }}
                    class='scroll-end-loading'
                    loading={true}
                    mode='spin'
                    size='mini'
                    theme='primary'
                    title={this.t('加载中...')}
                  />
                )
              : undefined
          }
          activeRowType='single'
          // @ts-expect-error 列配置中的 cell/title 渲染函数与 tdesign 的类型声明不完全匹配
          columns={[...this.columns, this.settingColumn]}
          data={this.data}
          hover={true}
          loading={this.loading}
          needCustomScroll={false}
          resizable={true}
          rowKey='span_id'
          showSortColumnBgColor={true}
          size='small'
          sort={this.sort}
          stripe={false}
          tableLayout='fixed'
          onSortChange={this.handleSortChange}
        />

        <StatisticsList
          ref='statisticsListRef'
          api={this.statisticsApi}
          commonParams={this.commonParams as any}
          fieldType={this.selectField?.type}
          isShow={this.showPopover}
          selectField={this.selectField?.name}
          timeRange={this.timeRange as any}
          onConditionChange={this.handleConditionChange}
          onShowMore={this.destroyPopover}
        />
      </div>
    );
  },
});
