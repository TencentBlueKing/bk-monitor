/* eslint-disable @typescript-eslint/naming-convention */
/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台社区版 (BlueKing PaaS Community Edition) available.
 *
 * Copyright (C) 2017-2025 Tencent.  All rights reserved.
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
import { type PropType, computed, defineComponent, provide, reactive, ref, watch } from 'vue';
import { shallowRef } from 'vue';

import { Button, Exception, Loading, Message, Popover, Sideslider, Switcher, Tab } from 'bkui-vue';
import { EnlargeLine } from 'bkui-vue/lib/icon';
import dayjs from 'dayjs';
import { CancelToken } from 'monitor-api/cancel';
import { query as apmProfileQuery } from 'monitor-api/modules/apm_profile';
import { getSceneView } from 'monitor-api/modules/scene_view';
import { copyText, deepClone, random } from 'monitor-common/utils/utils';
import { useI18n } from 'vue-i18n';
import VueJsonPretty from 'vue-json-pretty';

import ExceptionGuide, { type IGuideInfo } from '../../components/exception-guide/exception-guide';
import MonitorTab from '../../components/monitor-tab/monitor-tab';
import { formatDate, formatDuration, formatTime } from '../../components/trace-view/utils/date';
import ProfilingFlameGraph from '../../plugins/charts/profiling-graph/profiling-flame-graph/flame-graph';
import FlexDashboardPanel from '../../plugins/components/flex-dashboard-panel';
import { useIsEnabledProfilingInject } from '../../plugins/hooks';
import { BookMarkModel } from '../../plugins/typings';
import EmptyEvent from '../../static/img/empty-event.svg';
import { SPAN_KIND_MAPS } from '../../store/constant';
import { useAppStore } from '../../store/modules/app';
import { useSpanDetailQueryStore } from '../../store/modules/span-detail-query';
import { useTraceStore } from '../../store/modules/trace';
import {
  type IInfo,
  type IStageTimeItem,
  type IStageTimeItemContent,
  type ITagContent,
  type ITagsItem,
  EListItemType,
} from '../../typings/trace';
import { downFile } from '../../utils';
import { SPAN_KIND_MAPS as SPAN_KIND_MAPS_NEW } from '../trace-explore/components/trace-explore-table/constants';
import { safeParseJsonValueForWhere } from '../trace-explore/utils';
// import AiBluekingIcon from '@/components/ai-blueking-icon/ai-blueking-icon';
import DashboardPanel from './dashboard-panel/dashboard-panel';
import DecodeDialog from '@/components/decode-dialog/decode-dialog';

import type { Span } from '../../components/trace-view/typings';
import type { IFlameGraphDataItem } from 'monitor-ui/chart-plugins/hooks/profiling-graph/types';

import './span-details.scss';
import 'vue-json-pretty/lib/styles.css';
const guideInfoData: Record<string, IGuideInfo> = {
  Event: {
    type: '',
    icon: EmptyEvent,
    title: window.i18n.t('当前无异常事件'),
    subTitle: window.i18n.t('异常事件获取来源\n1. events.attributes.exception_stacktrace 字段\n2. status.message 字段'),
    link: null,
  },
  // Log: {},
  // Host: {},
  // Process: {},
  // Container: {},
  // Index: {}
};

