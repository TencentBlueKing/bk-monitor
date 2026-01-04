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
import LinkPanel from './components/link-panel';
import LogPanel from './components/log-panel';
import { DiagnosticTypeEnum, DiagnosticTypeIconMap, DiagnosticTypeMap } from './constant';

import type { IDiagnosticAnalysisItem } from './typing';

import './analysis-panel.scss';

/** 分析面板 */
export default defineComponent({
  name: 'AnalysisPanel',
  props: {
    data: {
      type: Object as PropType<IDiagnosticAnalysisItem>,
      default: () => ({}),
    },
  },
  setup(props) {
    const isExpand = shallowRef(true);

    const toggleExpand = (expand: boolean) => {
      isExpand.value = expand;
    };

    const renderAnalysisPanel = () => {
      switch (props.data.type) {
        case DiagnosticTypeEnum.DIMENSION:
          return <DimensionPanel data={props.data.list} />;
        case DiagnosticTypeEnum.LINK:
          return <LinkPanel data={props.data.list} />;
        case DiagnosticTypeEnum.LOG:
          return <LogPanel data={props.data.list} />;
        case DiagnosticTypeEnum.EVENT:
          return <LogPanel data={props.data.list} />;
      }
    };

    return {
      isExpand,
      toggleExpand,
      renderAnalysisPanel,
    };
  },
  render() {
    return (
      <div class={['analysis-panel', { expand: this.isExpand }]}>
        <div class='analysis-panel-wrapper'>
          <div
            class='analysis-panel-wrapper-header'
            onClick={() => this.toggleExpand(!this.isExpand)}
          >
            <i class='icon-monitor icon-mc-arrow-right arrow-icon' />
            <i class={['icon-monitor', 'analysis-type-icon', DiagnosticTypeIconMap[this.data.type]]} />
            <span class='panel-title'>{DiagnosticTypeMap[this.data.type]}</span>
          </div>
          <div class='analysis-panel-wrapper-content'>{this.renderAnalysisPanel()}</div>
        </div>
      </div>
    );
  },
});
