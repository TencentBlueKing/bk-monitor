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

import { Button, Input } from 'bkui-vue';
import dayjs from 'dayjs';
import { useI18n } from 'vue-i18n';

import { fetchMergeSources } from '../../services/issues-operations';
import IssueInfoItem from './issue-info-item';
import IssuesSplitDialog from './issues-split-dialog';
import EmptyStatus, { type EmptyStatusOperationType } from '@/components/empty-status/empty-status';
import MergedIssueIcon from '@/static/img/merged-Issue.svg';

import type { IssueItem, ListMergeSourcesResponse, MergeSourceActiveMember } from '../../typing';

import './split-content.scss';

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
    /** 当前待拆分的 Issue */
    const currentSplitIssue = shallowRef<MergeSourceActiveMember | null>(null);

    /** 被合并 Issue 列表 */
    const targetIssues = computed(() => {
      return mergeSources.value?.active_members?.filter(issue => issue.member_name?.includes(searchKey.value)) || [];
    });

    /** 获取 metric 列表 */
    const getMetricList = (issue: MergeSourceActiveMember) => issue.merge_reasons.map(reason => reason);

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
        <IssueInfoItem
          key={issue.member_issue_id}
          v-slots={{
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
              <span class='operate-record'>{`${issue.merge_operator} · ${dayjs(issue.merge_time * 1000).format('YYYY-MM-DD HH:mm')}`}</span>
            ),
          }}
          desc={issue.anomaly_message}
          list={getMetricList(issue)}
          name={issue.member_name}
        />
      ));
    };

    /** 处理拆分按钮点击，打开弹窗 */
    const handleSplit = (issue: MergeSourceActiveMember) => {
      currentSplitIssue.value = issue;
      dialogVisible.value = true;
    };

    /** 处理弹窗关闭 */
    const handleDialogShowChange = (show: boolean) => {
      dialogVisible.value = show;
      if (!show) {
        currentSplitIssue.value = null;
      }
    };

    /** 处理拆分成功 */
    const handleDialogSuccess = (memberIssueId: string) => {
      emit('success', memberIssueId);
    };

    onMounted(() => {
      getIssueMergeSources();
    });

    return {
      searchKey,
      targetIssues,
      dialogVisible,
      currentSplitIssue,
      renderSplitContent,
      handleDialogShowChange,
      handleDialogSuccess,
    };
  },
  render() {
    return (
      <div class='issues-split-content'>
        <div class='issue-group'>
          <div class='issue-header'>
            <div class='category-icon'>
              <img
                alt={this.$t('已并入但隐藏的 Issue')}
                src={MergedIssueIcon}
              />
            </div>
            <span class='issue-category-name'>{this.$t('已并入但隐藏的 Issue')}</span>
            <Input
              class='search-input'
              v-model={this.searchKey}
              size='small'
              type='search'
            />
          </div>
          <div class='issue-content'>{this.renderSplitContent()}</div>
        </div>
        <IssuesSplitDialog
          bizId={this.issues[0]?.bk_biz_id}
          isShow={this.dialogVisible}
          issue={this.currentSplitIssue}
          onSuccess={this.handleDialogSuccess}
          onUpdate:isShow={this.handleDialogShowChange}
        />
      </div>
    );
  },
});
