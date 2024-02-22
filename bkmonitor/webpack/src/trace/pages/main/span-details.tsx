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
import { computed, defineComponent, PropType, provide, reactive, ref, watch } from 'vue';
import { useI18n } from 'vue-i18n';
import VueJsonPretty from 'vue-json-pretty';
import { Button, Loading, Message, Popover, Sideslider, Switcher, Tab } from 'bkui-vue';
import { EnlargeLine } from 'bkui-vue/lib/icon';
import dayjs from 'dayjs';

import { getSceneView } from '../../../monitor-api/modules/scene_view';
import { copyText, deepClone, random } from '../../../monitor-common/utils/utils';
import ExceptionGuide, { IGuideInfo } from '../../components/exception-guide/exception-guide';
import MonitorTab from '../../components/monitor-tab/monitor-tab';
import { Span } from '../../components/trace-view/typings';
import { formatDate, formatDuration, formatTime } from '../../components/trace-view/utils/date';
import ProfilingFlameGraph from '../../plugins/charts/profiling-graph/flame-graph/flame-graph';
import FlexDashboardPanel from '../../plugins/components/flex-dashboard-panel';
import { BookMarkModel } from '../../plugins/typings';
import EmptyEvent from '../../static/img/empty-event.svg';
import { SPAN_KIND_MAPS } from '../../store/constant';
import { useAppStore } from '../../store/modules/app';
import { useTraceStore } from '../../store/modules/trace';
import {
  EListItemType,
  IInfo,
  IStageTimeItem,
  IStageTimeItemContent,
  ITagContent,
  ITagsItem
} from '../../typings/trace';
import { downFile, getSpanKindIcon } from '../../utils';

import './span-details.scss';
import 'vue-json-pretty/lib/styles.css';

const guideInfoData: Record<string, IGuideInfo> = {
  Event: {
    type: '',
    icon: EmptyEvent,
    title: window.i18n.t('当前无异常事件'),
    subTitle: window.i18n.t('异常事件获取来源\n1. events.attributes.exception_stacktrace 字段\n2. status.message 字段'),
    link: null
  }
  // Log: {},
  // Host: {},
  // Process: {},
  // Container: {},
  // Index: {}
};

