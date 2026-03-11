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
import { type PropType, defineComponent, shallowRef } from 'vue';

import DimensionPanel from './components/dimension-panel';
import EventPanel from './components/event-panel';
import LinkPanel from './components/link-panel';
import LogPanel from './components/log-panel';
import MetricPanel from './components/metric-panel';
import { DiagnosticTypeEnum, DiagnosticTypeIconMap, DiagnosticTypeMap } from './constant';

import type { DiagnosticTypeEnumType } from './typing';

import './analysis-panel.scss';

/** 分析面板渲染函数映射表 */
const PANEL_RENDER_MAP: Record<DiagnosticTypeEnumType, () => any> = {
  [DiagnosticTypeEnum.DIMENSION]: () => <DimensionPanel />,
  [DiagnosticTypeEnum.LINK]: () => <LinkPanel />,
  [DiagnosticTypeEnum.LOG]: () => <LogPanel />,
  [DiagnosticTypeEnum.EVENT]: () => <EventPanel />,
  [DiagnosticTypeEnum.METRIC]: () => <MetricPanel />,
};

/** 分析面板 */
export default defineComponent({
  name: 'AnalysisPanel',
  props: {
    type: {
      type: String as PropType<DiagnosticTypeEnumType>,
      default: '',
    },
  },
  setup() {
    const isExpand = shallowRef(true);

    const toggleExpand = (expand: boolean) => {
      isExpand.value = expand;
    };

    return {
      isExpand,
      toggleExpand,
    };
  },
  render() {
    const renderAnalysisPanel = () => {
      const renderFn = PANEL_RENDER_MAP[this.type];
      return renderFn ? renderFn() : null;
    };

    return (
      <div class={['analysis-panel', { expand: this.isExpand }]}>
        <div class='analysis-panel-wrapper'>
          <div
            class='analysis-panel-wrapper-header'
            onClick={() => this.toggleExpand(!this.isExpand)}
          >
            <i class={['icon-monitor', 'analysis-type-icon', DiagnosticTypeIconMap[this.type]]} />
            <span class='panel-title'>{DiagnosticTypeMap[this.type]}</span>
            <span class='count-tag'>2</span>
            <i class='icon-monitor icon-arrow-right-copy arrow-icon' />
          </div>
          <div class='analysis-panel-wrapper-content'>{renderAnalysisPanel()}</div>
        </div>
      </div>
    );
  },
});
