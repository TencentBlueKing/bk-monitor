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
import { type PropType, computed, defineComponent, nextTick, toRef, useTemplateRef, watch } from 'vue';

import { Checkbox } from 'bkui-vue';
import { storeToRefs } from 'pinia';
import { useI18n } from 'vue-i18n';

import BackTop from '../../../../components/back-top/back-top';
import { useTraceExploreStore } from '../../../../store/modules/explore';
import ChartWrapper from '../explore-chart/chart-wrapper';
import { useExploreTableData } from '../trace-explore-table/hooks/use-explore-table-data';
import { useExploreTableDisplayField } from '../trace-explore-table/hooks/use-explore-table-display-field';
import TraceExploreTable from '../trace-explore-table/trace-explore-table';
import { ExploreTableLoadingEnum } from '../trace-explore-table/typing';

import type { ConditionChangeEvent, ExploreFieldList, ICommonParams } from '../../typing';

import './trace-explore-view.scss';

/** 快速过滤项(包含) */
const TableCheckBoxFiltersEnum = {
  EntrySpan: 'entry_span',
  Error: 'error',
  RootSpan: 'root_span',
} as const;

export default defineComponent({
  name: 'TraceExploreView',
  props: {
    commonParams: {
      type: Object as PropType<ICommonParams>,
      default: () => ({}),
    },
    checkboxFilters: {
      type: Array as PropType<string[]>,
      default: () => [],
    },
    /** 不同视角下维度字段的列表 */
    fieldListMap: {
      type: Object as PropType<ExploreFieldList>,
      default: () => ({
        trace: [],
        span: [],
      }),
    },
    /** 是否展示详情 */
    showSlideDetail: {
      type: Object as PropType<{ id: string; type: 'span' | 'trace' }>,
      default: null,
    },
  },
  emits: {
    /** table上方快捷筛选操作区域（ "包含" 区域中的 复选框组）值改变后触发的回调 */
    checkboxFiltersChange: (checkboxGroupEvent: string[]) => Array.isArray(checkboxGroupEvent),
    /** 筛选条件改变后触发的回调 */
    conditionChange: (conditionEvent: ConditionChangeEvent) => conditionEvent,
    /** 清除检索过滤 */
    clearRetrievalFilter: () => true,
    /** 设置url参数 */
    setUrlParams: () => true,
  },
  setup(props, { emit }) {
    const { t } = useI18n();
    const store = useTraceExploreStore();
    const backTopRef = useTemplateRef<InstanceType<typeof BackTop>>('backTopRef');
    const traceExploreTableRef = useTemplateRef<InstanceType<typeof TraceExploreTable>>('traceExploreTable');

    const { mode, appName } = storeToRefs(store);
    const {
      displayColumnFields,
      fieldsWidthConfig,
      getCustomFieldsConfig,
      handleDisplayColumnFieldsChange,
      handleDisplayColumnResize,
    } = useExploreTableDisplayField({ mode, appName });

    /** 当前视角下的字段配置 */
    const sourceFieldConfigs = computed(() => props.fieldListMap?.[mode.value] ?? []);

    // 使用数据处理 hook
    const { tableViewData, tableHasScrollLoading, tableLoading, sortContainer, getExploreList, handleSortChange } =
      useExploreTableData({
        commonParams: toRef(props, 'commonParams'),
        sourceFieldConfigs,
        onBackTop: () => {
          backTopRef.value?.handleBackTop?.(false);
        },
      });

    /**
     * @description 触底加载更多
     */
    const handleScrollToEnd = () => {
      getExploreList(ExploreTableLoadingEnum.SCROLL);
    };

    /**
     * @description 排序变化处理
     */
    const handleTableSortChange = sortEvent => {
      handleSortChange(sortEvent);
      emit('setUrlParams');
    };

    /**
     * @description table上方快捷筛选操作区域（ "包含" 区域中的 复选框组） 渲染方法
     *
     */
    const filtersCheckBoxGroupRender = () => {
      return (
        <Checkbox.Group
          model-value={props.checkboxFilters}
          onChange={checkedGroup => emit('checkboxFiltersChange', checkedGroup)}
        >
          {mode.value === 'span'
            ? [
                <Checkbox
                  key={TableCheckBoxFiltersEnum.RootSpan}
                  v-bk-tooltips={{
                    content: t('整个 Trace 的第一个 Span'),
                    placement: 'top',
                    theme: 'light',
                  }}
                  label={TableCheckBoxFiltersEnum.RootSpan}
                >
                  {t('根 Span')}
                </Checkbox>,
                <Checkbox
                  key={TableCheckBoxFiltersEnum.EntrySpan}
                  v-bk-tooltips={{
                    content: t('每个 Service 的第一个 Span'),
                    placement: 'top',
                    theme: 'light',
                  }}
                  label={TableCheckBoxFiltersEnum.EntrySpan}
                >
                  {t('入口 Span')}
                </Checkbox>,
              ]
            : null}
          <Checkbox label={TableCheckBoxFiltersEnum.Error}>{t('错误')}</Checkbox>
        </Checkbox.Group>
      );
    };

    watch(
      () => props.showSlideDetail,
      val => {
        if (!val) return;
        nextTick(() => {
          traceExploreTableRef.value?.handleSliderShowChange(val.type, val.id);
        });
      },
      {
        immediate: true,
      }
    );

    return {
      mode,
      appName,
      displayColumnFields,
      fieldsWidthConfig,
      sourceFieldConfigs,
      tableViewData,
      tableHasScrollLoading,
      tableLoading,
      sortContainer,
      getCustomFieldsConfig,
      handleDisplayColumnFieldsChange,
      handleDisplayColumnResize,
      handleScrollToEnd,
      handleTableSortChange,
      filtersCheckBoxGroupRender,
      t,
    };
  },
  render() {
    return (
      <div class='trace-explore-view'>
        <div class='trace-explore-view-chart'>
          <ChartWrapper collapseTitle={window.i18n.t('总览')} />
        </div>
        <div class='trace-explore-view-filter'>
          <span class='filter-label'>{this.t('包含')}：</span>
          {this.filtersCheckBoxGroupRender()}
        </div>
        <div class='trace-explore-view-table'>
          <TraceExploreTable
            ref='traceExploreTable'
            appName={this.appName}
            commonParams={this.commonParams}
            displayFields={this.displayColumnFields}
            fieldsWidthConfig={this.fieldsWidthConfig}
            mode={this.mode}
            sortContainer={this.sortContainer}
            sourceFieldConfigs={this.sourceFieldConfigs}
            tableData={this.tableViewData}
            tableHasScrollLoading={this.tableHasScrollLoading}
            tableLoading={this.tableLoading}
            onClearRetrievalFilter={() => this.$emit('clearRetrievalFilter')}
            onColumnResize={this.handleDisplayColumnResize}
            onConditionChange={conditionEvent => this.$emit('conditionChange', conditionEvent)}
            onDisplayFieldChange={this.handleDisplayColumnFieldsChange}
            onScrollToEnd={this.handleScrollToEnd}
            onSortChange={this.handleTableSortChange}
          />
        </div>
        <BackTop
          ref='backTopRef'
          class='back-to-top'
          scrollTop={100}
        >
          <i class='icon-monitor icon-BackToTop' />
        </BackTop>
      </div>
    );
  },
});
