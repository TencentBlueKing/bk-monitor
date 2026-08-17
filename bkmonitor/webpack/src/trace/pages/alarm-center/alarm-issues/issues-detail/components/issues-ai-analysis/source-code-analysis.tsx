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
      /** 没有配置仓库 */
      if (!sourceAnalysisData.value.is_repository_configured) {
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
              <Button theme='primary'>{t('去配置 AI 设置')}</Button>
              <Button>{t('已配置，立即分析')}</Button>
            </div>
          </div>
        );
      }

      /** 配置了仓库，但是不支持分析 */
      if (!sourceAnalysisData.value.is_configured) {
        return (
          <div class='config-guide'>
            <div class='guide-icon'>
              <i class='icon-monitor icon-copy-link' />
            </div>
            <div class='guide-title'>{t('源码仓库已关联')}</div>
            <div class='guide-desc'>{sourceAnalysisData.value.unavailable_reason_display}</div>
          </div>
        );
      }

      /** 没有进行分析 */
      if (!sourceAnalysisData.value.latest) {
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
                <div>将由 bkfara 触发蓝盾 AI 分析流水线实例</div>
              </div>
              <ul class='relation-info'>
                <li class='relation-item'>
                  <span class='relation-label'>{t('关联项目')}：</span>
                  <span class='relation-value'>IEG-登录服务</span>
                </li>
                <li class='relation-item'>
                  <span class='relation-label'>{t('绑定智能体')}：</span>
                  <span class='relation-value'>我是智能体名称</span>
                </li>
                <li class='relation-item'>
                  <span class='relation-label'>{t('绑定知识库')}：</span>
                  <span class='relation-value'>日志深度归因知识库</span>
                </li>
                <li class='relation-item'>
                  <span class='relation-label'>{t('绑定 skill')}：</span>
                  <span class='relation-value'>告警分析 skill</span>
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
              <Button>{t('修改配置')}</Button>
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
                name: (sourceAnalysisData.value as SourceAnalysisView).latest.triggered_by,
                time: dayjs
                  .tz((sourceAnalysisData.value as SourceAnalysisView).latest.triggered_at * 1000, window.timezone)
                  .format('YYYY-MM-DD HH:mm:ssZZ'),
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
              <Button>{t('返回 Issue')}</Button>
            </div>
          </div>
        );
      }

      /** 分析失败 */
      if (sourceAnalysisData.value.latest.status === 'failed') {
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
              title={sourceAnalysisData.value.latest.failure.message}
            />
            <div class='guide-btns'>
              {sourceAnalysisData.value.latest.failure.retryable && (
                <Button
                  loading={loading.retryAnalysis}
                  theme='primary'
                  onClick={() => {
                    handleReanalyzeSourceAnalysis({
                      bk_biz_id: props.detail.bk_biz_id,
                      issue_id: props.detail.id,
                      analysis_id: sourceAnalysisData.value.latest.analysis_id,
                    });
                  }}
                >
                  {t('重新分析')}
                </Button>
              )}
              <Button>{t('查看配置')}</Button>
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
