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

import { type PropType, computed, defineComponent, onBeforeUnmount, shallowRef, watchEffect } from 'vue';

import { Alert, Button, Message } from 'bkui-vue';
import { Success } from 'bkui-vue/lib/icon';
import dayjs from 'dayjs';
import { useI18n } from 'vue-i18n';

import MarkdownViewer from '../../../../../../components/markdown-editor/viewer';
import { useIssuesAiAnalysis } from '../../../composables/use-issues-ai-analysis';
import { assignIssues } from '../../../services/issues-operations';
import AnalysisSummaryCard from './analysis-summary-card';

import type { IssueActivityItem, IssueDetail, SourceAnalysisView } from '../../../typing';

import './source-code-analysis.scss';

export default defineComponent({
  name: 'SourceCodeAnalysis',
  props: {
    detail: {
      type: Object as PropType<IssueDetail>,
      default: () => ({}),
    },
    show: {
      type: Boolean,
      default: false,
    },
  },
  emits: {
    assigneeChange: (_users: string[], _activities: IssueActivityItem[]) => true,
    backToIssue: () => true,
  },
  setup(props, { emit }) {
    const { t } = useI18n();
    const {
      sourceAnalysisData,
      sourceAnalysisIsPending,
      sourceAnalysisScene,
      loading,
      getSourceAnalysisData,
      handleReanalyzeSourceAnalysis,
      handleStartAnalysis,
      handleToSetting,
    } = useIssuesAiAnalysis();

    const assigneeChangeLoading = shallowRef(false);
    /**
     * 总结卡片所需的loading状态
     */
    const summaryCardLoading = computed(() => {
      return {
        assigneeChange: assigneeChangeLoading.value,
        retryAnalysis: loading.retryAnalysis,
      };
    });

    watchEffect(() => {
      sourceAnalysisScene.value = props.show ? 'view' : 'overview';
      if (props.detail?.id && props.show) {
        getSourceAnalysisData({ bk_biz_id: props.detail.bk_biz_id, issue_id: props.detail.id });
      }
    });

    const handleAssigneeChange = () => {
      assigneeChangeLoading.value = true;
      assignIssues({
        issues: [
          {
            bk_biz_id: props.detail.bk_biz_id,
            issue_id: props.detail.id,
          },
        ],
        assignee: [sourceAnalysisData.value.latest.result.result_card.responsibility.bk_username],
      })
        .then(({ succeeded, failed }) => {
          const activeItem = succeeded.find(item => item.issue_id === props.detail?.id);
          if (activeItem) {
            emit('assigneeChange', [], activeItem.activities);
          }
          Message({
            theme: activeItem ? 'success' : 'error',
            message: activeItem ? t('操作成功') : failed[0]?.message,
          });
        })
        .finally(() => {
          assigneeChangeLoading.value = false;
        });
    };

    const renderSourceCodeAnalysisView = () => {
      if (loading.sourceAnalysis)
        return (
          <div class='skeleton-wrapper'>
            {new Array(10).fill(0).map((_, index) => (
              <div
                key={index}
                class='skeleton-element'
              />
            ))}
          </div>
        );

      if (!sourceAnalysisData.value) return;

      const { is_repository_configured, is_configured, unavailable_reason_display, latest, next_execution_context } =
        sourceAnalysisData.value as SourceAnalysisView;

      /** 没有配置仓库 */
      if (!is_repository_configured) {
        return (
          <div class='config-guide'>
            <div class='guide-icon'>
              <i class='icon-monitor icon-Unlock' />
            </div>
            <div class='guide-title'>{t('尚未关联蓝盾项目及源码仓库')}</div>
            <div class='guide-desc'>
              {t('源码关联分析需要先知道告警对应的蓝盾项目和代码仓库，才能拉取构建记录、提交历史与 Blame 信息。')}
            </div>
            <div class='guide-btns'>
              <Button
                theme='primary'
                onClick={() => {
                  handleToSetting(props.detail.bk_biz_id);
                }}
              >
                {t('去配置 AI 设置')}
              </Button>
              <Button
                loading={loading.retryAnalysis}
                onClick={() => {
                  handleStartAnalysis({
                    bk_biz_id: props.detail.bk_biz_id,
                    issue_id: props.detail.id,
                  });
                }}
              >
                {t('已配置，立即分析')}
              </Button>
            </div>
          </div>
        );
      }

      /** 配置了仓库，但是不支持分析 */
      if (!is_configured) {
        return (
          <div class='config-guide'>
            <div class='guide-icon'>
              <i class='icon-monitor icon-copy-link' />
            </div>
            <div class='guide-title'>{t('源码仓库已关联')}</div>
            <div class='guide-desc'>{unavailable_reason_display}</div>
          </div>
        );
      }

      /** 没有进行分析 */
      if (!latest && next_execution_context.trigger_type === 'initial') {
        return (
          <div class='config-guide'>
            <div class='guide-icon'>
              <i class='icon-monitor icon-copy-link' />
            </div>
            <div class='guide-title'>{t('源码仓库已关联')}</div>
            <div class='guide-card'>
              <div class='card-header'>
                <Success
                  width={16}
                  height={16}
                />
                <span>{t('已就绪')}</span>
                <div class='divider' />
                <div>
                  {t('将由 {name} 触发蓝盾 AI 分析流水线实例', { name: next_execution_context.repository_alias })}
                </div>
              </div>
              <ul class='relation-info'>
                <li class='relation-item'>
                  <span class='relation-label'>{t('关联项目')}：</span>
                  <span class='relation-value'>{next_execution_context.bkci_project_id || t('无')}</span>
                </li>
                <li class='relation-item'>
                  <span class='relation-label'>{t('绑定智能体')}：</span>
                  <span class='relation-value'>{next_execution_context.agent_id || t('无')}</span>
                </li>
                <li class='relation-item'>
                  <span class='relation-label'>{t('绑定知识库')}：</span>
                  <span class='relation-value'>{next_execution_context.knowledge_base_ids.join('、') || t('无')}</span>
                </li>
                <li class='relation-item'>
                  <span class='relation-label'>{t('绑定 skill')}：</span>
                  <span class='relation-value'>{next_execution_context.skill_ids.join('、') || t('无')}</span>
                </li>
              </ul>
            </div>
            <div class='guide-btns'>
              <Button
                loading={loading.retryAnalysis}
                theme='primary'
                onClick={() => {
                  handleStartAnalysis({
                    bk_biz_id: props.detail.bk_biz_id,
                    issue_id: props.detail.id,
                  });
                }}
              >
                {t('立即分析')}
              </Button>
              <Button
                onClick={() => {
                  handleToSetting(props.detail.bk_biz_id);
                }}
              >
                {t('修改配置')}
              </Button>
            </div>
          </div>
        );
      }

      /** 分析中 */
      if (sourceAnalysisIsPending.value) {
        return (
          <div class='config-guide'>
            <div class='guide-icon'>
              <i class='icon-monitor icon-copy-link' />
            </div>
            <div class='guide-title'>{t('源码分析进行中')}</div>
            <div
              style='margin-bottom: 8px'
              class='guide-desc'
            >
              {t('由 {name} 于 {time} 发起, 完成后将通过企业微信通知本次发起人', {
                name: latest.triggered_by,
                time: dayjs.tz(latest.triggered_at * 1000, window.timezone).format('YYYY-MM-DD HH:mm:ssZZ'),
              })}
            </div>
            <Alert
              class='guide-alert pending'
              showIcon={false}
              theme='info'
              title={t('正在拉取来源构建、提交历史与 Blame 信息')}
            />
            <div class='guide-btns'>
              <Button
                theme='primary'
                disabled
              >
                {t('分析中···')}
              </Button>
              <Button
                onClick={() => {
                  emit('backToIssue');
                }}
              >
                {t('返回 Issue')}
              </Button>
            </div>
          </div>
        );
      }

      /** 分析失败 */
      if (latest?.status === 'failed') {
        return (
          <div class='config-guide'>
            <div class='guide-icon failed'>
              <i class='icon-monitor icon-alert-line' />
            </div>
            <div class='guide-title failed'>{t('源码分析失败')}</div>
            <div
              style='margin-bottom: 8px'
              class='guide-desc'
            >
              {t('蓝盾流水线执行失败，未生成本次分析结果')}
            </div>
            <Alert
              class='guide-alert failed'
              showIcon={false}
              theme='danger'
              title={latest.failure.message}
            />
            <div class='guide-btns'>
              {latest.failure.retryable && (
                <Button
                  loading={loading.retryAnalysis}
                  theme='primary'
                  onClick={() => {
                    handleReanalyzeSourceAnalysis({
                      bk_biz_id: props.detail.bk_biz_id,
                      issue_id: props.detail.id,
                      analysis_id: latest.analysis_id,
                    });
                  }}
                >
                  {t('重新分析')}
                </Button>
              )}
              <Button
                onClick={() => {
                  handleToSetting(props.detail.bk_biz_id);
                }}
              >
                {t('查看配置')}
              </Button>
            </div>
          </div>
        );
      }

      return (
        <div class='source-code-analysis-view'>
          <AnalysisSummaryCard
            loading={summaryCardLoading.value}
            sourceAnalysisData={sourceAnalysisData.value as SourceAnalysisView}
            onAssigneeChange={handleAssigneeChange}
            onReanalyzeAnalysis={() => {
              handleReanalyzeSourceAnalysis({
                bk_biz_id: props.detail.bk_biz_id,
                issue_id: props.detail.id,
              });
            }}
          />

          <MarkdownViewer
            height='420px'
            class='view-markdown-wrapper'
            value={latest.result.content}
          />
        </div>
      );
    };

    onBeforeUnmount(() => {
      sourceAnalysisScene.value = 'overview';
    });

    return {
      renderSourceCodeAnalysisView,
    };
  },
  render() {
    return <div class='source-code-analysis'>{this.renderSourceCodeAnalysisView()}</div>;
  },
});
