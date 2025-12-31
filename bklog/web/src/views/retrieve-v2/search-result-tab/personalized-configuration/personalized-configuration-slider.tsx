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

import { defineComponent, nextTick, ref, watch } from 'vue';

import { t } from '@/hooks/use-locale';
import { TabType } from './types';
import RetrieveHelper, { RetrieveEvent } from '@/views/retrieve-helper';
import useStore from '@/hooks/use-store';
import GradeOption from '@/components/monitor-echarts/components/grade-option';
import LogKeywordSetting from './log-keyword-setting';
import LogMetric from './log-metric';

import './personalized-configuration-slider.scss';

const TAB_TYPE_LABELS: Record<TabType, string> = {
  [TabType.LOG_LEVEL]: t('日志分级展示'),
  [TabType.LOG_KEYWORD]: t('日志关键词设置'),
  [TabType.LOG_METRIC]: t('日志转指标'),
} as const;

export default defineComponent({
  name: 'PersonalizedConfigurationSlider',
  components: {
    LogKeywordSetting,
    LogMetric,
  },
  props: {
    isShow: {
      type: Boolean,
      default: false,
    },
  },
  emits: ['cancel-slider'],

  setup(props, { emit }) {
    const store = useStore();

    const tabs = ref([
      // tab配置
      TabType.LOG_LEVEL,
      TabType.LOG_KEYWORD,
      // TabType.LOG_METRIC,
    ]);
    const activeTab = ref<TabType>(TabType.LOG_LEVEL); // 激活的tab
    const tableData = ref([]); // 表格数据
    const refGradeOption = ref();

    // 关键词配置数据
    const keywordConfigs = ref([]);

    // 指标配置数据
    const metricConfigs = ref([]);

    // tab点击事件
    const handleTabClick = (title: TabType) => {
      activeTab.value = title;
    };

    // 监听侧滑弹窗打开状态
    watch(
      () => props.isShow,
      async (isShow) => {
        if (isShow) {
          await nextTick();
          // 更新分级配置
          const cfg = store.state.indexFieldInfo.custom_config?.grade_options ?? {};
          refGradeOption.value?.updateOptions?.(cfg);
        }
      },
    );

    // 监听tab切换
    watch(activeTab, async (title: TabType) => {
      if (title === TabType.LOG_LEVEL) {
        // 更新分级配置
        const cfg = store.state.indexFieldInfo.custom_config?.grade_options ?? {};
        await nextTick();
        refGradeOption.value?.updateOptions?.(cfg);
      } else if (title === TabType.LOG_KEYWORD) {
        tableData.value = keywordConfigs.value;
      } else {
        tableData.value = metricConfigs.value;
      }
    });

    // 取消操作/关闭侧滑弹窗
    const handleCancel = () => {
      emit('cancel-slider');
    };

    // 分级配置变更回调
    const handleGradeOptionChange = ({ isSave }) => {
      handleCancel();
      if (isSave) {
        RetrieveHelper.fire(RetrieveEvent.TREND_GRAPH_SEARCH); // 触发趋势图刷新
      }
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
                    class={['tab-item', activeTab.value === tab && 'active']}
                    onClick={() => {
                      handleTabClick(tab);
                    }}
                  >
                    {TAB_TYPE_LABELS[tab]}
                  </div>
                ))}
              </div>
              <div class='personalized-configuration-content'>
                {/* 日志分级展示 */}
                {activeTab.value === TabType.LOG_LEVEL && (
                  <div class='bklog-v3-grade-setting'>
                    <GradeOption
                      ref={refGradeOption}
                      on-Change={handleGradeOptionChange}
                    />
                  </div>
                )}
                {/* 日志关键词设置 */}
                {activeTab.value === TabType.LOG_KEYWORD && (
                  <div>
                    <LogKeywordSetting />
                  </div>
                )}
                {/* 日志转指标部分 */}
                {activeTab.value === TabType.LOG_METRIC && (
                  <div>
                    <LogMetric />
                  </div>
                )}
              </div>
            </div>
          </div>
        </bk-sideslider>
      </div>
    );
  },
});
