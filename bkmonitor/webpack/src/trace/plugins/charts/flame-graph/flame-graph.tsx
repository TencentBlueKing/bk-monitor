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
import { defineComponent, inject, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue';

import { addListener, removeListener } from '@blueking/fork-resize-detector';
import { Exception } from 'bkui-vue';
import { traceDiagram } from 'monitor-api/modules/apm_trace';
import { lightenDarkenColor, random } from 'monitor-common/utils';
// import stackTrace from './data.json';
import { echarts } from 'monitor-ui/monitor-echarts/types/monitor-echarts';
import { getValueFormat } from 'monitor-ui/monitor-echarts/valueFormats';
import { debounce } from 'throttle-debounce';
import { useI18n } from 'vue-i18n';

import traceIcons from '../../utls/icons';
import { storeImage } from '../../utls/store-img';
import DiffColorList from './diff-color-list';
import GraphTools from './graph-tools/graph-tools';

import './flame-graph.scss';

const usFormat = getValueFormat('µs');
const RootSpanId = '__root_span__';
const MaxScale = 1000;
const MinScale = 100;
const scaleStep = 20;
const TotalStep = MaxScale / scaleStep;

interface IDataItem {
  name: string;
  value: Array<number | Record<string, any> | string>;
  itemStyle: {
    color: string;
  };
}
interface IJsonItem {
  baseline?: number;
  children?: IJsonItem[];
  comparison?: number;
  delta?: number;
  end_time: number;
  icon_type?: keyof typeof traceIcons;
  id: string;
  name: string;
  original?: Record<string, any>;
  rawValue: number;
  start_time: number;
  value?: number;
}
const ColorTypes = {
  http: '#aea2e0',
  db: '#f9ba8f',
  rpc: '#eba8e6',
  other: '#59c0a3',
  mysql: '#82b5d8',
  message: '#4e92f9',
  elasticsearch: '#fee174',
  redis: '#ea6460',
  async_backend: '#699DF4',
};
const defaultHeight = 30;
const height = ref(100);
export interface ICommonMenuItem {
  icon: string;
  id: string;
  name: string;
}
const CommonMenuList: ICommonMenuItem[] = [
  {
    id: 'span',
    name: window.i18n.t('Span 详情'),
    icon: 'icon-xiangqing1',
  },
  {
    id: 'reset',
    name: window.i18n.t('重置图表'),
    icon: 'icon-zhongzhi1',
  },
  {
    id: 'highlight',
    name: window.i18n.t('高亮相似 Span'),
    icon: 'icon-beauty',
  },
];
// const width = ref(300);
export default defineComponent({
  name: 'FlameGraph',
  props: {
    traceId: {
      type: String,
      required: true,
    },
    appName: {
      type: String,
      required: true,
    },
    diffTraceId: {
      type: String,
      default: 'f5d9eb1e258bc1343bf49aec8fa60c0c',
    },
    filters: {
      type: Array,
      required: false,
    },
  },
  emits: ['update:loading', 'showSpanDetail'],
  setup(props, { emit, expose }) {
    const { t } = useI18n();
    const chartRef = ref<HTMLDivElement>();
    const chartWrapRef = ref<HTMLDivElement>();
    let chartInstance = null; // echarts 实例
    let chartData: IJsonItem = null;
    // 最大层级
    const maxLevel = ref(0);
    // 点击层级
    const clickLevel = ref(0);
    // 是否全屏
    const isFullscreen = inject('isFullscreen', false);
    // hover 图表右侧线条距离
    const axisLeft = ref(0);
    const wrapRefRect = ref({ left: 0, top: 0 }); // 图表区域
    const wrapRefWidth = ref(0);
    const axisLabelValue = ref('');
    // is show context menu
    const showContextMenu = ref(false);
    const contextMenuRect = ref({ left: 0, top: 0 });
    const contextMenuSpanId = ref('');
    // 高亮的 span name
    const hilightSpanName = ref('');
    // 是否显示异常
    const showException = ref(false);
    // click spanid
    const clickSpanId = ref('');
    // 右键menu id
    const contextMenuId = ref('');
    let rootValue = 0;
    // 缩放区域 对于 start end
    const dataZoom = ref({
      startTime: 0,
      endTime: 0,
    });
    // 放大系数
    const scaleValue = ref(100);
    const scaleStepValue = ref(0);
    // 转换 对应 id value
    function transformData(json: IJsonItem, id?: string): IJsonItem {
      if (!id) return json;
      const reduce = (item: IJsonItem, id?: string): IJsonItem | undefined => {
        if (item.id === id) return item;
        for (const child of item.children || []) {
          const temp = reduce(child, id);
          if (temp) {
            item.children = [temp];
            item.rawValue = item.value;
            item.value = getSpanValue(temp);
            item.start_time = temp.start_time;
            item.end_time = temp.end_time;
            return item;
          }
        }
      };
      return reduce(json, id) || json;
    }
    // 转换 datazom start end time value
    function transformDataZoomData(json: IJsonItem) {
      if (!dataZoom.value.endTime && !dataZoom.value.endTime) return json;
      const { startTime, endTime } = dataZoom.value;
      const reduce = (item: IJsonItem): IJsonItem | undefined => {
        if (item.end_time <= startTime || item.start_time >= endTime) {
          return undefined;
        }
        return {
          ...item,
          start_time: item.start_time < startTime ? startTime : item.start_time,
          end_time: item.end_time > endTime ? endTime : item.end_time,
          children: item.children?.map(set => reduce(set)).filter(Boolean),
        };
      };
      return reduce(json);
    }
    function getSpanValue(item: IJsonItem) {
      if ('comparison' in item && 'baseline' in item) {
        return item.comparison & item.baseline;
      }
      return item.value;
    }
    // reduce data
    function recursionJson(json: IJsonItem, id?: string): IDataItem[] {
      if (!json) return [];
      const data: IDataItem[] = [];
      const rootVal = getSpanValue(json);
      const a = transformDataZoomData(structuredClone(json));
      const transData = transformData(a, id);
      const rootStart = transData.start_time;
      const reduce = (item: IJsonItem, start = 0, level = 0): void => {
        const rawValue = item.rawValue || getSpanValue(item);
        const temp: IDataItem = {
          name: item.id || random(10),
          value: [
            level,
            item.start_time - start,
            item.end_time - start,
            item.name,
            (rawValue / rootVal) * 100,
            item.icon_type,
            rawValue,
            {
              status: item.original?.status,
              span_id: item.original?.span_id,
              kind: item.original?.kind,
            },
          ],
          itemStyle: {
            color: ColorTypes[item.icon_type || 'other'],
          },
        };
        data.push(temp);
        item.children.sort((a, b) => a.start_time - b.start_time);
        for (const child of item.children || []) {
          reduce(child, rootStart, level + 1);
        }
      };
      reduce(transData, rootStart, 0);
      rootValue = +data?.[0]?.value[2] || 0;
      data.sort((a: any, b: any) => a.value[0] - b.value[0]);
      return data;
    }
    // function resetParallelData(data: IDataItem[]) {
    //   const maxValue = data.reduce((prev, curr) => {

    // }
    // max level
    function getMaxLevelOfJson(json: IJsonItem): number {
      const reduce = (item: IJsonItem, level = 0): number => {
        if ((item.children || []).length === 0) {
          return level;
        }
        let maxLevel = level;
        for (const child of item.children!) {
          const tempLevel = reduce(child, level + 1);
          maxLevel = Math.max(maxLevel, tempLevel);
        }
        return maxLevel;
      };
      return reduce(json);
    }
    function renderItem(param, api: any, data: IDataItem[]) {
      const level = api.value(0);
      const start = api.coord([api.value(1), maxLevel.value - level + 2]);
      const end = api.coord([api.value(2), maxLevel.value - level + 2]);
      const height: number = api.size([1, 1])[1];
      const width = Math.max(end[0] - start[0], 2);
      const isMinWidth = width === 2;
      const isHighlight = api.value(3) === hilightSpanName.value;
      const grayFill = isMinWidth || (contextMenuId.value === 'highlight' && !isHighlight);
      const y = defaultHeight >= height ? start[1] : 20 + defaultHeight * level;
      const needIcon = width > 36;
      const { text, suffix } = usFormat(api.value(6));
      const textWidth = needIcon ? width - 24 : width - 4;
      const { status } = data[param.dataIndexInside]?.value?.[7] as Record<string, any>;
      // const textCount = Math.floor(textWidth / 18);
      const rect = {
        type: 'rect',
        transition: ['shape'],
        animation: false,
        z2: 8,
        shape: {
          x: start[0],
          y,
          width,
          height: Math.min(height, defaultHeight),
          r: 0,
        },
        style: {
          fill: grayFill ? '#aaa' : api.visual('color'),
          stroke: status?.code === 2 ? '#EA3636' : '#2b2b2d',
          lineWidth: status?.code === 2 ? 1 : isMinWidth ? 0 : 0.5,
        },
        emphasis: {
          style: {
            stroke: status?.code === 2 ? '#EA3636' : '#2b2b2d',
            fill: grayFill ? '#aaa' : lightenDarkenColor(api.visual('color'), 60),
          },
        },
        textConfig: {
          position: needIcon ? [24, 9] : 'insideLeft',
          inside: true,
        },
        textContent: {
          type: 'text',
          style: {
            textAlign: 'right',
            text: `${api.value(3)} (${api.value(4).toFixed(2)}%, ${text}${suffix})`,
            fill: '#000',
            width: textWidth,
            overflow: 'truncate',
            ellipsis: '..',
            truncateMinChar: 1,
          },
        },
      };
      if (needIcon)
        return {
          type: 'group',
          children: [
            {
              type: 'image',
              x: start[0] + 4,
              y: y + 6,
              z2: 10,
              style: {
                image: status?.code === 2 ? traceIcons.error : traceIcons[api.value(5)],
                width: 16,
                height: 16,
              },
            },
            {
              ...rect,
            },
          ],
        };
      return rect;
    }
    function getEchartsOptions(data: IDataItem[]) {
      return {
        grid: {
          left: 8,
          top: 20,
          bottom: 2,
          right: 2,
        },
        backgroundColor: '#F5F6F9',
        tooltip: {
          padding: 0,
          backgroundColor: '#000',
          borderColor: '#000',
          appendToBody: !isFullscreen,
          trigger: 'item',
          axisPointer: {
            snap: false,
          },
          formatter: (params: any) => {
            const { text, suffix } = usFormat(params.value[6]);
            const title = params.name === RootSpanId ? 'total' : `Span：${params.value[3]}`;
            const html = `
          <div class="flame-graph-tips">
           <div class="funtion-name">${title}</div>
            <table class="tips-table">
              <tbody>
                <tr>
                  <td>${window.i18n.t('占比')}</td>
                  <td>${params.value[4].toFixed(4).replace(/[0]+$/g, '')}%</td>
                </tr>
                <tr>
                  <td>${window.i18n.t('耗时')}</td>
                  <td>${text}${suffix}</td>
                </tr>
              </tbody>
            </table>
            <div class="tips-info">
              <span class="icon-monitor icon-mc-mouse tips-info-icon"></span>${window.i18n.t('鼠标右键有更多菜单')}
            </div>
          </div>`;
            return html;
          },
        },
        title: {
          show: false,
        },
        toolbox: {
          showTitle: false,
          itemSize: 0,
          feature: {
            dataZoom: {
              icon: {
                zoom: 'path://',
                back: 'path://',
              },
              show: true,
              yAxisIndex: false,
              iconStyle: {
                opacity: 0,
              },
            },
          },
        },
        // dataZoom: [
        //   {
        //     type: 'inside',
        //     xAxisIndex: 0,
        //     start: 0,
        //     end: 100,
        //     filterMode: 'none'
        //   },
        //   {
        //     xAxisIndex: 0,
        //     type: 'slider',
        //     bottom: 10,
        //     filterMode: 'none',
        //     start: 0,
        //     end: 100
        //   }
        // {
        //   type: 'inside',
        //   yAxisIndex: 0,
        //   start: 0,
        //   end: 100,
        //   filterMode: 'none'
        // },
        // {
        //   yAxisIndex: 0,
        //   type: 'slider',
        //   left: 10,
        //   filterMode: 'none',
        //   start: 0,
        //   end: 100
        // }
        // ],
        xAxis: {
          show: true,
          max: data[0].value[2],
          position: 'top',
          axisLine: {
            show: true,
            color: '#ddd',
          },
          splitLine: {
            show: true,
          },
          splitArea: {
            show: false,
          },
          axisTick: {
            inside: false,
          },
          axisLabel: {
            overflow: 'truncate',
            ellipsis: '..',
            align: 'right',
            formatter: (value: number) => {
              if (!value) return 0;
              const { text, suffix } = usFormat(value);
              return (text.replace(/\.[0]+$/g, '') || 0) + suffix;
            },
          },
        },
        yAxis: {
          inverse: true,
          show: false,
          max: maxLevel.value + 2,
        },
        // animation: false,
        series: [
          {
            type: 'custom',
            renderItem: (_: any, api: any) => renderItem(_, api, data),
            encode: {
              x: [1, 2],
              y: 0,
            },
            data,
          },
        ],
      };
    }

    function addRootNode(data: IJsonItem[]): IJsonItem {
      const root: IJsonItem = {
        value: 0,
        name: 'total',
        id: RootSpanId,
        start_time: 0,
        end_time: 0,
        rawValue: 0,
      };
      data.forEach((item, index) => {
        root.start_time = index === 0 ? item.start_time : Math.min(root.start_time, item.start_time);
        root.end_time = Math.max(root.end_time, item.end_time);
      });
      root.value = root.end_time - root.start_time;
      return {
        ...root,
        rawValue: root.value,
        children: data,
      };
    }
    function activeDataZoom(active = true) {
      chartInstance.dispatchAction({
        type: 'takeGlobalCursor',
        key: 'dataZoomSelect',
        dataZoomSelectActive: active,
      });
    }
    watch(
      [() => props.traceId, () => props.appName, () => props.diffTraceId, () => props.filters],
      debounce(16, async () => {
        emit('update:loading', true);
        showException.value = false;
        try {
          const data = await traceDiagram(
            {
              trace_id: props.traceId,
              app_name: props.appName,
              diagram_type: 'flamegraph',
              show_attrs: 0,
              displays: props.filters.filter(item => item !== 'duration'),
              // diff_trace_id: props.diffTraceId
            },
            {
              needCancel: true,
            }
          ).catch(() => false);
          if (data.diagram_data) {
            emit('update:loading', true);
            showException.value = false;
            nextTick(() => {
              if (!chartInstance) {
                chartInstance = echarts.init(chartRef.value!);
              }
              chartInstance.off('click');
              chartInstance.off('contextmenu');
              chartInstance.off('dataZoom');
              chartData = addRootNode(data.diagram_data);
              maxLevel.value = getMaxLevelOfJson(chartData);
              height.value = Math.max(height.value, maxLevel.value * defaultHeight + 40);
              calcScaleStepValue(chartData.value);
              chartInstance.setOption(getEchartsOptions(recursionJson(chartData)));
              emit('update:loading', false);
              activeDataZoom();
              requestIdleCallback(() => {
                chartInstance.on('dataZoom', (event: any) => {
                  // chartInstance.clear();
                  // const rootValue =  chartData.value;
                  // const start = 'batch' in event ? event.batch[0].start : event.start;
                  // const end = 'batch' in event ? event.batch[0].end : event.end;
                  // dataZoom.value.startTime = chartData.start_time + (rootValue * start / 100);
                  // dataZoom.value.endTime = chartData.start_time + (rootValue * end / 100);

                  // console.info(start, end);
                  // calcScaleStepValue(dataZoom.value.endTime - dataZoom.value.startTime);
                  // chartInstance.setOption(
                  //   {
                  //     ...getEchartsOptions(recursionJson(chartData, clickSpanId.value || undefined)),
                  //     dataZoom: [
                  //       {
                  //         type: 'inside',
                  //         xAxisIndex: 0,
                  //         start: start || 0,
                  //         end: end || 100,
                  //         filterMode: 'none'
                  //       },
                  //       {
                  //         xAxisIndex: 0,
                  //         type: 'slider',
                  //         bottom: 10,
                  //         filterMode: 'none',
                  //         start: start || 0,
                  //         end: end || 100
                  //       }
                  //       // {
                  //       //   type: 'inside',
                  //       //   yAxisIndex: 0,
                  //       //   start: 0,
                  //       //   end: 100,
                  //       //   filterMode: 'none'
                  //       // },
                  //       // {
                  //       //   yAxisIndex: 0,
                  //       //   type: 'slider',
                  //       //   left: 10,
                  //       //   filterMode: 'none',
                  //       //   start: 0,
                  //       //   end: 100
                  //       // }
                  //     ]
                  //   },
                  //   true,
                  //   false
                  // );
                  // activeDataZoom();
                  if ('batch' in event) {
                    const [batch] = event.batch;
                    if (chartInstance && (batch.startValue || batch.endValue)) {
                      scaleValue.value = MinScale;
                      let startTime = 0;
                      if (clickSpanId.value) {
                        const transData = transformData(structuredClone(chartData), clickSpanId.value);
                        startTime = +(dataZoom.value.startTime || transData.start_time);
                      } else {
                        startTime = +(dataZoom.value.startTime || chartData.start_time);
                      }
                      dataZoom.value.startTime = startTime + batch.startValue;
                      dataZoom.value.endTime = startTime + batch.endValue;
                      calcScaleStepValue(dataZoom.value.endTime - dataZoom.value.startTime);
                      chartInstance.setOption(
                        getEchartsOptions(recursionJson(chartData, clickSpanId.value || undefined)),
                        true,
                        false
                      );
                      activeDataZoom();
                    }
                  }
                  // else if (event.end) {
                  //   const rootValue =  chartData.value;
                  //   dataZoom.value.startTime = chartData.start_time + rootValue * event.start / 100;
                  //   dataZoom.value.endTime = chartData.start_time + rootValue * event.end / 100;
                  //   calcScaleStepValue(dataZoom.value.endTime - dataZoom.value.startTime);
                  //   chartInstance.setOption(
                  //     getEchartsOptions(recursionJson(chartData, undefined)),
                  //     true,
                  //     false
                  //   );
                  //   activeDataZoom();
                  // }
                });
                chartInstance.on('click', (params: any) => {
                  [clickLevel.value] = params.data.value;
                  clickSpanId.value = params.data.name;
                  showContextMenu.value = false;
                  if (clickSpanId.value === RootSpanId) {
                    hilightSpanName.value = '';
                    contextMenuId.value = '';
                    scaleValue.value = MinScale;
                    dataZoom.value = { startTime: 0, endTime: 0 };
                    calcScaleStepValue(chartData.value);
                  }
                  chartInstance.setOption(getEchartsOptions(recursionJson(chartData, clickSpanId.value)), true, false);
                  activeDataZoom();
                });
                chartInstance.on('contextmenu', params => {
                  activeDataZoom(false);
                  contextMenuSpanId.value = params.name;
                  hilightSpanName.value = params.value[3];
                  contextMenuRect.value = { left: params.event.offsetX, top: params.event.offsetY };
                  showContextMenu.value = true;
                });
              });
            });
            return;
          }
          showException.value = true;
          emit('update:loading', false);
        } catch (e) {
          console.error(e);
          emit('update:loading', false);
          showException.value = true;
        }
      }),
      { immediate: true }
    );
    onMounted(() => {
      addListener(chartWrapRef.value!, handleResize);
      requestIdleCallback(() => {
        chartInstance = echarts.init(chartRef.value!);
      });
    });
    function handleResize() {
      if (chartRef.value) {
        const rect = chartWrapRef.value.getBoundingClientRect();
        wrapRefRect.value = { left: rect.x, top: rect.y };
        height.value = Math.max(rect.height, maxLevel.value * defaultHeight + 40);
        chartInstance?.resize?.();
      }
    }
    onBeforeUnmount(() => {
      chartWrapRef.value && removeListener(chartWrapRef.value, handleResize);
    });
    function handleGraphWarpOver() {
      if (showException.value) return;
      chartWrapRef.value?.focus?.();
      const rect = chartWrapRef.value.getBoundingClientRect();
      wrapRefRect.value = { left: rect.x, top: rect.y };
      wrapRefWidth.value = rect.width - 6 - 8 - 6 - 2;
    }
    function handleGraphWarpMove(event: MouseEvent) {
      if (showException.value) return;
      axisLeft.value = event.x - wrapRefRect.value.left;
      const { text, suffix } = usFormat(((axisLeft.value - 14) / wrapRefWidth.value) * rootValue);
      axisLabelValue.value = text + suffix;
    }

    function handleGraphWarpLeave() {
      axisLeft.value = 0;
    }
    /**
     * @description: click context menu
     * @param {ICommonMenuItem} item menu item
     * @return {*}
     */
    function handleContextMenuClick(item: ICommonMenuItem) {
      showContextMenu.value = false;
      contextMenuId.value = item.id;
      if (item.id === 'span') {
        return contextMenuSpanId.value && emit('showSpanDetail', contextMenuSpanId.value);
      }
      if (item.id === 'reset') {
        hilightSpanName.value = '';
        scaleValue.value = MinScale;
        dataZoom.value = { startTime: 0, endTime: 0 };
        calcScaleStepValue(chartData.value);
        chartInstance.setOption(getEchartsOptions(recursionJson(chartData)), true, false);
        activeDataZoom();
        clickLevel.value = 0;
      } else if (item.id === 'highlight') {
        chartInstance.setOption(getEchartsOptions(recursionJson(chartData, clickSpanId.value)), true, false);
        activeDataZoom();
      }
    }
    function calcScaleStepValue(rootValue: number) {
      scaleStepValue.value = rootValue / TotalStep;
    }
    watch(scaleValue, (v: number, o: number) => {
      const changeScale = v - o;
      // 不能跨级
      if (Math.abs(changeScale) > scaleStep) return;
      if (chartInstance) {
        const direction = changeScale > 0 ? +1 : -1;
        const changeValue = direction * (scaleStepValue.value * (Math.abs(changeScale) / scaleStep));
        let startTime = 0;
        if (clickSpanId.value) {
          startTime = +(
            dataZoom.value.startTime || transformData(structuredClone(chartData), clickSpanId.value).start_time
          );
        } else {
          startTime = +(dataZoom.value.startTime || chartData.start_time);
        }

        dataZoom.value.startTime = startTime + changeValue / 2;

        dataZoom.value.endTime =
          startTime + (TotalStep - (v - MinScale) / scaleStep) * scaleStepValue.value - changeValue / 2;
        chartInstance.setOption(
          getEchartsOptions(recursionJson(chartData, clickSpanId.value || undefined)),
          true,
          false
        );
        activeDataZoom();
      }
    });
    function handleGraphWarpBlur() {
      showContextMenu.value = false;
    }
    function handlesSaleValueChange(v: number) {
      scaleValue.value = v;
    }
    function handleStoreImg() {
      storeImage(`${props.appName}_${props.traceId}`, chartRef.value);
    }
    expose(chartInstance);
    return {
      chartRef,
      chartWrapRef,
      chartInstance,
      maxLevel,
      scaleValue,
      clickLevel,
      clickSpanId,
      axisLabelValue,
      contextMenuSpanId,
      wrapRefRect,
      wrapRefWidth,
      rootValue,
      height,
      axisLeft,
      isFullscreen,
      showException,
      showContextMenu,
      contextMenuRect,
      getEchartsOptions,
      handleGraphWarpOver,
      handleGraphWarpLeave,
      handleGraphWarpMove,
      handleContextMenuClick,
      handleGraphWarpBlur,
      handlesSaleValueChange,
      handleStoreImg,
      t,
    };
  },
  render() {
    if (this.showException)
      return (
        <Exception
          description={this.t('暂无数据')}
          type='empty'
        />
      );
    return (
      <div class='flame-graph-wrap'>
        {false && <DiffColorList />}
        <div
          ref='chartWrapRef'
          class='flame-graph'
          tabindex={0}
          onBlur={this.handleGraphWarpBlur}
          onMouseleave={this.handleGraphWarpLeave}
          onMousemove={this.handleGraphWarpMove}
          onMouseover={this.handleGraphWarpOver}
        >
          <div
            ref='chartRef'
            style={{ height: `${this.height.value}px` }}
            class='flame-graph-chart'
            onContextmenu={e => e.preventDefault()}
          />
          <div
            style={{ height: `${Math.max(30 * this.clickLevel, 0)}px` }}
            class='flame-graph-blur'
          />
          <div
            style={{
              left: `${this.axisLeft}px`,
              visibility: this.axisLeft < 14 || this.axisLeft > this.wrapRefWidth + 14 ? 'hidden' : 'visible',
            }}
            class='flame-graph-axis'
          >
            <span class='axis-label'>{this.axisLabelValue}</span>
          </div>
          <ul
            style={{
              left: `${this.contextMenuRect.left}px`,
              top: `${this.contextMenuRect.top}px`,
              visibility: this.showContextMenu ? 'visible' : 'hidden',
            }}
            class='flame-graph-menu'
          >
            {CommonMenuList.map(item => (
              <li
                key={item.id}
                class='menu-item'
                onClick={() => this.handleContextMenuClick(item)}
              >
                <i class={`menu-item-icon icon-monitor ${item.icon}`} />
                <span class='menu-item-text'>{item.name}</span>
              </li>
            ))}
          </ul>
          <GraphTools
            maxScale={MaxScale}
            minScale={MinScale}
            scaleStep={scaleStep}
            scaleValue={this.scaleValue}
            showThumbnail={false}
            onScaleChange={this.handlesSaleValueChange}
            onStoreImg={this.handleStoreImg}
          />
        </div>
      </div>
    );
  },
});
