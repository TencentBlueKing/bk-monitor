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

import { type PropType, computed, defineComponent, shallowRef } from 'vue';

import { Button, Message } from 'bkui-vue';
import { useI18n } from 'vue-i18n';

import { ISSUES_REGRESSION_MAP } from '../../constant';
import { mergeIssues } from '../../services/issues-operations';
import IssueInfoItem from './issue-info-item';
import MergeStrategyTips from './merge-strategy-tips';
import ReasonSection from './reason-section';
import MainIssueIcon from '@/static/img/main-Issue.svg';
import MergedIssueIcon from '@/static/img/merged-Issue.svg';

import type { IssueItem } from '../../typing';

import './merge-content.scss';

export default defineComponent({
  name: 'MergeContent',
  props: {
    issues: {
      type: Array as PropType<IssueItem[]>,
      default: () => [],
    },
  },
  emits: ['close', 'success'],
  setup(props, { emit }) {
    const { t } = useI18n();

    const submitLoading = shallowRef(false);
    /** 默认主 Issue*/
    const defaultMainIssue = computed(() => {
      return props.issues.find(issue => issue.merge_status?.role === 'main');
    });

    /** 自定义主 Issue ID */
    const customMainIssueId = shallowRef('');
    /** 主 Issue */
    const mainIssue = computed(() => {
      /** 有默认主 Issue时，直接返回 */
      if (defaultMainIssue.value) return defaultMainIssue.value;
      /** 没有默认主 Issue时，根据自定义主 Issue ID 返回 */
      if (customMainIssueId.value) return props.issues.find(issue => issue.id === customMainIssueId.value);
      /** 没有自定义主 Issue ID时，返回第一个 Issue */
      return props.issues[0];
    });
    /** 被合并 Issue 列表 */
    const targetIssues = computed(() => {
      return props.issues.filter(issue => issue.id !== mainIssue.value?.id);
    });

    /** 获取 metric 列表 */
    const getMetricList = (issue: IssueItem) =>
      Object.entries(issue.impact_scope ?? {}).map(([, resource]) => ({
        label: resource.display_name,
        value: resource.count,
      }));

    /** 处理设置主 Issue */
    const handleSetMain = (issue: IssueItem) => {
      customMainIssueId.value = issue.id;
    };

    /** 合并依据选项列表 */
    const mergeReasonOptions = [
      t('异常类型 / 日志模块相近'),
      t('message 高度相似'),
      t('堆栈顶帧一致'),
      t('服务或链路维度相关'),
      t('时间窗口接近'),
      t('日志聚类一致'),
      t('人工确认同根因'),
    ];

    const selectReason = shallowRef<string[]>([]);
    const inputReason = shallowRef('');
    const handleReasonSelectChange = (value: string[]) => {
      selectReason.value = value;
    };
    const handleReasonInput = (value: string) => {
      inputReason.value = value;
    };

    /** 处理确认 */
    const handleConfirm = () => {
      submitLoading.value = true;
      const reasons = inputReason.value ? [...selectReason.value, inputReason.value] : selectReason.value;
      mergeIssues({
        bk_biz_id: mainIssue.value.bk_biz_id,
        main_issue_id: mainIssue.value.id,
        members: targetIssues.value.map(issue => issue.id),
        reasons,
      })
        .then(() => {
          Message({
            theme: 'success',
            message: t('issue合并成功'),
          });
          emit('success');
          handleClose();
        })
        .finally(() => {
          submitLoading.value = false;
        });
    };

    const handleClose = () => {
      emit('close');
    };

    return {
      submitLoading,
      defaultMainIssue,
      mainIssue,
      targetIssues,
      mergeReasonOptions,
      selectReason,
      inputReason,
      handleReasonSelectChange,
      handleReasonInput,
      getMetricList,
      handleSetMain,
      handleConfirm,
      handleClose,
    };
  },
  render() {
    return (
      <div class='issues-merge-content'>
        {/* 合并策略提示 */}
        <div class='strategy-section'>
          <MergeStrategyTips hasMainIssue={Boolean(this.defaultMainIssue)} />
        </div>

        {/* 合并设置区域 */}
        <div class='settings-section'>
          <div class='section-title'>{this.$t('合并设置')}</div>
          <div class='issue-list'>
            {/* 主 Issue */}
            <div class='issue-group main-issue'>
              <div class='issue-header'>
                <div class='group-icon'>
                  <img
                    alt={this.$t('主 Issue')}
                    src={MainIssueIcon}
                  />
                </div>
                <span class='issue-group-name'>{this.$t('主 Issue')}</span>
                <span class='divider' />
                <span class='issue-group-tips'>{this.$t('合并后保留')}</span>
              </div>
              <div class='issue-content'>
                {this.mainIssue && (
                  <IssueInfoItem
                    v-slots={{
                      prefix: () => (
                        <span class='tag-item issues-alert-count'>
                          <i class='icon-monitor icon-alert-line' />
                          <span class='issues-alert-count-number'>{this.mainIssue.alert_count}</span>
                        </span>
                      ),
                    }}
                    desc={this.mainIssue.anomaly_message}
                    icon={ISSUES_REGRESSION_MAP[String(this.mainIssue.is_regression)]}
                    list={this.getMetricList(this.mainIssue)}
                    name={this.mainIssue.name}
                  />
                )}
              </div>
            </div>

            {/* 被合并 Issue 列表 */}
            <div class='issue-group target-issue'>
              <div class='issue-header'>
                <div class='group-icon'>
                  <img
                    alt={this.$t('被合并 Issue')}
                    src={MergedIssueIcon}
                  />
                </div>
                <span class='issue-group-name'>{this.$t('被合并 Issue')}</span>
                <span class='divider' />
                <span class='issue-group-tips'>{this.$t('合并后隐藏')}</span>
              </div>
              <div class='issue-content'>
                {this.targetIssues.map(issue => {
                  return (
                    <IssueInfoItem
                      key={issue.id}
                      v-slots={{
                        prefix: () => (
                          <span class='tag-item issues-alert-count'>
                            <i class='icon-monitor icon-alert-line' />
                            <span class='issues-alert-count-number'>{issue.alert_count}</span>
                          </span>
                        ),
                        actions: () => {
                          return this.defaultMainIssue ? null : (
                            <Button
                              class='set-main-btn'
                              size='small'
                              theme='primary'
                              outline
                              onClick={() => this.handleSetMain(issue)}
                            >
                              {this.$t('设为主 Issue')}
                            </Button>
                          );
                        },
                      }}
                      desc={issue.anomaly_message}
                      icon={ISSUES_REGRESSION_MAP[String(issue.is_regression)]}
                      list={this.getMetricList(issue)}
                      name={issue.name}
                    />
                  );
                })}
              </div>
            </div>
          </div>
        </div>

        {/* 合并依据区域 */}
        <ReasonSection
          inputValue={this.inputReason}
          options={this.mergeReasonOptions}
          placeholder={this.$t('自定义新增合并依据，例如：同一蓝盾发布后集中出现')}
          selectValue={this.selectReason}
          tips={this.$t('由执行合并的用户指定，合并后会沉淀到主 Issue 的合并来源种，便于后续复盘。')}
          title={this.$t('合并依据')}
          onInput={this.handleReasonInput}
          onSelectChange={this.handleReasonSelectChange}
        />

        {/* 底部按钮区域 */}
        <div class='footer-section'>
          <Button
            loading={this.submitLoading}
            theme='primary'
            onClick={this.handleConfirm}
          >
            {this.$t('确认合并')}
          </Button>
          <Button onClick={this.handleClose}>{this.$t('取消')}</Button>
        </div>
      </div>
    );
  },
});
