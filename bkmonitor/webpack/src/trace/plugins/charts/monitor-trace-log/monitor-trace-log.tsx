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
import {
  type ComputedRef,
  type Ref,
  computed,
  defineComponent,
  inject,
  nextTick,
  onActivated,
  onBeforeUnmount,
  onDeactivated,
  ref,
  shallowRef,
  watch,
} from 'vue';

import {
  i18n,
  initGlobalComponents,
  initMonitorState,
  initWindowState,
  MonitorTraceLog as Log,
  logStore,
  Vue2,
} from '@blueking/monitor-trace-log/main';
import { Button, Exception } from 'bkui-vue';
import { serviceLogInfo, serviceRelationList } from 'monitor-api/modules/apm_log';
import { useI18n } from 'vue-i18n';

import { handleTransformToTimestamp } from '../../../components/time-range/utils';
import { useAppStore } from '../../../store/modules/app';
import { useSpanDetailQueryStore } from '../../../store/modules/span-detail-query';
import { REFRESH_IMMEDIATE_KEY, REFRESH_INTERVAL_KEY, useTimeRangeInject } from '../../hooks';
import { useTraceExploreStore } from '@/store/modules/explore';

import './monitor-trace-log.scss';
import '@blueking/monitor-trace-log/css/main.css';
window.AJAX_URL_PREFIX = '/apm_log_forward/bklog/api/v1';
export const APM_LOG_ROUTER_QUERY_KEYS = ['search_mode', 'addition', 'keyword'];
export default defineComponent({
  name: 'MonitorTraceLog',
  setup() {
    const { t } = useI18n();
    const spanDetailQueryStore = useSpanDetailQueryStore();
    const traceStore = useTraceExploreStore();
    const empty = ref(true);
    const loading = ref(true);
    const injectedBizId = inject<Ref<number | string> | undefined>('bizId', undefined);
    const bizId = computed(() => {
      const fromInject = injectedBizId?.value;
      if (fromInject != null && fromInject !== '' && !Number.isNaN(+fromInject)) {
        return +fromInject;
      }
      return +(useAppStore().bizId || window.bk_biz_id || window.cc_biz_id || 0);
    });

    const serviceName = inject<Ref<string>>('serviceName');
    const appName = inject<Ref<string>>('appName');
    const refreshImmediate = inject<Ref<string>>(REFRESH_IMMEDIATE_KEY, shallowRef(traceStore.refreshImmediate));
    const refreshInterval = inject<Ref<number>>(REFRESH_INTERVAL_KEY, shallowRef(traceStore.refreshInterval));
    const spanId = inject<Ref<string>>('spanId', ref(''));
    const traceId = inject<Ref<string>>('traceId', ref(''));

    const mainRef = ref<HTMLDivElement>();
    let logAppInstance: any;
    /**
     * monitor-apm-log / monitor-trace-log 都会写同一组 window 全局标记与 mainComponent。
     * 在 APM 日志页嵌套打开 Trace 详情日志 tab 时，若不在卸载时还原，外层会一直按 Trace 模式运行：
     * - __IS_MONITOR_TRACE__=true 会关闭行悬浮「关联Trace检索」
     * - 划词「添加到本次检索」也会被提前 return 掉
     */
    const hostWindowState = {
      mainComponent: window.mainComponent,
      __IS_MONITOR_COMPONENT__: window.__IS_MONITOR_COMPONENT__,
      __IS_MONITOR_TRACE__: window.__IS_MONITOR_TRACE__,
      __IS_MONITOR_APM__: window.__IS_MONITOR_APM__,
    };
    const restoreHostWindowState = () => {
      window.mainComponent = hostWindowState.mainComponent;
      window.__IS_MONITOR_COMPONENT__ = hostWindowState.__IS_MONITOR_COMPONENT__;
      window.__IS_MONITOR_TRACE__ = hostWindowState.__IS_MONITOR_TRACE__;
      window.__IS_MONITOR_APM__ = hostWindowState.__IS_MONITOR_APM__;
    };
    const destroyLogAppInstance = () => {
      if (!logAppInstance) {
        return;
      }
      logStore.commit('resetState');
      // 只销毁本组件创建的实例，避免误毁外层 APM 的 window.mainComponent
      if (window.mainComponent === logAppInstance) {
        window.mainComponent = null;
      }
      logAppInstance.$destroy();
      logAppInstance = null;
    };
    const customTimeProvider = inject<ComputedRef<string[]>>(
      'customTimeProvider',
      computed(() => traceStore.timeRange)
    );
    const defaultTimeRange = useTimeRangeInject();
    const timeRange = computed(() => {
      // 如果有自定义时间取自定义时间，否则使用默认的 timeRange inject
      return customTimeProvider.value?.length ? customTimeProvider.value : defaultTimeRange?.value || [];
    });
    const isTraceDetail = computed(() => traceId.value && !spanId.value);

    const logInstance = null;
    const unPropsWatch = watch([timeRange, refreshImmediate, refreshInterval], () => {
      logInstance?.$forceUpdate?.();
    });

    async function init() {
      destroyLogAppInstance();
      empty.value = true;
      loading.value = true;
      initWindowState();
      const data = await getServiceLogInfo();
      loading.value = false;
      if (data && empty.value) {
        empty.value = false;
        const targetBizId = bizId.value || window.bk_biz_id;
        const spaceUid = window.space_list.find(item => +item.bk_biz_id === +targetBizId)?.space_uid || targetBizId;
        window.space_uid = `${spaceUid}`;
        initMonitorState({
          bkBizId: targetBizId,
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
            spanDetailQueryStore.queryData = { ...query };
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
        logAppInstance = new Vue2({
          store: logStore,
          i18n,
          render: h => {
            return h(Log, {
              ref: 'componentRef',
              props: {
                indexSetApi,
                timeRange: timeRange.value,
                refreshImmediate: refreshImmediate.value,
                refreshInterval: refreshInterval.value,
              },
            });
          },
        });
        logAppInstance.$router = fakeRouter;
        logAppInstance.$route = fakeRoute;
        logAppInstance._$route = fakeRoute;
        logAppInstance.$t = (...args) => i18n.t(...args);
        await nextTick();
        logAppInstance.$mount(mainRef.value);
        window.mainComponent = logAppInstance;
      } else {
        empty.value = true;
        // 未成功挂载时也要还原，避免残留 Trace 模式标记影响外层 APM 日志
        restoreHostWindowState();
      }
    }

    async function indexSetApi() {
      const [startTime, endTime] = handleTransformToTimestamp(timeRange.value);
      if (!startTime || !endTime) {
        return [];
      }
      const params = isTraceDetail.value
        ? {
            app_name: appName.value,
            trace_id: traceId.value,
            start_time: startTime,
            end_time: endTime,
          }
        : {
            app_name: appName.value,
            service_name: serviceName.value,
            start_time: startTime,
            end_time: endTime,
            span_id: spanId.value,
          };
      const data = await serviceRelationList(params).catch(() => []);
      return data;
    }

    async function getServiceLogInfo() {
      const [startTime, endTime] = handleTransformToTimestamp(timeRange.value);
      if (!startTime || !endTime) {
        return [];
      }
      const params = isTraceDetail.value
        ? {
            app_name: appName.value,
            trace_id: traceId.value,
          }
        : {
            app_name: appName.value,
            service_name: serviceName.value,
            start_time: startTime,
            end_time: endTime,
            span_id: spanId.value,
          };
      const data = await serviceLogInfo(params)
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

    init();

    // ExploreTraceSlider 使用 KeepAlive，关闭侧边栏只会 deactivated，不会 unmount
    onDeactivated(() => {
      restoreHostWindowState();
    });
    onActivated(() => {
      initWindowState();
      if (logAppInstance && !logAppInstance._isDestroyed) {
        window.mainComponent = logAppInstance;
      }
    });

    onBeforeUnmount(() => {
      destroyLogAppInstance();
      restoreHostWindowState();
      unPropsWatch?.();
    });

    return {
      mainRef,
      empty,
      loading,
      handleRelated,
      t,
    };
  },
  render() {
    return (
      <div class='monitor-trace-log'>
        {this.empty ? (
          <div class='empty-chart-log'>
            {this.loading ? (
              this.t('加载中...')
            ) : (
              <Exception type='building'>
                <span>{this.t('暂无关联日志')}</span>
                <div class='text-wrap'>
                  <pre class='text-row'>
                    {this.t(
                      '关联日志方法：\n1. 开启应用的日志上报开关，开启后会自动关联对应的索引集\n2. 在服务配置 - 关联日志出关联对应索引集\n3. 在 Span 中增加 IP 地址，将会自动关联此主机对应的采集项'
                    )}
                  </pre>
                  <Button
                    theme='primary'
                    onClick={() => this.handleRelated()}
                  >
                    {this.t('日志采集')}
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
