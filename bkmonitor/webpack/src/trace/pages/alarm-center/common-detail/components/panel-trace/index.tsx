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
import { type PropType, computed, defineComponent, onMounted, shallowRef, toRef, watch } from 'vue';

import deepmerge from 'deepmerge';
import { Button } from 'bkui-vue';
import { listApplicationInfo } from 'monitor-api/modules/apm_meta';
import { listTraceViewConfig } from 'monitor-api/modules/apm_trace';
import { useI18n } from 'vue-i18n';

import RetrievalFilter from '../../../../../components/retrieval-filter/retrieval-filter';
import { EFieldType, EMode } from '../../../../../components/retrieval-filter/typing';
import { traceWhereChangeFormatter, traceWhereFormatter } from '../../../../../components/retrieval-filter/utils';
import TraceExploreTable from '../../../../trace-explore/components/trace-explore-table/trace-explore-table';
import { useCandidateValue } from '../../../../trace-explore/hooks/use-candidate-value';
import { useAlertTraces } from '../../../composables/use-alert-traces';
import { useDiagnosticNavigate } from '../../../composables/use-diagnostic-navigate';
import PanelSourceSelector from '../panel-source-selector/panel-source-selector';
import {
  ALERT_TRACE_DURATION_KEYS,
  ALERT_TRACE_FIELD_CONFIGS,
  ALERT_TRACE_INPUT_TAG_KEYS,
  ALERT_TRACE_NOT_SUPPORT_ENUM_KEYS,
} from './constants';
import { ALARM_CENTER_PANEL_TAB_MAP } from '../../../utils/constant';
import { useAlarmCenterDetailStore } from '@/store/modules/alarm-center-detail';

import type { IGetValueFnParams } from '../../../../../components/retrieval-filter/typing';
import type { IDimensionField } from '../../../../trace-explore/typing';

import './index.scss';

/** 筛选组件里无需填写检索值的操作符 */
const NO_VALUE_OF_METHODS = ['exists', 'not exists'];

