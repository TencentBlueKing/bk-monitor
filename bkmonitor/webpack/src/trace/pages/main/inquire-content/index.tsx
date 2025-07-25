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
import { type PropType, computed, defineComponent } from 'vue';

import { useI18n } from 'vue-i18n';

import EmptyStatus from '../../../components/empty-status/empty-status';
import PreciseQueryImg from '../../../static/img/precise-query.png';
import RangeQueryImg from '../../../static/img/range-query.png';
import { useTraceStore } from '../../../store/modules/trace';
import SpanDetails from '../span-details';
import TraceDetail from './trace-detail';
import TraceList from './trace-list';

import type { Span } from '../../../components/trace-view/typings';
import type { IPanelModel } from '../../../plugins/typings';
import type { IAppItem } from '../../../typings';

import './index.scss';

export default defineComponent({
  name: 'InquireContent',
  props: {
    isAlreadyAccurateQuery: {
      type: Boolean,
      default: false,
    },
    isAlreadyScopeQuery: {
      type: Boolean,
      default: false,
    },
    queryType: {
      type: String as PropType<'accurate' | 'scope'>,
      default: 'accurate',
    },
    // 视图列表
    chartList: {
      type: Array as PropType<IPanelModel[]>,
      default: () => [],
    },
    traceListTableLoading: {
      type: Boolean,
      default: false,
    },
    appName: {
      type: String,
      default: '',
    },
    emptyApp: {
      type: Boolean,
      default: false,
    },
    appList: {
      type: Array as PropType<IAppItem[]>,
      default: () => [],
    },
    searchIdType: {
      type: String,
      default: 'traceID',
    },
    spanDetails: {
      type: Object as PropType<Span>,
      default: () => null,
    },
    traceColumnFilters: {
      type: Object as PropType<Record<string, string[]>>,
      default: () => {},
    },
  },
  emits: [
    'changeQuery',
    'traceListScrollBottom',
    'traceListStatusChange',
    'traceListSortChange',
    'traceListColumnFilter',
    'listTypeChange',
    'traceListColumnSortChange',
    'traceTypeChange',
    'spanTypeChange',
    'interfaceStatisticsChange',
    'serviceStatisticsChange',
  ],
  setup(props, { emit }) {
    const { t } = useI18n();
    const emptyTextMap = {
      'empty-app': t('暂无应用'),
    };

    const store = useTraceStore();

    const isLoading = computed<boolean>(() => store.loading);
    const isEmptyResult = computed<boolean>(() => {
      if (props.queryType === 'accurate') {
        if (props.searchIdType === 'spanID') {
          return !props.spanDetails;
        }
        return !store.traceData?.trace_id || !store.traceData?.original_data?.length;
      }
      if (props.queryType === 'scope') {
        // return !store.traceList.length;
        return false;
      }
      return true;
    });

    function handleScrollBottom() {
      emit('traceListScrollBottom');
    }

    function handleStatusChange(id: string) {
      emit('traceListStatusChange', id);
    }

    function handleColumnFilterChange(val: Record<string, string[]>) {
      emit('traceListColumnFilter', val);
    }

    function handleSortChange(sortKey: string) {
      emit('traceListSortChange', sortKey);
    }

    function handleCreateApp() {
      const url = location.href.replace(location.hash, '#/apm/home');
      window.open(url, '_blank');
    }

    function handleSourceData() {
      const { appList, appName } = props;
      const name = appList.find(app => app.app_name === appName)?.app_name || '';
      if (name) {
        const hash = `#/apm/application/config/${name}?active=dataStatus`;
        const url = location.href.replace(location.hash, hash);
        window.open(url, '_blank');
      }
    }

    function handleTraceTypeChange(v: string[]) {
      emit('traceTypeChange', v);
    }

    function handleSpanTypeChange(v: string[]) {
      emit('spanTypeChange', v);
    }

    function handleInterfaceStatisticsChange(v: string[]) {
      emit('interfaceStatisticsChange', v);
    }

    function handleServiceStatisticsChange(v: string[]) {
      emit('serviceStatisticsChange', v);
    }

    return {
      isLoading,
      isEmptyResult,
      handleScrollBottom,
      handleStatusChange,
      handleSortChange,
      handleCreateApp,
      handleSourceData,
      emptyTextMap,
      handleColumnFilterChange,
      handleSpanTypeChange,
      handleInterfaceStatisticsChange,
      handleServiceStatisticsChange,
      handleTraceTypeChange,
      t,
    };
  },
  render() {
    const {
      queryType,
      emptyApp,
      traceListTableLoading,
      isAlreadyAccurateQuery,
      isAlreadyScopeQuery,
      appList,
      searchIdType,
      spanDetails,
      traceColumnFilters,
    } = this.$props;

    /** 精确查询结果 traceInfo or spanDetails */
    const accurateContent =
      searchIdType === 'traceID' ? (
        <TraceDetail appName={this.appName} />
      ) : (
        spanDetails && (
          <SpanDetails
            show={true}
            spanDetails={spanDetails}
            withSideSlider={false}
          />
        )
      );

    const getQueryTypeContent = (type: string) => {
      const isAlreadyQuery = type === 'accurate' ? isAlreadyAccurateQuery : isAlreadyScopeQuery;
      const comp =
        type === 'accurate' ? (
          accurateContent
        ) : (
          <TraceList
            appList={appList}
            appName={this.appName}
            tableLoading={traceListTableLoading}
            traceColumnFilters={traceColumnFilters}
            onColumnFilterChange={val => this.handleColumnFilterChange(val)}
            onColumnSortChange={value => this.$emit('traceListColumnSortChange', value)}
            onInterfaceStatisticsChange={this.handleInterfaceStatisticsChange}
            // TODO：这里不应该逐层冒泡 onQuery 事件。后续优化
            onListTypeChange={() => this.$emit('listTypeChange')}
            onScrollBottom={() => this.handleScrollBottom()}
            onServiceStatisticsChange={this.handleServiceStatisticsChange}
            onSortChange={sortKey => this.handleSortChange(sortKey)}
            onSpanTypeChange={this.handleSpanTypeChange}
            onStatusChange={id => this.handleStatusChange(id)}
            onTraceTypeChange={this.handleTraceTypeChange}
          />
        );

      if (!isAlreadyQuery) {
        return defaultContent();
      }

      if (this.isEmptyResult) {
        return (
          <div class='search-empty-page'>
            <EmptyStatus type='search-empty'>
              <div class='search-empty-content'>
                <div class='tips'>{this.t('你可以按照以下方式优化检索结果')}</div>
                <div class='description'>1.{this.t('检查应用选择是否正确')}</div>
                <div class='description'>
                  2.{this.t('检查')}
                  <span
                    class='link'
                    onClick={() => this.handleSourceData()}
                  >
                    {this.t('数据源配置')}
                  </span>
                  {this.t('情况')}
                </div>
                <div class='description'>3.{this.t('是否启用了采样，采样不保证全量数据')}</div>
              </div>
            </EmptyStatus>
          </div>
        );
      }

      return comp;
    };

    const defaultContent = () => (
      <div class='default-empty-main'>
        <div
          class='intro-card'
          onClick={() => this.$emit('changeQuery', 'accurate')}
        >
          <h5 class='title'>{this.t('有明确的 ID')}</h5>
          <p class='desc'>
            <i18n-t keypath='直接进行{0}，定位到 Trace 详情'>
              <span class='query-type'>{this.t('精准查询')}</span>
            </i18n-t>
          </p>
          <img
            alt=''
            src={PreciseQueryImg}
          />
        </div>
        <div
          class='intro-card'
          onClick={() => this.$emit('changeQuery', 'scope')}
        >
          <h5 class='title'>{this.t('无明确的 ID')}</h5>
          <p class='desc'>
            <i18n-t keypath='可以切换到{0}，根据条件筛选 Trace'>
              <span class='query-type'>{this.t('范围查询')}</span>
            </i18n-t>
          </p>
          <img
            alt=''
            src={RangeQueryImg}
          />
        </div>
      </div>
    );

    return (
      <div class='inquire-content'>
        {emptyApp ? (
          <div class='create-app-guide'>
            <EmptyStatus
              textMap={this.emptyTextMap}
              type='empty-app'
            >
              <p class='subTitle'>
                <i18n-t keypath='无法查询调用链，请先 {0}'>
                  <span onClick={() => this.handleCreateApp()}>{this.t('创建应用')}</span>
                </i18n-t>
              </p>
            </EmptyStatus>
          </div>
        ) : (
          getQueryTypeContent(queryType || 'accurate')
        )}
      </div>
    );
  },
});
