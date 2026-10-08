/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 *
 * Copyright (C) 2017-2025 THL A29 Limited, a Tencent company. All rights reserved.
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
import { type PropType, defineComponent, onScopeDispose, shallowRef, watch } from 'vue';

import EmptyStatus from 'trace/components/empty-status/empty-status';
import OverflowTips from 'trace/directive/overflow-tips';
import { useI18n } from 'vue-i18n';

import { useTapdIssueActivities } from '../../../issues-tapd/composables/use-tapd-issue-activities';
import { getTapdRelations } from '../../../services/relation-tapd';
import IssuesLoading from '../issues-loading';
import { DetailLoadStatus } from '../../../../common-detail/detail-loading';

import BasicCard from '../basic-card/basic-card';
import RelationTapdItem from './relation-tapd-item';

import type { TapdRelationItem } from '../../../services/relation-tapd';
import type { IssueDetail } from '../../../typing';

import './issues-relation-tapd.scss';

export default defineComponent({
  name: 'IssuesRelationTapd',
  directive: {
    OverflowTips,
  },
  props: {
    refreshKey: { type: String, default: '' },
    detail: {
      type: Object as PropType<IssueDetail>,
      default: () => ({}),
    },
  },

  setup(props) {
    const { t } = useI18n();

    const list = shallowRef<TapdRelationItem[]>([]);
    const loading = shallowRef(false);
    const loaded = shallowRef(false);
    const error = shallowRef(false);
    let controller: AbortController;
    onScopeDispose(() => controller?.abort());

    /** TAPD 单据操作成功后的全局活动记录，用于回写到当前 Issue 活动列表 */
    const tapdIssueActivities = useTapdIssueActivities();

    /** 获取 TAPD 关联列表 */
    const getTapdList = async () => {
      controller?.abort();
      controller = new AbortController();
      const { signal } = controller;
      if (!props.detail?.id || !props.detail?.bk_biz_id) return;
      loading.value = true;
      error.value = false;
      try {
        const res = await getTapdRelations({ bk_biz_id: props.detail.bk_biz_id, issue_id: props.detail.id }, { signal });
        if (signal.aborted) return;
        list.value = Array.isArray(res) ? res : [];
        loaded.value = true;
      } catch {
        if (!signal.aborted) error.value = true;
      } finally {
        if (!signal.aborted) loading.value = false;
      }
    };

    watch(
      [() => props.detail?.id, () => props.detail?.bk_biz_id, () => props.refreshKey],
      getTapdList,
      { immediate: true }
    );

    watch(
      () => tapdIssueActivities.infos.value,
      () => {
        if (
          tapdIssueActivities.infos.value?.issueId === props.detail?.id &&
          tapdIssueActivities.infos.value?.list?.length
        ) {
          controller?.abort();
          loading.value = false;
          error.value = false;
          loaded.value = true;
          list.value = tapdIssueActivities.infos.value.list;
        }
      }
    );

    return {
      t,
      list,
      loading,
      loaded,
      error,
      retry: getTapdList,
    };
  },

  render() {
    const count = this.list.length;

    return (
      <BasicCard
        class='issues-detail-issues-relation-tapd'
        v-slots={{ header: () => <span>{this.t('关联单据')} ({this.loading && !this.loaded ? <IssuesLoading variant='count' /> : !this.loaded ? '--' : count})</span> }}
      >
        <DetailLoadStatus loading={this.loading && this.loaded} error={this.error} onRetry={this.retry} />
        {this.loading && !this.loaded && <IssuesLoading variant='tapd' />}
        {this.loaded && count === 0 && <EmptyStatus />}

        {this.loaded &&
          this.list.map(item => (
            <RelationTapdItem
              key={item.tapd_id}
              value={item}
            />
          ))}
      </BasicCard>
    );
  },
});
