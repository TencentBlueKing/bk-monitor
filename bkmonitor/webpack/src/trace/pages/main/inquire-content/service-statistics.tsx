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

import { type PropType, defineComponent } from 'vue';
import { useI18n } from 'vue-i18n';
import { useRoute } from 'vue-router';

import { Popover, Table } from 'bkui-vue';

import { formatDuration } from '../../../components/trace-view/utils/date';
import { SPAN_KIND_MAPS } from '../../../store/constant';
import { useTraceStore } from '../../../store/modules/trace';

import type { TraceListType } from './trace-list';

import './service-statistics.scss';

export default defineComponent({
  name: 'ServiceStatistics',
  props: {
    interfaceTypeList: {
      type: Array,
      default: () => [],
    },
    sourceTypeList: {
      type: Array,
      default: () => [],
    },
    filterList: {
      type: Object as PropType<TraceListType>,
      default: () => ({}),
    },
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
            content='Service'
            placement='right'
            popoverDelay={[500, 0]}
            theme='light'
          >
            <span class='th-label'>Service</span>
          </Popover>
        ),
        field: 'service_name',
        filter: {
          list: props.filterList['resource.service.name'],
          filterFn: () => true as any,
        },

        render: ({ cell }: { cell: string }) => (
          <div>
            <span
              class='ellipsis-text'
              title={cell}
            >
              {cell}
            </span>
          </div>
        ),
      },
      // {
      //   label: () => (
      //     <Popover popoverDelay={[500, 0]} content="Service" theme="light" placement="right">
      //       <span class="th-label">{t('服务类型')}</span>
      //     </Popover>
      //   ),
      //   field: 'kind',
      //   filter: {
      //     list: props.filterList.kind,
      //     filterFn: () => true as any
      //   },
      //   // eslint-disable-next-line @typescript-eslint/no-unused-vars
      //   render: ({ cell }: {cell: string }) => (
      //     <div>
      //       <span title={SPAN_KIND_MAPS[cell]}>{ SPAN_KIND_MAPS[cell] }</span>
      //     </div>
      //   )
      // },
      {
        label: () => (
          <Popover
            content={t('服务类型')}
            placement='right'
            popoverDelay={[500, 0]}
            theme='light'
          >
            <span class='th-label'>{t('服务类型')}</span>
          </Popover>
        ),
        field: 'kind',
        filter: {
          list: props.filterList.kind,
          filterFn: () => true as any,
        },

        render: ({ cell }: { cell: string }) => (
          <div>
            <span title={SPAN_KIND_MAPS[cell]}>{SPAN_KIND_MAPS[cell]}</span>
          </div>
        ),
      },
      {
        label: () => (
          <Popover
            content={t('Span数量')}
            placement='right'
            popoverDelay={[500, 0]}
            theme='light'
          >
            <span class='th-label'>{t('Span数量')}</span>
          </Popover>
        ),
        field: 'span_count',
        width: 120,
        sort: {
          sortScope: 'all',
          value: '',
        },
      },
      {
        label: () => (
          <Popover
            content={t('错误数')}
            placement='right'
            popoverDelay={[500, 0]}
            theme='light'
          >
            <span class='th-label'>{t('错误数')}</span>
          </Popover>
        ),
        field: 'error_count',
        width: 120,
        sort: {
          sortScope: 'all',
          value: '',
        },
      },
      {
        label: () => (
          <Popover
            content={t('错误率')}
            placement='right'
            popoverDelay={[500, 0]}
            theme='light'
          >
            <span class='th-label'>{t('错误率')}</span>
          </Popover>
        ),
        field: 'error_rate',
        sort: {
          sortScope: 'all',
          value: '',
        },
      },
      {
        label: () => (
          <Popover
            content={t('平均耗时')}
            placement='right'
            popoverDelay={[500, 0]}
            theme='light'
          >
            <span class='th-label'>{t('平均耗时')}</span>
          </Popover>
        ),
        field: 'avg_duration',
        width: 120,
        sort: {
          sortScope: 'all',
          value: '',
        },
        render: ({ cell }: { cell: number }) => (
          <div>
            <span>{formatDuration(cell)}</span>
          </div>
        ),
      },
      {
        label: () => (
          <Popover
            content={t('P90耗时')}
            placement='right'
            popoverDelay={[500, 0]}
            theme='light'
          >
            <span class='th-label'>{t('P90耗时')}</span>
          </Popover>
        ),
        field: 'p90_duration',
        width: 120,
        sort: {
          sortFn: () => false,
        },
        render: ({ cell }: { cell: number }) => (
          <div>
            <span>{formatDuration(cell)}</span>
          </div>
        ),
      },
      {
        label: () => (
          <Popover
            content={t('P50耗时')}
            placement='right'
            popoverDelay={[500, 0]}
            theme='light'
          >
            <span class='th-label'>{t('P50耗时')}</span>
          </Popover>
        ),
        field: 'p50_duration',
        width: 120,
        sort: {
          sortScope: 'all',
          value: '',
        },
        render: ({ cell }: { cell: number }) => (
          <div>
            <span>{formatDuration(cell)}</span>
          </div>
        ),
      },
      {
        label: t('操作'),
        // eslint-disable-next-line @typescript-eslint/no-unused-vars
        render: ({ cell, data }: { cell: Record<string, string>; data: any }) => (
          <div style='display: flex;'>
            <div
              style='width: 40px;'
              class='link-column'
              onClick={() => handleToTraceQuery(data)}
            >
              <span
                class='link-text'
                title={t('检索')}
              >
                {t('检索')}
              </span>
              <i class='icon-monitor icon-fenxiang' />
            </div>

            <div
              style='margin-left: 10px;'
              class='link-column'
              onClick={() => handleToObserve(data)}
            >
              <span
                class='link-text'
                title={t('去观测')}
              >
                {t('去观测')}
              </span>
              <i class='icon-monitor icon-fenxiang' />
            </div>
          </div>
        ),
      },
    ];

    // const filteredTableColumn = computed(() => {
    //   const hasSelectInterfaceType = !!props.interfaceTypeList.length;
    //   const hasSelectSourceType = !!props.sourceTypeList.length;
    //   return tableColumn.filter((item) => {
    //     if (item.field === '接口类型' && !hasSelectInterfaceType) return false;
    //     if (item.field === 'source_type' && !hasSelectSourceType) return false;
    //     return true;
    //   });
    // });

    /** 跳转服务 */
    const handleToService = (serviceName: string) => {
      const hash = `#/apm/service?filter-service_name=${serviceName}&filter-app_name=${route.query.app_name}`;
      const url = location.href.replace(location.hash, hash);
      window.open(url, '_blank');
    };
    /** 跳转接口 */
    // const handleToEndpoint = (serviceName: string, endpointName: string) => {

    //   const hash = `#/apm/service?filter-app_name=${route.query.app_name}&filter-span_name=${endpointName}&filter-service_name=${serviceName}&sceneType=detail&sceneId=apm_service&dashboardId=service-default-endpoint`;
    //   const url = location.href.replace(location.hash, hash);
    //   window.open(url, '_blank');
    // };

    // 带上服务、接口、来源类型、接口类型 跳转到 trace 范围查询下 trace视角
    function handleToTraceQuery(data) {
      const conditionList = {
        kind: {
          // 固定写死
          selectedCondition: { label: '=', value: 'equal' },
          isInclude: true,
          //   读 data
          selectedConditionValue: [data.kind],
        },
        'resource.service.name': {
          // 固定写死
          selectedCondition: { label: '=', value: 'equal' },
          isInclude: true,
          //   读 data
          selectedConditionValue: [data.service_name],
        },
      };

      const hash = `#/trace/home??app_name=${
        route.query.app_name
      }&search_type=scope&listType=serviceStatistics&conditionList=${JSON.stringify(conditionList)}`;
      const url = location.href.replace(location.hash, hash);
      window.open(url, '_blank');
    }

    function handleToObserve(data) {
      handleToService(data?.service_name);
    }

    function handleTableSettingChange(settings: { checked: string[]; size: string; height: number }) {
      store.tableSettings.serviceStatistics.checked = settings.checked;
    }

    const tableContent = () => (
      <Table
        ref='tableSpanElem'
        style='height: 100%'
        height='100%'
        class='service-statistics-table'
        border={['outer']}
        columns={tableColumn}
        data={store.serviceStatisticsList}
        rowHeight={40}
        settings={store.tableSettings.serviceStatistics as any}
        onSettingChange={handleTableSettingChange}
        // TODO：后期确认空数据的设计样式
        // v-slots={{ empty: () => tableEmptyContent() }}
      />
    );
    return {
      tableContent,
      store,
    };
  },
  render() {
    return this.tableContent();
  },
});