type TabName = 'BasicInfo' | 'Container' | 'Event' | 'Host' | 'Index' | 'Log' | 'Process' | 'Profiling';
export default defineComponent({
  name: 'SpanDetails',
  props: {
    show: { type: Boolean, default: false },
    isShowPrevNextButtons: { type: Boolean, default: false }, // 是否展示上一跳/下一跳
    withSideSlider: { type: Boolean, default: true }, // 详情信息在侧滑弹窗展示
    spanDetails: { type: Object as PropType<Span>, default: () => null },
    isFullscreen: { type: Boolean, default: false } /* 当前是否为全屏状态 */,
    isPageLoading: { type: Boolean, default: false },
    activeTab: { type: String, default: 'BasicInfo' },
  },
  emits: ['show', 'prevNextClicked'],
  setup(props, { emit }) {
    const store = useTraceStore();
    const spanDetailQueryStore = useSpanDetailQueryStore();
    const { t } = useI18n();
    /* 侧栏show */
    const localShow = ref(false);
    /* 详情数据 */
    const tempInfo = {
      title: '',
      header: {
        title: '',
        timeTag: '',
        others: [],
      },
      list: [],
    };
    const info = reactive<IInfo>(deepClone(tempInfo));

    /** 切换显示原始数据 */
    const showOriginalData = ref(false);

    /** 原始数据 */
    const originalData = ref<null | Record<string, any>>(null);

    /* 当前应用名称 */
    const appName = computed(() => store.traceData.appName);

    const spanStatus = computed<{ alias: string; icon: string }>(() => {
      const statusMap = {
        0: { alias: t('未设置'), icon: 'warning' },
        1: { alias: t('正常'), icon: 'normal' },
        2: { alias: t('异常'), icon: 'failed' },
      };
      const status = props.spanDetails?.attributes?.find(item => item.query_key === 'status.code')?.query_value;
      return statusMap[status];
    });

    const fullscreen = shallowRef(false);

    const ellipsisDirection = computed(() => store.ellipsisDirection);

    const bizId = computed(() => useAppStore().bizId || 0);

    const spans = computed(() => store.spanGroupTree);

    const profilingFlameGraph = shallowRef<IFlameGraphDataItem>(null);

    /** 主机容器接口 */
    let hostAndContainerCancelToken = null;

    // const countOfInfo = ref<object | Record<TabName, number>>({});
    const enableProfiling = useIsEnabledProfilingInject();
    const activeTab = shallowRef<TabName>('BasicInfo');

    /** 主机和容器的自定义时间，不走右上角的时间选择器 */
    const customTimeProvider = computed(() => {
      if (activeTab.value === 'Container' || activeTab.value === 'Host' || activeTab.value === 'Log') {
        const diff = dayjs(spanEndTime.value).diff(dayjs(spanStartTime.value), 'millisecond');
        /**
         * 2025/2/12 容器，主机，日志 时间规则调整
           【如果 end_time - start_time 没超过 2 小时，即 span 跨度在 2 小时内】
           1.  如果 span 的 end_time 比当前一小时外，那么时间范围就是 span 的 start_time - 1h 到 span 的 end_time + 1h
           2.  如果 span 的 end_time 在当前一小时内，那么时间范围就是 span 的 start_time - 1h 到当前时间
           【如果 end_time - start_time 超过 2 小时】
           时间范围固定为：end_time - 2h ，  end_time
         */
        /** end_time - start_time 没超过 2 小时 */
        if (Math.abs(diff) <= 2 * 60 * 60 * 1000) {
          const diff2 = dayjs().diff(dayjs(spanEndTime.value), 'millisecond');
          // span 的 end_time 在当前一小时内
          if (Math.abs(diff2) <= 60 * 60 * 1000)
            return [
              dayjs(spanStartTime.value).subtract(1, 'hour').format('YYYY-MM-DD HH:mm:ss'),
              dayjs().format('YYYY-MM-DD HH:mm:ss'),
            ];
          return [
            dayjs(spanStartTime.value).subtract(1, 'hour').format('YYYY-MM-DD HH:mm:ss'),
            dayjs(spanEndTime.value).add(1, 'hour').format('YYYY-MM-DD HH:mm:ss'),
          ];
        }
        return [
          dayjs(spanEndTime.value).subtract(2, 'hour').format('YYYY-MM-DD HH:mm:ss'),
          dayjs(spanEndTime.value).format('YYYY-MM-DD HH:mm:ss'),
        ];
      }
      return [];
    });
    provide('customTimeProvider', customTimeProvider);

    const serviceNameProvider = ref('');
    // 服务、应用 名在日志 tab 里能用到
    provide('serviceName', serviceNameProvider);
    provide('appName', appName);

    // 用于关联日志跳转信息
    const traceId = ref('');
    provide('traceId', traceId);
    const spanTime = ref(0);
    const spanStartTime = ref(0);
    const spanEndTime = ref(0);
    const originSpanStartTime = ref(0);
    provide('originSpanStartTime', originSpanStartTime);
    const originSpanEndTime = ref(0);
    provide('originSpanEndTime', originSpanEndTime);

    const spanId = computed(() => props.spanDetails.span_id);
    provide('spanId', spanId);
    // 用作 Event 栏的首行打开。
    let isInvokeOnceFlag = true;
    /* 初始化 */
    watch(
      () => props.show,
      (value: boolean) => {
        // 异步加载数据时，需要重置数据，不然会看到上一次打开的数据。
        Object.assign(info, deepClone(tempInfo));
        localShow.value = value;
        if (value) {
          // 这里提前执行，如果是碰到异步加载，这里会报错，这里做了兼容处理。
          if (!props.isPageLoading) getDetails();
          if (props.isFullscreen && !document.querySelector('.bk-modal-outside')) {
            const maskEle = document.createElement('div');
            maskEle.className = 'bk-modal-outside';
            document.querySelector('.span-details-sideslider')?.appendChild(maskEle);
          }
        } else {
          isInvokeOnceFlag = true;
          activeTab.value = 'BasicInfo';
          // countOfInfo.value = {};
          fullscreen.value = false;
        }
      },
      {
        immediate: true,
      }
    );

    // 上面监听 props.show 里会直接执行 getDetails() ，这里因为要添加loading，
    // 且需要保证之前用到该组件的地方能正常运行，这里添加兼容代码。保证使用loading与否，都可以正常显示数据。
    watch(
      () => props.isPageLoading,
      (value: boolean) => {
        if (!value) {
          getDetails();
        }
      }
    );

    watch(
      () => props.spanDetails,
      val => {
        if (val && (!props.withSideSlider || (props.isShowPrevNextButtons && Object.keys(val).length))) {
          getDetails();
        }
      },
      { immediate: true, deep: true }
    );

    /** 获取 span 类型描述 */
    function getTypeText() {
      const { kind, source, ebpf_kind: ebpfKind, is_virtual: isVirtual } = props.spanDetails;
      if (isVirtual) return t('推断');
      if (source === 'ebpf') return ebpfKind;
      return SPAN_KIND_MAPS[kind];
    }

    /* 获取详情数据 */
    function getDetails() {
      const {
        span_id: originalSpanId,
        app_name: appName,
        service_name: serviceName,
        duration,
        startTime,
        operationName,
        attributes,
        events,
        process,
        source,
        stage_duration,
        resource: spanResource,
      } = props.spanDetails as any | Span;
      // 服务、应用 名在日志 tab 里能用到
      serviceNameProvider.value = serviceName;
      const originalDataList = [...store.traceData.original_data, ...store.compareTraceOriginalData];
      // 根据span_id获取原始数据
      const curSpan = originalDataList.find((data: any) => data.span_id === originalSpanId);
      if (!curSpan) return;
      spanStartTime.value = Math.floor(curSpan.start_time / 1000) || 0;
      spanEndTime.value = Math.floor(curSpan.end_time / 1000) || 0;
      spanTime.value = Number(curSpan.time || 0);
      originSpanStartTime.value = Math.floor(startTime / 1000);
      originSpanEndTime.value = Math.floor((startTime + duration) / 1000);
      if (curSpan) originalData.value = handleFormatJson(curSpan);
      const {
        kind,
        trace_id: originTraceId,
        resource,
        is_virtual: isVirtual,
      } = originalData.value as Record<string, any>;
      traceId.value = originTraceId;

      info.title = originalSpanId;
      /** 头部基本信息 */
      info.header = {
        title: operationName,
        timeTag: formatDuration(duration),
        others: [
          {
            label: t('服务'),
            content: (
              <span
                style='max-width: 168px'
                class='link'
                onClick={() => handleToServiceName(serviceName)}
              >
                <i class='icon-monitor icon-wangye' />
                <span>{serviceName}</span>
                <i class='icon-monitor icon-fenxiang' />
              </span>
            ),
            title: serviceName,
          },
          {
            label: t('应用'),
            content: (
              <span
                style='max-width: 168px'
                class='link'
                onClick={() => handleToAppName(appName)}
              >
                <span>{appName}</span>
                <i class='icon-monitor icon-fenxiang' />
              </span>
            ),
            title: appName,
          },
          // { label: '日志', content: logs.length ? '有日志' :  '无日志' },
          {
            label: t('开始时间'),
            content: dayjs.tz(startTime / 1e3).format('YYYY-MM-DD HH:mm:ss'),
            title: dayjs.tz(startTime / 1e3).format('YYYY-MM-DD HH:mm:ss'),
          },
          {
            label: t('来源'),
            content: source || '--',
            title: source || '',
          },
          {
            label: t('类型'),
            content: (
              <span class='content-detail-type'>
                {/* {!isVirtual && <i class={`icon-monitor icon-type icon-${getTypeIcon()}`} />} */}
                {!isVirtual && kind < 6 && (SPAN_KIND_MAPS_NEW[kind].prefixIcon as () => any)()}
                <span>{getTypeText()}</span>
              </span>
            ),
            title: SPAN_KIND_MAPS[kind],
          },
          {
            label: t('SDK 版本'),
            content: resource['telemetry.sdk.version'] || '--',
            title: resource['telemetry.sdk.version'] || '',
          },
          {
            label: t('所属 Trace'),
            content: (
              <span
                class='link'
                onClick={() => handleToTraceQuery(traceId.value)}
              >
                <span>{traceId.value}</span>
                <i class='icon-monitor icon-fenxiang' />
              </span>
            ),
            title: traceId.value,
          },
        ],
      };
      info.list = [];
      /** Tags 信息 */
      if (attributes?.length) {
        info.list.push({
          type: EListItemType.tags,
          isExpan: true,
          title: 'Attributes',
          [EListItemType.tags]: {
            list:
              attributes.map(
                (item: { key: string; query_key: string; query_value: any; type: string; value: string }) => ({
                  label: item.key,
                  content: item.value === '' || item.value == null ? '--' : item.value,
                  type: item.type,
                  isFormat: false,
                  query_key: item.query_key,
                  query_value: item.query_value,
                })
              ) || [],
          },
        });
      }
      /** 阶段耗时信息 */
      if (stage_duration) {
        const active = stage_duration[stage_duration.target].type;
        info.list.push({
          type: EListItemType.stageTime,
          isExpan: true,
          title: t('阶段耗时 (同步)'),
          [EListItemType.stageTime]: {
            active,
            list: [
              {
                id: stage_duration.left.type,
                label: stage_duration.left.label,
                error: stage_duration.left.error,
                errorMsg: stage_duration.left.error_message,
              },
              {
                id: stage_duration.right.type,
                label: stage_duration.right.label,
                error: stage_duration.right.error,
                errorMsg: stage_duration.right.error_message,
              },
            ],
            content: {
              [active]: [
                {
                  type: 'useTime',
                  useTime: {
                    tags: [
                      `send: ${formatDate(stage_duration.left.start_time)} ${formatTime(
                        stage_duration.left.start_time,
                        true
                      )}`,
                      `receive: ${formatDate(stage_duration.right.start_time)} ${formatTime(
                        stage_duration.right.start_time,
                        true
                      )}`,
                    ],
                    gap: {
                      type: 'toRight',
                      value: formatDuration(stage_duration.right.start_time - stage_duration.left.start_time),
                    },
                  },
                },
                {
                  type: 'gapTime',
                  gapTime: formatDuration(stage_duration.right.end_time - stage_duration.right.start_time),
                },
                {
                  type: 'useTime',
                  useTime: {
                    tags: [
                      `receive: ${formatDate(stage_duration.left.end_time)} ${formatTime(
                        stage_duration.left.end_time,
                        true
                      )}`,
                      `send: ${formatDate(stage_duration.right.end_time)} ${formatTime(
                        stage_duration.right.end_time,
                        true
                      )}`,
                    ],
                    gap: {
                      type: 'toLeft',
                      value: formatDuration(stage_duration.left.end_time - stage_duration.right.end_time),
                    },
                  },
                },
              ],
            },
          },
        });
      }
      const processTags = spanResource || process?.tags || [];
      /** process信息 */
      if (processTags.length) {
        info.list.push({
          type: EListItemType.tags,
          isExpan: true,
          title: 'Resource',
          [EListItemType.tags]: {
            list:
              processTags.map((item: { key: any; query_key: string; query_value: any; type: string; value: any }) => ({
                label: item.key,
                content: item.value === '' || item.value == null ? '--' : item.value,
                type: item.type,
                isFormat: false,
                query_key: item.query_key,
                query_value: item.query_value,
              })) || [],
          },
        });
      }
      /** Events信息 来源：status_message & events */
      if (events?.length) {
        const eventList = [];
        eventList.push(
          ...events
            .sort((a, b) => b.timestamp - a.timestamp)
            .map(
              (item: {
                attributes: { key: string; query_key?: string; query_value?: any; type: string; value: string }[];
                duration: number;
                name: any;
                timestamp: number;
              }) => ({
                isExpan: false,
                header: {
                  timestamp: item.timestamp,
                  date: `${formatDate(item.timestamp)} ${formatTime(item.timestamp)}`,
                  duration: formatDuration(item.duration),
                  name: item.name,
                },
                content: item.attributes.map(attribute => ({
                  label: attribute.key,
                  content: attribute.value === '' || attribute.value == null ? '--' : attribute.value,
                  type: attribute.type,
                  isFormat: false,
                  query_key: attribute?.query_key || '',
                  query_value: attribute?.query_value || '',
                })),
              })
            )
        );
        info.list.push({
          type: EListItemType.events,
          isExpan: true,
          title: 'Events',
          [EListItemType.events]: {
            list: eventList,
          },
        });
      }

      // // TODO：先统计事件的数量
      // info.list.forEach(item => {
      //   if (item.type === EListItemType.events) {
      //     countOfInfo.value = Object.assign({}, { Event: item?.Events?.list?.length || 0 });
      //   }
      // });
    }

    /** 递归检测符合json格式的字符串并转化 */
    function handleFormatJson(obj: Record<string, any>) {
      try {
        const newData: Record<string, any> = {};
        Object.keys(obj).forEach(item => {
          if (Object.prototype.toString.call(obj[item]) === '[object Object]') {
            // 对象 遍历属性
            newData[item] = handleFormatJson(obj[item]);
          } else if (Object.prototype.toString.call(obj[item]) === '[object Array]') {
            // 数组对象
            newData[item] = obj[item].map((arrItme: Record<string, any>) => {
              if (typeof arrItme === 'string') {
                return arrItme;
              }
              return handleFormatJson(arrItme);
            });
          } else if (typeof obj[item] === 'string' && isJson(obj[item])) {
            // 符合json格式的字符串
            newData[item] = handleFormatJson(JSON.parse(obj[item]));
          } else {
            newData[item] = obj[item];
          }
        });
        return newData;
      } catch {
        return obj;
      }
    }

    /* 关闭侧栏 */
    const handleHiddenChange = () => {
      localShow.value = false;
      emit('show', localShow.value);
    };

    /* 上一跳/下一跳 */
    const handlePrevNextClick = val => {
      handleActiveTabChange();
      emit('prevNextClicked', val);
    };

    /* 展开收起 */
    const handleExpanChange = (isExpan: boolean, index: number) => {
      info.list[index].isExpan = !isExpan;
    };

    const handleSmallExpanChange = (isExpan: boolean, index: number, childIndex: number) => {
      info.list[index][EListItemType.events].list[childIndex].isExpan = !isExpan;
    };

    /** 添加查询语句查询 */
    const handleKvQuery = (content: ITagContent) => {
      const where = encodeURIComponent(
        JSON.stringify([
          {
            key: content.query_key,
            operator: 'equal',
            value: safeParseJsonValueForWhere(content.query_value),
          },
        ])
      );
      const url = location.href.replace(
        location.hash,
        `#/trace/home?app_name=${appName.value}&sceneMode=span&where=${where}&filterMode=ui`
      );
      window.open(url, '_blank');
    };

    /* 复制kv部分文本 */
    const handleCopy = (content: ITagContent) => {
      const queryStr = `${content.query_key}: "${String(content.query_value)?.replace(/"/g, '\\"') ?? ''}"`; // value转义双引号
      copyText(
        queryStr,
        (msg: string) => {
          Message({
            message: msg,
            theme: 'error',
          });
          return;
        },
        props.isFullscreen ? '.trace-table-main' : ''
      );
      Message({
        theme: 'success',
        message: t('复制成功'),
        width: 200,
      });
    };

    /* event 错误链接 */
    function handleEventErrLink() {
      const { app_name: appName } = props.spanDetails;
      const hash = `#/apm/application?filter-app_name=${appName}&method=AVG&interval=auto&dashboardId=error&from=now-1h&to=now&refreshInterval=-1`;
      const url = location.href.replace(location.hash, hash);
      window.open(url, '_blank');
    }

    /* 跳转到服务 */
    function handleToServiceName(serviceName: string) {
      const { app_name: appName } = props.spanDetails;
      const hash = `#/apm/service?filter-service_name=${serviceName}&filter-app_name=${appName}&method=AVG&interval=auto&from=now-1h&to=now&refreshInterval=-1`;
      const url = location.href.replace(location.hash, hash);
      window.open(url, '_blank');
    }

    /** 跳转到应用 */
    function handleToAppName(appName?: string) {
      const hash = `#/apm/application?filter-app_name=${appName}`;
      const url = location.href.replace(location.hash, hash);
      window.open(url, '_blank');
    }

    /** 跳转traceId精确查询 */
    function handleToTraceQuery(traceId: string) {
      const hash = `#/trace/home?app_name=${appName.value}&sceneMode=trace&trace_id=${traceId}`;
      const url = location.href.replace(location.hash, hash);
      window.open(url, '_blank');
    }

    /** 切换原始数据 */
    function handleOriginalDataChange(val: boolean) {
      showOriginalData.value = val;
    }

    function handleFullScreen(status = false) {
      fullscreen.value = status;
    }

    // 复制操作
    function handleTitleCopy(content: string) {
      let text = '';
      const { spanID } = props.spanDetails;
      switch (content) {
        case 'text': {
          text = spanID;
          break;
        }
        case 'original': {
          text = JSON.stringify(originalData.value);
          break;
        }
        default: {
          const hash = `#${window.__BK_WEWEB_DATA__?.baseroute || '/'}home/?app_name=${
            appName.value
          }&search_type=accurate&search_id=spanID&trace_id=${spanID}`;
          text = location.href.replace(location.hash, hash);
          break;
        }
      }
      copyText(text, (msg: string) => {
        Message({
          message: msg,
          theme: 'error',
        });
        return;
      });
      Message({
        message: window.i18n.t('复制成功'),
        width: 200,
        theme: 'success',
      });
    }

    async function getFlameGraphData() {
      const { start_time, end_time } = getProfilingTimeRange();
      const data: IFlameGraphDataItem = await apmProfileQuery(
        {
          bk_biz_id: bizId.value,
          app_name: appName.value,
          service_name: serviceNameProvider.value,
          start: start_time,
          end: end_time,
          profile_id: originalData.value.span_id,
          diagram_types: ['flamegraph'],
        },
        {
          needCancel: true,
        }
      ).catch(() => null);
      profilingFlameGraph.value = data?.flame_data || [];
    }

    /* 折叠 */
    const expanItem = (
      isExpan: boolean,
      title: string | undefined,
      content: any,
      subTitle: any = '',
      expanChange: (v: boolean) => void
    ) => (
      <div class='expan-item'>
        <div
          class='expan-item-head'
          onClick={() => expanChange(isExpan)}
        >
          <span class={['icon-monitor icon-mc-arrow-down', { active: isExpan }]} />
          <span class='expan-item-title'>{title}</span>
          {subTitle || undefined}
        </div>
        <div class={['expan-item-content', { active: isExpan }]}>{content}</div>
      </div>
    );

    /* 折叠(small) */
    const expanItemSmall = (
      isExpan: boolean,
      title: string,
      content: any,
      subTitle: any = '',
      expanChange: (v: boolean) => void
    ) => (
      <div class='expan-item-small'>
        <div
          class={['expan-item-small-head', 'grey']}
          onClick={() => expanChange(isExpan)}
        >
          <span class={['icon-monitor icon-arrow-down', { active: isExpan }]} />
          <span
            class='title'
            title={title}
          >
            {title}
          </span>
          {subTitle || undefined}
        </div>
        <div class={['expan-item-small-content', { active: isExpan }]}>{content}</div>
      </div>
    );

    /** 判断是否符合Json格式 */
    const isJson = (str?: string) => {
      if (typeof str === 'string') {
        try {
          return typeof JSON.parse(str) === 'object';
        } catch {
          return false;
        }
      }

      return false;
    };

    const formatContent = (content?: number | string, isFormat?: boolean) => {
      if ((typeof content === 'number' && content.toString().length < 10) || typeof content === 'undefined')
        return content;
      if (!isJson(content?.toString())) {
        const str = typeof content === 'string' ? content : JSON.stringify(content);
        return <DecodeDialog content={str} />;
      }
      const data = JSON.parse(content?.toString() || '');
      return isFormat ? <VueJsonPretty data={handleFormatJson(data)} /> : content;
    };

    /** 导出原始数据 json */
    const handleExportOriginData = () => {
      if (originalData.value) {
        const jsonString = JSON.stringify(originalData.value, null, 4);
        const blob = new Blob([jsonString], { type: 'application/json' });
        const fileUrl = URL.createObjectURL(blob);
        downFile(fileUrl, `${originalData.value.span_id}.json`);
      }
    };

    /* kv 结构数据展示 */
    const tagsTemplate = (data: ITagsItem['list']) => {
      data.sort(({ label: labelA }, { label: labelB }) => {
        return labelA.toUpperCase() >= labelB.toUpperCase() ? 1 : -1;
      });
      return (
        <div class='tags-template'>
          {data.map((item, index) => (
            <div
              key={index}
              class={['tags-row', { grey: !(index % 2) }]}
            >
              <span class='left'>
                <span
                  class='left-title'
                  v-overflow-tips
                >
                  {item.label}
                </span>
                <div class='operator'>
                  <EnlargeLine
                    class='icon-add-query'
                    v-bk-tooltips={{
                      content: t('检索'),
                    }}
                    onClick={() => handleKvQuery(item)}
                  />
                  <span
                    class='icon-monitor icon-mc-copy'
                    v-bk-tooltips={{
                      content: t('复制'),
                    }}
                    onClick={() => handleCopy(item)}
                  />
                </div>
              </span>
              {item.type === 'error' ? (
                <div class='right'>
                  <span class='error-text'>{formatContent(item.content, item.isFormat)}</span>
                  <span class='icon-monitor icon-mind-fill' />
                </div>
              ) : (
                <div class='right'>{formatContent(item.content, item.isFormat)}</div>
              )}
              {isJson(item.content) && (
                <Button
                  class='format-button'
                  outline={!item.isFormat}
                  size='small'
                  theme='primary'
                  onClick={() => {
                    item.isFormat = !item.isFormat;
                  }}
                >
                  <i class='icon-monitor icon-code' />
                  {t('格式化')}
                </Button>
              )}
            </div>
          ))}
        </div>
      );
    };

    /* 阶段耗时 */
    const stageTimeTemplate = (active: string, list: IStageTimeItem['list'], content: IStageTimeItemContent[]) => (
      <div class='stage-time'>
        <div class='stage-time-list'>
          {list.map((item, index) => (
            <Popover
              key={index}
              content={item.errorMsg}
              disabled={!item.error || !item.errorMsg}
              placement={'left'}
            >
              <div class={['list-item', { active: active === item.id }]}>
                <span class='title'>{item.id}</span>
                <div class='content'>
                  {item.error ? (
                    <span class='err-point'>
                      <span class='red-point' />
                    </span>
                  ) : undefined}
                  {item.label}
                </div>
              </div>
            </Popover>
          ))}
        </div>
        <div class='stage-time-content'>
          {content.map((item, index) => {
            if (item.type === 'useTime') {
              const times = item[item.type] as any;
              return (
                <div
                  key={index}
                  class='use-time'
                >
                  <span class='left'>{times.tags[0]}</span>
                  <span class='center'>
                    {times.gap.type === 'toLeft'
                      ? [
                          <span
                            key={1}
                            class='to-left'
                          />,
                          <span
                            key={2}
                            class='center-text'
                          >
                            {times.gap.value}
                          </span>,
                          <span
                            key={3}
                            class='line'
                          />,
                        ]
                      : [
                          <span
                            key={1}
                            class='line'
                          />,
                          <span
                            key={2}
                            class='center-text'
                          >
                            {times.gap.value}
                          </span>,
                          <span
                            key={3}
                            class='to-right'
                          />,
                        ]}
                  </span>
                  <span class='right'>{times.tags[1]}</span>
                </div>
              );
            }
            if (item.type === 'gapTime') {
              return (
                <div
                  key={index}
                  class='gap-time'
                >
                  <div class='top' />
                  <div class='center'>{item[item.type]}</div>
                  <div class='bottom' />
                </div>
              );
            }
            return undefined;
          })}
        </div>
      </div>
    );

    watch(
      () => props.activeTab,
      val => {
        activeTab.value = val as TabName;
      }
    );

    const tabList = [
      {
        label: t('基础信息'),
        name: 'BasicInfo',
      },
      // {
      //   label: t('事件'),
      //   name: 'Event',
      // },
      {
        label: t('日志'),
        name: 'Log',
      },
      {
        label: t('主机'),
        name: 'Host',
      },
      {
        label: t('容器'),
        name: 'Container',
      },
      // 20230525 这期暂时不需要
      // {
      //   label: t('进程'),
      //   name: 'Process'
      // },
      // {
      //   label: t('容器'),
      //   name: 'Container'
      // },
      // {
      //   label: t('指标'),
      //   name: 'Index'
      // }
    ];

    // 快捷跳转文案
    const exploreButtonName = computed(() => {
      switch (activeTab.value) {
        case 'Container':
          return spanDetailQueryStore.queryData?.pod_name ? t('容器监控') : '';
        case 'Host':
          return spanDetailQueryStore.queryData?.bk_host_id ? t('主机监控') : '';
        case 'Log':
          return spanDetailQueryStore.queryData?.indexId || spanDetailQueryStore.queryData.unionList
            ? t('日志检索')
            : '';
        case 'Profiling':
          return spanId.value ? t('Profiling检索') : '';
      }
      return '';
    });

    const sceneData = ref<BookMarkModel>({});
    const isSingleChart = computed<boolean>(() => {
      return (
        sceneData.value?.panelCount < 2 &&
        sceneData.value?.panels?.some(item => item.type !== 'graph') &&
        sceneData.value.panels.length < 2 &&
        (sceneData.value.panels?.[0].type === 'row'
          ? sceneData.value.panels[0]?.panels?.some(item => item.type !== 'graph')
          : true)
      );
    });
    // 第一个span禁用上一跳
    const isDisabledPre = computed(
      () => spans.value.findIndex(span => span.span_id === props.spanDetails?.span_id) === 0
    );
    // 最后一个span禁用下一跳
    const isDisabledNext = computed(
      () => spans.value.findIndex(span => span.span_id === props.spanDetails?.span_id) === spans.value.length - 1
    );
    const isTabPanelLoading = ref(false);
    const handleActiveTabChange = async () => {
      isTabPanelLoading.value = true;
      if (hostAndContainerCancelToken) {
        hostAndContainerCancelToken?.();
        hostAndContainerCancelToken = null;
      }
      if (activeTab.value === 'Log') {
        const result = await getSceneView({
          scene_id: 'apm_trace',
          id: activeTab.value.toLowerCase(),
          bk_biz_id: window.bk_biz_id,
          apm_app_name: props.spanDetails.app_name,
          apm_service_name: props.spanDetails.service_name,
          apm_span_id: props.spanDetails.span_id,
        }).catch(console.log);
        if (result?.overview_panels?.length) {
          result.overview_panels[0] = {
            ...result.overview_panels[0],
            type: 'monitor-trace-log',
          };
          result.overview_panels[0].options = {
            ...result.overview_panels[0].options,
            related_log_chart: {
              defaultKeyword: traceId.value || '',
            },
          };
        }
        sceneData.value = new BookMarkModel(result);
        isTabPanelLoading.value = false;
      }
      if (activeTab.value === 'Host') {
        const result = await getSceneView(
          {
            scene_id: 'apm_trace',
            id: 'host',
            bk_biz_id: window.bk_biz_id,
            apm_app_name: props.spanDetails.app_name,
            apm_service_name: props.spanDetails.service_name,
            apm_span_id: props.spanDetails.span_id,
          },
          {
            cancelToken: new CancelToken(cb => {
              hostAndContainerCancelToken = cb;
            }),
          }
        ).catch(() => null);
        sceneData.value = new BookMarkModel(result);
        isTabPanelLoading.value = false;
      }
      if (activeTab.value === 'Container') {
        const startTime = dayjs(spanTime.value).unix() - 60 * 60;
        let endTime = dayjs(spanTime.value).unix() + 30 * 60;
        const curUnix = dayjs().unix();
        endTime = endTime > curUnix ? curUnix : endTime;
        const result = await getSceneView(
          {
            scene_id: 'apm_trace',
            id: 'container',
            bk_biz_id: window.bk_biz_id,
            apm_app_name: props.spanDetails.app_name,
            apm_service_name: props.spanDetails.service_name,
            apm_span_id: props.spanDetails.span_id,
            start_time: startTime,
            end_time: endTime,
          },
          {
            cancelToken: new CancelToken(cb => {
              hostAndContainerCancelToken = cb;
            }),
          }
        ).catch(() => null);
        sceneData.value = new BookMarkModel(result);
        isTabPanelLoading.value = false;
      }
      if (activeTab.value === 'Profiling') {
        if (enableProfiling.value) {
          await getFlameGraphData();
        }
        isTabPanelLoading.value = false;
      }
    };
    const getProfilingTimeRange = () => {
      const halfHour = 18 * 10 ** 8;
      return {
        start_time: originalData.value?.start_time - halfHour,
        end_time: originalData.value?.start_time + halfHour,
      };
    };
    // 快捷跳转
    const handleQuickJump = () => {
      switch (activeTab.value) {
        case 'Log': {
          if (!spanDetailQueryStore.queryData?.indexId && !spanDetailQueryStore.queryData?.unionList) return;
          const { indexId, unionList, start_time, end_time, addition } = spanDetailQueryStore.queryData;
          let url = '';
          if (unionList) {
            url = `${window.bk_log_search_url}#/retrieve?bizId=${window.bk_biz_id}&search_mode=ui&start_time=${start_time ? dayjs(start_time).valueOf() : ''}&end_time=${end_time ? dayjs(end_time).valueOf() : ''}&addition=${addition || ''}&unionList=${unionList}`;
          } else {
            url = `${window.bk_log_search_url}#/retrieve/${indexId}?bizId=${window.bk_biz_id}&search_mode=ui&start_time=${start_time ? dayjs(start_time).valueOf() : ''}&end_time=${end_time ? dayjs(end_time).valueOf() : ''}&addition=${addition || ''}`;
          }
          window.open(url, '_blank');
          return;
        }
        case 'Host': {
          if (!spanDetailQueryStore.queryData?.bk_host_id) return;
          window.open(`#/performance/detail/${spanDetailQueryStore.queryData.bk_host_id}`, '_blank');
          return;
        }
        case 'Container': {
          if (!spanDetailQueryStore.queryData?.pod_name) return;
          const { pod_name, bcs_cluster_id, namespace } = spanDetailQueryStore.queryData;
          window.open(
            `#/k8s-new/?sceneId=kubernetes&cluster=${bcs_cluster_id}&filterBy=${encodeURIComponent(JSON.stringify({ namespace: [namespace], pod: [pod_name] }))}&groupBy=${encodeURIComponent(JSON.stringify(['namespace', 'pod']))}`
          );
          return;
        }
        case 'Profiling': {
          const { app_name, service_name, span_id } = props.spanDetails;
          if (!span_id) return;
          const { start_time, end_time } = getProfilingTimeRange();
          window.open(
            `#/trace/profiling/?target=${encodeURIComponent(
              JSON.stringify({
                app_name,
                service_name,
                start: (start_time / 1000).toFixed(0),
                end: (end_time / 1000).toFixed(0),
                filter_labels: {
                  span_id,
                },
              })
            )}`
          );
          return;
        }
      }
    };

    /** 是否显示空数据提示 */
    const showEmptyGuide = () => {
      if (activeTab.value === 'Event') {
        return !info.list.filter(val => val.type === EListItemType.events).length;
      }

      return false;
    };

    const titleInfoElem = () => (
      <div
        key={props.spanDetails?.span_id}
        class='title-info'
      >
        <span class='trace-id'>Span ID:&nbsp;&nbsp;{props.spanDetails?.span_id}</span>
        <span class='tag'>{info.header.timeTag}</span>
        <Popover
          content={t('复制 Span ID')}
          placement='right'
          theme='light'
        >
          <span
            class='icon-monitor icon-mc-copy'
            onClick={() => handleTitleCopy('text')}
          />
        </Popover>
        <Popover
          content={t('复制链接')}
          placement='right'
          theme='light'
        >
          <span
            class='icon-monitor icon-copy-link'
            onClick={() => handleTitleCopy('link')}
          />
        </Popover>
      </div>
    );

    // 复制json字符串数据的icon
    const copyOriginalElem = () => (
      <div class='json-head'>
        <Popover
          content={t('复制')}
          placement='right'
          theme='light'
        >
          <span
            class='icon-monitor icon-mc-copy'
            onClick={() => handleTitleCopy('original')}
          />
        </Popover>
      </div>
    );
    if (window.enable_apm_profiling) {
      tabList.push({
        label: t('性能分析'),
        name: 'Profiling',
      });
    }
    const detailsMain = () => {
      // profiling 查询起始时间根据 span 开始时间前后各推半小时
      const { start_time, end_time } = getProfilingTimeRange();
      return (
        <Loading
          style='height: 100%;'
          loading={props.isPageLoading}
        >
          {props.withSideSlider && showOriginalData.value ? (
            <div class='json-text-style'>
              {copyOriginalElem()}
              <VueJsonPretty data={originalData.value} />
            </div>
          ) : (
            <div class={`span-details-sideslider-content ${!props.withSideSlider ? 'is-main' : ''}`}>
              {!props.withSideSlider && (
                <div class='header-tool'>
                  <Switcher
                    class='switcher'
                    v-model={showOriginalData.value}
                    size='small'
                    theme='primary'
                    onChange={handleOriginalDataChange}
                  />
                  <span>{t('原始数据')}</span>
                  <Button
                    class='download-btn'
                    size='small'
                    onClick={handleExportOriginData}
                  >
                    <i class='icon-monitor icon-xiazai1' />
                    <span>{t('下载')}</span>
                  </Button>
                </div>
              )}
              {showOriginalData.value ? (
                <div class='accurate-original-panel'>
                  {titleInfoElem()}
                  <div class='json-text-style'>
                    {copyOriginalElem()}
                    <VueJsonPretty data={originalData.value} />
                  </div>
                </div>
              ) : (
                [
                  <div
                    key='header'
                    class='details-header'
                  >
                    {props.withSideSlider ? (
                      <div class='title'>
                        <span
                          class='name'
                          title={info.header.title}
                        >
                          {info.header.title}
                        </span>
                        <span class='tag'>{info.header.timeTag}</span>
                      </div>
                    ) : (
                      titleInfoElem()
                    )}
                    <div class='details-others'>
                      {info.header.others.map((item, index) => (
                        <span
                          key={index}
                          class='other-item'
                        >
                          <span class='label'>{`${item.label}: `}</span>
                          <span
                            class='content'
                            title={item.title}
                          >
                            {item.content}
                          </span>
                        </span>
                      ))}
                    </div>
                  </div>,
                  <MonitorTab
                    key='info-tab'
                    class='info-tab'
                    v-slots={{
                      setting: () => {
                        return (
                          exploreButtonName.value && (
                            <Button
                              class='quick-jump'
                              size='small'
                              theme='primary'
                              outline
                              onClick={handleQuickJump}
                            >
                              {exploreButtonName.value}
                              <i class='icon-monitor icon-fenxiang' />
                            </Button>
                          )
                        );
                      },
                    }}
                    active={activeTab.value}
                    onTabChange={v => {
                      activeTab.value = v;
                      handleActiveTabChange();
                    }}
                  >
                    {tabList.map((item, index) => (
                      <Tab.TabPanel
                        key={index}
                        v-slots={{
                          label: () => (
                            <div style='display: flex;'>
                              <span>{item.label || '-'}</span>
                              {/* {countOfInfo.value?.[item.name] ? (
                                <span
                                  class={{
                                    'num-badge': true,
                                    'num-badge-active': activeTab.value === item.name,
                                  }}
                                >
                                  {countOfInfo.value[item.name]}
                                </span>
                              ) : (
                                ''
                              )} */}
                            </div>
                          ),
                        }}
                        name={item.name}
                      />
                    ))}
                  </MonitorTab>,
                  <div
                    key='content-list'
                    class={{
                      'content-list': true,
                      // 以下 is-xxx-tab 用于 Span ID 精确查询下的 日志、主机 tap 的样式进行动态调整。以免影响 span id 列表下打开弹窗的 span detail 样式。
                      'is-log-tab': activeTab.value === 'Log',
                      'is-host-tab': activeTab.value === 'Host',
                      'is-container-tab': activeTab.value === 'Container',
                    }}
                  >
                    {info.list.map((item, index) => {
                      if (item.type === EListItemType.tags && activeTab.value === 'BasicInfo') {
                        const content = item[EListItemType.tags];
                        return expanItem(
                          item.isExpan,
                          item.title,
                          tagsTemplate(content.list),
                          <span class='expan-item-subtitle'>
                            {item.isExpan ? '' : content.list.map(kv => `${kv.label} = ${kv.content}`).join('  |  ')}
                          </span>,
                          isExpan => handleExpanChange(isExpan, index)
                        );
                      }
                      if (item.type === EListItemType.events && activeTab.value === 'BasicInfo') {
                        const content = item[EListItemType.events];
                        const isException =
                          content?.list.some(val => val.header?.name === 'exception') && props.spanDetails?.error;
                        return expanItem(
                          item.isExpan,
                          item.title,
                          <div>
                            {isException && (
                              <Button
                                style='margin: 16px 0;'
                                onClick={handleEventErrLink}
                              >
                                {t('错误分析')}
                                <span
                                  style='margin-left: 8px;'
                                  class='icon-monitor icon-fenxiang'
                                />
                              </Button>
                            )}
                            {content.list.map((child, childIndex) => {
                              // 默认开启第一个
                              if (childIndex === 0 && isInvokeOnceFlag) {
                                isInvokeOnceFlag = false;
                                handleSmallExpanChange(false, index, childIndex);
                              }
                              return (
                                <div key={childIndex}>
                                  {expanItemSmall(
                                    child.isExpan,
                                    child.header.name,
                                    tagsTemplate(child.content),
                                    [
                                      <span
                                        key='subtitle'
                                        class='expan-item-small-subtitle'
                                      >
                                        {child.isExpan
                                          ? ''
                                          : child.content.map(kv => `${kv.label} = ${kv.content}`).join('  |  ')}
                                      </span>,
                                      <span
                                        key='time'
                                        class='time'
                                      >
                                        {child.header.date}
                                      </span>,
                                      child.header.duration ? (
                                        <span
                                          key='tag'
                                          class='tag'
                                        >
                                          {child.header.duration}
                                        </span>
                                      ) : (
                                        ''
                                      ),
                                    ],
                                    isExpan => handleSmallExpanChange(isExpan, index, childIndex)
                                  )}
                                </div>
                              );
                            })}
                          </div>,
                          ` (${content.list.length})`,
                          isExpan => handleExpanChange(isExpan, index)
                        );
                      }
                      if (item.type === EListItemType.stageTime && activeTab.value === 'BasicInfo') {
                        const content = item[EListItemType.stageTime];
                        return expanItem(
                          item.isExpan,
                          item.title,
                          stageTimeTemplate(
                            content.active,
                            content.list,
                            content.content[content.active]
                            // stageItem => handleStageTimeChange(stageItem, index)
                          ),
                          '',
                          isExpan => handleExpanChange(isExpan, index)
                        );
                      }
                      return undefined;
                    })}
                    {
                      // 日志 部分
                      activeTab.value === 'Log' && (
                        <Loading
                          style='height: 100%;'
                          loading={isTabPanelLoading.value}
                        >
                          {/* 由于视图早于数据先加载好会导致样式错乱，故 loading 完再加载视图 */}
                          {!isTabPanelLoading.value && (
                            <div>
                              <FlexDashboardPanel
                                id={random(10)}
                                column={0}
                                dashboardId={random(10)}
                                isSingleChart={isSingleChart.value}
                                needOverviewBtn={!!sceneData.value?.list?.length}
                                panels={sceneData.value.overview_panels}
                              />
                            </div>
                          )}
                        </Loading>
                      )
                    }
                    {
                      // 主机 部分
                      activeTab.value === 'Host' && (
                        <Loading
                          style='height: 100%;'
                          loading={isTabPanelLoading.value}
                        >
                          {/* 由于视图早于数据先加载好会导致样式错乱，故 loading 完再加载视图 */}
                          {!isTabPanelLoading.value && (
                            <div class='host-tab-container'>
                              <DashboardPanel
                                groupTitle={t('主机列表')}
                                isSingleChart={isSingleChart.value}
                                sceneData={sceneData.value}
                                sceneId={'host'}
                              />
                            </div>
                          )}
                        </Loading>
                      )
                    }
                    {
                      // 容器 部分
                      activeTab.value === 'Container' && (
                        <Loading
                          style='height: 100%;'
                          loading={isTabPanelLoading.value}
                        >
                          {/* 由于视图早于数据先加载好会导致样式错乱，故 loading 完再加载视图 */}
                          {!isTabPanelLoading.value && (
                            <div class='host-tab-container'>
                              <DashboardPanel
                                groupTitle={'Groups'}
                                isSingleChart={isSingleChart.value}
                                podName={originalData.value?.resource?.['k8s.pod.name']}
                                sceneData={sceneData.value}
                                sceneId={'container'}
                              />
                            </div>
                          )}
                        </Loading>
                      )
                    }
                    {
                      // 火焰图 部分
                      activeTab.value === 'Profiling' && (
                        <Loading
                          style='height: 100%;'
                          loading={enableProfiling.value && isTabPanelLoading.value}
                        >
                          {!isTabPanelLoading.value &&
                            (enableProfiling.value ? (
                              <ProfilingFlameGraph
                                appName={appName.value}
                                bizId={bizId.value}
                                data={profilingFlameGraph.value}
                                end={start_time}
                                profileId={originalData.value.span_id}
                                serviceName={serviceNameProvider.value}
                                start={end_time}
                                textDirection={ellipsisDirection.value}
                                onUpdate:loading={val => {
                                  isTabPanelLoading.value = val;
                                }}
                              />
                            ) : (
                              <div class='exception-guide-wrap'>
                                <Exception type='building'>
                                  <span>{t('暂未开启 Profiling 功能')}</span>
                                  <div class='text-wrap'>
                                    <pre class='text-row'>{t('该服务所在 APM 应用未开启 Profiling 功能')}</pre>
                                  </div>
                                </Exception>
                              </div>
                            ))}
                        </Loading>
                      )
                    }
                    {showEmptyGuide() && <ExceptionGuide guideInfo={guideInfoData[activeTab.value]} />}
                  </div>,
                ]
              )}
            </div>
          )}
        </Loading>
      );
    };

    const renderDom = () => (
      <Sideslider
        width={fullscreen.value ? '100%' : '80%'}
        ext-cls={`span-details-sideslider ${props.isFullscreen ? 'full-screen' : ''}`}
        v-model={[localShow.value, 'isShow']}
        v-slots={{
          header: () => (
            <div class='sideslider-header'>
              <div class={['sideslider-hd', { 'show-flip-button': props.isShowPrevNextButtons }]}>
                <span class='sideslider-title'>
                  <span class='text'>Span ID: </span>
                  <span class={['status', spanStatus.value?.icon]} />
                  <span class='name'>{props.spanDetails?.span_id || info.title}</span>
                  {/* <AiBluekingIcon
                    content={props.spanDetails?.span_id || info.title}
                    shortcutId={AI_BLUEKING_SHORTCUTS_ID.EXPLANATION}
                  /> */}
                </span>
                {props.isShowPrevNextButtons ? (
                  <>
                    <div
                      class={['arrow-wrap', { disabled: isDisabledPre.value }]}
                      v-bk-tooltips={{
                        content: isDisabledPre.value ? t('已经是第一个span') : t('上一跳'),
                      }}
                      onClick={() => {
                        if (!isDisabledPre.value) {
                          handlePrevNextClick('previous');
                        }
                      }}
                    >
                      <span class='icon-monitor icon-a-mini-arrowxiaojiantou top' />
                    </div>
                    <div
                      class={['arrow-wrap', { disabled: isDisabledNext.value }]}
                      v-bk-tooltips={{
                        content: isDisabledNext.value ? t('已经是最后一个span') : t('下一跳'),
                      }}
                      onClick={() => {
                        if (!isDisabledNext.value) {
                          handlePrevNextClick('next');
                        }
                      }}
                    >
                      <span class='icon-monitor icon-a-mini-arrowxiaojiantou' />
                    </div>
                  </>
                ) : null}
              </div>
              <div class='header-tool'>
                <div class='tool-item'>
                  <div class='tool-item-content'>
                    <Switcher
                      class='switcher'
                      v-model={showOriginalData.value}
                      size='small'
                      theme='primary'
                      onChange={handleOriginalDataChange}
                    />
                    <span>{t('原始数据')}</span>
                  </div>
                </div>
                <div class='tool-item'>
                  <div
                    class='tool-item-content'
                    onClick={() => handleFullScreen(!fullscreen.value)}
                  >
                    <i class='icon-monitor icon-fullscreen' />
                    <span>{t(fullscreen.value ? '退出全屏' : '全屏')}</span>
                  </div>
                </div>
                <div class='tool-item'>
                  <div
                    class='tool-item-content'
                    onClick={handleExportOriginData}
                  >
                    <i class='icon-monitor icon-xiazai2' />
                    <span>{t('下载')}</span>
                  </div>
                </div>
              </div>
            </div>
          ),
        }}
        transfer={(document.querySelector('.trace-list-wrapper') as HTMLDivElement) ?? true}
        quick-close
        show-mask
        onHidden={handleHiddenChange}
      >
        {detailsMain()}
      </Sideslider>
    );

    return {
      localShow,
      info,
      detailsMain,
      renderDom,
      sceneData,
      isTabPanelLoading,
      // countOfInfo,
    };
  },
  render() {
    return this.$props.withSideSlider ? this.renderDom() : this.detailsMain();
  },
});
