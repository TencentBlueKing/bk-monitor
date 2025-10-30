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
import { defineComponent, reactive } from 'vue';

import { useI18n } from 'vue-i18n';

import './dimension-panel.scss';

export default defineComponent({
  name: 'DimensionPanel',
  setup() {
    const { t } = useI18n();

    const expandMap = reactive(new Map());

    const toggleExpand = (key: string) => {
      expandMap.set(key, !expandMap.get(key));
    };

    return {
      t,
      expandMap,
      toggleExpand,
    };
  },

  render() {
    return (
      <div class='suspicious-dimension-panel'>
        <i18n-t
          class='tips'
          keypath='经过 {0} 分析，发现以下可疑维度（组合）：'
          tag='div'
        >
          <span class='link-text'>{this.t('维度下钻分析')}</span>
        </i18n-t>
        <div class='dimension-group-list'>
          <div class={['dimension-group-item', { expand: this.expandMap.get('group1') }]}>
            <div class='group-wrapper'>
              <div
                class='group-header'
                onClick={() => {
                  this.toggleExpand('group1');
                }}
              >
                <i class='icon-monitor icon-arrow-down' />
                <span class='group-name'>异常维度（组合）1</span>
                <div class='abnormal-degree'>异常程度 90%</div>
              </div>
              <div class='group-content'>
                <div class='dimension-item'>
                  <div class='dimension-name'>主机名</div>
                  <div class='dimension-value'>VM-156-110-centos</div>
                </div>
                <div class='dimension-item even'>
                  <div class='dimension-name'>目标IP</div>
                  <div class='dimension-value'>11.185.157.110</div>
                </div>
                <div class='dimension-item'>
                  <div class='dimension-name'>管控区域</div>
                  <div class='dimension-value'>0</div>
                </div>
              </div>
              <div class='group-footer'>
                <span class='question-reason'>可疑原因：主调成功率 17%</span>
                <span class='link-text link-detail'>
                  <i class='icon-monitor icon-xiangqing1' />
                  {this.t('分析详情')}
                </span>
              </div>
            </div>
          </div>
        </div>
      </div>
    );
  },
});
