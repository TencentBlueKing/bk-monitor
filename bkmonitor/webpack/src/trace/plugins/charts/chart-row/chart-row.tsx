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
import { type PropType, defineComponent } from 'vue';

import { RightShape } from 'bkui-vue/lib/icon';

import type { PanelModel } from '../../typings';

import './chart-row.scss';

export default defineComponent({
  name: 'ChartRowMigrated',
  props: {
    panel: {
      type: Object as PropType<PanelModel>,
      default: () => {},
      required: true,
    },
  },
  emits: ['collapse'],
  setup(props, { emit }) {
    const handleCollapsed = () => {
      if (!props.panel.draging) {
        emit('collapse', !props.panel.collapsed);
      }
      props.panel.updateDraging(false);
    };

    const handleClickIcon = (e: MouseEvent) => {
      if (props.panel.collapsed && e.target === e.currentTarget) {
        setTimeout(handleCollapsed, 20);
      }
    };

    return {
      handleCollapsed,
      handleClickIcon,
    };
  },
  render() {
    return (
      <div
        class={`chart-row ${this.panel.collapsed ? 'is-collapsed' : ''} `}
        onClick={this.handleCollapsed}
      >
        <RightShape class='chart-row-icon' />
        {/* <i class='bk-icon icon-right-shape chart-row-icon' /> */}
        <div class={`chart-row-content ${this.panel.collapsed ? '' : 'draggable-handle'} `}>
          {this.panel.title}
          <span class='panel-count'>({this.panel.panels?.length || 0})</span>
        </div>
      </div>
    );
  },
});
