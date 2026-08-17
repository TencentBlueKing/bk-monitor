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

import { type PropType, computed, defineComponent, watch } from 'vue';

import { Button, Exception, Loading } from 'bkui-vue';
import { useI18n } from 'vue-i18n';

import { useIssuesAiAnalysis } from '../../../composables/use-issues-ai-analysis';
import BasicCard from '../basic-card/basic-card';

import type { IssueDetail } from '../../../typing';

import './issues-ai-analysis-overview.scss';
export default defineComponent({
  name: 'IssuesAiAnalysisOverview',
  props: {
    detail: {
      type: Object as PropType<IssueDetail>,
      default: () => ({}),
    },
  },
  emits: {
    viewReport: () => true,
  },
  setup(props, { emit }) {
    const { t } = useI18n();

    const {
      sourceAnalysisData,
      loading: analysisLoading,
      sourceAnalysisIsPending,
      handleReanalyzeSourceAnalysis,
      getSourceAnalysisData,
      handleToSetting,
      handleStartAnalysis,
    } = useIssuesAiAnalysis();

    const loading = computed(() => analysisLoading.sourceAnalysis);

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

      if (!sourceAnalysisData.value.is_configured) {
        return (
          <Exception
            class='tips-exception'
            scene='part'
            type='search-empty'
          >
            {sourceAnalysisData.value.unavailable_reason_display}
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
                loading={analysisLoading.retryAnalysis}
                mode='spin'
                size='mini'
                theme='primary'
              >
                <span
                  class='btn'
                  onClick={() => {
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

      if (sourceAnalysisData.value.latest.status === 'failed') {
        return (
          <Exception
            class='tips-exception'
            scene='part'
            type='500'
          >
            <div>{sourceAnalysisData.value.latest.failure.message}</div>
            {sourceAnalysisData.value.latest.failure.retryable && (
              <Button
                style='margin-top: 10px'
                loading={analysisLoading.retryAnalysis}
                theme='primary'
                text
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
          </Exception>
        );
      }

      const {
        latest: { result },
      } = sourceAnalysisData.value;

      return (
        <div class='analysis-content'>
          <div class='analysis-overview-info'>{result.result_card.description}</div>
          <div class='operation-btns'>
            <Button
              theme='primary'
              text
              onClick={() => {
                emit('viewReport');
              }}
            >
              <i class='icon-monitor icon-back-right' />
              {t('查看完整报告')}
            </Button>
            <div class='divider' />
            <Loading
              loading={analysisLoading.retryAnalysis}
              mode='spin'
              size='mini'
              theme='primary'
            >
              <Button
                theme='primary'
                text
                onClick={() => {
                  handleReanalyzeSourceAnalysis({
                    bk_biz_id: props.detail.bk_biz_id,
                    issue_id: props.detail.id,
                  });
                }}
              >
                <i class='icon-monitor icon-shuaxin' />
                {t('重新分析')}
              </Button>
            </Loading>
          </div>
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
        class='issues-detail-issues-ai-analysis-overview'
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
