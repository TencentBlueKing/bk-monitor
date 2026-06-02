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

import { defineComponent } from 'vue';

import { useI18n } from 'vue-i18n';

import './merge-strategy-tips.scss';

export default defineComponent({
  name: 'MergeStrategyTips',
  props: {
    hasMainIssue: {
      type: Boolean,
      default: false,
    },
  },
  setup() {
    const { t } = useI18n();

    return {
      t,
    };
  },
  render() {
    return (
      <div class='merge-strategy-tips'>
        <div class='merge-strategy-icon'>
          <i class='icon-monitor icon-hint' />
        </div>
        <div class='merge-strategy-content'>
          <div class='merge-strategy-title'>{this.t('合并策略：')}</div>
          <ul class='merge-strategy-list'>
            {!this.hasMainIssue && (
              <li class='merge-strategy-item'>
                {this.$t('默认保留第 1 条选中的 Issue 作为主 Issue，也可以在下方表单切换；')}
              </li>
            )}

            <li class='merge-strategy-item'>
              <span class='item-name'>【{this.$t('主 Issue')}】</span>
              <span>{this.$t('只能继续作为主 Issue，不支持再合并入其他 Issue；')}</span>
            </li>
            <li class='merge-strategy-item'>
              <span class='item-name'>【{this.$t('被合并 Issue')}】</span>
              <span> {this.$t('事件数、影响范围会并入主 Issue；')}</span>
            </li>
          </ul>
        </div>
      </div>
    );
  },
});
