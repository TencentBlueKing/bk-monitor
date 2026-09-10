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
import { type PropType, computed, defineComponent, onMounted, shallowRef } from 'vue';

import { Button } from 'bkui-vue';
import { alertEvents, alertEventTotal } from 'monitor-api/modules/alert_v2';
import { getDataSourceConfig } from 'monitor-api/modules/grafana';
import { random } from 'monitor-common/utils/utils';
import { useI18n } from 'vue-i18n';

import RetrievalFilter from '../../../../../components/retrieval-filter/retrieval-filter';
import { EFieldType, EMode } from '../../../../../components/retrieval-filter/typing';
// 【临时联调 mock，联调就绪后删除本行 import 与下方 filterRowsByPanelFilterMock / filterRowsBySourceMock 调用】
import { filterRowsByPanelFilterMock, filterRowsBySourceMock } from '../../../../../mock/alarm-detail-panel-filter';
import PanelSourceSelector from '../panel-source-selector/panel-source-selector';
import EventTable from './components/event-table';
import { SourceTypeEnum } from './components/typing';
import { type IAlertEventQueryConfig, pickQueryConfig, useEventFilter } from './use-event-filter';
import { useDiagnosticNavigate } from '../../../composables/use-diagnostic-navigate';
import { ALARM_CENTER_PANEL_TAB_MAP } from '../../../utils/constant';

import type { IFilterField, IGetValueFnParams, IWhereItem } from '../../../../../components/retrieval-filter/typing';
import type { AlarmDetail } from '../../../typings/detail';

import './index.scss';

/** 「事件来源」在筛选组件里的字段名，提交查询时会被还原成接口的 sources 参数 */
const SOURCE_FIELD_NAME = 'source';
/** 筛选组件里无需填写检索值的操作符 */
const NO_VALUE_OF_METHODS = ['exists', 'not exists'];
/**
 * 未选择「事件来源」时提交的默认值。
 * 关联事件总数接口是异步的，表格的首屏请求会早于它返回，这里保持与改造前一致的固定全集，
 * 避免首屏把 sources 传成空数组。
 */
const DEFAULT_SOURCE_OPTIONS = [
  { id: SourceTypeEnum.BCS, name: window.i18n.t('容器') as string },
  { id: SourceTypeEnum.BKCI, name: window.i18n.t('蓝盾') as string },
  { id: SourceTypeEnum.HOST, name: window.i18n.t('主机') as string },
  { id: SourceTypeEnum.DEFAULT, name: window.i18n.t('业务上报') as string },
];

