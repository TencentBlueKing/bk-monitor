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
import { defineComponent, type PropType, shallowRef } from 'vue';
import { useI18n } from 'vue-i18n';

import AICard from './ai-card';
import ContentCollapse from './content-collapse';
import DiagnosticCollapse from './diagnostic-collapse';
import { aiContent, dimensional } from './mockData';

import './index.scss';

export default defineComponent({
  name: 'DiagnosticAnalysis',
  props: {
    id: String as PropType<string>,
  },
  setup(props) {
    const { t } = useI18n();
    const isAllCollapsed = shallowRef(true);
    const activeIndex = shallowRef([0, 1]);
    const isFixed = false;
    const list = [
      {
        name: t('可疑维度'),
        icon: 'icon-dimension-line',
        render: () => (
          <ContentCollapse
            label={'经过 维度下钻 分析，发现以下可疑维度（组合）：'}
            list={dimensional}
          />
        ),
      },
      {
        name: t('可疑调用链'),
        icon: 'icon-Tracing',
        render: () => <ContentCollapse list={dimensional} />,
      },
      {
        name: t('可疑日志'),
        icon: 'icon-dimension-line',
        render: () => <ContentCollapse list={dimensional} />,
      },
      {
        name: t('可疑事件'),
        icon: 'icon-shijianjiansuo',
        render: () => (
          <ContentCollapse
            label={'通过分析告警产生前 1 小时时间窗口事件，可疑事件为：'}
            list={dimensional}
          />
        ),
      },
      {
        name: t('相关性指标'),
        icon: 'icon-zhibiaojiansuo',
        render: () => <ContentCollapse list={dimensional} />,
      },
    ];
    const aiConfig = aiContent;
    const handleToggleAll = () => {
      isAllCollapsed.value = !isAllCollapsed.value;
      activeIndex.value = isAllCollapsed.value ? list.map((_, ind) => ind) : [];
    };
    return () => (
      <div class='alarm-center-detail-diagnostic-analysis'>
        <div class='diagnostic-analysis-title'>
          {t('诊断分析')}
          <span class='header-bg' />
          <span class='diagnostic-analysis-title-btn'>
            <i
              class={`icon-monitor icon-${isAllCollapsed.value ? 'zhankai2' : 'shouqi3'} icon-btn`}
              v-bk-tooltips={{
                content: isAllCollapsed.value ? t('全部收起') : t('全部展开'),
                placements: ['top'],
              }}
              onClick={handleToggleAll}
            />
            <i
              class={`icon-monitor icon-a-${isFixed ? 'pinnedtuding' : 'pintuding'} icon-btn`}
              v-bk-tooltips={{
                content: isFixed ? t('取消固定') : t('固定在界面上'),
                placements: ['top'],
              }}
            />
            <i
              class='icon-monitor icon-mc-close icon-btn'
              v-bk-tooltips={{
                content: t('关闭'),
                placements: ['top'],
              }}
            />
          </span>
        </div>
        <div class='diagnostic-analysis-main'>
          <AICard
            content={aiConfig}
            title={`${t('诊断概率：')}85%`}
          />
          <DiagnosticCollapse
            activeIndex={activeIndex.value}
            list={list}
          />
        </div>
      </div>
    );
  },
});
