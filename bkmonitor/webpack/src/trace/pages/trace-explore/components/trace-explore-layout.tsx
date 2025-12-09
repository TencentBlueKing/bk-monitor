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
import { defineComponent, shallowRef, watch } from 'vue';

import { useI18n } from 'vue-i18n';

import MonitorDrag from '../../../components/monitor-drag/monitor-drag';

import './trace-explore-layout.scss';

export default defineComponent({
  name: 'TraceExploreLayout',
  props: {
    minWidth: {
      type: Number,
      default: 200,
    },
    maxWidth: {
      type: Number,
      default: 400,
    },
    initialDivide: {
      type: Number,
      default: 200,
    },
    isCollapsed: {
      type: Boolean,
      default: false,
    },
  },
  emits: ['update:isCollapsed'],
  setup(props, { emit }) {
    const { t } = useI18n();
    const width = shallowRef(props.initialDivide);
    watch(
      () => props.isCollapsed,
      v => {
        width.value = v ? 0 : props.initialDivide;
      },
      {
        immediate: true,
      }
    );
    const handleDragChange = (w: number) => {
      if (w < props.minWidth) {
        updateIsCollapsed(true);
      } else {
        width.value = w;
      }
    };

    const updateIsCollapsed = (collapsed?: boolean) => {
      emit('update:isCollapsed', collapsed);
    };

    return {
      width,
      handleDragChange,
      updateIsCollapsed,
      t,
    };
  },
  render() {
    return (
      <div class='trace-explore-layout-comp'>
        <div class='layout-aside'>
          <div
            style={{ width: `${this.width}px` }}
            class='layout-aside-content'
          >
            {this.$slots.aside?.()}
          </div>

          {!this.isCollapsed ? (
            <MonitorDrag
              isShow={!this.isCollapsed}
              lineText=''
              maxWidth={this.maxWidth}
              minWidth={this.minWidth}
              startPlacement='right'
              theme='simple-line-round'
              onMove={this.handleDragChange}
            />
          ) : (
            <div
              class='expand-trigger'
              v-bk-tooltips={{ content: this.t('展开') }}
              onClick={() => this.updateIsCollapsed(false)}
            >
              <i class='icon-monitor icon-gongneng-shouqi' />
            </div>
          )}
        </div>
        <div class='layout-main'>{this.$slots.default?.()}</div>
      </div>
    );
  },
});
