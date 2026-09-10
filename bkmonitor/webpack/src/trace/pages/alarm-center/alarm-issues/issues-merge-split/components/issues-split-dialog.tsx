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

import { Button, Dialog, Message } from 'bkui-vue';
import dayjs from 'dayjs';
import { useI18n } from 'vue-i18n';

import { splitIssues } from '../../services/issues-operations';
import IssueInfoItem from './issue-info-item';
import ReasonSection from './reason-section';

import type { MergeSourceActiveMember, SplitIssueResultItem } from '../../typing';

import './issues-split-dialog.scss';

export default defineComponent({
  name: 'IssuesSplitDialog',
  props: {
    bizId: {
      type: [Number, String],
      default: null,
    },
    /** 是否显示 */
    isShow: {
      type: Boolean,
      default: false,
    },
    /** 待拆分的 Issue 列表：单条为行内拆分，多条为批量拆分 */
    issues: {
      type: Array as PropType<MergeSourceActiveMember[]>,
      default: () => [],
    },
  },
  emits: ['update:isShow', 'success'],
  setup(props, { emit }) {
    const { t } = useI18n();

    /** 拆分依据选项 */
    const splitReasonOptions = [
      t('误合并，根因不同'),
      t('影响范围不同'),
      t('责任 Owner 不同'),
      t('修复方案不同'),
      t('后续复盘需要独立跟踪'),
    ];

    const selectReason = shallowRef<string[]>([]);
    const inputReason = shallowRef('');

    /** 批量形态下已选 Issue 列表是否展开，按设计默认展开 */
    const listExpanded = shallowRef(true);

    /** 是否批量拆分形态 */
    const isBatch = computed(() => props.issues.length > 1);

    const handleSelectReasonChange = (value: string[]) => {
      selectReason.value = value;
    };

    const handleInputReasonChange = (value: string) => {
      inputReason.value = value;
    };

    /** 获取 metric 列表 */
    const getMetricList = (issue: MergeSourceActiveMember) => issue.merge_reasons.map(reason => reason);

    const submitLoading = shallowRef(false);

    /**
     * @description 汇总逐条拆分结果并分级提示：全部达成 success / 部分失败 warning / 全部失败 error。
     *   skipped 表示合并关系已不活跃（并发或重复触发），目标状态已达成，故计入达成数但不参与行高亮。
     * @param {SplitIssueResultItem[]} results - 接口返回的逐条执行结果
     * @returns {string[]} 本次真正拆出的成员 Issue ID 列表
     */
    const resolveSplitResults = (results: SplitIssueResultItem[]) => {
      const splitIds: string[] = [];
      let settledCount = 0;
      for (const item of results) {
        if (item.status === 'failed') continue;
        settledCount += 1;
        if (item.status === 'ok') splitIds.push(item.member_issue_id);
      }

      const failedCount = results.length - settledCount;
      if (!settledCount) {
        Message({ theme: 'error', message: t('拆分失败，请稍后重试') });
      } else if (failedCount) {
        Message({
          theme: 'warning',
          message: t('成功拆分 {success} 个，失败 {failed} 个', { success: settledCount, failed: failedCount }),
        });
      } else {
        Message({
          theme: 'success',
          message: isBatch.value ? t('已拆分为 {n} 个独立 Issue', { n: settledCount }) : t('已拆分为独立 Issue'),
        });
      }
      return splitIds;
    };

    /** 处理确认拆分 */
    const handleConfirm = () => {
      submitLoading.value = true;
      const reasons = inputReason.value ? [...selectReason.value, inputReason.value] : selectReason.value;
      splitIssues({
        bk_biz_id: +props.bizId,
        member_issue_ids: props.issues.map(issue => issue.member_issue_id),
        reasons,
      })
        .then(data => {
          const splitIds = resolveSplitResults(Array.isArray(data) ? data : (data?.results ?? []));
          // 全部失败时保留弹窗，让用户在原上下文重试，不丢失已填写的拆分依据
          if (!splitIds.length) return;
          handleShowChange(false);
          emit('success', splitIds);
        })
        .finally(() => {
          submitLoading.value = false;
        });
    };

    const handleShowChange = (show: boolean) => {
      emit('update:isShow', show);
    };

    // 每次打开重置依据与展开态，避免上一次的填写内容串场
    watch(
      () => props.isShow,
      show => {
        if (!show) return;
        selectReason.value = [];
        inputReason.value = '';
        listExpanded.value = true;
      }
    );

    /** 单条形态：沿用 IssueInfoItem 展示待拆分 Issue 的完整信息 */
    const renderSingleIssue = () => {
      const issue = props.issues[0];
      return (
        <div class='issue-preview-section'>
          <IssueInfoItem
            v-slots={{
              suffix: () => (
                <span class='operate-record'>{`${issue.merge_operator} · ${dayjs(issue.merge_time * 1000).format('YYYY-MM-DD HH:mm')}`}</span>
              ),
            }}
            desc={issue.anomaly_message}
            list={getMetricList(issue)}
            name={issue.member_name}
          />
        </div>
      );
    };

    /** 批量形态：可折叠的已选 Issue 清单，默认展开、限高 5 条后内部滚动 */
    const renderBatchIssues = () => (
      <div class='issue-select-list'>
        <div
          class='select-list-header'
          onClick={() => {
            listExpanded.value = !listExpanded.value;
          }}
        >
          <i
            class={['icon-monitor', 'icon-mc-triangle-down', 'expand-icon', { 'is-collapsed': !listExpanded.value }]}
          />
          <span class='select-list-title'>
            <i18n-t keypath='已选择 {0} 个 Issue'>
              <span class='select-count'>{props.issues.length}</span>
            </i18n-t>
          </span>
        </div>
        {listExpanded.value && (
          <div class='select-list-body'>
            {props.issues.map(issue => (
              <div
                key={issue.member_issue_id}
                class='select-list-item'
                v-overflow-tips
              >
                {issue.member_name}
              </div>
            ))}
          </div>
        )}
      </div>
    );

    return {
      isBatch,
      selectReason,
      inputReason,
      splitReasonOptions,
      submitLoading,
      renderSingleIssue,
      renderBatchIssues,
      handleSelectReasonChange,
      handleInputReasonChange,
      handleConfirm,
      handleShowChange,
    };
  },
  render() {
    return (
      <Dialog
        width={640}
        class='issues-split-dialog'
        isShow={this.isShow}
        title={this.isBatch ? this.$t('批量拆分为新 Issue') : this.$t('拆分为新 Issue')}
        onUpdate:isShow={this.handleShowChange}
      >
        {{
          default: () => (
            <div class='split-dialog-content'>
              {/* Issue 信息展示：单条展示完整信息，批量展示可折叠清单 */}
              {this.issues.length > 0 && (this.isBatch ? this.renderBatchIssues() : this.renderSingleIssue())}

              {/* 拆分依据区域 */}
              <ReasonSection
                inputValue={this.inputReason}
                options={this.splitReasonOptions}
                placeholder={this.$t('自定义拆分依据，例如：同一蓝盾发布后集中出现')}
                selectValue={this.selectReason}
                tips={this.$t('选择或填写拆分依据后，再确认拆分为新 Issue。')}
                title={this.$t('拆分依据')}
                onInput={this.handleInputReasonChange}
                onSelectChange={this.handleSelectReasonChange}
              />
            </div>
          ),
          footer: () => (
            <div class='dialog-footer'>
              <Button
                class='confirm-btn'
                loading={this.submitLoading}
                theme='primary'
                onClick={this.handleConfirm}
              >
                {this.$t('确认拆分')}
              </Button>
              <Button
                onClick={() => {
                  this.handleShowChange(false);
                }}
              >
                {this.$t('取消')}
              </Button>
            </div>
          ),
        }}
      </Dialog>
    );
  },
});
