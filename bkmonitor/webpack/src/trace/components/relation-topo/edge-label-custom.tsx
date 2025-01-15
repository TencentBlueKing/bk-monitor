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

import { computed, defineComponent, onMounted, ref } from 'vue';

import { BaseEdge, EdgeLabelRenderer, getBezierPath } from '@vue-flow/core';

import { formatDuration } from '../trace-view/utils/date';

import './edge-label-custom.scss';
export default defineComponent({
  name: 'EdgeLabelCustom',
  inheritAttrs: false,
  props: {
    id: {
      type: String,
      required: true,
    },
    data: {
      type: Object,
      default: () => ({}),
    },
    label: {
      type: String,
      default: '',
    },
    animated: {
      type: Boolean,
      default: false,
    },
    sourceX: {
      type: Number,
      required: true,
    },
    sourceY: {
      type: Number,
      required: true,
    },
    targetX: {
      type: Number,
      required: true,
    },
    targetY: {
      type: Number,
      required: true,
    },
    isShowDuration: {
      type: Boolean,
      default: false,
    },
  },
  emits: ['panelClick'],
  setup(props, { emit }) {
    /** 连线路径 */
    const path = computed(() => {
      return getBezierPath({
        sourceX: props.sourceX,
        sourceY: props.sourceY,
        targetX: props.targetX,
        targetY: props.targetY,
      });
    });

    /** 最大耗时 */
    const maxDuration = computed(() => {
      const spans = props.data.spans || [];
      return Math.max(...spans.map(span => span.duration));
    });

    const page = ref(1);

    const curSpan = computed(() => {
      const spans = props.data.spans || [];
      const span = spans[page.value - 1];
      if (!span) return {};
      return {
        ...span,
        text: formatDuration(span.duration),
        isMax: span.duration === maxDuration.value && spans.length > 1,
      };
    });

    function handlePageChange(newPage: number) {
      if (newPage < 1 || newPage > props.data.spans.length) return;
      page.value = newPage;
    }

    /**
     * 计算时间面板坐标
     */
    const calcPanelPosition = computed(() => {
      const { data } = props;
      // // 面板高度
      const panelHeight = data.spans.length > 1 ? 40 : 24;
      // // 文本高度
      // const labelHeight = 14 * panelScale.value;
      // // x轴偏移量在10左右，就认定为一条竖线
      // const X_OFFSET = 10 * panelScale.value;
      // if (targetX >= sourceX - X_OFFSET && targetX <= sourceX + X_OFFSET) {
      //   // 竖线情况， 面板展示在label的右侧
      //   return {
      //     right: `${-11.5 * panelScale.value}px`,
      //     top: `${-panelHeight / 2 + labelHeight / 2}px`,
      //     transform: `translateX(100%) scale(${panelScale.value})`,
      //   };
      // } else if (targetX < sourceX) {
      //   // 向左下的线段  面板展示在label的右下方
      //   return {
      //     right: 0,
      //     top: `${labelHeight}px`,
      //     transform: `translateX(100%) scale(${panelScale.value})`,
      //   };
      // } else {
      //   // 向右下的线段， 面板展示在label的右上方
      //   return {
      //     top: `${-panelHeight - 2}px`,
      //     right: 0,
      //     transform: `translateX(100%) scale(${panelScale.value})`,
      //   };
      // }
      return {
        left: '7px',
        top: `${(-panelHeight - 5) * 0.9}px`,
        transform: 'translateX(-50%) scale(0.9)',
      };
    });

    function handlePanelClick() {
      emit('panelClick', props.id);
    }

    onMounted(() => {
      const index = props.data.spans.findIndex(span => span.duration === maxDuration.value);
      page.value = index + 1;
    });

    return {
      path,
      page,
      curSpan,
      calcPanelPosition,
      handlePageChange,
      handlePanelClick,
    };
  },
  render() {
    return [
      <BaseEdge
        id={this.id}
        path={this.path[0]}
        {...this.$attrs}
      />,
      <EdgeLabelRenderer>
        <div
          style={{
            transform: `translate(-50%, -50%) translate(${this.path[1]}px,${this.path[2]}px)`,
          }}
          class={{
            'edge-label-custom': true,
            active: this.animated,
          }}
        >
          <div
            class={{
              'edge-label-custom-label': true,
              hidden: Number(this.label) === 1 && !this.isShowDuration,
            }}
          >
            {Number(this.label) === 1 && !this.isShowDuration ? '' : this.label}
          </div>
          {this.isShowDuration && (
            <div
              style={this.calcPanelPosition}
              class='edge-duration-panel'
              onClick={this.handlePanelClick}
            >
              <div
                class={{
                  'edge-duration-panel-header': true,
                  'show-max': this.curSpan.isMax,
                }}
              >
                <i class='icon-monitor icon-mc-time duration-icon' />
                <span class='duration'>{this.curSpan.text}</span>
                {this.curSpan.isMax && <span class='max-icon'>MAX</span>}
              </div>
              {this.data.spans.length > 1 && (
                <div class='edge-duration-panel-footer'>
                  <i
                    class='icon-monitor icon-arrow-left page-btn'
                    onClick={() => this.handlePageChange(this.page - 1)}
                  />
                  <span class='page'>
                    <span>{this.page}</span>
                    <span class='split-char'>/</span>
                    <span>{this.data.spans?.length}</span>
                  </span>
                  <i
                    class='icon-monitor icon-arrow-right page-btn'
                    onClick={() => this.handlePageChange(this.page + 1)}
                  />
                </div>
              )}
            </div>
          )}
        </div>
      </EdgeLabelRenderer>,
    ];
  },
});
