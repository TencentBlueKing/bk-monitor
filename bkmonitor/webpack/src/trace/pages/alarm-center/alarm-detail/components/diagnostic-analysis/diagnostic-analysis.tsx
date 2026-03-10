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
import { defineComponent, shallowRef, Teleport } from 'vue';

import { useI18n } from 'vue-i18n';

import AiDiagnosticInfoCard from './ai-diagnostic-info-card';
import AnalysisPanel from './analysis-panel';
import { DiagnosticTypeEnum } from './constant';

import './diagnostic-analysis.scss';
export default defineComponent({
  name: 'DiagnosticAnalysis',
  emits: ['close'],
  setup(_, { emit }) {
    const { t } = useI18n();
    /** 是否全部展开 */
    const isAllExpand = shallowRef(true);
    /** 是否固定 */
    const isFixed = shallowRef(false);

    /** 分析面板 ref 映射 */
    const analysisPanelRefs = shallowRef<Map<string, InstanceType<typeof AnalysisPanel>>>(new Map());

    /**
     * 设置 ref
     * @param el 组件实例
     * @param type 诊断类型
     */
    const setItemRef = (el: InstanceType<typeof AnalysisPanel> | null, type: string) => {
      if (el) {
        analysisPanelRefs.value.set(type, el);
      } else {
        analysisPanelRefs.value.delete(type);
      }
    };

    const handleAllExpandChange = () => {
      isAllExpand.value = !isAllExpand.value;
      for (const item of analysisPanelRefs.value.values()) {
        item?.toggleExpand(isAllExpand.value);
      }
    };

    const handleFixedChange = () => {
      isFixed.value = !isFixed.value;
    };

    const handleClosed = () => {
      emit('close');
    };

    return {
      t,
      DiagnosticTypeEnum,
      isAllExpand,
      isFixed,
      setItemRef,
      handleAllExpandChange,
      handleFixedChange,
      handleClosed,
    };
  },
  render() {
    return (
      <Teleport
        disabled={!this.isFixed}
        to='body'
      >
        <div class={['diagnostic-analysis-panel-comp', { fixed: this.isFixed }]}>
          <div class='diagnostic-analysis-wrapper'>
            <div class='diagnostic-analysis-wrapper-header'>
              <div class='title'>{this.t('诊断分析')}</div>
              <div class='tool-btns'>
                <i
                  class={['icon-monitor', 'expand-icon', this.isAllExpand ? 'icon-zhankai-2' : 'icon-shouqi3']}
                  v-bk-tooltips={{
                    content: this.isAllExpand ? this.t('全部收起') : this.t('全部展开'),
                  }}
                  onClick={this.handleAllExpandChange}
                />
                <i
                  class={['icon-monitor', 'fixed-icon', this.isFixed ? 'icon-a-pinnedtuding' : 'icon-a-pintuding']}
                  v-bk-tooltips={{
                    content: this.isFixed ? this.t('取消固定') : this.t('固定在界面上'),
                  }}
                  onClick={this.handleFixedChange}
                />
                <i
                  class='icon-monitor icon-mc-close-copy close-icon'
                  v-bk-tooltips={{
                    content: this.t('关闭'),
                  }}
                  onClick={this.handleClosed}
                />
              </div>
            </div>
            <div class='diagnostic-analysis-wrapper-content'>
              <AiDiagnosticInfoCard />

              {[
                this.DiagnosticTypeEnum.DIMENSION,
                this.DiagnosticTypeEnum.LINK,
                this.DiagnosticTypeEnum.LOG,
                this.DiagnosticTypeEnum.EVENT,
                this.DiagnosticTypeEnum.METRIC,
              ].map(type => (
                <AnalysisPanel
                  key={type}
                  ref={el => this.setItemRef(el as InstanceType<typeof AnalysisPanel>, type)}
                  type={type}
                />
              ))}
            </div>
          </div>
        </div>
      </Teleport>
    );
  },
});
