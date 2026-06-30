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

import { useI18n } from 'vue-i18n';

import { HOST_CONTENT_TAB_LIST, type HostContentTab } from '../../constants/constants';

import './host-content-tabs.scss';

export default defineComponent({
  name: 'HostContentTabs',
  setup() {
    const { t } = useI18n();
    /** 当前激活 Tab，默认主机列表 */
    const activeTab = shallowRef<HostContentTab>('list');

    const handleTabChange = (value: HostContentTab) => {
      activeTab.value = value;
    };

    return () => (
      <div class='host-content-tabs'>
        <div class='host-content-tabs__tabs'>
          {HOST_CONTENT_TAB_LIST.map(tab => (
            <div
              key={tab.value}
              class={['host-content-tabs__tab', { 'is-active': activeTab.value === tab.value }]}
              onClick={() => handleTabChange(tab.value)}
            >
              <i class={['icon-monitor', tab.icon, 'host-content-tabs__tab-icon']} />
              <span>{t(tab.label)}</span>
            </div>
          ))}
        </div>
        <div class='host-content-tabs__content'>
          {/* 主机列表 / 指标汇聚 内容本期暂以占位替代 */}
          <div class='host-content-tabs__placeholder' />
        </div>
      </div>
    );
  },
});
