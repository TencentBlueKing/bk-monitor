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

import { type PropType, computed, defineComponent, shallowRef, watch } from 'vue';

import { Button, Exception, Loading, Message } from 'bkui-vue';
import { useI18n } from 'vue-i18n';

import { useIssuesAiAnalysis } from '../../../composables/use-issues-ai-analysis';
import { assignIssues } from '../../../services/issues-operations';
import BasicCard from '../basic-card/basic-card';

import type { IssueActivityItem, IssueDetail } from '../../../typing';

import './issues-ai-analysis-view.scss';
export default defineComponent({
  name: 'IssuesAiAnalysisView',
  props: {
    detail: {
      type: Object as PropType<IssueDetail>,
      default: () => ({}),
    },
  },
  emits: {
    assigneeChange: (_users: string[], _activities: IssueActivityItem[]) => true,
  },
  setup(props, { emit }) {
    const { t } = useI18n();
    const assigning = shallowRef(false);

    const {
      sourceAnalysisData,
      loading: analysisLoading,
      sourceAnalysisIsPending,
      getSourceAnalysisData,
      handleToSetting,
      handleStartAnalysis,
    } = useIssuesAiAnalysis();

    const loading = computed(() => analysisLoading.sourceAnalysis);

    const handleAssignResponsibility = async (username: string) => {
      if (!username || assigning.value) return;

      assigning.value = true;
      const { succeeded, failed } = await assignIssues({
        issues: [{ bk_biz_id: props.detail.bk_biz_id, issue_id: props.detail.id }],
        assignee: [username],
      });
      const succeededItem = succeeded.find(item => item.issue_id === props.detail.id);
      if (succeededItem) {
        emit('assigneeChange', [username], succeededItem.activities);
      }
      Message({
        theme: succeededItem ? 'success' : 'error',
        message: succeededItem ? t('操作成功') : failed[0]?.message || t('操作失败'),
      });
      assigning.value = false;
    };

    watch(
      () => props.detail,
      detail => {
        if (detail?.id) {
          getSourceAnalysisData({ bk_biz_id: detail.bk_biz_id, issue_id: detail.id });
        }
      },
      { immediate: true }
    );

    const renderSkeleton = () => {
      return (
        <div class='ai-analysis-skeleton-wrap'>
          {new Array(5).fill(0).map((_, index) => (
            <div
              key={index}
              class='skeleton-element'
            />
          ))}
        </div>
      );
    };

    const renderSourceCodeAnalysisView = () => {
      if (!sourceAnalysisData.value) return;
      /** 没有配置仓库 */
      if (!sourceAnalysisData.value.is_repository_configured) {
        return (
          <Exception
            class='tips-exception'
            scene='part'
            type='search-empty'
          >
            <i18n-t
              class='text'
              keypath='暂未关联蓝盾项目 & 源码仓库，{0}'
            >
              <span
                class='btn'
                onClick={handleToSetting}
              >
                {t('去配置')}
              </span>
            </i18n-t>
          </Exception>
        );
      }

      /** 配置了仓库，但是没有分析 */
      if (!sourceAnalysisData.value.latest) {
        return (
          <Exception
            class='tips-exception'
            scene='part'
            type='search-empty'
          >
            <i18n-t
              class='text'
              keypath='已关联蓝盾项目 & 源码仓库，{0}'
            >
              <Loading
                style='display: inline-block'
                loading={analysisLoading.startAnalysis}
                mode='spin'
                size='mini'
                theme='primary'
              >
                <span
                  class='btn'
                  onClick={() => {
                    if (analysisLoading.startAnalysis) return;
                    handleStartAnalysis({
                      bk_biz_id: props.detail.bk_biz_id,
                      issue_id: props.detail.id,
                    });
                  }}
                >
                  {t('立即分析')}
                </span>
              </Loading>
            </i18n-t>
          </Exception>
        );
      }

      /** 分析中 */
      if (sourceAnalysisIsPending.value) {
        return (
          <div class='analysis-pending'>
            <Loading
              mode='spin'
              size='small'
              theme='primary'
              loading
            >
              <div class='loading-wrap' />
            </Loading>
            <span class='text'>{t('源码分析进行中')}</span>
          </div>
        );
      }

      const {
        latest: { failure, result },
      } = sourceAnalysisData.value;
      if (!result) {
        return <div class='analysis-error'>{failure?.message || t('源码分析未生成有效结果')}</div>;
      }

      const { result_card: resultCard, result_type: resultType } = result;
      const responsibility = resultCard.responsibility;
      const bkUsername = responsibility?.bk_username;
      const resultTypeText = resultType === 'HIGH_CONFIDENCE' ? t('高置信度') : t('证据不足');

      return (
        <div class='analysis-content'>
          <div class='analysis-item'>
            <span class='item-label'>{t('分析结论')}:</span>
            <span class={['result-type', resultType.toLowerCase().replace('_', '-')]}>{resultTypeText}</span>
          </div>
          <div class='analysis-item'>
            <span class='item-label'>{t('结论说明')}:</span>
            <span class='item-content description'>{resultCard.description}</span>
          </div>
          {responsibility && (
            <div class='analysis-item'>
              <span class='item-label'>{t('责任提交')}:</span>
              <span class='item-content responsibility-content'>
                <span class='commit-id'>{responsibility.commit_id.slice(-7)}</span>
                <span
                  class='commit-message'
                  v-overflow-tips
                >
                  {responsibility.commit_message}
                </span>
                <span>·</span>
                <span class='commit-author'>{bkUsername || responsibility.author_name}</span>
                {bkUsername && (
                  <Button
                    class='assign-button'
                    loading={assigning.value}
                    size='small'
                    text
                    theme='primary'
                    onClick={() => handleAssignResponsibility(bkUsername)}
                  >
                    {t('一键分派')}
                  </Button>
                )}
              </span>
            </div>
          )}
        </div>
      );
    };

    return {
      t,
      loading,
      sourceAnalysisData,
      renderSkeleton,
      renderSourceCodeAnalysisView,
    };
  },
  render() {
    return (
      <BasicCard
        class='issues-detail-issues-ai-analysis-view'
        title={this.t('AI 分析快览')}
      >
        {this.loading && this.renderSkeleton()}

        {!this.loading && (
          <div class='source-code-analysis-view'>
            <div class='analysis-title'>
              <i class='icon-monitor icon-code' />
              <span class='title'>{this.t('源码关联分析')}</span>
            </div>
            {this.renderSourceCodeAnalysisView()}
          </div>
        )}
      </BasicCard>
    );
  },
});
