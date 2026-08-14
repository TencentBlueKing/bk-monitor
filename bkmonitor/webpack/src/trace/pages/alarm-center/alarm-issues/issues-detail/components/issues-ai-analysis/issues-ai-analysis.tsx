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

import { Tab } from 'bkui-vue';
import { useI18n } from 'vue-i18n';

import SourceCodeAnalysis from './source-code-analysis';

import type { IssueDetail } from '../../../typing';

import './issues-ai-analysis.scss';
export default defineComponent({
  name: 'IssuesAiAnalysis',
  props: {
    detail: {
      type: Object as PropType<IssueDetail>,
      default: () => ({}),
    },
  },
  setup() {
    const { t } = useI18n();

    const currentTab = shallowRef('source');

    const renderTabLabel = (icon: string, label: string) => (
      <span class='ai-config-tab-label'>
        <i class={['icon-monitor', icon]} />
        <span>{label}</span>
      </span>
    );

    const handleTabChange = (tab: 'source') => {
      currentTab.value = tab;
    };

    return {
      t,
      currentTab,
      handleTabChange,
      renderTabLabel,
    };
  },
  render() {
    return (
      <div class='issues-detail-issues-ai-analysis'>
        <Tab
          class='ai-analysis-tab'
          active={this.currentTab}
          type='card-grid'
          onUpdate:active={this.handleTabChange}
        >
          <Tab.TabPanel
            v-slots={{ label: () => this.renderTabLabel('icon-code', this.t('源码 AI 分析')) }}
            name='source'
          >
            <SourceCodeAnalysis
              detail={this.detail}
              show={this.currentTab === 'source'}
            />
          </Tab.TabPanel>
        </Tab>
      </div>
    );
  },
});
