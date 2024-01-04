/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台社区版 (BlueKing PaaS Community Edition) available.
 *
 * Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
 *
 * 蓝鲸智云PaaS平台社区版 (BlueKing PaaS Community Edition) is licensed under the MIT License.
 *
 * License for 蓝鲸智云PaaS平台社区版 (BlueKing PaaS Community Edition):
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

import { computed, defineComponent, PropType } from 'vue';
import { useI18n } from 'vue-i18n';
import { useRoute } from 'vue-router';
import { Popover, Table } from 'bkui-vue';

import { formatDuration } from '../../../components/trace-view/utils/date';
import { SPAN_KIND_MAPS } from '../../../store/constant';
import { useTraceStore } from '../../../store/modules/trace';

import { TraceListType } from './trace-list';

import './interface-statistics.scss';

export default defineComponent({
  name: 'InterfaceStatistics',
  props: {
    interfaceTypeList: {
      type: Array,
      default: () => []
    },
    sourceTypeList: {
      type: Array,
      default: () => []
    },
    filterList: {
      type: Object as PropType<TraceListType>,
      default: () => ({})
    }
  },
  setup(props) {
    const route = useRoute();
    const store = useTraceStore();
    const { t } = useI18n();
    // 这个 table 比较特别，来源类型 和 接口类型 是基于右上角的选项去控制的，而非 settings 。
    // 所以这里需要通过 computed 返回这个对象，并进行筛选。
    const tableColumn = [
      {
        label: () => (
          <Popover
            popoverDelay={[500, 0]}
            content={t('接口名')}
            theme='light'
            placement='right'
          >
            <span class='th-label'>{t('接口名')}</span>
          </Popover>
        ),
        field: 'span_name',
        filter: {
          list: props.filterList.span_name,
          filterFn: () => true as any
        },
        // eslint-disable-next-line @typescript-eslint/no-unused-vars
        render: ({ cell }: { cell: string }) => (
          <div>
            <span
              class='ellipsis-text'
              title={cell}
            >
              {cell}
            </span>
          </div>
        )
      },
      {
        label: () => (
          <Popover
            popoverDelay={[500, 0]}
            content={t('所属Service')}
            theme='light'
            placement='right'
          >
            <span class='th-label'>{t('所属Service')}</span>
          </Popover>
        ),
        field: 'service_name',
        filter: {
          list: props.filterList['resource.service.name'],
          filterFn: () => true as any
        },
        // eslint-disable-next-line @typescript-eslint/no-unused-vars
        render: ({ cell }: { cell: string }) => (
          <div>
            <span
              class='ellipsis-text'
              title={cell}
            >
              {cell}
            </span>
          </div>
        )
      },
      {
        label: () => (
          <Popover
            popoverDelay={[500, 0]}
            content={t('来源类型')}
            theme='light'
            placement='right'
          >
            <span class='th-label'>{t('来源类型')}</span>
          </Popover>
        ),
        field: 'source'
        // 只有一个 OTel ，不需要过滤
        // filter: {
        //   // list: traceListFilter.span_name,
        //   filterFn: () => true as any
        // }
      },
      {
        label: () => (
          <Popover
            popoverDelay={[500, 0]}
            content={t('接口类型')}
            theme='light'
            placement='right'
          >
            <span class='th-label'>{t('接口类型')}</span>
          </Popover>
        ),
        field: 'kind',
        width: 160,
        filter: {
          list: props.filterList.kind,
          filterFn: () => true as any
        },
        // eslint-disable-next-line @typescript-eslint/no-unused-vars
        render: ({ cell }: { cell: string }) => (
          <div>
            <span title={SPAN_KIND_MAPS[cell]}>{SPAN_KIND_MAPS[cell]}</span>
          </div>
        )
      },
      {
        label: () => (
          <Popover
            popoverDelay={[500, 0]}
            content={t('Span数量')}
            theme='light'
            placement='right'
          >
            <span class='th-label'>{t('Span数量')}</span>
          </Popover>
        ),
        width: 120,
        field: 'span_count',
        sort: {
          sortScope: 'all',
          value: ''
        }
      },
      {
        label: () => (
          <Popover
            popoverDelay={[500, 0]}
            content={t('错误数')}
            theme='light'
            placement='right'
          >
            <span class='th-label'>{t('错误数')}</span>
          </Popover>
        ),
        width: 120,
        field: 'error_count',
        sort: {
          sortScope: 'all',
          value: ''
        }
      },
      {
        label: () => (
          <Popover
            popoverDelay={[500, 0]}
            content={t('错误率')}
            theme='light'
            placement='right'
          >
            <span class='th-label'>{t('错误率')}</span>
          </Popover>
        ),
        field: 'error_rate',
        sort: {
          sortScope: 'all',
          value: ''
        }
      },
      {
        label: () => (
          <Popover
            popoverDelay={[500, 0]}
            content={t('平均耗时')}
            theme='light'
            placement='right'
          >
            <span class='th-label'>{t('平均耗时')}</span>
          </Popover>
        ),
        field: 'avg_duration',
        width: 120,
        sort: {
          sortScope: 'all',
          value: ''
        },
        render: ({ cell }: { cell: number }) => (
          <div>
            <span>{formatDuration(cell)}</span>
          </div>
        )
      },
      {
        label: () => (
          <Popover
            popoverDelay={[500, 0]}
            content={t('P90耗时')}
            theme='light'
            placement='right'
          >
            <span class='th-label'>{t('P90耗时')}</span>
          </Popover>
        ),
        field: 'p90_duration',
        width: 120,
        sort: {
          sortScope: 'all',
          value: ''
        },
        render: ({ cell }: { cell: number }) => (
          <div>
            <span>{formatDuration(cell)}</span>
          </div>
        )
      },
      {
        label: () => (
          <Popover
            popoverDelay={[500, 0]}
            content={t('P50耗时')}
            theme='light'
            placement='right'
          >
            <span class='th-label'>{t('P50耗时')}</span>
          </Popover>
        ),
        field: 'p50_duration',
        width: 120,
        sort: {
          sortScope: 'all',
          value: ''
        },
        render: ({ cell }: { cell: number }) => (
          <div>
            <span>{formatDuration(cell)}</span>
          </div>
        )
      },
      {
        label: t('操作'),
        width: 160,
        // eslint-disable-next-line @typescript-eslint/no-unused-vars
        render: ({ cell, data }: { cell: Record<string, string>; data: any }) => (
          <div style='display: flex;'>
            <div
              class='link-column'
              onClick={() => handleToTraceQuery(data)}
              style='width: 40px;'
            >
              <span
                class='link-text'
                title={t('检索')}
              >
                {t('检索')}
              </span>
              <i class='icon-monitor icon-fenxiang'></i>
            </div>

            <div
              class='link-column'
              onClick={() => handleToObserve(data)}
              style='margin-left: 10px;'
            >
              <span
                class='link-text'
                title={t('去观测')}
              >
                {t('去观测')}
              </span>
              <i class='icon-monitor icon-fenxiang'></i>
            </div>
          </div>
        )
      }
    ];

    const filteredTableColumn = computed(() => tableColumn);

    /** 跳转服务 */
    const handleToService = (serviceName: string) => {
      const hash = `#/apm/service?filter-service_name=${serviceName}&filter-app_name=${route.query.app_name}`;
      const url = location.href.replace(location.hash, hash);
      window.open(url, '_blank');
    };
    /** 跳转接口 */
    const handleToEndpoint = (serviceName: string, endpointName: string) => {
      const hash = `#/apm/service?filter-app_name=${route.query.app_name}&filter-span_name=${endpointName}&filter-service_name=${serviceName}&sceneType=detail&sceneId=apm_service&dashboardId=service-default-endpoint`;
      const url = location.href.replace(location.hash, hash);
      window.open(url, '_blank');
    };

    // 带上服务、接口、来源类型、接口类型 跳转到 trace 范围查询下 trace视角
    function handleToTraceQuery(data) {
      const conditionList = {
        kind: {
          // 固定写死
          selectedCondition: { label: '=', value: 'equal' },
          isInclude: true,
          //   读 data
          selectedConditionValue: [data.kind]
        },
        span_name: {
          // 固定写死
          selectedCondition: { label: '=', value: 'equal' },
          isInclude: true,
          //   读 data
          selectedConditionValue: [data.span_name]
        },
        'resource.service.name': {
          // 固定写死
          selectedCondition: { label: '=', value: 'equal' },
          isInclude: true,
          //   读 data
          selectedConditionValue: [data.service_name]
        }
      };
      // eslint-disable-next-line no-useless-escape
      const hash = `#/trace/home??app_name=${
        route.query.app_name
      }&search_type=scope&listType=trace&conditionList=${JSON.stringify(conditionList)}`;
      const url = location.href.replace(location.hash, hash);
      window.open(url, '_blank');
    }

    function handleToObserve(data) {
      const filters = store.interfaceStatisticsType;
      if (filters.includes('root_span') && filters.includes('root_service_span')) {
        handleToEndpoint(data.service_name, data.span_name);
      } else if (filters.includes('root_span')) {
        handleToEndpoint(data.service_name, data.span_name);
      } else if (filters.includes('root_service_span')) {
        handleToService(data.service_name);
      } else {
        handleToService(data.service_name);
      }
    }

    function handleTableSettingChange(settings: { checked: string[]; size: string; height: number }) {
      store.tableSettings.interfaceStatistics.checked = settings.checked;
    }

    const tableContent = () => (
      <Table
        ref='tableSpanElem'
        style='height: 100%'
        height='100%'
        class='interface-statistics-table'
        rowHeight={40}
        border={['outer']}
        columns={filteredTableColumn.value}
        data={store.interfaceStatisticsList}
        settings={store.tableSettings.interfaceStatistics as any}
        onSettingChange={handleTableSettingChange}
        // TODO：后期确认空数据的设计样式
        // v-slots={{ empty: () => tableEmptyContent() }}
      />
    );
    return {
      tableContent,
      store
    };
  },
  render() {
    return this.tableContent();
  }
});
