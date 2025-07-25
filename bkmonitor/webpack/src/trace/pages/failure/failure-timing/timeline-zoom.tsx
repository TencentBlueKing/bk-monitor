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
import { type PropType, defineComponent, defineExpose, ref, watch } from 'vue';

import { Popover, Slider } from 'bkui-vue';
import { useI18n } from 'vue-i18n';

import type { IAlert } from '../types';

import './timeline-zoom.scss';

const NODE_TYPE = [
  {
    text: '已恢复 / 已解决 / 已失效告警',
    status: 'normal',
    type: 'normal',
  },
  {
    text: '未恢复告警',
    status: 'error',
    type: 'normal',
  },
  {
    text: '根因',
    status: 'root',
    type: 'tag',
  },
  {
    text: '反馈的根因',
    status: 'feedBackRoot',
    type: 'tag',
  },
];
const INFO_TYPE = [
  {
    text: '告警系统事件',
    icon: 'icon-gaojing1',
  },
  {
    text: '故障系统事件',
    icon: 'icon-mc-fault',
  },
  {
    text: '人工操作',
    icon: 'icon-mc-user-one',
  },
];
export default defineComponent({
  name: 'TimelineZoom',
  props: {
    maxZoom: {
      type: Number,
      default: 20,
    },
    treeData: {
      type: Array as PropType<IAlert[]>,
      default: () => [],
    },
    showTickArr: {
      type: Array as PropType<string[]>,
      default: () => [],
    },
    ratio: {
      type: Number,
      default: 0,
    },
    mouseRatio: {
      type: Number,
      default: 0,
    },
  },
  emits: ['zoom', 'move'],
  setup(props, { emit }) {
    /** 时序图工具栏 */
    const { t } = useI18n();
    const MIN_ZOOM = 0;
    const showLegend = ref<boolean>(localStorage.getItem('showTimeLegend') === 'true');
    const showMinimap = ref<boolean>(false);
    const zoomValue = ref<number>(0);
    const legendRef = ref(null);
    const minimapRef = ref(null);
    const mapContentWidth = ref<number>(240);
    const isDragging = ref<boolean>(false);
    const selectionLeft = ref<number>(0);
    const selectionWidth = ref<number>(240);
    const canvasRef = ref(null);
    const ctx = ref(null);
    const step = ref<number>(0);
    const beginTick = ref<number>(0);
    const selectionRef = ref(null);
    const legendFn = () => (
      <div class='failure-topo-graph-legend-content'>
        <ul class='node-type'>
          {NODE_TYPE.map(node => {
            const isTag = node.type === 'tag';
            return (
              <li key={node.type}>
                <span class={['circle', node.status, { 'node-tag': isTag }]}>{isTag ? t('根因') : ''}</span>
                <span>{t(node.text)}</span>
              </li>
            );
          })}
        </ul>
        <ul class='info-type'>
          {INFO_TYPE.map(node => {
            return (
              <li key={node.text}>
                <span>
                  <i class={`icon-monitor item-icon ${node.icon}`} />
                </span>
                <span>{t(node.text)}</span>
              </li>
            );
          })}
        </ul>
      </div>
    );
    const setEndTime = time => {
      return time || Math.floor(new Date().getTime() / 1000);
    };
    const popoverConfig = {
      legend: {
        type: 'legend',
        tips: t('显示图例'),
        icon: legendFn,
        contentFn: legendFn,
      },
      minimap: {
        type: 'minimap',
        tips: t('显示图例'),
        icon: 'icon-minimap',
      },
    };
    const currentPopover = ref(popoverConfig.legend);
    const handleShowLegend = () => {
      if (showMinimap.value) {
        minimapRef.value?.hide();
        showMinimap.value = !showMinimap.value;
      }
      showLegend.value = !showLegend.value;
      localStorage.setItem('showTimeLegend', String(showLegend.value));
    };
    const handleShowMinimap = () => {
      if (showLegend.value) {
        legendRef.value?.hide();
        showLegend.value = !showLegend.value;
        localStorage.setItem('showTimeLegend', String(showLegend.value));
      }
      showMinimap.value = !showMinimap.value;
      drawCanvas();
    };
    function determineItemColor(item): string {
      if (item.is_root) return '#EA3636';
      if (item.is_feedback_root) return '#FF9C01';
      const StatusToColorMap: { [status: string]: string } = {
        RECOVERED: '#C4C6CC',
        CLOSED: '#C4C6CC',
        ABNORMAL: '#FD9C9C',
      };
      return StatusToColorMap[item.status ?? ''] || '#fff';
    }
    const drawMinimap = () => {
      const barHeight = 1.5;
      let yOffset = 1;
      const drawBars = (data, level = 1) => {
        data.forEach(item => {
          const isDraw = item.isShow && item.level_name !== 'status' && item.isDraw;
          if (isDraw) {
            const endTime = setEndTime(item.end_time);
            const width = (endTime - item.begin_time) * step.value;
            const barWidth = width > 0 ? width : 3;
            const xPos = (item.begin_time - beginTick.value) * step.value;
            ctx.value.fillStyle = determineItemColor(item);
            ctx.value.fillRect(xPos, yOffset, barWidth, barHeight);
          }

          yOffset += barHeight + 1.8;

          if (item.children && item.children.length > 0) {
            drawBars(item.children, level + 1);
          }
        });
      };
      drawBars(props.treeData);
    };
    const handleTickChange = () => {
      const len = props.showTickArr.length;
      beginTick.value = new Date(props.showTickArr[0]).getTime() / 1000;
      const endTick = new Date(props.showTickArr[len - 1]).getTime() / 1000;
      const count = endTick - beginTick.value;
      step.value = mapContentWidth.value / count;
    };
    const clearCanvas = () => {
      const canvas = canvasRef.value;
      if (canvas) {
        const ctx = canvas.getContext('2d');
        ctx?.clearRect(0, 0, canvas.width, canvas.height);
      }
    };
    const drawCanvas = () => {
      const canvas = canvasRef.value;
      handleTickChange();
      if (canvas) {
        ctx.value = canvas.getContext('2d');
        ctx.value && drawMinimap();
      }
    };
    const handleZoomChange = (value, percentage) => {
      emit('zoom', value, percentage);
    };
    const handleUpdateZoom = val => {
      const value = Math.max(MIN_ZOOM, zoomValue.value + Number(val));
      zoomValue.value = Math.min(props.maxZoom, value);
      const percentage = zoomValue.value / props.maxZoom;
      selectionWidth.value = mapContentWidth.value - percentage * 140;
      // selectionLeft.value = (mapContentWidth.value - selectionWidth.value) / 2;
      selectionLeft.value = 0;
      handleZoomChange(zoomValue.value, percentage);
    };
    const handleResetZoom = () => {
      zoomValue.value = 0;
      handleUpdateZoom(0);
    };
    function getTransformX(elem) {
      const style: any = window.getComputedStyle(elem);
      const matrix = style.transform || style.webkitTransform || style.mozTransform;
      if (matrix === 'none' || !matrix) return 0;
      const values = matrix.match(/matrix.*\((.+)\)/)[1].split(', ');
      return Number.parseFloat(values[4]);
    }
    const onSelectionMouseDown = (event: MouseEvent) => {
      isDragging.value = true;
      const startX = event.clientX;
      const selection = selectionRef.value;
      const startTransform = getTransformX(selection);

      const onMouseMove = (e: MouseEvent) => {
        if (!isDragging.value) return;
        const deltaX = e.clientX - startX;
        const newTransformX = startTransform + deltaX;
        const maxTransformX = selection.parentNode.offsetWidth - selection.offsetWidth;
        const newPos = Math.max(-maxTransformX / 2, Math.min(maxTransformX / 2, newTransformX));
        const ratio = newPos / maxTransformX + 0.5;
        selectionLeft.value = newPos;
        emit('move', ratio);
      };

      const onMouseUp = () => {
        isDragging.value = false;
        selectionRef.value.removeEventListener('mousemove', onMouseMove);
        selectionRef.value.removeEventListener('mouseup', onMouseUp);
      };

      selectionRef.value.addEventListener('mousemove', onMouseMove);
      selectionRef.value.addEventListener('mouseup', onMouseUp);
    };
    const zoomMove = (ratio: number) => {
      const selection = selectionRef.value;
      const num = mapContentWidth.value * ratio;
      const maxTransformX = (mapContentWidth.value - selection.offsetWidth) / 2;
      const left = (num - maxTransformX / 2 - selection.offsetWidth) / 2;
      selectionLeft.value = left;
    };
    const watchMapChange = () => {
      clearCanvas();
      drawCanvas();
    };
    watch(
      () => props.treeData,
      () => watchMapChange(),
      { deep: true }
    );
    watch(
      () => props.showTickArr,
      () => watchMapChange(),
      { deep: true }
    );
    watch(
      () => props.ratio,
      val => {
        zoomMove(val);
      }
    );
    /** 时序图鼠标左右滑动时，缩略图一起移动 */
    watch(
      () => props.mouseRatio,
      val => {
        const selection = selectionRef.value;
        const maxTransformX = selection.parentNode.offsetWidth - selection.offsetWidth;
        const newPos = (val - 0.5) * maxTransformX;
        const left = Math.max(-maxTransformX / 2, Math.min(maxTransformX / 2, newPos));
        selectionLeft.value = left;
      }
    );

    defineExpose({
      handleUpdateZoom,
    });

    return {
      MIN_ZOOM,
      showMinimap,
      zoomValue,
      showLegend,
      currentPopover,
      handleShowLegend,
      handleUpdateZoom,
      handleZoomChange,
      handleResetZoom,
      handleShowMinimap,
      legendRef,
      minimapRef,
      mapContentWidth,
      selectionWidth,
      selectionLeft,
      onSelectionMouseDown,
      canvasRef,
      selectionRef,
      t,
    };
  },
  render() {
    return (
      <div class='timeline-zoom'>
        <Popover
          ref='legendRef'
          width={210}
          extCls='timeline-zoom-legend-popover'
          v-slots={{
            content: (
              <div class='failure-topo-graph-legend-content'>
                <ul class='node-type'>
                  {NODE_TYPE.map(node => {
                    const isTag = node.type === 'tag';
                    return (
                      <li key={node.type}>
                        <span class={['circle', node.status, { 'node-tag': isTag }]}>
                          {isTag ? this.t('根因') : ''}
                        </span>
                        <span>{this.t(node.text)}</span>
                      </li>
                    );
                  })}
                  {INFO_TYPE.map(node => (
                    <li key={node.text}>
                      <span class='info-circle'>
                        <i class={`icon-monitor item-icon ${node.icon}`} />
                      </span>
                      <span>{this.t(node.text)}</span>
                    </li>
                  ))}
                </ul>
              </div>
            ),
            default: (
              <div
                class='failure-topo-graph-legend'
                v-bk-tooltips={{
                  content: this.t('显示图例'),
                  disabled: this.showLegend,
                  boundary: 'parent',
                  extCls: 'failure-topo-graph-tooltip',
                }}
                onClick={this.handleShowLegend}
              >
                <i class='icon-monitor icon-legend' />
              </div>
            ),
          }}
          always={this.showLegend}
          arrow={false}
          boundary='body'
          isShow={this.showLegend}
          offset={{ crossAxis: 90, mainAxis: 10 }}
          placement='top'
          renderType='auto'
          theme='light'
          trigger='manual'
          zIndex={999}
        />
        <Popover
          ref='minimapRef'
          width={242}
          extCls='timeline-zoom-map-popover'
          v-slots={{
            content: (
              <div
                id='miniMap'
                style={{ width: `${this.mapContentWidth}px` }}
                class='failure-topo-graph-map-content'
              >
                <canvas
                  ref='canvasRef'
                  width='242'
                  height='120'
                />
                <div
                  ref='selectionRef'
                  style={{ width: `${this.selectionWidth}px`, transform: `translateX(${this.selectionLeft}px)` }}
                  class='map-selection'
                  onMousedown={this.onSelectionMouseDown}
                />
              </div>
            ),
            default: (
              <div
                class='failure-topo-graph-legend'
                v-bk-tooltips={{
                  content: this.t('显示小地图'),
                  disabled: this.showMinimap,
                  boundary: 'parent',
                  placement: 'bottom',
                  extCls: 'failure-topo-graph-tooltip',
                }}
                onClick={this.handleShowMinimap}
              >
                <i class='icon-monitor icon-minimap' />
              </div>
            ),
          }}
          always={this.showMinimap}
          arrow={false}
          boundary='body'
          isShow={this.showMinimap}
          offset={{ crossAxis: 70, mainAxis: 10 }}
          placement='top'
          renderType='auto'
          theme='light'
          trigger='manual'
          zIndex={999}
        />
        <span class='failure-topo-graph-line' />
        <div class='failure-topo-graph-zoom-slider'>
          <div
            class='failure-topo-graph-setting'
            onClick={this.handleUpdateZoom.bind(this, -2)}
          >
            <i class='icon-monitor icon-minus-line' />
          </div>
          <Slider
            class='slider'
            v-model={this.zoomValue}
            maxValue={this.$props.maxZoom}
            minValue={this.MIN_ZOOM}
            onChange={this.handleUpdateZoom}
          />
          <div
            class='failure-topo-graph-setting'
            onClick={this.handleUpdateZoom.bind(this, 2)}
          >
            <i class='icon-monitor icon-plus-line' />
          </div>
        </div>
        <span class='failure-topo-graph-line' />
        <div
          class='failure-topo-graph-proportion'
          v-bk-tooltips={{ content: this.t('重置比例'), boundary: 'parent', extCls: 'failure-topo-graph-tooltip' }}
          onClick={this.handleResetZoom}
        >
          <i class='icon-monitor icon-mc-restoration-ratio' />
        </div>
      </div>
    );
  },
});
