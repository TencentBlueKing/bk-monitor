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

import { computed, defineComponent, nextTick, onBeforeUnmount, ref, watch } from 'vue';
import { shallowRef } from 'vue';
import { useI18n } from 'vue-i18n';

import { removeListener, addListener } from '@blueking/fork-resize-detector';
import { Exception, Message } from 'bkui-vue';
import { query } from 'monitor-api/modules/apm_profile';
import { updateColorOpacity } from 'monitor-common/utils';
import { copyText } from 'monitor-common/utils/utils';
import {
  COMPARE_DIFF_COLOR_LIST,
  getSingleDiffColor,
} from 'monitor-ui/chart-plugins/plugins/profiling-graph/flame-graph/utils';
import {
  parseProfileDataTypeValue,
  type ProfileDataUnit,
} from 'monitor-ui/chart-plugins/plugins/profiling-graph/utils';
import { getSpanColorByName, type BaseDataType } from 'monitor-ui/chart-plugins/typings/flame-graph';
import { CommonMenuList, type ICommonMenuItem } from 'monitor-ui/chart-plugins/typings/flame-graph';
import { echarts } from 'monitor-ui/monitor-echarts/types/monitor-echarts';
import { debounce } from 'throttle-debounce';

import type { IFlameGraphDataItem, IProfilingGraphData } from './types';

import './flame-graph.scss';