export default defineComponent({
  name: 'PanelTrace',
  props: {
    /** 告警ID */
    alertId: String as PropType<string>,
  },
  setup(props) {
    const { t } = useI18n();
    const {
      traceList,
      traceQueryConfig,
      currentAppName,
      tableLoading,
      pagination,
      tableHasMoreData,
      filterMode,
      where,
      queryString,
      handleWhereChange,
      handleQueryStringChange,
      handleFilterModeChange,
      handleAppNameChange,
      applyExternalFilter,
      handleSearch,
    } = useAlertTraces(toRef(props, 'alertId'));

    useDiagnosticNavigate(ALARM_CENTER_PANEL_TAB_MAP.TRACE, filter => {
      applyExternalFilter(filter);
    });

    const alarmCenterDetailStore = useAlarmCenterDetailStore();
    const { getFieldsOptionValuesProxy } = useCandidateValue();

    /** Trace 视角维度字段列表，与「调用链检索」页保持同一份配置 */
    const traceFieldList = shallowRef<Record<string, any>[]>([]);
    /** 可切换的应用列表，与「Tracing 检索」页同一个数据源 */
    const appList = shallowRef<{ id: string; name: string }[]>([]);
    const appListLoading = shallowRef(true);

    watch(
      currentAppName,
      async appName => {
        if (!appName) {
          traceFieldList.value = [];
          return;
        }
        const viewConfig = await listTraceViewConfig({
          app_name: appName,
          bk_biz_id: alarmCenterDetailStore.bizId,
        }).catch(() => null);
        traceFieldList.value = viewConfig?.trace_config || [];
      },
      { immediate: true }
    );

    const getAppList = async () => {
      const data = await listApplicationInfo({ bk_biz_id: alarmCenterDetailStore.bizId }).catch(() => []);
      appList.value = (data || []).map((item: Record<string, any>) => ({
        id: item.app_name,
        name: item.app_alias ? `${item.app_alias}(${item.app_name})` : item.app_name,
      }));
      appListLoading.value = false;
    };

    onMounted(getAppList);

    const retrievalFields = computed(() => {
      const getType = (item: Record<string, any>) => {
        if (ALERT_TRACE_DURATION_KEYS.includes(item.name)) {
          return EFieldType.duration;
        }
        if (ALERT_TRACE_INPUT_TAG_KEYS.includes(item.name)) {
          return EFieldType.input;
        }
        return item.type;
      };
      return traceFieldList.value
        .filter(item => item?.is_searched)
        .map(item => ({
          ...item,
          isEnableOptions: ALERT_TRACE_NOT_SUPPORT_ENUM_KEYS.includes(item.name)
            ? false
            : !!item?.is_dimensions || item?.type === EFieldType.boolean,
          type: getType(item),
          methods:
            item?.supported_operations?.map(operation => ({
              ...operation,
              alias: operation.label,
              value: operation.operator,
              wildcardValue: operation?.wildcard_operator || '',
            })) || [],
        }));
    });

    /** 拉取筛选条件的候选值，时间范围取告警关联的调用链查询区间 */
    const getRetrievalFilterValueData = (params: IGetValueFnParams) => {
      const config = traceQueryConfig.value;
      return getFieldsOptionValuesProxy(
        {
          bk_biz_id: alarmCenterDetailStore.bizId,
          app_name: currentAppName.value,
          start_time: Math.floor((config?.start_time || 0) / 1000),
          end_time: Math.floor((config?.end_time || 0) / 1000),
          fields: params?.fields || [],
          limit: params?.limit || 5,
          filters:
            params?.where?.map(item => ({
              key: item.key,
              operator: 'like',
              value: item.value || [],
            })) || [],
          query_string: params?.queryString || '',
          mode: 'trace',
          isInit__: params?.isInit__ || false,
        } as any,
        traceFieldList.value as Array<{ [key: string]: any; type: string }>
      )
        .then(res => ({ count: res.count, list: res.list }))
        .catch(() => ({ count: 0, list: [] }));
    };

    const displayFields = [
      'trace_id',
      'trace_duration',
      'min_start_time',
      'root_span_name',
      'root_service',
      'root_service_span_name',
      'error_msg',
    ];

    const handleSliderShow = (openMode: '' | 'span' | 'trace', activeId: string) => {
      const query = deepmerge(traceQueryConfig.value, {
        where: [
          {
            key: openMode === 'span' ? 'span_id' : 'trace_id',
            operator: 'equal',
            value: [activeId],
          },
        ],
      });
      const newQuery = Object.entries(query).reduce((prev, [key, value]) => {
        if (typeof value === 'object') {
          prev[key] = decodeURIComponent(JSON.stringify(value));
        } else {
          prev[key] = value;
        }
        return prev;
      }, {});
      window.open(`#/trace/home/?${new URLSearchParams(newQuery).toString()}`);
    };

    /** 跳转当前业务的 Tracing 检索页，带上当前应用、时间与筛选条件 */
    const handleGoTrace = () => {
      const config = traceQueryConfig.value;
      const bizId = alarmCenterDetailStore.bizId || window.cc_biz_id;
      const isUiMode = filterMode.value === EMode.ui;
      const detailTimeRange = alarmCenterDetailStore.timeRange || [];
      const query: Record<string, string> = {
        start_time: config?.start_time
          ? String(config.start_time)
          : detailTimeRange[0]
            ? String(detailTimeRange[0])
            : 'now-1h',
        end_time: config?.end_time
          ? String(config.end_time)
          : detailTimeRange[1]
            ? String(detailTimeRange[1])
            : 'now',
        timezone: window.timezone || 'Asia/Shanghai',
        refreshInterval: '-1',
        sceneMode: config?.sceneMode || 'trace',
        app_name: currentAppName.value || '',
        where: JSON.stringify(isUiMode ? where.value : []),
        commonWhere: JSON.stringify([]),
        showResidentBtn: 'true',
        filterMode: filterMode.value,
        selectedType: JSON.stringify([]),
        sortBy: config?.sortBy || '',
        descending: config?.descending ?? 'null',
      };
      if (!isUiMode && queryString.value) {
        query.queryString = queryString.value;
      }
      const hash = `#/trace/home?${new URLSearchParams(query).toString()}`;
      window.open(`${location.origin}${location.pathname}?bizId=${bizId}${hash}`, '_blank');
    };

    const handleScrollToEnd = () => {
      pagination.offset += pagination.limit;
    };

    return {
      t,
      displayFields,
      traceList,
      traceQueryConfig,
      currentAppName,
      appList,
      appListLoading,
      pagination,
      tableLoading,
      tableHasMoreData,
      filterMode,
      where,
      queryString,
      retrievalFields,
      getRetrievalFilterValueData,
      handleWhereChange,
      handleQueryStringChange,
      handleFilterModeChange,
      handleAppNameChange,
      handleSearch,
      handleSliderShow,
      handleGoTrace,
      handleScrollToEnd,
    };
  },
  render() {
    return (
      <div class='alarm-center-detail-panel-trace'>
        <div class='alarm-center-detail-panel-trace-wrapper'>
          <div class='panel-trace-header'>
            <PanelSourceSelector
              label={this.t('应用')}
              list={this.appList}
              loading={this.appListLoading}
              placeholder={this.t('请输入 关键字')}
              value={this.currentAppName}
              onChange={this.handleAppNameChange}
            />
            <Button
              class='ml-16'
              theme='primary'
              text
              onClick={this.handleGoTrace}
            >
              <span>{this.t('Tracing 检索')}</span>
              <span class='icon-monitor icon-fenxiang ml-6' />
            </Button>
          </div>
          <div class='panel-trace-filter'>
            <RetrievalFilter
              changeWhereFormatter={traceWhereChangeFormatter}
              fields={this.retrievalFields as any[]}
              filterMode={this.filterMode}
              getValueFn={this.getRetrievalFilterValueData}
              isShowClear={true}
              noValueOfMethods={NO_VALUE_OF_METHODS}
              queryString={this.queryString}
              where={this.where}
              whereFormatter={traceWhereFormatter}
              zIndex={4000}
              onModeChange={this.handleFilterModeChange}
              onQueryStringChange={this.handleQueryStringChange}
              onSearch={this.handleSearch}
              onWhereChange={this.handleWhereChange}
            />
          </div>
          <TraceExploreTable
            class='panel-trace-table'
            appName={this.currentAppName}
            canSortFieldTypes={[]}
            displayFields={this.displayFields}
            enabledClickMenu={false}
            enabledDisplayFieldSetting={false}
            enableStatistics={false}
            mode='trace'
            scrollContainerSelector='.alarm-center-detail-box'
            showHeaderIcon={false}
            showOperation={false}
            sourceFieldConfigs={ALERT_TRACE_FIELD_CONFIGS as unknown as IDimensionField[]}
            tableData={this.traceList}
            tableHasScrollLoading={this.tableHasMoreData}
            tableLoading={this.tableLoading}
            onScrollToEnd={this.handleScrollToEnd}
            onSliderShow={this.handleSliderShow}
          />
        </div>
      </div>
    );
  },
});
