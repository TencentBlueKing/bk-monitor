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
  props: {
    show: {
      type: Boolean,
      default: true,
    },
  },
  emits: ['close'],
  setup(_, { emit }) {
    const { t } = useI18n();
    /** 是否全部展开 */
    const isAllExpand = shallowRef(true);
    /** 是否固定 */
    const isFixed = shallowRef(false);

    const analysisPanelRefs = shallowRef<InstanceType<typeof AnalysisPanel>[]>([]);

    // 设置 ref 的函数
    const setItemRef = (el, index: number) => {
      if (el) {
        analysisPanelRefs.value[index] = el;
      } else {
        analysisPanelRefs.value.splice(index, 1);
      }
    };

    const handleAllExpandChange = () => {
      isAllExpand.value = !isAllExpand.value;
      for (const item of analysisPanelRefs.value) {
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
                DiagnosticTypeEnum.DIMENSION,
                DiagnosticTypeEnum.LINK,
                DiagnosticTypeEnum.LOG,
                DiagnosticTypeEnum.EVENT,
                DiagnosticTypeEnum.Metic,
              ].map((item, index) => (
                <AnalysisPanel
                  key={item}
                  ref={el => this.setItemRef(el, index)}
                  type={item}
                />
              ))}
            </div>
          </div>
        </div>
      </Teleport>
    );
  },
});
