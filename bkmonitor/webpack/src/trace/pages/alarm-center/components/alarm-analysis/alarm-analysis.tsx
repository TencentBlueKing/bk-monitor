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

import { defineComponent, onMounted, reactive, shallowRef } from 'vue';
import { computed } from 'vue';

import { Message } from 'bkui-vue';
import { copyText } from 'monitor-common/utils';
import { useI18n } from 'vue-i18n';

import EmptyStatus from '../../../../components/empty-status/empty-status';
import useUserConfig from '../../../../hooks/useUserConfig';
import { useAlarmAnalysis } from '../../composables/use-analysis';
import AlarmAnalysisDetail from './alarm-analysis-detail';
import AnalysisList from './analysis-list';
import SettingDialog from './setting-dialog';
import ChartCollapse from '@/pages/trace-explore/components/explore-chart/chart-collapse';

import type { AnalysisListItem, AnalysisListItemBucket } from '../../typings';

import './alarm-analysis.scss';

export const AlarmAnalysisCollapse = 'ALARM_ANALYSIS_COLLAPSE';

export default defineComponent({
  name: 'AlarmAnalysis',
  emits: ['conditionChange'],
  setup(_, { emit }) {
    const { t } = useI18n();
    const {
      analysisFieldTopNData,
      analysisFieldTopNLoading,
      analysisFields,
      dimensionTags,
      analysisFieldsMap,
      analysisDimensionTopNData,
      getAnalysisDataByFields,
      analysisSettings,
    } = useAlarmAnalysis();
    const { handleGetUserConfig, handleSetUserConfig } = useUserConfig();

    /** 告警字段分析列表 */
    const analysisFieldList = computed(() => {
      return analysisFields.value.map(item => {
        return {
          id: item,
          name: analysisFieldsMap.value[item],
        };
      });
    });

    /** 告警分析TopN列表(包含字段和维度) */
    const analysisList = computed(() => {
      return [...analysisFieldTopNData.value.fields, ...analysisDimensionTopNData.value.fields];
    });

    /** 当前展示的告警分析 */
    const showAnalysisList = computed<AnalysisListItem[]>(() => {
      return analysisSettings.value.reduce((pre, cur) => {
        const field = analysisList.value.find(item => item.field === cur);
        if (field) pre.push(field);
        return pre;
      }, []);
    });

    const expand = shallowRef(false);

    onMounted(() => {
      handleGetUserConfig<boolean>(AlarmAnalysisCollapse).then(res => {
        expand.value = res ?? true;
      });
    });

    const handleCollapse = (val: boolean) => {
      expand.value = val;
      handleSetUserConfig(JSON.stringify(expand.value));
    };

    const showSetting = shallowRef(false);
    const handleSettingsClick = (e: Event) => {
      e.stopPropagation();
      showSetting.value = true;
    };

    /** 批量复制 */
    const handleCopyNames = (names: AnalysisListItemBucket[] = []) => {
      const value = names.map(item => item.name).join('\n');
      copyText(value, msg => {
        Message({
          message: msg,
          theme: 'error',
        });
        return;
      });
      Message({
        message: t('复制成功'),
        theme: 'success',
      });
    };

    const handleConditionChange = (type: string, value: string, field: string) => {
      emit('conditionChange', {
        key: field,
        value: [value],
        method: type,
      });
    };

    /** 渲染折叠内容区域 */
    const renderCollapseContent = () => {
      if (analysisFieldTopNLoading.value) {
        return (
          <div class='skeleton-wrap'>
            {new Array(5).fill(0).map((_, index) => (
              <div
                key={index}
                class='skeleton-panel-item'
              >
                {new Array(6).fill(0).map((_, i) => (
                  <div
                    key={i}
                    class={['skeleton-element', { title: i === 0 }]}
                  />
                ))}
              </div>
            ))}
          </div>
        );
      }

      if (!showAnalysisList.value.length) return <EmptyStatus type='empty' />;

      return (
        <div class='collapse-content'>
          {showAnalysisList.value.map(panel => (
            <div
              key={panel.field}
              class='panel-item'
            >
              <div class='panel-item-header'>
                <div class='header-left'>
                  <span class='title'>{panel.name}</span>
                  <div class='count'>{panel.bucket_count}</div>
                  <i
                    class='icon-monitor icon-mc-copy'
                    v-bk-tooltips={{ content: '批量复制' }}
                    onClick={() => handleCopyNames(panel.buckets.slice(0, 5))}
                  />
                </div>
                {panel.bucket_count > 5 && (
                  <span
                    class='header-right'
                    onClick={() => handleViewAll(panel)}
                  >
                    {t('查看全部')}
                  </span>
                )}
              </div>
              <div class='panel-item-content'>
                <AnalysisList
                  field={panel.field}
                  list={panel.buckets.slice(0, 5)}
                  onConditionChange={(type, value) => handleConditionChange(type, value, panel.field)}
                />
              </div>
            </div>
          ))}
        </div>
      );
    };

    /** 设置字段，维度是否展示 */
    const handleSelectValueChange = (val: string[]) => {
      analysisSettings.value = val;
    };

    /** 加载更多-侧栏数据 */
    const detailSliderShow = shallowRef(false);
    const detailSliderLoading = shallowRef(false);
    const detailSliderInfo = reactive({
      field: '',
      name: '',
      count: 0,
      list: [],
    });

    /** 查看全部 */
    const handleViewAll = async (panel: AnalysisListItem) => {
      detailSliderShow.value = true;
      detailSliderInfo.field = panel.field;
      detailSliderInfo.name = panel.name;
      detailSliderLoading.value = true;
      const data = await getAnalysisDataByFields([panel.field], true);
      detailSliderLoading.value = false;
      detailSliderInfo.list = data.fields[0]?.buckets || [];
      detailSliderInfo.count = data.fields[0]?.bucket_count || 0;
    };

    return {
      t,
      expand,
      handleCollapse,
      showAnalysisList,
      analysisFieldTopNLoading,
      analysisFieldList,
      dimensionTags,
      handleCopyNames,
      analysisFields,
      analysisSettings,
      showSetting,
      handleSettingsClick,
      detailSliderShow,
      detailSliderInfo,
      detailSliderLoading,
      handleViewAll,
      handleSelectValueChange,
      renderCollapseContent,
      handleConditionChange,
    };
  },
  render() {
    return (
      <div class='alarm-analysis-comp'>
        <ChartCollapse
          defaultHeight={0}
          defaultIsExpand={this.expand}
          hasResize={false}
          title={this.t('告警分析')}
          onCollapseChange={this.handleCollapse}
        >
          {{
            headerCustom: () => (
              <div
                class='settings'
                onClick={this.handleSettingsClick}
              >
                <i class='icon-monitor icon-shezhi1' />
                <span>{this.t('设置')}</span>
              </div>
            ),
            default: this.renderCollapseContent,
          }}
        </ChartCollapse>

        <AlarmAnalysisDetail
          v-model:show={this.detailSliderShow}
          count={this.detailSliderInfo.count}
          list={this.detailSliderInfo.list}
          loading={this.detailSliderLoading}
          title={this.detailSliderInfo.name}
          onConditionChange={(type, value) => {
            this.handleConditionChange(type, value, this.detailSliderInfo.field);
          }}
          onCopyNames={this.handleCopyNames}
        />

        <SettingDialog
          v-model:show={this.showSetting}
          dimensionList={this.dimensionTags}
          fieldList={this.analysisFieldList}
          selectValue={this.analysisSettings}
          onSelectValueChange={this.handleSelectValueChange}
        />
      </div>
    );
  },
});
