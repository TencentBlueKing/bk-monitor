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
import { defineComponent, inject, ref, computed, type Ref, onUnmounted, onMounted, nextTick, watch } from 'vue';

import {
  MonitorRetrieve as Log,
  initMonitorState,
  initGlobalComponents,
  Vue2,
  logStore,
  i18n,
} from '@blueking/monitor-trace-log/main';
import { Button, Exception } from 'bkui-vue';
import { serviceRelationList, serviceLogInfo } from 'monitor-api/modules/apm_log';

import { handleTransformToTimestamp, type TimeRangeType } from '../../../components/time-range/utils';
import { useAppStore } from '../../../store/modules/app';
import { REFLESH_IMMEDIATE_KEY, REFLESH_INTERVAL_KEY, TIME_RANGE_KEY } from '../../hooks';

import './monitor-trace-log.scss';
import '@blueking/monitor-trace-log/css/main.css';
window.AJAX_URL_PREFIX = '/apm_log_forward/bklog/api/v1';
export const APM_LOG_ROUTER_QUERY_KEYS = ['search_mode', 'addition', 'keyword'];
export default defineComponent({
  name: 'MonitorTraceLog',
  setup() {
    const empty = ref(true);
    const loading = ref(true);
    const bizId = computed(() => useAppStore().bizId || 0);
    const serviceName = inject<Ref<string>>('serviceName');
    const appName = inject<Ref<string>>('appName');
    const timeRange = inject<Ref<TimeRangeType>>(TIME_RANGE_KEY);
    const refleshImmediate = inject<Ref<string>>(REFLESH_IMMEDIATE_KEY);
    const refleshInterval = inject<Ref<number>>(REFLESH_INTERVAL_KEY);
    const spanId = inject<Ref<string>>('spanId', ref(''));
    const mainRef = ref<HTMLDivElement>();

    let unPropsWatch = null;

    async function init() {
      empty.value = true;
      loading.value = true;
      const data = await getServiceLogInfo();
      loading.value = false;
      if (data && empty.value) {
        empty.value = false;
        const spaceUid =
          window.space_list.find(item => +item.bk_biz_id === +window.bk_biz_id)?.space_uid || window.bk_biz_id;
        window.space_uid = `${spaceUid}`;
        initMonitorState({
          bkBizId: window.bk_biz_id,
          spaceUid,
        });
        initGlobalComponents();
        const fakeRoute = {
          query: {},
          params: {},
        };
        const fakeRouter = {
          get currentRoute() {
            return fakeRoute;
          },
          replace: c => {
            const { query = {}, params = {} } = c;
            fakeRoute.query = query;
            fakeRoute.params = params;
          },
          push: () => {
            return {};
          },
          resolve: () => {
            return {};
          },
        };
        Vue2.prototype.$router = fakeRouter;
        Vue2.prototype.$route = fakeRoute;
        const app: any = new Vue2({
          store: logStore,
          i18n,
          render: h => {
            return h(Log, {
              ref: 'componentRef',
              props: {
                indexSetApi,
                timeRange: timeRange.value,
                refleshImmediate: refleshImmediate.value,
                refleshInterval: refleshInterval.value,
              },
            });
          },
        });
        app.$router = fakeRouter;
        app.$route = fakeRoute;
        app._$route = fakeRoute;
        app.$t = (...args) => i18n.t(...args);
        unPropsWatch = watch([timeRange, refleshImmediate, refleshInterval], () => {
          app.$forceUpdate();
        });
        await nextTick();
        app.$mount(mainRef.value);
        window.mainComponent = app;
      } else {
        empty.value = true;
      }
    }

    async function indexSetApi() {
      const [startTime, endTime] = handleTransformToTimestamp(timeRange.value);
      const data = await serviceRelationList({
        app_name: appName.value,
        service_name: serviceName.value,
        start_time: startTime,
        end_time: endTime,
        span_id: spanId.value,
      }).catch(() => []);
      return data;
    }

    async function getServiceLogInfo() {
      const [startTime, endTime] = handleTransformToTimestamp(timeRange.value);
      const data = await serviceLogInfo({
        app_name: appName.value,
        service_name: serviceName.value,
        start_time: startTime,
        end_time: endTime,
        span_id: spanId.value,
      })
        .then(data => {
          return !!data;
        })
        .catch(() => {
          return true;
        });
      return data;
    }

    /**
     * @desc 关联日志
     */
    function handleRelated() {
      const url = `${window.bk_log_search_url}#/manage/log-collection/collection-item?bizId=${
        bizId.value || window.bk_biz_id
      }`;
      window.open(url);
    }

    watch(
      () => spanId.value,
      () => {
        init();
      }
    );

    onMounted(() => {
      init();
    });

    onUnmounted(() => {
      if (!empty.value) {
        logStore.commit('resetState');
        window.mainComponent.$destroy();
        window.mainComponent = null;
        unPropsWatch?.();
      }
    });

    return {
      mainRef,
      empty,
      loading,
      handleRelated,
    };
  },
  render() {
    return (
      <div class='monitor-trace-log'>
        {this.empty ? (
          <div class='empty-chart-log'>
            {this.loading ? (
              window.i18n.tc('加载中...')
            ) : (
              <Exception type='building'>
                <span>{this.$t('暂无关联日志')}</span>
                <div class='text-wrap'>
                  <pre class='text-row'>
                    {this.$t(
                      '关联日志方法：\n1. 开启应用的日志上报开关，开启后会自动关联对应的索引集\n2. 在服务配置 - 关联日志出关联对应索引集\n3. 在 Span 中增加 IP 地址，将会自动关联此主机对应的采集项'
                    )}
                  </pre>
                  <Button
                    theme='primary'
                    onClick={() => this.handleRelated()}
                  >
                    {this.$t('日志采集')}
                  </Button>
                </div>
              </Exception>
            )}
          </div>
        ) : (
          <div
            id='trace-log'
            ref='mainRef'
          />
        )}
      </div>
    );
  },
});
