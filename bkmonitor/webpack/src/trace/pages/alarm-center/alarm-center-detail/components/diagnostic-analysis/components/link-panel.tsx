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

import './link-panel.scss';
export default defineComponent({
  name: 'LinkPanel',
  props: {},
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
      <div class='suspicious-link-panel'>
        <div class='link-group-list'>
          <div class={['link-group-item', { expand: this.expandMap.get('group1') }]}>
            <div class='group-wrapper'>
              <div
                class='group-header'
                onClick={() => {
                  this.toggleExpand('group1');
                }}
              >
                <i class='icon-monitor icon-arrow-down' />
                <span class='group-name'>{this.t('调用链')}：</span>
                <div class='link-text'>dfasdfsdfg4534saldfj3l4j52345</div>
              </div>
              <div class='group-content'>
                <div class='error-info-item'>
                  <div class='error-info-item-name'>错误情况</div>
                  <div class='error-info-item-value'>
                    {
                      "tE monitor_web，incident，resources, fronted_resources. IncidentHandlersResource 这个 span 中，发生了一个类型为 TypeError 的异常。异常信息为'<' not supported between instances of 'str' and 'int'. 这表明在代表中存在一个比较操作。试图将字符串和整数进行比较，导致了类型错误。"
                    }
                  </div>
                </div>
                <div class='error-info-item'>
                  <div class='error-info-item-name'>错误详情</div>
                  <div class='error-info-item-value'>异常类型：TypenError</div>
                  <div class='error-info-item-value'>
                    {"异常信息：'<' not supported between instances of 'str' and 'int'"}
                  </div>
                </div>
                <div class='error-info-item'>
                  <div class='error-info-item-name'>堆栈跟踪</div>
                  <div class='error-info-item-value'>TraranarkImnct rarant</div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    );
  },
});
