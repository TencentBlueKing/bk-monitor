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
import DiagnosticCollapse from './diagnostic-collapse';

import type { IPanelItem } from '../../typeing';

import './index.scss';

export default defineComponent({
  name: 'DiagnosticAnalysis',
  props: {
    id: String as PropType<string>,
    panels: Array as PropType<IPanelItem[]>,
    aiConfig: Object as PropType<any>,
    aiTitle: String as PropType<string>,
    isFixed: {
      type: Boolean as PropType<boolean>,
      default: false,
    },
  },
  emits: ['close', 'fixed'],
  setup(props, { emit, slots }) {
    const { t } = useI18n();
    const isAllCollapsed = shallowRef(true);
    const activeIndex = shallowRef([0, 1]);
    /** 展开/收起全部 */
    const handleToggleAll = () => {
      isAllCollapsed.value = !isAllCollapsed.value;
      activeIndex.value = isAllCollapsed.value ? props.panels.map((_, ind) => ind) : [];
    };
    /** 关闭 */
    const handleClose = () => {
      emit('close');
    };
    /** 固定 */
    const handleFixed = () => {
      emit('fixed', !props.isFixed);
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
              class={`icon-monitor icon-a-${props.isFixed ? 'pinnedtuding' : 'pintuding'} icon-btn`}
              v-bk-tooltips={{
                content: props.isFixed ? t('取消固定') : t('固定在界面上'),
                placements: ['top'],
              }}
              onClick={handleFixed}
            />
            <i
              class='icon-monitor icon-mc-close icon-btn'
              v-bk-tooltips={{
                content: t('关闭'),
                placements: ['top'],
              }}
              onClick={handleClose}
            />
          </span>
        </div>
        <div class='diagnostic-analysis-main'>
          <AICard
            v-slots={{
              default: () => slots.aiDefault?.(),
            }}
            content={props.aiConfig}
            title={props.aiTitle}
          />
          <DiagnosticCollapse
            activeIndex={activeIndex.value}
            list={props.panels}
          />
        </div>
      </div>
    );
  },
});
