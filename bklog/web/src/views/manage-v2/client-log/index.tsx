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

import { defineComponent, ref } from 'vue';

import './index.scss';
import { t } from '@/hooks/use-locale';

// tab类型常量定义
const TAB_TYPES = {
  COLLECT: t('采集下发'),
  REPORT: t('用户上报'),
} as const;

type TabType = (typeof TAB_TYPES)[keyof typeof TAB_TYPES];

export default defineComponent({
  name: 'ClientLog',
  setup() {
    const tabs = ref([
      {
        title: TAB_TYPES.COLLECT,
        count: '453',
      },
      {
        title: TAB_TYPES.REPORT,
        count: 87,
      },
    ]);
    const activeTab = ref<TabType>(TAB_TYPES.COLLECT);

    // tab点击事件
    const handleTabClick = (title: TabType) => {
      activeTab.value = title;
    };

    return () => (
      <div class='client-log-main'>
        {/* tab部分 */}
        <div class='tabs'>
          {tabs.value.map(tab => (
            <div
              class={['tab-item', activeTab.value === tab.title && 'active']}
              onClick={() => {
                handleTabClick(tab.title as TabType);
              }}
            >
              <span class='tab-item-title'>{tab.title}</span>
              <span class='tab-item-num'>{tab.count}</span>
            </div>
          ))}
        </div>
        <div class='client-log-container'>
          {/* 按钮、搜索、alter提示区域 */}
          {activeTab.value === TAB_TYPES.COLLECT ? (
            <div class='deploy-header'>
              {/* 采集下发 */}
              <div>
                <bk-button theme='primary'>{t('新建采集')}</bk-button>
                <bk-button>{t('清洗配置')}</bk-button>
              </div>
              <div>
                <bk-input
                  placeholder={t('搜索 任务 ID、任务名称、openID、创建方式、任务状态、任务阶段、创建人')}
                  clearable
                  right-icon={'bk-icon icon-search'}
                ></bk-input>
              </div>
            </div>
          ) : (
            <div>
              {/* 用户上报 */}
              <bk-alert
                class='alert-info'
                type='info'
                title={t('Alert 文案占位，用于说明如果用 SDK 上报。')}
              ></bk-alert>
              <div class='operating-area'>
                <bk-button>{t('清洗配置')}</bk-button>
                <div>
                  <bk-input
                    placeholder={t('搜索 任务 ID、任务名称、openID、创建方式、任务状态、任务阶段、创建人')}
                    clearable
                    right-icon={'bk-icon icon-search'}
                  ></bk-input>
                </div>
              </div>
            </div>
          )}
          {/* 表格内容区域 */}
          <section>表格内容</section>
        </div>
      </div>
    );
  },
});
