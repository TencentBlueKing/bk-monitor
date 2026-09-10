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

import { type PropType, computed, defineComponent, onMounted, shallowRef } from 'vue';

import { Button, Checkbox, Input } from 'bkui-vue';
import dayjs from 'dayjs';
import { useI18n } from 'vue-i18n';

import { fetchMergeSources } from '../../services/issues-operations';
import IssueInfoItem from './issue-info-item';
import IssuesSplitDialog from './issues-split-dialog';
import EmptyStatus, { type EmptyStatusOperationType } from '@/components/empty-status/empty-status';
import MergedIssueIcon from '@/static/img/merged-Issue.svg';

import type { IssueItem, ListMergeSourcesResponse, MergeSourceActiveMember } from '../../typing';

import './split-content.scss';

/** 单次批量拆分的最大条数，与后端 member_issue_ids 的 max_length 对齐 */
const MAX_BATCH_SPLIT_COUNT = 50;

export default defineComponent({
  name: 'SplitContent',
  props: {
    issues: {
      type: Array as PropType<IssueItem[]>,
      default: () => [],
    },
  },
  emits: ['success'],
  setup(props, { emit }) {
    const { t } = useI18n();
    const loading = shallowRef(false);
    const searchKey = shallowRef('');

    const mergeSources = shallowRef<ListMergeSourcesResponse | null>(null);

    /** 弹窗显示状态 */
    const dialogVisible = shallowRef(false);
    /** 当前待拆分的 Issue 列表：行内拆分为 1 条，批量拆分为全部勾选项 */
    const splitTargets = shallowRef<MergeSourceActiveMember[]>([]);

    /** 已勾选的成员 Issue ID；用 Set 保证行渲染时的勾选态判定为 O(1) */
    const selectedIds = shallowRef<Set<string>>(new Set());

    /** 被合并 Issue 列表（按搜索词过滤后的可见列表） */
    const targetIssues = computed(() => {
      return mergeSources.value?.active_members?.filter(issue => issue.member_name?.includes(searchKey.value)) || [];
    });

    /** 可见列表中已勾选的条数，用于全选框的全选 / 半选态判定 */
    const visibleSelectedCount = computed(() => {
      const selected = selectedIds.value;
      if (!selected.size) return 0;
      return targetIssues.value.reduce((count, issue) => count + (selected.has(issue.member_issue_id) ? 1 : 0), 0);
    });

    /** 可见列表是否已全部勾选 */
    const isAllChecked = computed(
      () => targetIssues.value.length > 0 && visibleSelectedCount.value === targetIssues.value.length
    );

    /** 全选框半选态：可见列表部分勾选 */
    const isIndeterminate = computed(() => visibleSelectedCount.value > 0 && !isAllChecked.value);

    /** 已勾选总数（含被搜索过滤掉的项） */
    const selectedCount = computed(() => selectedIds.value.size);

    /** 批量拆分按钮禁用时的提示，非空即代表禁用 */
    const batchDisabledTip = computed(() => {
      if (!selectedCount.value) return t('请先勾选需要拆分的 Issue');
      if (selectedCount.value > MAX_BATCH_SPLIT_COUNT)
        return t('单次最多拆分 {n} 个 Issue', { n: MAX_BATCH_SPLIT_COUNT });
      return '';
    });

    /** 获取 metric 列表 */
    const getMetricList = (issue: MergeSourceActiveMember) => issue.merge_reasons.map(reason => reason);

    const formatAlertTime = (timestamp?: number) =>
      timestamp ? dayjs(timestamp * 1000).format('YYYY-MM-DD HH:mm') : '--';

    const getIssueMergeSources = async () => {
      const issue = props.issues[0];
      if (!issue) return;
      loading.value = true;
      const data = await fetchMergeSources({
        bk_biz_id: issue.bk_biz_id,
        main_issue_id: issue.id,
      });
      loading.value = false;
      mergeSources.value = data;
    };

    const handleOperation = (type: EmptyStatusOperationType) => {
      if (type === 'clear-filter') {
        searchKey.value = '';
      }
    };

    /** 处理单行勾选态变更 */
    const handleRowCheck = (memberIssueId: string, checked: boolean) => {
      const next = new Set(selectedIds.value);
      if (checked) next.add(memberIssueId);
      else next.delete(memberIssueId);
      selectedIds.value = next;
    };

    /** 处理全选：仅作用于当前搜索结果，搜索结果外的已勾选项保持不变 */
    const handleCheckAll = (checked: boolean) => {
      const next = new Set(selectedIds.value);
      for (const issue of targetIssues.value) {
        if (checked) next.add(issue.member_issue_id);
        else next.delete(issue.member_issue_id);
      }
      selectedIds.value = next;
    };

    const renderSplitContent = () => {
      if (loading.value) {
        return new Array(3).fill(0).map((_, index) => (
          <IssueInfoItem
            key={index}
            loading={true}
          />
        ));
      }

      if (targetIssues.value.length === 0)
        return (
          <EmptyStatus
            type={searchKey.value ? 'search-empty' : 'empty'}
            onOperation={handleOperation}
          />
        );

      return targetIssues.value.map(issue => (
        <div
          key={issue.member_issue_id}
          class='split-issue-row'
        >
          <Checkbox
            class='row-checkbox'
            modelValue={selectedIds.value.has(issue.member_issue_id)}
            onChange={(checked: boolean) => handleRowCheck(issue.member_issue_id, checked)}
          />
          <IssueInfoItem
            v-slots={{
              prefix: () =>
                issue.via_issue_id ? (
                  <span
                    class='tag-item via-issue-tag'
                    v-bk-tooltips={{
                      content: t('该 Issue 原挂在 {id} 下，随其合并平移而来', { id: issue.via_issue_id }),
                    }}
                  >
                    {t('随合并平移')}
                  </span>
                ) : null,
              actions: () => (
                <Button
                  class='split-btn'
                  size='small'
                  theme='primary'
                  outline
                  onClick={() => handleSplit(issue)}
                >
                  <i class='icon-monitor icon-ziyuantuopu' />
                  {t('拆分为新 Issue')}
                </Button>
              ),
              suffix: () => (
                <span class='operate-record'>
                  {`${issue.merge_operator} · ${t('最后出现时间')}: ${formatAlertTime(issue.last_alert_time)}  ${t('最早发生时间')}: ${formatAlertTime(issue.first_alert_time)}`}
                </span>
              ),
              content: () => (
                <div class='issues-name-description'>
                  <span
                    class='issues-alert-count'
                    v-bk-tooltips={{
                      content: `${t('告警事件数')}: ${issue.alert_count ?? '--'}`,
                    }}
                  >
                    <i class='icon-monitor icon-alert-line' />
                    <span class='issues-alert-count-number'>{issue.alert_count ?? '--'}</span>
                  </span>
                  <span
                    class='issues-name-exception-text'
                    v-overflow-tips
                  >
                    {issue.anomaly_message}
                  </span>
                </div>
              ),
            }}
            list={getMetricList(issue)}
            name={issue.member_es_status === null ? `${issue.member_issue_id} (${t('已删除')})` : issue.member_name}
          />
        </div>
      ));
    };

    /** 处理行内拆分按钮点击，打开弹窗 */
    const handleSplit = (issue: MergeSourceActiveMember) => {
      splitTargets.value = [issue];
      dialogVisible.value = true;
    };

    /** 处理批量拆分按钮点击：取全部勾选项，顺序与原始成员列表一致（不受搜索影响） */
    const handleBatchSplit = () => {
      const selected = selectedIds.value;
      splitTargets.value =
        mergeSources.value?.active_members?.filter(issue => selected.has(issue.member_issue_id)) ?? [];
      dialogVisible.value = true;
    };

    /** 处理弹窗关闭 */
    const handleDialogShowChange = (show: boolean) => {
      dialogVisible.value = show;
      if (!show) {
        splitTargets.value = [];
      }
    };

    /** 处理拆分成功 */
    const handleDialogSuccess = (memberIssueIds: string[]) => {
      emit('success', memberIssueIds);
    };

    onMounted(() => {
      getIssueMergeSources();
    });

    return {
      searchKey,
      targetIssues,
      dialogVisible,
      splitTargets,
      selectedCount,
      isAllChecked,
      isIndeterminate,
      batchDisabledTip,
      renderSplitContent,
      handleCheckAll,
      handleBatchSplit,
      handleDialogShowChange,
      handleDialogSuccess,
    };
  },
  render() {
    return (
      <div class='issues-split-content'>
        <div class='split-toolbar'>
          <span v-tippy={this.batchDisabledTip ? { content: this.batchDisabledTip } : undefined}>
            <Button
              class='batch-split-btn'
              disabled={!!this.batchDisabledTip}
              theme='primary'
              outline
              onClick={this.handleBatchSplit}
            >
              {this.$t('批量拆分')}
            </Button>
          </span>
          {this.selectedCount > 0 && (
            <span class='selected-count'>
              <i18n-t keypath='当前已选 {0} 项'>
                <span class='count-number'>{this.selectedCount}</span>
              </i18n-t>
            </span>
          )}
          <Input
            class='search-input'
            v-model={this.searchKey}
            placeholder={this.$t('搜索')}
            type='search'
          />
        </div>
        <div class='issue-group'>
          <div class='issue-header'>
            <Checkbox
              class='check-all'
              disabled={this.targetIssues.length === 0}
              indeterminate={this.isIndeterminate}
              modelValue={this.isAllChecked}
              onChange={this.handleCheckAll}
            />
            <div class='category-icon'>
              <img
                alt={this.$t('已并入但隐藏的 Issue')}
                src={MergedIssueIcon}
              />
            </div>
            <span class='issue-category-name'>{this.$t('已并入但隐藏的 Issue')}</span>
          </div>
          <div class='issue-content'>{this.renderSplitContent()}</div>
        </div>
        <IssuesSplitDialog
          bizId={this.issues[0]?.bk_biz_id}
          isShow={this.dialogVisible}
          issues={this.splitTargets}
          onSuccess={this.handleDialogSuccess}
          onUpdate:isShow={this.handleDialogShowChange}
        />
      </div>
    );
  },
});
