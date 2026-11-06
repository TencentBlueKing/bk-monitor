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
import { type PropType, defineComponent, onScopeDispose, shallowRef, watch } from 'vue';

import dayjs from 'dayjs';
import { listIssueHistory } from 'monitor-api/modules/issue';

import IssuesLoading from '../issues-loading';
import { DetailLoadStatus } from '../../../../common-detail/detail-loading';

import BasicCard from '../basic-card/basic-card';
import EmptyStatus from '@/components/empty-status/empty-status';


import type { IssueDetail, IssueHistoryItem } from '../../../typing';

import './issues-history.scss';

export default defineComponent({
  name: 'IssuesHistory',
  props: {
    refreshKey: { type: String, default: '' },
    detail: {
      type: Object as PropType<IssueDetail>,
      default: () => ({}),
    },
  },

  setup(props) {
    const historyList = shallowRef<IssueHistoryItem[]>([]);
    const loading = shallowRef(false);
    const loaded = shallowRef(false);
    const error = shallowRef(false);
    let controller: AbortController;
    onScopeDispose(() => controller?.abort());


    /** 获取 Issue 历史列表*/
    const getIssuesHistoryList = async () => {
      controller?.abort();
      controller = new AbortController();
      const { signal } = controller;
      if (!props.detail?.id || !props.detail?.bk_biz_id) return;
      loading.value = true;
      error.value = false;
      try {
        const res = await listIssueHistory({ bk_biz_id: props.detail.bk_biz_id, issue_id: props.detail.id }, { signal });
        if (signal.aborted) return;
        historyList.value = Array.isArray(res) ? res : [];
        loaded.value = true;
      } catch {
        if (!signal.aborted) error.value = true;
      } finally {
        if (!signal.aborted) loading.value = false;
      }
    };

    /** 新开页展示issues详情 */
    const handleClick = (item: IssueHistoryItem) => {
      const hash = `#/alarm-center/?alarmType=issues&detailId=${item.issue_id}&detailBizId=${item.bk_biz_id}&showDetail=true`;
      const url = location.href.replace(location.hash, hash);
      window.open(url, '_blank');
    };

    watch(
      [() => props.detail?.id, () => props.detail?.bk_biz_id, () => props.refreshKey],
      getIssuesHistoryList,
      { immediate: true }
    );


    return {
      historyList,
      loading,
      handleClick,
      loaded,
      error,
      retry: getIssuesHistoryList,
    };
  },

  render() {
    return (
      <BasicCard
        class='issues-history'
        title={this.$t('历史 Issue')}
      >
        <div class='issues-history-list'>
          <DetailLoadStatus loading={this.loading && this.loaded} error={this.error} onRetry={this.retry} />
          {this.loading && !this.loaded ? (
            <IssuesLoading variant='history' />
          ) : !this.loaded ? null : this.historyList.length ? (
            this.historyList.map(item => (
              <div
                key={item.issue_id}
                class='issues-history-item'
              >
                <div
                  class='item-title'
                  v-overflow-tips
                  onClick={() => {
                    this.handleClick(item);
                  }}
                >
                  {item.name}
                </div>
                <div
                  class='item-time'
                  v-bk-tooltips={{ content: dayjs(item.resolved_time * 1000).format('YYYY-MM-DD HH:mm:ss') }}
                >
                  {dayjs(item.resolved_time * 1000).fromNow()}
                </div>
              </div>
            ))
          ) : (
            <EmptyStatus
              textMap={{ empty: this.$t('暂无历史 Issue') }}
              type='empty'
            />
          )}
        </div>
      </BasicCard>
    );
  },
});