const defaultHeight = 20;
export default defineComponent({
  name: 'FlameGraph',
  props: {
    data: {
      type: Object as () => BaseDataType,
      default: () => {},
    },
    appName: {
      type: String,
      default: '',
    },
    serviceName: {
      type: String,
      default: '',
    },
    diffTraceId: {
      type: String,
      default: '',
    },
    filterKeyword: {
      type: String,
      default: '',
    },
    textDirection: {
      type: String as () => 'ltr' | 'rtl',
      default: 'ltr',
    },
    profileId: {
      type: String,
      default: '',
    },
    start: {
      type: Number,
      default: 0,
    },
    end: {
      type: Number,
      default: 0,
    },
    bizId: {
      type: [Number, String],
      default: '',
    },
    isCompared: {
      type: Boolean,
      default: false,
    },
    unit: {
      type: String as () => ProfileDataUnit,
      default: 'nanoseconds',
    },
  },
  emits: ['update:loading', 'diffTraceSuccess', 'update:filterKeyword'],
  setup(props, { emit }) {
    const { t } = useI18n();
    let chartInstance = null; // echarts 实例

    const chartRef = ref<HTMLElement>(null);
    const wrapperRef = ref<HTMLElement>(null);
    const flameToolsPopoverContent = ref<HTMLElement>(null);
    const showException = ref(true);
    const graphToolsRect = ref<Partial<DOMRect>>({ left: 0, top: 0, width: 120, height: 300 });
    /** 是否显示图例 */
    const showLegend = ref(false);
    // 放大系数
    const scaleValue = ref(100);
    const localIsCompared = ref(false);

    const maxLevel = ref(0);
    const height = ref(100);
    const highlightNode = ref<IProfilingGraphData>();

    const profilingData = shallowRef<IProfilingGraphData[]>([]);
    const currentGraphData = shallowRef<IProfilingGraphData[]>([]);

    const showContextMenu = ref(false);
    const contextMenuRect = ref({ left: 0, top: 0 });

    const diffPercentList = computed(() =>
      COMPARE_DIFF_COLOR_LIST.map(val => `${val.value > 0 ? '+' : ''}${val.value}%`)
    );
    const canvas = document.createElement('canvas');
    const context = canvas.getContext('2d');
    context.font = '12px sans-serif';
    function getMaxWidthText(text: string, width: number) {
      context.clearRect(0, 0, canvas.width, canvas.height);
      const charWidth = (text: string): number => context.measureText(text).width;
      let truncatedText = text;
      while (charWidth(truncatedText) > width && truncatedText.length > 0) {
        truncatedText = truncatedText.slice(0, -1);
      }
      return truncatedText;
    }
    function renderItem(param, api) {
      const level = api.value(0);
      const start = api.coord([api.value(1), level]);
      const end = api.coord([api.value(2), level]);
      const nodeItem: IFlameGraphDataItem = currentGraphData.value[param.dataIndexInside]?.value?.[3];
      const height: number = api.size([1, 1])[1];
      const width = Math.max(end[0] - start[0], 2);
      const isMinWidth = width < 4;
      const y = defaultHeight >= height ? start[1] : defaultHeight * level + 2;
      // const { value } = parseProfileDataTypeValue(nodeItem.value, props.unit);
      const color = nodeItem.diff_info ? getSingleDiffColor(nodeItem.diff_info) : getSpanColorByName(nodeItem.name);
      let rectColor = color;
      if (isMinWidth) {
        rectColor = '#ddd';
      } else if (props.filterKeyword) {
        rectColor = nodeItem.name.toLocaleLowerCase().includes(props.filterKeyword.toString().toLocaleLowerCase())
          ? color
          : '#aaa';
      } else if (+highlightNode.value?.level > level) {
        rectColor = '#aaa';
      }
      const name = props.textDirection === 'ltr' ? nodeItem.name : nodeItem.name.split('').reverse().join('');
      let text = '';
      if (!isMinWidth) {
        text = getMaxWidthText(name, width - 4);
        if (props.textDirection !== 'ltr') {
          text = text.split('').reverse().join('');
        }
      }
      return {
        type: 'rect',
        transition: [],
        animation: false,
        // z2: 10,
        shape: {
          x: start[0],
          y,
          width,
          height: defaultHeight,
          r: 0,
        },
        style: {
          fill: rectColor,
          stroke: '#fff',
          lineWidth: isMinWidth ? 0 : 0.5,
        },
        emphasisDisabled: true,
        emphasis: {
          style: {
            stroke: '#fff',
            fill: updateColorOpacity('#edeef3', 0.3),
          },
        },
        textConfig: {
          position: 'insideLeft',
          inside: true,
          outsideFill: 'transparent',
        },
        textContent: {
          type: 'text',
          // z2: 100,
          style: {
            textAlign: props.textDirection === 'ltr' ? 'left' : 'right',
            text,
            fill: '#000',
            width: width,
            overflow: 'truncate',
            ellipsis: '',
            truncateMinChar: 1,
          },
        },
      };
    }
    function getEchartsOptions(data: IProfilingGraphData[]) {
      currentGraphData.value = data;
      return {
        grid: {
          id: 'grid',
          show: false,
          left: 2,
          top: 2,
          bottom: 2,
          right: 2,
        },
        animation: false,
        tooltip: {
          padding: 0,
          backgroundColor: '#000',
          borderColor: '#000',
          appendToBody: false,
          trigger: 'item',
          axisPointer: {
            snap: false,
          },
          formatter: (params: any) => {
            const nodeItem: IFlameGraphDataItem = params.value?.[3];
            const { value } = parseProfileDataTypeValue(nodeItem.value, props.unit);
            const { name, diff_info, proportion } = nodeItem;
            let reference = undefined;
            let difference = undefined;
            if (props.isCompared && diff_info) {
              reference = parseProfileDataTypeValue(diff_info.comparison, props.unit)?.value;
              difference = diff_info.comparison === 0 || diff_info.mark === 'unchanged' ? 0 : diff_info.diff;
            }
            return `<div class="flame-graph-tips" style="display: block; left: 1241px; top: 459px;">
            <div class="funtion-name">${name}</div>
            <table class="tips-table">
              ${
                diff_info
                  ? `<thead>
                <th></th>
                <th>当前</th>
                <th>参照</th>
                <th>差异</th>
              </thead>`
                  : ''
              }
              <tbody>
                ${
                  !diff_info
                    ? `<tr>
                        <td>${t('占比')}</td>
                        <td>${proportion.toFixed(4).replace(/[0]+$/g, '')}%</td>
                      </tr>
                      <tr>
                        <td>${t('耗时')}</td>
                        <td>${value}</td>
                      </tr>`
                    : `<tr>
                      <td>${t('耗时')}</td>
                      <td>${value}</td>
                      <td>${reference ?? '--'}</td>
                      <td>
                        ${
                          diff_info.mark === 'added'
                            ? `<span class='tips-added'>${diff_info.mark}</span>`
                            : `${(difference * 100).toFixed(2)}%`
                        }
                      </td>
                    </tr>`
                }
              </tbody>
            </table>
            <div class="tips-info">
              <span class="icon-monitor icon-mc-mouse tips-info-icon"></span>${window.i18n.t('鼠标右键有更多菜单')}
            </div>`;
          },
        },
        title: {
          show: false,
        },
        toolbox: false,
        hoverLayerThreshold: 1000 ** 5,
        xAxis: {
          show: false,
          max: data[0].value[2],
          position: 'top',
        },
        yAxis: {
          inverse: true,
          show: false,
          max: data.at(-1)?.level,
        },
        series: [
          {
            type: 'custom',
            renderItem: renderItem,
            encode: {
              x: [1, 2],
              y: 0,
            },
            data,
            animation: false,
          },
        ],
      };
    }
    function recursionData(jsonData: IFlameGraphDataItem) {
      const rootValue = jsonData.value;
      function flattenTreeWithLevelBFS(data: IFlameGraphDataItem[]): any[] {
        const result: IProfilingGraphData[] = [];
        const queue: { node: IFlameGraphDataItem; level: number; start: number; end: number }[] = [];
        queue.push({ node: data[0], level: 0, start: 0, end: 0 });
        while (queue.length > 0) {
          const { node, level, start, end } = queue.shift();
          const { children, ...others } = node;
          const item = {
            ...others,
            level,
            start,
            end: level === 0 ? node.value : end,
          };
          result.push({
            ...item,
            // name: node.id,
            value: [
              level,
              start,
              level === 0 ? node.value : end,
              { ...item, proportion: (item.value / rootValue) * 100 },
            ],
          });
          if (node.children && node.children.length > 0) {
            let parentStart = start || 0; // 记录当前兄弟节点的 end 值
            for (const child of node.children) {
              queue.push({
                node: child,
                level: level + 1,
                start: parentStart,
                end: parentStart + child.value,
              });
              parentStart += child.value;
            }
          }
        }
        return result;
      }
      const list = flattenTreeWithLevelBFS(Array.isArray(jsonData) ? jsonData : [jsonData]);
      console.info(list);
      return list;
    }
    watch(
      [() => props.data, props.appName],
      debounce(16, async () => {
        emit('update:loading', true);
        showException.value = false;
        try {
          const { bizId, appName, serviceName, start, end, profileId } = props;
          const data: IFlameGraphDataItem = props.data
            ? props.data
            : ((
                await query(
                  {
                    bk_biz_id: bizId,
                    app_name: appName,
                    service_name: serviceName,
                    start,
                    end,
                    profile_id: profileId,
                    diagram_types: ['flamegraph'],
                  },
                  {
                    needCancel: true,
                  }
                ).catch(() => false)
              )?.flame_data ?? false);

          if (data) {
            if (props.diffTraceId) {
              emit('diffTraceSuccess');
            }
            showException.value = false;
            await nextTick();
            if (!chartRef.value?.clientWidth) return;
            localIsCompared.value = props.isCompared;
            showException.value = false;
            profilingData.value = recursionData(data);
            maxLevel.value = profilingData.value.at(-1)?.level;
            height.value = Math.max(height.value, maxLevel.value * defaultHeight + 40);
            const rect = chartRef.value?.getBoundingClientRect();
            setTimeout(() => {
              if (!chartInstance) {
                chartInstance = echarts.init(chartRef.value!, undefined, {
                  renderer: 'canvas',
                  useDirtyRect: false,
                  height: height.value,
                  ssr: false,
                });
              }
              console.info(rect.width, rect.height, height.value, '++++++');
              chartInstance.off('click');
              chartInstance.off('contextmenu');
              const options = getEchartsOptions(profilingData.value);
              console.info(options);
              chartInstance.setOption(options);
              addListener(wrapperRef.value, handleResizeGraph);
              chartInstance.on('click', async (params: any) => {
                chartInstance.dispatchAction({
                  type: 'downplay',
                  seriesIndex: params.seriesIndex,
                  seriesId: params.seriesId,
                  seriesName: params.seriesName,
                  dataIndex: params.dataIndex,
                });
                await new Promise(r => setTimeout(r, 16));
                // chartInstance.clear();
                // debugger;
                const id = params.data.value[3].id;
                const clickNode = profilingData.value.find(item => item.id === id);
                highlightNode.value = clickNode;
                const [, start, end, { value }] = clickNode.value;
                const cloneData = structuredClone(profilingData.value);
                const list = [];
                for (const item of cloneData) {
                  if (item.start >= end || item.end <= start) {
                    continue;
                  }
                  const newStart = Math.max(item.start - start, 0);
                  const newValue = Math.min(item.end - item.start, value);
                  list.push({
                    ...item,
                    value: [item.level, newStart, newStart + newValue, item.value[3]],
                  });
                }
                currentGraphData.value = list;
                chartInstance.setOption(getEchartsOptions(list), {
                  notMerge: true,
                });
                console.info(chartInstance.getOption());
              });
              chartInstance.on('contextmenu', (params: any) => {
                console.info(params);
                highlightNode.value = params.value[3];
                contextMenuRect.value = { left: params.event.offsetX, top: params.event.offsetY };
                showContextMenu.value = true;
              });
              emit('update:loading', false);
            }, 16);
            nextTick(() => {
              emit('update:loading', false);
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
    watch([() => props.filterKeyword], () => {
      if (!props.filterKeyword) {
        highlightNode.value = null;
        currentGraphData.value = profilingData.value;
      }
      chartInstance.setOption({
        xAxis: { max: currentGraphData.value[0].value[2] },
        series: [{ data: currentGraphData.value }],
      });
    });
    watch(
      () => props.textDirection,
      () => {
        chartInstance.setOption({
          xAxis: { max: currentGraphData.value[0].value[2] },
          series: [{ data: currentGraphData.value }],
        });
      }
    );
    function handleContextMenuClick(item: ICommonMenuItem) {
      contextMenuRect.value.left = -1;
      showContextMenu.value = false;
      if (item.id === 'copy') {
        let hasErr = false;
        copyText(highlightNode.value.name, (errMsg: string) => {
          Message({
            message: errMsg,
            theme: 'error',
          });
          hasErr = !!errMsg;
        });
        if (!hasErr) Message({ theme: 'success', message: t('复制成功') });

        return;
      }
      if (item.id === 'reset') {
        highlightNode.value = null;
        currentGraphData.value = profilingData.value;
        chartInstance.setOption({
          xAxis: { max: currentGraphData.value[0].value[2] },
          series: [{ data: currentGraphData.value }],
        });
      }
      if (item.id === 'highlight') {
        emit('update:filterKeyword', highlightNode.value.name);
      }
    }
    function handleClickWrapper() {
      contextMenuRect.value.left = -1;
      showContextMenu.value = false;
    }
    function handleResizeGraph() {
      chartInstance?.resize();
    }
    onBeforeUnmount(() => {
      removeListener(wrapperRef.value, handleResizeGraph);
    });
    return {
      chartRef,
      wrapperRef,
      graphToolsRect,
      scaleValue,
      showException,
      flameToolsPopoverContent,
      showLegend,
      diffPercentList,
      localIsCompared,
      height,
      contextMenuRect,
      showContextMenu,
      handleContextMenuClick,
      handleClickWrapper,
    };
  },
  render() {
    if (this.showException)
      return (
        <Exception
          style='flex: 1'
          description={this.$t('暂无数据')}
          type='empty'
        />
      );
    return (
      <div
        ref='wrapperRef'
        style='height: fit-content; flex: 1; position: relative'
        tabindex={1}
        onBlur={this.handleClickWrapper}
        onClick={this.handleClickWrapper}
      >
        {this.isCompared && (
          <div class='profiling-compare-legend'>
            <span class='tag tag-new'>added</span>
            <div class='percent-queue'>
              {this.diffPercentList.map((item, index) => (
                <span
                  key={index}
                  class={`percent-tag tag-${index + 1}`}
                >
                  {item}
                </span>
              ))}
            </div>
            <span class='tag tag-removed'>removed</span>
          </div>
        )}
        <div
          key='chart'
          ref='chartRef'
          style={{ height: `${this.height}px` }}
          class='flame-graph'
          onContextmenu={e => e.preventDefault()}
        />
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
      </div>
    );
  },
});
