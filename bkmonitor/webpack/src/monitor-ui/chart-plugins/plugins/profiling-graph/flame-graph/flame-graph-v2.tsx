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

import { addListener, removeListener } from '@blueking/fork-resize-detector';
import dayjs from 'dayjs';
import { query } from 'monitor-api/modules/apm_profile';
import { copyText } from 'monitor-common/utils/utils';
import { debounce } from 'throttle-debounce';

import { echarts } from '../../../../monitor-echarts/types/monitor-echarts';
import {
  downloadBase64AsPng,
  getGraphOptions,
  recursionData,
} from '../../../hooks/profiling-graph/use-profiling-flame-graph';
import { type ICommonMenuItem, CommonMenuList } from '../../../typings/flame-graph';
import { COMPARE_DIFF_COLOR_LIST } from '../flame-graph/utils';

import type { IFlameGraphDataItem, IProfilingGraphData } from '../../../hooks/profiling-graph/types';
import type { BaseDataType } from '../../../typings/flame-graph';
import type { ProfileDataUnit } from '../utils';

import './flame-graph-v2.scss';

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
    downloadImgIndex: {
      type: Number,
      default: 0,
    },
  },
  emits: ['updateLoading', 'diffTraceSuccess', 'updateFilterKeyword'],
  setup(props, { emit }) {
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
    function getEchartsOptions() {
      return getGraphOptions(currentGraphData.value, {
        unit: props.unit,
        filterKeyword: props.filterKeyword,
        textDirection: props.textDirection,
        highlightNode: highlightNode.value,
        isCompared: localIsCompared.value,
      });
    }
    watch(
      [() => props.data, () => props.appName],
      debounce(16, async () => {
        emit('updateLoading', true);
        showException.value = false;
        chartInstance?.clear();
        chartInstance?.dispose();
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
            setTimeout(() => {
              chartInstance = echarts.init(chartRef.value!, undefined, {
                renderer: 'canvas',
                useDirtyRect: false,
                height: height.value,
                ssr: false,
              });
              chartInstance.off('click');
              chartInstance.off('contextmenu');
              currentGraphData.value = profilingData.value;
              chartInstance.setOption(getEchartsOptions());
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
                chartInstance.setOption(getEchartsOptions(), {
                  notMerge: true,
                });
              });
              chartInstance.on('contextmenu', (params: any) => {
                console.info(params);
                highlightNode.value = params.value[3];
                contextMenuRect.value = { left: params.event.offsetX, top: params.event.offsetY };
                showContextMenu.value = true;
              });
              emit('updateLoading', false);
            }, 16);
            nextTick(() => {
              emit('updateLoading', false);
            });
            return;
          }
          showException.value = true;
          emit('updateLoading', false);
        } catch (e) {
          console.error(e);
          emit('updateLoading', false);
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
      chartInstance.setOption(getEchartsOptions());
    });
    watch(
      () => props.textDirection,
      () => {
        chartInstance.setOption(getEchartsOptions());
      }
    );
    watch(
      () => props.downloadImgIndex,
      () => {
        const base64Url = chartInstance?.getDataURL({
          type: 'png',
          pixelRatio: window.devicePixelRatio,
          backgroundColor: '#fff',
        });
        downloadBase64AsPng(base64Url, `${props.appName || ''}${dayjs().format('YYYY-MM-DD HH:mm:ss')}.png`);
      }
    );
    function handleContextMenuClick(item: ICommonMenuItem) {
      contextMenuRect.value.left = -1;
      showContextMenu.value = false;
      if (item.id === 'copy') {
        let hasErr = false;
        copyText(highlightNode.value.name, (errMsg: string) => {
          this.$bkMessage({
            message: errMsg,
            theme: 'error',
          });
          hasErr = !!errMsg;
        });
        if (!hasErr) this.$bkMessage({ theme: 'success', message: this.$t('复制成功') });

        return;
      }
      if (item.id === 'reset') {
        highlightNode.value = null;
        currentGraphData.value = profilingData.value;
        chartInstance.setOption(getEchartsOptions());
      }
      if (item.id === 'highlight') {
        emit('updateFilterKeyword', highlightNode.value.name);
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
        <bk-exception
          style='flex: 1'
          scene='part'
          type='empty'
        >
          {this.$t('暂无数据')}
        </bk-exception>
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
          class='profiling-flame-graph'
          onContextmenu={e => e.preventDefault()}
        />
        <ul
          style={{
            left: `${this.contextMenuRect.left}px`,
            top: `${this.contextMenuRect.top}px`,
            visibility: this.showContextMenu ? 'visible' : 'hidden',
          }}
          class='profiling-flame-graph-menu'
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