type TabName = 'BasicInfo' | 'Event' | 'Log' | 'Host' | 'Process' | 'Container' | 'Index' | 'Profiling';
export default defineComponent({
  name: 'SpanDetails',
  props: {
    show: { type: Boolean, default: false },
    withSideSlider: { type: Boolean, default: true }, // 详情信息在侧滑弹窗展示
    spanDetails: { type: Object as PropType<Span>, default: () => null },
    isFullscreen: { type: Boolean, default: false } /* 当前是否为全屏状态 */,
    isPageLoading: { type: Boolean, default: false }
  },
  emits: ['show'],
  setup(props, { emit }) {
    const store = useTraceStore();
    const { t } = useI18n();
    /* 侧栏show */
    const localShow = ref(false);
    /* 详情数据 */
    const tempInfo = {
      title: '',
      header: {
        title: '',
        timeTag: '',
        others: []
      },
      list: []
    };
    const info = reactive<IInfo>(deepClone(tempInfo));

    /** 切换显示原始数据 */
    const showOriginalData = ref(false);

    /** 原始数据 */
    const originalData = ref<Record<string, any> | null>(null);

    /* 当前应用名称 */
    const appName = computed(() => store.traceData.appName);

    const ellipsisDirection = computed(() => store.ellipsisDirection);

    const bizId = computed(() => useAppStore().bizId || 0);

    const countOfInfo = ref<Record<TabName, number> | {}>({});

    // 20230807 当前 span 开始和结束时间。用作 主机（host）标签下请求接口的时间区间参数。
    const startTimeProvider = ref('');
    provide('startTime', startTimeProvider);
    const endTimeProvider = ref('');
    provide('endTime', endTimeProvider);
    const serviceNameProvider = ref('');
    // 服务、应用 名在日志 tab 里能用到
    provide('serviceName', serviceNameProvider);
    provide('appName', appName);

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
          countOfInfo.value = {};
        }
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
        if (val && !props.withSideSlider) {
          getDetails();
        }
      },
      { immediate: true, deep: true }
    );

    /** 获取 span 类型icon */
    function getTypeIcon() {
      const { source, kind, ebpf_kind: ebpfKind } = props.spanDetails;
      if (source === 'ebpf') {
        // ebpf 类型
        return ebpfKind === 'ebpf_system' ? 'System1' : 'Network1';
      }

      return getSpanKindIcon(kind);
    }

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
        // eslint-disable-next-line @typescript-eslint/no-unused-vars
        spanID,
        app_name: appName,
        service_name: serviceName,
        duration,
        startTime,
        operationName,
        attributes,
        events,
        process,
        icon,
        source,
        error,
        message,
        /* eslint-disable-next-line @typescript-eslint/naming-convention */
        stage_duration
      } = props.spanDetails as Span | any;
      // 服务、应用 名在日志 tab 里能用到
      serviceNameProvider.value = serviceName;
      const originalDataList = [...store.traceData.original_data, ...store.compareTraceOriginalData];
      // 根据span_id获取原始数据
      const curSpan = originalDataList.find((data: any) => data.span_id === originalSpanId);
      startTimeProvider.value = `${formatDate(curSpan.start_time)} ${formatTime(curSpan.start_time)}`;
      endTimeProvider.value = `${formatDate(curSpan.end_time)} ${formatTime(curSpan.end_time)}`;
      if (curSpan) originalData.value = handleFormatJson(curSpan);
      const { kind, trace_id: traceId, resource, is_virtual: isVirtual } = originalData.value as Record<string, any>;

      info.title = `Span ID：${originalSpanId}`;
      /** 头部基本信息 */
      info.header = {
        title: operationName,
        timeTag: formatDuration(duration),
        others: [
          {
            label: t('服务'),
            content: (
              <span
                class='link'
                onClick={() => handleToServiceName(serviceName)}
              >
                <img
                  class='span-icon'
                  src={icon}
                  alt=''
                />
                <span>{serviceName}</span>
                <i class='icon-monitor icon-fenxiang' />
              </span>
            ),
            title: serviceName
          },
          {
            label: t('应用'),
            content: (
              <span
                class='link'
                onClick={() => handleToAppName(appName)}
              >
                <span>{appName}</span>
                <i class='icon-monitor icon-fenxiang' />
              </span>
            ),
            title: appName
          },
          // { label: '日志', content: logs.length ? '有日志' :  '无日志' },
          {
            label: t('开始时间'),
            content: dayjs.tz(startTime / 1e3).format('YYYY-MM-DD HH:mm:ss'),
            title: dayjs.tz(startTime / 1e3).format('YYYY-MM-DD HH:mm:ss')
          },
          {
            label: t('来源'),
            content: source || '--',
            title: source || ''
          },
          {
            label: t('类型'),
            content: (
              <span>
                {!isVirtual && <i class={`icon-monitor icon-type icon-${getTypeIcon()}`}></i>}
                <span>{getTypeText()}</span>
              </span>
            ),
            title: SPAN_KIND_MAPS[kind]
          },
          {
            label: t('版本'),
            content: resource['telemetry.sdk.version'] || '--',
            title: resource['telemetry.sdk.version'] || ''
          },
          {
            label: t('所属Trace'),
            content: (
              <span
                class='link'
                onClick={() => handleToTraceQuery(traceId)}
              >
                <span>{traceId}</span>
                <i class='icon-monitor icon-fenxiang' />
              </span>
            ),
            title: traceId
          }
        ]
      };
      info.list = [];
      /** Tags 信息 */
      if (attributes?.length) {
        info.list.push({
          type: EListItemType.tags,
          isExpan: true,
          title: 'Tags',
          [EListItemType.tags]: {
            list:
              attributes.map(
                (item: { key: string; value: string; type: string; query_key: string; query_value: any }) => ({
                  label: item.key,
                  content: item.value || '--',
                  type: item.type,
                  isFormat: false,
                  query_key: item.query_key,
                  query_value: item.query_value
                })
              ) || []
          }
        });
      }
      /** Events信息 来源：status_message & events */
      if (error || events?.length) {
        const eventList = [];
        if (error) {
          eventList.push({
            isExpan: false,
            header: {
              date: `${formatDate(startTime)} ${formatTime(startTime)}`,
              name: 'status_message'
            },
            content: [
              {
                label: 'span.status_message',
                content: message || '--',
                type: 'string',
                isFormat: false,
                // 这里固定写死
                query_key: 'status.message',
                query_value: message
              }
            ]
          });
        }
        if (events?.length) {
          eventList.push(
            ...events.map(
              (item: {
                timestamp: number;
                duration: number;
                name: any;
                attributes: { key: string; value: string; type: string; query_key?: string; query_value?: any }[];
              }) => ({
                isExpan: false,
                header: {
                  date: `${formatDate(item.timestamp)} ${formatTime(item.timestamp)}`,
                  duration: formatDuration(item.duration),
                  name: item.name
                },
                content: item.attributes.map(attribute => ({
                  label: attribute.key,
                  content: attribute.value || '--',
                  type: attribute.type,
                  isFormat: false,
                  query_key: attribute?.query_key || '',
                  query_value: attribute?.query_value || ''
                }))
              })
            )
          );
        }
        info.list.push({
          type: EListItemType.events,
          isExpan: true,
          title: 'Events',
          [EListItemType.events]: {
            list: eventList
          }
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
                errorMsg: stage_duration.left.error_message
              },
              {
                id: stage_duration.right.type,
                label: stage_duration.right.label,
                error: stage_duration.right.error,
                errorMsg: stage_duration.right.error_message
              }
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
                      )}`
                    ],
                    gap: {
                      type: 'toRight',
                      value: formatDuration(stage_duration.right.start_time - stage_duration.left.start_time)
                    }
                  }
                },
                {
                  type: 'gapTime',
                  gapTime: formatDuration(stage_duration.right.end_time - stage_duration.right.start_time)
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
                      )}`
                    ],
                    gap: {
                      type: 'toLeft',
                      value: formatDuration(stage_duration.left.end_time - stage_duration.right.end_time)
                    }
                  }
                }
              ]
            }
          }
        });
      }
      /** process信息 */
      if (process?.tags?.length) {
        info.list.push({
          type: EListItemType.tags,
          isExpan: true,
          title: 'Process',
          [EListItemType.tags]: {
            list:
              process?.tags.map(
                (item: { key: any; value: any; type: string; query_key: string; query_value: any }) => ({
                  label: item.key,
                  content: item.value || '--',
                  type: item.type,
                  isFormat: false,
                  query_key: item.query_key,
                  query_value: item.query_value
                })
              ) || []
          }
        });
      }

      // TODO：先统计事件的数量
      info.list.forEach(item => {
        if (item.type === EListItemType.events) {
          countOfInfo.value = Object.assign({}, { Event: item?.Events?.list?.length || 0 });
        }
      });
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
      } catch (error) {
        return obj;
      }
    }

    /* 关闭侧栏 */
    const handleHiddenChange = () => {
      localShow.value = false;
      emit('show', localShow.value);
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
      // eslint-disable-next-line no-useless-escape
      const queryStr = `${content.query_key}: "${String(content.query_value)?.replace(/\"/g, '\\"') ?? ''}"`; // value转义双引号
      const url = location.href.replace(
        location.hash,
        `#/trace/home?app_name=${appName.value}&search_type=scope&listType=span&query=${queryStr}`
      );
      window.open(url, '_blank');
    };

    /* 复制kv部分文本 */
    const handleCopy = (content: ITagContent) => {
      // debugger;
      // eslint-disable-next-line no-useless-escape
      const queryStr = `${content.query_key}: "${String(content.query_value)?.replace(/\"/g, '\\"') ?? ''}"`; // value转义双引号
      copyText(
        queryStr,
        (msg: string) => {
          Message({
            message: msg,
            theme: 'error'
          });
          return;
        },
        props.isFullscreen ? '.trace-table-main' : ''
      );
      Message({
        theme: 'success',
        message: t('复制成功'),
        width: 200
      });
    };

    /* event 错误链接 */
    function handleEventErrLink() {
      const { app_name: appName } = props.spanDetails;
      const hash = `#/apm/application?filter-app_name=${appName}&method=AVG&interval=auto&dashboardId=error&from=now-1h&to=now&refleshInterval=-1`;
      const url = location.href.replace(location.hash, hash);
      window.open(url, '_blank');
    }

    /* 跳转到服务 */
    function handleToServiceName(serviceName: string) {
      const { app_name: appName } = props.spanDetails;
      const hash = `#/apm/service?filter-service_name=${serviceName}&filter-app_name=${appName}&method=AVG&interval=auto&from=now-1h&to=now&refleshInterval=-1`;
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
      // eslint-disable-next-line no-useless-escape
      const hash = `#/trace/home?app_name=${appName.value}&search_type=accurate&trace_id=${traceId}`;
      const url = location.href.replace(location.hash, hash);
      window.open(url, '_blank');
    }

    /** 切换原始数据 */
    function handleOriginalDataChange(val: boolean) {
      showOriginalData.value = val;
    }

    // 复制操作
    function handleTitleCopy(content: string) {
      let text = '';
      const { spanID } = props.spanDetails;
      if (content === 'text') {
        text = spanID;
      } else {
        const hash = `#${window.__BK_WEWEB_DATA__?.baseroute || '/'}home/?app_name=${
          appName.value
        }&search_type=accurate&search_id=spanID&trace_id=${spanID}`;
        text = location.href.replace(location.hash, hash);
      }
      copyText(text, (msg: string) => {
        Message({
          message: msg,
          theme: 'error'
        });
        return;
      });
      Message({
        message: window.i18n.t('复制成功'),
        width: 200,
        theme: 'success'
      });
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
          <span class={['icon-monitor icon-mc-triangle-down', { active: isExpan }]}></span>
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
          <span class={['icon-monitor icon-arrow-down', { active: isExpan }]}></span>
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
        } catch (e) {
          return false;
        }
      }

      return false;
    };

    const formatContent = (content?: string, isFormat?: boolean) => {
      if (!isJson(content)) return content;

      const data = JSON.parse(content || '');
      return isFormat ? <VueJsonPretty data={handleFormatJson(data)} /> : content;
    };

    /** 导出原始数据josn */
    const handleExportOriginData = () => {
      if (originalData.value) {
        const jsonString = JSON.stringify(originalData.value, null, 4);
        const blob = new Blob([jsonString], { type: 'application/json' });
        const fileUrl = URL.createObjectURL(blob);
        downFile(fileUrl, `${originalData.value.span_id}.json`);
      }
    };

    /* kv 结构数据展示 */
    const tagsTemplate = (data: ITagsItem['list']) => (
      <div class='tags-template'>
        {data.map((item, index) => (
          <div class={['tags-row', { grey: !(index % 2) }]}>
            <span class='left'>
              {item.label}
              <div class='operator'>
                <EnlargeLine
                  class='icon-add-query'
                  onClick={() => handleKvQuery(item)}
                />
                <span
                  class='icon-monitor icon-mc-copy'
                  onClick={() => handleCopy(item)}
                ></span>
              </div>
            </span>
            {item.type === 'error' ? (
              <div class='right'>
                <span class='error-text'>{formatContent(item.content, item.isFormat)}</span>
                <span class='icon-monitor icon-mind-fill'></span>
              </div>
            ) : (
              <div class='right'>{formatContent(item.content, item.isFormat)}</div>
            )}
            {isJson(item.content) && (
              <Button
                class='format-button'
                theme='primary'
                size='small'
                outline={!item.isFormat}
                // eslint-disable-next-line no-param-reassign
                onClick={() => (item.isFormat = !item.isFormat)}
              >
                <i class='icon-monitor icon-code'></i>
                {t('格式化')}
              </Button>
            )}
          </div>
        ))}
      </div>
    );

    /* 阶段耗时 */
    const stageTimeTemplate = (active: string, list: IStageTimeItem['list'], content: IStageTimeItemContent[]) => (
      <div class='stage-time'>
        <div class='stage-time-list'>
          {list.map(item => (
            <Popover
              disabled={!item.error || !item.errorMsg}
              placement={'left'}
              content={item.errorMsg}
            >
              <div class={['list-item', { active: active === item.id }]}>
                <span class='title'>{item.id}</span>
                <div class='content'>
                  {item.error ? (
                    <span class='err-point'>
                      <span class='red-point'></span>
                    </span>
                  ) : undefined}
                  {item.label}
                </div>
              </div>
            </Popover>
          ))}
        </div>
        <div class='stage-time-content'>
          {content.map(item => {
            if (item.type === 'useTime') {
              const times = item[item.type] as any;
              return (
                <div class='use-time'>
                  <span class='left'>{times.tags[0]}</span>
                  <span class='center'>
                    {times.gap.type === 'toLeft'
                      ? [
                          <span class='to-left'></span>,
                          <span class='center-text'>{times.gap.value}</span>,
                          <span class='line'></span>
                        ]
                      : [
                          <span class='line'></span>,
                          <span class='center-text'>{times.gap.value}</span>,
                          <span class='to-right'></span>
                        ]}
                  </span>
                  <span class='right'>{times.tags[1]}</span>
                </div>
              );
            }
            if (item.type === 'gapTime') {
              return (
                <div class='gap-time'>
                  <div class='top'></div>
                  <div class='center'>{item[item.type]}</div>
                  <div class='bottom'></div>
                </div>
              );
            }
            return undefined;
          })}
        </div>
      </div>
    );

    const activeTab = ref<TabName>('BasicInfo');
    provide('SpanDetailActiveTab', activeTab);
    const tabList = [
      {
        label: t('基础信息'),
        name: 'BasicInfo'
      },
      {
        label: t('异常事件'),
        name: 'Event'
      },
      {
        label: t('日志'),
        name: 'Log'
      },
      {
        label: t('主机'),
        name: 'Host'
      }
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

    const sceneData = ref<Record<string, any>>({});
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
    const isTabPanelLoading = ref(false);
    const handleActiveTabChange = async () => {
      isTabPanelLoading.value = true;
      if (activeTab.value === 'Log') {
        const result = await getSceneView({
          scene_id: 'apm_trace',
          id: activeTab.value.toLowerCase(),
          bk_biz_id: window.bk_biz_id,
          apm_app_name: props.spanDetails.app_name,
          apm_service_name: props.spanDetails.service_name,
          apm_span_id: props.spanDetails.span_id
        })
          .catch(console.log)
          .finally(() => (isTabPanelLoading.value = false));
        sceneData.value = new BookMarkModel(result);
      }
      if (activeTab.value === 'Host') {
        const result = await getSceneView({
          scene_id: 'apm_trace',
          id: activeTab.value.toLowerCase(),
          bk_biz_id: window.bk_biz_id,
          apm_app_name: props.spanDetails.app_name,
          apm_span_id: props.spanDetails.span_id
        })
          .catch(console.log)
          .finally(() => (isTabPanelLoading.value = false));
        sceneData.value = new BookMarkModel(result);
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
        class='title-info'
        key={props.spanDetails?.span_id}
      >
        <span class='trace-id'>Span ID:&nbsp;&nbsp;{props.spanDetails?.span_id}</span>
        <span class='tag'>{info.header.timeTag}</span>
        <Popover
          theme='light'
          placement='right'
          content={t('复制 Span ID')}
        >
          <span
            class='icon-monitor icon-mc-copy'
            onClick={() => handleTitleCopy('text')}
          />
        </Popover>
        <Popover
          theme='light'
          placement='right'
          content={t('复制链接')}
        >
          <span
            class='icon-monitor icon-copy-link'
            onClick={() => handleTitleCopy('link')}
          />
        </Popover>
      </div>
    );
    if (window.enable_apm_profiling) {
      tabList.push({
        label: t('性能分析'),
        name: 'Profiling'
      });
    }
    const detailsMain = () => (
      <Loading
        loading={props.isPageLoading}
        style='height: 100%;'
      >
        {props.withSideSlider && showOriginalData.value ? (
          <div class='json-text-style'>
            <VueJsonPretty data={originalData.value} />
          </div>
        ) : (
          <div class={`span-details-sideslider-content ${!props.withSideSlider ? 'is-main' : ''}`}>
            {!props.withSideSlider && (
              <div class='header-tool'>
                <Switcher
                  v-model={showOriginalData.value}
                  class='switcher'
                  theme='primary'
                  size='small'
                  onChange={handleOriginalDataChange}
                />
                <span>{t('原始数据')}</span>
                <Button
                  class='download-btn'
                  size='small'
                  onClick={handleExportOriginData}
                >
                  <i class='icon-monitor icon-xiazai1'></i>
                  <span>{t('下载')}</span>
                </Button>
              </div>
            )}
            {showOriginalData.value ? (
              <div class='accurate-original-panel'>
                {titleInfoElem()}
                <div class='json-text-style'>
                  <VueJsonPretty data={originalData.value} />
                </div>
              </div>
            ) : (
              [
                <div class='header'>
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
                  <div class='others'>
                    {info.header.others.map(item => (
                      <span class='other-item'>
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
                  active={activeTab.value}
                  onTabChange={v => {
                    activeTab.value = v;
                    handleActiveTabChange();
                  }}
                  class='info-tab'
                >
                  {tabList.map(item => (
                    <Tab.TabPanel
                      name={item.name}
                      v-slots={{
                        label: () => (
                          <div style='display: flex;'>
                            <span>{item.label}</span>
                            {countOfInfo.value?.[item.name] ? (
                              <span
                                class={{
                                  'num-badge': true,
                                  'num-badge-active': activeTab.value === item.name
                                }}
                              >
                                {countOfInfo.value[item.name]}
                              </span>
                            ) : (
                              ''
                            )}
                          </div>
                        )
                      }}
                    />
                  ))}
                </MonitorTab>,

                <div
                  class={{
                    'content-list': true,
                    // 以下 is-xxx-tab 用于 Span ID 精确查询下的 日志、主机 tap 的样式进行动态调整。以免影响 span id 列表下打开弹窗的 span detail 样式。
                    'is-log-tab': activeTab.value === 'Log',
                    'is-host-tab': activeTab.value === 'Host'
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
                    if (item.type === EListItemType.events && activeTab.value === 'Event') {
                      const content = item[EListItemType.events];
                      const isException =
                        content?.list.some(val => val.header?.name === 'exception') && props.spanDetails?.error;
                      return (
                        <div>
                          {isException && (
                            <Button
                              onClick={handleEventErrLink}
                              style='margin-top: 16px;'
                            >
                              {t('错误分析')}
                              <span
                                class='icon-monitor icon-fenxiang'
                                style='margin-left: 8px;'
                              ></span>
                            </Button>
                          )}
                          {content.list.map((child, childIndex) => {
                            // 默认开启第一个
                            if (childIndex === 0 && isInvokeOnceFlag) {
                              isInvokeOnceFlag = false;
                              handleSmallExpanChange(false, index, childIndex);
                            }
                            return (
                              <div style='margin-top: 16px;'>
                                {expanItemSmall(
                                  child.isExpan,
                                  child.header.name,
                                  tagsTemplate(child.content),
                                  [
                                    <span class='time'>{child.header.date}</span>,
                                    child.header.duration ? <span class='tag'>{child.header.duration}</span> : ''
                                  ],
                                  isExpan => handleSmallExpanChange(isExpan, index, childIndex)
                                )}
                              </div>
                            );
                          })}
                        </div>
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
                        loading={isTabPanelLoading.value}
                        style='height: 100%;'
                      >
                        {/* 由于视图早于数据先加载好会导致样式错乱，故 loading 完再加载视图 */}
                        {!isTabPanelLoading.value && (
                          <div>
                            <FlexDashboardPanel
                              isSingleChart={isSingleChart.value}
                              needOverviewBtn={!!sceneData.value?.list?.length}
                              id={random(10)}
                              dashboardId={random(10)}
                              panels={sceneData.value.overview_panels}
                              column={0}
                            ></FlexDashboardPanel>
                          </div>
                        )}
                      </Loading>
                    )
                  }
                  {
                    // 主机 部分
                    activeTab.value === 'Host' && (
                      <Loading
                        loading={isTabPanelLoading.value}
                        style='height: 100%;'
                      >
                        {/* 由于视图早于数据先加载好会导致样式错乱，故 loading 完再加载视图 */}
                        {!isTabPanelLoading.value && (
                          <div>
                            <FlexDashboardPanel
                              isSingleChart={isSingleChart.value}
                              needOverviewBtn={!!sceneData.value?.list?.length}
                              id={random(10)}
                              dashboardId={random(10)}
                              panels={sceneData.value.overview_panels}
                              column={3}
                            ></FlexDashboardPanel>
                          </div>
                        )}
                      </Loading>
                    )
                  }
                  {
                    // 火焰图 部分
                    activeTab.value === 'Profiling' && (
                      <Loading
                        loading={isTabPanelLoading.value}
                        style='height: 100%;'
                      >
                        <ProfilingFlameGraph
                          appName={appName.value}
                          serviceName={serviceNameProvider.value}
                          profileId={originalData.value.span_id}
                          start={originalData.value.start_time}
                          end={originalData.value.end_time}
                          bizId={bizId.value}
                          textDirection={ellipsisDirection.value}
                          onUpdate:loading={val => (isTabPanelLoading.value = val)}
                        />
                      </Loading>
                    )
                  }
                  {showEmptyGuide() && <ExceptionGuide guideInfo={guideInfoData[activeTab.value]} />}
                </div>
              ]
            )}
          </div>
        )}
      </Loading>
    );

    const renderDom = () => (
      <Sideslider
        v-model={[localShow.value, 'isShow']}
        quick-close
        width={960}
        ext-cls={`span-details-sideslider ${props.isFullscreen ? 'full-screen' : ''}`}
        onHidden={handleHiddenChange}
        show-mask
        transfer={document.querySelector('.trace-list-wrapper') ?? true}
        v-slots={{
          header: () => (
            <div class='sideslider-header'>
              <span>{info.title}</span>
              <div class='header-tool'>
                <Switcher
                  v-model={showOriginalData.value}
                  class='switcher'
                  theme='primary'
                  onChange={handleOriginalDataChange}
                />
                <span>{t('原始数据')}</span>
                <Button
                  class='download-btn'
                  size='small'
                  onClick={handleExportOriginData}
                >
                  <i class='icon-monitor icon-xiazai1'></i>
                  <span>{t('下载')}</span>
                </Button>
              </div>
            </div>
          )
        }}
      >
        {detailsMain()}
      </Sideslider>
    );

    return {
      localShow,
      info,
      detailsMain,
      renderDom,
      countOfInfo
    };
  },
  render() {
    return this.$props.withSideSlider ? this.renderDom() : this.detailsMain();
  }
});
