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

import { Button, Input } from 'bkui-vue';
import { useI18n } from 'vue-i18n';

import EmptyStatus, { type EmptyStatusOperationType } from '@/components/empty-status/empty-status';
import MergedIssueIcon from '@/static/img/merged-Issue.svg';

import type { IssueItem } from '../../typing';

import './split-content.scss';

export default defineComponent({
  name: 'SplitContent',
  props: {
    mainIssue: {
      type: Object as PropType<IssueItem>,
      default: () => null,
    },
    issues: {
      type: Array as PropType<IssueItem[]>,
      default: () => [],
    },
  },
  emits: ['close'],
  setup(props, { emit }) {
    const { t } = useI18n();

    const searchKey = shallowRef('');

    /** 被合并 Issue 列表 */
    const targetIssues = computed(() => {
      return props.issues.filter(issue => issue.id !== props.mainIssue?.id && issue.name.includes(searchKey.value));
    });

    const handleOperation = (type: EmptyStatusOperationType) => {
      if (type === 'clear-filter') {
        searchKey.value = '';
      }
    };

    const renderIssueItem = (issue: IssueItem) => {
      if (!issue) return null;
      return (
        <div class='issue-item'>
          <div class='issue-info-row'>
            <div class='issue-info'>
              <span class='issue-name'>{issue.name}</span>
              <span class='divider' />
              <span
                class='issue-desc'
                v-overflow-tips
              >
                {issue.anomaly_message}
              </span>
            </div>
            <Button
              size='small'
              theme='primary'
              outline
            >
              <i class='icon-monitor icon-ziyuantuopu' />
              {t('拆分为新 Issue')}
            </Button>
          </div>
          <div class='issue-metrics-row'>
            {Object.entries(issue.impact_scope ?? {}).map(([resourceKey, resource]) => (
              <div
                key={resourceKey}
                class='tag-item metric-item'
              >
                <div class='label'>{resource.display_name}</div>
                <div class='value'>{resource.count}</div>
              </div>
            ))}
            <span class='operate-record'>edwinwu · 2025-04-10 00:00:00</span>
          </div>
        </div>
      );
    };

    /** 处理确认 */
    const handleConfirm = () => {
      console.log('confirm');
      emit('close');
    };

    const handleClose = () => {
      console.log('cancel');
      emit('close');
    };

    return {
      searchKey,
      targetIssues,
      handleOperation,
      renderIssueItem,
      handleConfirm,
      handleClose,
    };
  },
  render() {
    return (
      <div class='split-content'>
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
          <div class='issue-content'>
            {this.targetIssues.map(issue => this.renderIssueItem(issue))}
            {this.targetIssues.length === 0 && (
              <EmptyStatus
                type={this.searchKey ? 'search-empty' : 'empty'}
                onOperation={this.handleOperation}
              />
            )}
          </div>
        </div>
      </div>
    );
  },
});