export default defineComponent({
  name: 'PanelEvent',
  props: {
    detail: {
      type: Object as PropType<AlarmDetail>,
      default: () => null,
    },
  },
  setup(props) {
    const { t } = useI18n();
    const { setQueryConfig, getFieldList, getFieldsOptionValues } = useEventFilter();

    const eventQueryConfig = shallowRef<IAlertEventQueryConfig>(null);
    /** 事件检索字段列表 */
    const eventFieldList = shallowRef<IFilterField[]>([]);
    /** 事件来源候选值，同时用于把筛选条件还原成接口的 sources 参数（带数量的别名由总数接口回填） */
    const sourceOptions = shallowRef<{ id: string; name: string }[]>(DEFAULT_SOURCE_OPTIONS);
    const filterMode = shallowRef<EMode>(EMode.ui);
    const where = shallowRef<IWhereItem[]>([]);
    const queryString = shallowRef('');
    /** 表格靠它感知筛选条件变化并从第一页重新拉取 */
    const tableRefreshKey = shallowRef('');
    /** 用户手动切换的数据ID，空值表示跟随告警自身关联的数据源 */
    const selectedTable = shallowRef('');
    /** 可切换的数据ID 列表，与「事件检索」页同一个数据源 */
    const dataIdList = shallowRef<{ id: string; name: string }[]>([]);
    const dataIdLoading = shallowRef(true);
    let dataIdRequested = false;

    /** 告警自身关联的数据ID */
    const originTable = computed(() => pickQueryConfig(eventQueryConfig.value)?.table || '');
    /** 当前查询的数据ID：用户选过就用选的，否则用告警返回的 */
    const currentTable = computed(() => selectedTable.value || originTable.value);

    /** 「事件来源」条件走接口既有的 sources 参数，其余条件才是真正的 where */
    const selectedSources = computed(() => {
      const allSources = sourceOptions.value.map(item => item.id);
      if (filterMode.value !== EMode.ui) return allSources;
      const sourceItem = where.value.find(item => item.key === SOURCE_FIELD_NAME);
      const values = (sourceItem?.value || []).map(String).filter(value => allSources.includes(value));
      return values.length ? values : allSources;
    });

    const whereWithoutSource = computed(() => where.value.filter(item => item.key !== SOURCE_FIELD_NAME));

    const isFiltered = computed(() =>
      filterMode.value === EMode.ui ? !!where.value.length : !!queryString.value.trim()
    );

    /** 事件来源字段由本页拼装：接口只认 sources 参数，候选值取自关联事件总数接口 */
    const sourceField = computed<IFilterField>(() => ({
      name: SOURCE_FIELD_NAME,
      alias: t('事件来源'),
      type: EFieldType.keyword,
      isEnableOptions: true,
      methods: [{ alias: '=', value: 'eq' }],
    }));

    const retrievalFields = computed<IFilterField[]>(() => [
      sourceField.value,
      ...eventFieldList.value.filter(item => item.name !== SOURCE_FIELD_NAME),
    ]);

    const getRetrievalFilterValueData = (params: IGetValueFnParams) => {
      if (params?.fields?.[0] === SOURCE_FIELD_NAME) {
        const search = String(params.where?.[0]?.value?.[0] || '').toLocaleLowerCase();
        const list = search
          ? sourceOptions.value.filter(item => `${item.id}${item.name}`.toLocaleLowerCase().includes(search))
          : sourceOptions.value;
        return Promise.resolve({ count: list.length, list });
      }
      return getFieldsOptionValues(params);
    };

    const getData = async (params: { limit: number; offset: number; sort: string[] }) => {
      const isUiMode = filterMode.value === EMode.ui;
      const res = await alertEvents({
        bk_biz_id: props.detail.bk_biz_id,
        alert_id: props.detail.id,
        limit: params.limit,
        offset: params.offset,
        // sort: params.sort,
        sources: selectedSources.value,
        // 【待后端支持】alert/events 目前忽略 table / where / query_string，联调完成前由 mock 在前端模拟
        table: currentTable.value,
        where: isUiMode ? whereWithoutSource.value : [],
        query_string: isUiMode ? '' : queryString.value,
      }).catch(() => {
        return {
          list: [],
          total: 0,
        };
      });
      if (res?.query_config) {
        eventQueryConfig.value = res.query_config;
        setQueryConfig(res.query_config);
        // 字段列表不阻塞表格渲染
        if (!eventFieldList.value.length) {
          getFieldList().then(list => {
            eventFieldList.value = list;
          });
        }
        // 数据ID 列表依赖接口返回的数据源类型，拿到 query_config 后再拉
        if (!dataIdRequested) {
          dataIdRequested = true;
          initDataIdList(pickQueryConfig(res.query_config));
        }
      }
      // 【临时联调 mock，联调就绪后删除这两段，直接用 res.list】
      const originTableOfRes = pickQueryConfig(res.query_config)?.table || originTable.value;
      const rows = filterRowsBySourceMock<Record<string, any>>(
        res.list || [],
        !selectedTable.value || selectedTable.value === originTableOfRes
      );
      const list = filterRowsByPanelFilterMock<Record<string, any>>(rows, {
        filterMode: filterMode.value,
        where: whereWithoutSource.value,
        queryString: queryString.value,
        getFieldValue: (row, key) => row?.[key] ?? row?.origin_data?.[key],
        getAllValues: row => Object.values(row || {}),
      });
      return {
        data: list.map(item => ({
          ...item,
          key: random(8),
        })),
        total: res?.total || 0,
      };
    };

    const initDataIdList = async (queryConfig: null | Record<string, any>) => {
      if (!queryConfig?.data_source_label) {
        dataIdLoading.value = false;
        return;
      }
      const data = await getDataSourceConfig({
        bk_biz_id: eventQueryConfig.value?.bk_biz_id || props.detail?.bk_biz_id,
        data_source_label: queryConfig.data_source_label,
        data_type_label: queryConfig.data_type_label,
        return_dimensions: false,
      }).catch(() => []);
      dataIdList.value = (data || []).map((item: Record<string, any>) => ({
        id: item.id,
        name: item.name,
      }));
      dataIdLoading.value = false;
    };

    const initSourceOptions = async () => {
      const data = await alertEventTotal({
        bk_biz_id: props.detail.bk_biz_id,
        alert_id: props.detail.id,
      }).catch(() => {
        return {
          total: 0,
          list: [],
        };
      });
      if (!data?.list?.length) return;
      sourceOptions.value = data.list.map(item => ({
        id: item.value,
        name: `${item.alias}(${item.total ?? 0})`,
      }));
    };

    const handleSearch = () => {
      tableRefreshKey.value = random(8);
    };

    const handleWhereChange = (val: IWhereItem[]) => {
      where.value = val;
      handleSearch();
    };

    const handleQueryStringChange = (val: string) => {
      queryString.value = val;
      handleSearch();
    };

    const handleFilterModeChange = (mode: EMode) => {
      filterMode.value = mode;
      if (mode === EMode.ui) {
        queryString.value = '';
      } else {
        where.value = [];
      }
      handleSearch();
    };

    const handleClearFilter = () => {
      where.value = [];
      queryString.value = '';
      handleSearch();
    };

    /** 切换数据ID 后原有筛选条件的字段可能不存在，一并清空并重新拉字段列表 */
    const handleTableChange = (table: string) => {
      selectedTable.value = table;
      where.value = [];
      queryString.value = '';
      eventFieldList.value = [];
      handleSearch();
    };

    const handleGoEvent = () => {
      const serviceName = props.detail?.dimensions?.find(item => item.key === 'service_name')?.value || '';
      const appName = props.detail?.dimensions?.find(item => item.key === 'app_name')?.value || '';
      const startTime = eventQueryConfig.value?.start_time || '';
      const endTime = eventQueryConfig.value?.end_time || '';
      const fromToStr = `${startTime ? `&from=${startTime * 1000}` : ''}${endTime ? `&to=${endTime * 1000}` : ''}`;
      const targetsStr = eventQueryConfig.value?.query_configs
        ? `&targets=${encodeURIComponent(JSON.stringify([{ data: { query_configs: [eventQueryConfig.value?.query_configs] } }]))}`
        : '';
      const bizId = eventQueryConfig.value?.bk_biz_id || props.detail?.bk_biz_id || window.cc_biz_id;
      let hash = `#/event-explore?${fromToStr}${targetsStr}`;
      if (serviceName && appName) {
        hash = `#/apm/service?filter-service_name=${serviceName}&filter-app_name=${appName}&dashboardId=service-default-event${fromToStr}${targetsStr}`;
      }
      const url = `${location.origin}${location.pathname}?bizId=${bizId}${hash}`;
      window.open(url, '_blank');
    };

    useDiagnosticNavigate(ALARM_CENTER_PANEL_TAB_MAP.EVENT, filter => {
      const mode = filter.filterMode ?? EMode.ui;
      filterMode.value = mode;
      if (mode === EMode.queryString) {
        queryString.value = filter.queryString || '';
        where.value = [];
      } else {
        where.value = filter.where || [];
        queryString.value = '';
      }
      handleSearch();
    });

    onMounted(initSourceOptions);

    return {
      t,
      filterMode,
      where,
      queryString,
      retrievalFields,
      isFiltered,
      tableRefreshKey,
      currentTable,
      dataIdList,
      dataIdLoading,
      getData,
      getRetrievalFilterValueData,
      handleWhereChange,
      handleQueryStringChange,
      handleFilterModeChange,
      handleTableChange,
      handleSearch,
      handleClearFilter,
      handleGoEvent,
    };
  },
  render() {
    return (
      <div class='alarm-center-detail-panel-alarm-relation-event'>
        <div class='panel-event-header'>
          <PanelSourceSelector
            label={this.t('数据ID')}
            list={this.dataIdList}
            loading={this.dataIdLoading}
            placeholder={this.t('请输入 关键字')}
            value={this.currentTable}
            onChange={this.handleTableChange}
          />
          <Button
            class='ml-16'
            theme='primary'
            text
            onClick={this.handleGoEvent}
          >
            <span>{this.t('更多事件')}</span>
            <span class='icon-monitor icon-fenxiang ml-6' />
          </Button>
        </div>
        <div class='panel-event-filter'>
          <RetrievalFilter
            fields={this.retrievalFields}
            filterMode={this.filterMode}
            getValueFn={this.getRetrievalFilterValueData}
            isShowClear={true}
            noValueOfMethods={NO_VALUE_OF_METHODS}
            queryString={this.queryString}
            where={this.where}
            zIndex={4000}
            onModeChange={this.handleFilterModeChange}
            onQueryStringChange={this.handleQueryStringChange}
            onSearch={this.handleSearch}
            onWhereChange={this.handleWhereChange}
          />
        </div>
        {this.detail?.id ? (
          <EventTable
            key={this.detail.id}
            getTableData={this.getData}
            isFiltered={this.isFiltered}
            refreshKey={this.tableRefreshKey}
            onClearFilter={this.handleClearFilter}
          />
        ) : undefined}
      </div>
    );
  },
});
