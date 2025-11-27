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

import { defineComponent, ref, watch } from 'vue';

import { t } from '@/hooks/use-locale';
import { TAB_TYPES, TabType } from '../constants';

import ConfigurationTable from './configuration-table';

import './personalized-configuration-slider.scss';

export default defineComponent({
  name: 'PersonalizedConfigurationSlider',
  components: {
    ConfigurationTable,
  },
  props: {
    isShow: {
      type: Boolean,
      default: false,
    },
  },
  emits: ['cancel-slider'],

  setup(props, { emit }) {
    const tabs = ref([
      // tab配置
      {
        title: TAB_TYPES.KEYWORD,
      },
      {
        title: TAB_TYPES.METRIC,
      },
    ]);
    const activeTab = ref<TabType>(TAB_TYPES.KEYWORD); // 激活的tab
    const tableData = ref([]); // 表格数据

    // 关键词配置数据
    const keywordConfigs = ref([]);

    // 指标配置数据
    const metricConfigs = ref([]);

    // tab点击事件
    const handleTabClick = (title: TabType) => {
      activeTab.value = title;
    };

    // 监听tab切换
    watch(
      activeTab,
      (title: TabType) => {
        if (title === TAB_TYPES.KEYWORD) {
          tableData.value = keywordConfigs.value;
        } else {
          tableData.value = metricConfigs.value;
        }
      },
      { immediate: true },
    );

    // 取消操作/关闭侧滑弹窗
    const handleCancel = () => {
      emit('cancel-slider');
    };

    return () => (
      <div class='personalized-configuration-slider'>
        <bk-sideslider
          width={960}
          title={t('个性化设置')}
          quick-close
          is-show={props.isShow}
          onAnimation-end={handleCancel}
          transfer
        >
          <div slot='content'>
            <div class='personalized-configuration-container'>
              {/* tab部分 */}
              <div class='tabs'>
                {tabs.value.map(tab => (
                  <div
                    class={['tab-item', activeTab.value === tab.title && 'active']}
                    onClick={() => {
                      handleTabClick(tab.title as TabType);
                    }}
                  >
                    {tab.title}
                  </div>
                ))}
              </div>
              <div class='personalized-configuration-content'>
                {/* 内容部分 */}
                <bk-button
                  theme='primary'
                  title={t('新建')}
                >
                  {t('新建')}
                </bk-button>
                <ConfigurationTable
                  tabType={activeTab.value}
                  data={tableData.value}
                />
              </div>
            </div>
          </div>
        </bk-sideslider>
      </div>
    );
  },
});
