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
import { type PropType, defineComponent, shallowRef, watch } from 'vue';

import dayjs from 'dayjs';
import { listIssueHistory } from 'monitor-api/modules/issue';

import BasicCard from '../basic-card/basic-card';
import EmptyStatus from '@/components/empty-status/empty-status';
import useRequestAbort from '@/hooks/useRequestAbort';

import type { IssueDetail, IssueHistoryItem } from '../../../typing';

import './issues-history.scss';

export default defineComponent({
  name: 'IssuesHistory',
  props: {
    detail: {
      type: Object as PropType<IssueDetail>,
      default: () => ({}),
    },
  },

  setup(props) {
    const historyList = shallowRef<IssueHistoryItem[]>([]);
    const loading = shallowRef(false);

    const { run, signal } = useRequestAbort<IssueHistoryItem[]>(listIssueHistory);

    /** 获取 Issue 历史列表*/
    const getIssuesHistoryList = async () => {
      loading.value = true;
      const res = await run({
        bk_biz_id: props.detail.bk_biz_id,
        issue_id: props.detail.id,
      });
      if (signal?.aborted) return;
      historyList.value = res;
      loading.value = false;
    };

    /** 新开页展示issues详情 */
    const handleClick = (item: IssueHistoryItem) => {
      const hash = `#/alarm-center/?alarmType=issues&detailId=${item.issue_id}&detailBizId=${item.bk_biz_id}&showDetail=true&issueFirstAlarmTime=${item.first_alert_time}`;
      const url = location.href.replace(location.hash, hash);
      window.open(url, '_blank');
    };

    const renderSkeleton = () => {
      return new Array(5).fill(0).map((_, index) => (
        <div
          key={index}
          class='issues-history-item skeleton-element'
        />
      ));
    };

    watch(
      () => props.detail?.id,
      id => {
        if (id) {
          getIssuesHistoryList();
        }
      }
    );

    getIssuesHistoryList();

    return {
      historyList,
      loading,
      handleClick,
      renderSkeleton,
    };
  },

  render() {
    return (
      <BasicCard
        class='issues-history'
        title={this.$t('历史 Issue')}
      >
        <div class='issues-history-list'>
          {this.loading ? (
            this.renderSkeleton()
          ) : this.historyList.length ? (
            this.historyList.map(item => (
              <div
                key={item.issue_id}
                class='issues-history-item'
              >
                <div
                  class='item-title'
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
            <EmptyStatus type='empty' />
          )}
        </div>
      </BasicCard>
    );
  },
});
