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
import { defineComponent, shallowRef } from 'vue';

import { Tab } from 'bkui-vue';
import { useI18n } from 'vue-i18n';
import { useRoute, useRouter } from 'vue-router';

import AnomalyDetection from './components/anomaly-detection/anomaly-detection';
import SourceCodeAnalysis from './components/source-code-analysis/source-code-analysis';
import { EAiConfigTab } from './typings';

import './ai-config.scss';

/**
 * @description AI 设置：异常检测与源码 AI 分析的配置入口
 */
export default defineComponent({
  name: 'AiConfig',
  setup() {
    const { t } = useI18n();
    const route = useRoute();
    const router = useRouter();

    /** 当前 Tab 由 url query 决定，保证刷新与分享后仍停留在同一 Tab */
    const activeTab = shallowRef(
      route.query.tab === EAiConfigTab.sourceCodeAnalysis
        ? EAiConfigTab.sourceCodeAnalysis
        : EAiConfigTab.anomalyDetection
    );

    const handleTabChange = (tab: string) => {
      activeTab.value = tab as EAiConfigTab;
      router.replace({ query: { ...route.query, tab } });
    };

    const renderTabLabel = (icon: string, label: string) => (
      <span class='ai-config-tab-label'>
        <i class={['icon-monitor', icon]} />
        <span>{label}</span>
      </span>
    );

    return () => (
      <div class='ai-config'>
        <Tab
          class='ai-config-tab'
          active={activeTab.value}
          type='card-grid'
          onChange={handleTabChange}
        >
          <Tab.TabPanel
            v-slots={{ label: () => renderTabLabel('icon-mc-intelligent-detection', t('异常检测')) }}
            label={t('异常检测')}
            name={EAiConfigTab.anomalyDetection}
          >
            <AnomalyDetection />
          </Tab.TabPanel>
          <Tab.TabPanel
            v-slots={{ label: () => renderTabLabel('icon-code', t('源码 AI 分析')) }}
            label={t('源码 AI 分析')}
            name={EAiConfigTab.sourceCodeAnalysis}
          >
            <SourceCodeAnalysis />
          </Tab.TabPanel>
        </Tab>
      </div>
    );
  },
});
