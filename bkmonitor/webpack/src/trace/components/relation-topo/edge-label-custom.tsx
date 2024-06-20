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

import { defineComponent, computed, ref } from 'vue';

import { BaseEdge, EdgeLabelRenderer, getBezierPath } from '@vue-flow/core';
import { Popover } from 'bkui-vue';

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
    selected: {
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
    scale: {
      type: Number,
      default: 1,
    },
  },
  setup(props) {
    const path = computed(() => {
      return getBezierPath({
        sourceX: props.sourceX,
        sourceY: props.sourceY,
        targetX: props.targetX,
        targetY: props.targetY,
      });
    });

    const page = ref(1);

    const curSpan = computed(() => {
      const spans = props.data.spans || [];
      const maxDuration = Math.max(...spans.map(span => span.duration));
      const span = spans[page.value - 1];
      if (!span) return {};
      return {
        ...span,
        text: formatDuration(span.duration),
        isMax: span.duration === maxDuration && spans.length > 1,
      };
    });

    function handlePageChange(e: Event, newPage: number) {
      e.preventDefault();
      console.log(newPage);
      if (newPage < 1 || newPage > props.data.spans.length) return;
      page.value = newPage;
    }

    return {
      path,
      page,
      curSpan,
      handlePageChange,
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
        <Popover
          always={this.isShowDuration}
          arrow={false}
          boundary='parent'
          disableTransform={true}
          is-show={this.isShowDuration}
          placement='top'
          theme={`light edge-duration-popover-theme ${this.selected ? 'selected' : ''}`}
        >
          {{
            default: () => (
              <div
                style={{
                  transform: `translate(-50%, -50%) translate(${this.path[1]}px,${this.path[2]}px)`,
                }}
                class={{
                  'edge-label-custom-label': true,
                  selected: this.selected,
                  hidden: this.isShowDuration && Number(this.label) <= 1,
                }}
              >
                {Number(this.label) > 1 ? this.label : ''}
              </div>
            ),
            content: () => (
              <div
                style={{ transform: `scale(${this.scale})` }}
                class='edge-duration-popover'
              >
                <div
                  class={{
                    'edge-duration-popover-header': true,
                    'show-max': this.curSpan.isMax,
                  }}
                >
                  <i class='icon-monitor icon-mc-time duration-icon'></i>
                  <span class='duration'>{this.curSpan.text}</span>
                  {this.curSpan.isMax && <span class='max-icon'>MAX</span>}
                </div>
                {this.data.spans.length > 1 && (
                  <div class='edge-duration-popover-footer'>
                    <i
                      class='icon-monitor icon-arrow-left page-btn'
                      onClick={e => this.handlePageChange(e, this.page - 1)}
                    ></i>
                    <span class='page'>
                      <span>{this.page}</span>
                      <span class='split-char'>/</span>
                      <span>{this.data.spans?.length}</span>
                    </span>
                    <i
                      class='icon-monitor icon-arrow-right page-btn'
                      onClick={e => this.handlePageChange(e, this.page + 1)}
                    ></i>
                  </div>
                )}
              </div>
            ),
          }}
        </Popover>
      </EdgeLabelRenderer>,
    ];
  },
});
