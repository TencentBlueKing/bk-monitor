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

import useStore from '@/hooks/use-store';
import { computed, defineComponent, provide, watch } from 'vue';

import { TimeRangeType } from '../../../components/time-range/time-range';
import { handleTransformToTimestamp } from '../../../components/time-range/utils';
import { updateTimezone } from '../../../language/dayjs';
import '../../../static/font-face/index.css';
import '../../../static/style.css';
import { BK_LOG_STORAGE } from '../../../store/store.type';
import V3Container from '../container';
import V3Collection from '../favorite';
import V3Searchbar from '../search-bar';
import V3SearchResult from '../search-result';
import V3Toolbar from '../toolbar';

import './monitor.scss';
import useMonitorAppInit from './use-monitor-app-init';
export default defineComponent({
  name: 'RetrieveV3',
  props: {
    handleChartDataZoom: {
      default: null,
      type: Function,
    },
    indexSetApi: {
      default: null,
      type: Function,
    },
    refreshImmediate: {
      default: '',
      type: String,
    },
    timeRange: {
      default: () => ['now-15m', 'now'],
      type: Array,
    },
    timezone: {
      default: '',
      type: String,
    },
  },
  setup(props) {
    const store = useStore();
    provide('handleChartDataZoom', props.handleChartDataZoom);
    const {
      getIndexSetList,
      isPreApiLoaded,
      isSearchContextStickyTop,
      isSearchResultStickyTop,
      setDefaultRouteUrl,
      stickyStyle,
    } = useMonitorAppInit(props.indexSetApi);
    const isStartTextEllipsis = computed(
      () => store.state.storage[BK_LOG_STORAGE.TEXT_ELLIPSIS_DIR] === 'start'
    );
    const init = () => {
      const result = handleTransformToTimestamp(
        props.timeRange as TimeRangeType,
        store.getters.retrieveParams.format
      );
      store.commit('updateIndexItem', {
        datePickerValue: props.timeRange,
        end_time: result[1],
        start_time: result[0],
      });
      setDefaultRouteUrl();
    };
    init();

    const isMonitorTraceComponent = window.__IS_MONITOR_TRACE__;

    watch(
      () => props.timeRange,
      async (val) => {
        if (!val) return;
        getIndexSetList();
        store.commit('updateIsSetDefaultTableColumn', false);
        const result = handleTransformToTimestamp(
          val as TimeRangeType,
          store.getters.retrieveParams.format
        );
        store.commit('updateIndexItemParams', {
          datePickerValue: val,
          end_time: result[1],
          start_time: result[0],
        });
        await store.dispatch('requestIndexSetFieldInfo');
        store.dispatch('requestIndexSetQuery');
      }
    );

    watch(
      () => props.timezone,
      (val) => {
        if (!val) return;
        store.commit('updateIndexItemParams', { timezone: val });
        updateTimezone(val);
        store.dispatch('requestIndexSetQuery');
      }
    );

    watch(
      () => props.refreshImmediate,
      () => {
        store.dispatch('requestIndexSetQuery');
      }
    );

    const renderResultContent = () => {
      if (isPreApiLoaded.value) {
        return (
          <div class="v3-bklog-content" style="width: 100%">
            <V3Toolbar></V3Toolbar>
            <V3Container>
              <V3Searchbar
                class={{
                  'is-sticky-top': isSearchContextStickyTop.value,
                  'is-sticky-top-result': isSearchResultStickyTop.value,
                }}
              ></V3Searchbar>
              <V3SearchResult></V3SearchResult>
            </V3Container>
          </div>
        );
      }

      return <div style={{ minHeight: '50vh', width: '100%' }}></div>;
    };

    return () => (
      <div
        class={[
          'v3-bklog-root',
          { 'is-start-text-ellipsis': isStartTextEllipsis.value },
          {
            'is-sticky-top': isSearchContextStickyTop.value,
            'is-sticky-top-result': isSearchResultStickyTop.value,
            'is-trace': isMonitorTraceComponent,
          },
        ]}
        style={stickyStyle.value}
        v-bkloading={{ isLoading: !isPreApiLoaded.value }}
      >
        <V3Collection></V3Collection>
        {renderResultContent()}
      </div>
    );
  },
});
