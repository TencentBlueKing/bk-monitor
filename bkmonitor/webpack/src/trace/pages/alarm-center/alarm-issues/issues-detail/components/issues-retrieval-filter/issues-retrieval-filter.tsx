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
import { type PropType, computed, defineComponent, shallowRef } from 'vue';

import { handleTransformToTimestamp } from 'trace/components/time-range/utils';

import RetrievalFilter from '../../../../../../components/retrieval-filter/retrieval-filter';
import { type IFilterField, EMode } from '../../../../../../components/retrieval-filter/typing';
import { useAlarmFilter } from '../../../../components/alarm-retrieval-filter/hooks/use-alarm-filter';
import { AlarmServiceFactory } from '../../../../services/factory';
import { type CommonCondition, AlarmType } from '../../../../typings';

import './issues-retrieval-filter.scss';

export default defineComponent({
  name: 'IssuesRetrievalFilter',
  props: {
    /* 时间范围 */
    timeRange: {
      type: Array as PropType<(number | string)[]>,
      default: () => [],
    },
    /* ui模式条件值 */
    conditions: {
      type: Array as PropType<CommonCondition[]>,
      default: () => [],
    },
    /* 语句模式语句 */
    queryString: {
      type: String,
      default: '',
    },
    /* 查询模式 */
    filterMode: {
      type: String as PropType<EMode>,
      default: EMode.ui,
    },
    /* 业务ID列表 */
    bizIds: {
      type: Array as PropType<number[]>,
      default: () => [],
    },
    /** Issue ID */
    issueId: {
      type: String,
      default: '',
    },
  },
  emits: {
    conditionChange: (_v: CommonCondition[]) => true,
    queryStringChange: (_v: string) => true,
    filterModeChange: (_v: EMode) => true,
    search: () => true,
  },
  setup(props, { emit }) {
    // 告警服务实例
    const alarmService = shallowRef(AlarmServiceFactory(AlarmType.ALERT));

    // 内部定义 fields - 使用 AlertService 的 filterFields
    const fields = computed<IFilterField[]>(() => {
      return [...alarmService.value.filterFields];
    });

    // 内部定义 getValueFn - 使用 useAlarmFilter hook
    const { getRetrievalFilterValueData } = useAlarmFilter(() => {
      const [start, end] = handleTransformToTimestamp(props.timeRange);
      return {
        alarmType: AlarmType.ALERT,
        commonFilterParams: {
          bk_biz_ids: window.APM_QUERY_STRING ? [window.bk_biz_id] : props.bizIds,
          start_time: start,
          end_time: end,
          conditions: props.conditions,
        },
        filterMode: props.filterMode,
        preConditions: [{ key: 'issue_id', value: [props.issueId], method: 'eq' }],
      };
    });

    function handleConditionChange(val: CommonCondition[]) {
      emit('conditionChange', val);
    }

    function handleQueryStringChange(val: string) {
      emit('queryStringChange', val);
    }

    function handleFilterModeChange(val: EMode) {
      emit('filterModeChange', val);
    }

    function handleSearch() {
      emit('search');
    }

    return {
      fields,
      getRetrievalFilterValueData,
      handleConditionChange,
      handleQueryStringChange,
      handleFilterModeChange,
      handleSearch,
    };
  },
  render() {
    return (
      <RetrievalFilter
        class='issues-retrieval-filter'
        changeWhereFormatter={where => {
          return where.map(w => ({
            key: w.key,
            method: w.method,
            value: w.value,
            condition: w.condition,
          }));
        }}
        fields={this.fields}
        filterMode={this.filterMode}
        getValueFn={this.getRetrievalFilterValueData}
        isShowClear={true}
        isShowCopy={false}
        isShowFavorite={false}
        isShowResident={false}
        loadDelay={0}
        queryString={this.queryString}
        where={this.conditions}
        zIndex={9999}
        onModeChange={this.handleFilterModeChange}
        onQueryStringChange={this.handleQueryStringChange}
        onSearch={this.handleSearch}
        onWhereChange={this.handleConditionChange}
      />
    );
  },
});
