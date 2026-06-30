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
import { type PropType, defineComponent, shallowRef, watch } from 'vue';

import EmptyStatus from 'trace/components/empty-status/empty-status';
import useRequestAbort from 'trace/hooks/useRequestAbort';
import tapdLogo from 'trace/static/img/issues/tapd-logo.png';
import { useI18n } from 'vue-i18n';

import { getTapdRelations } from '../../../services/relation-tapd';
import BasicCard from '../basic-card/basic-card';

import type { TapdRelationItem } from '../../../services/relation-tapd';
import type { IssueDetail } from '../../../typing';

import './issues-relation-tapd.scss';

export default defineComponent({
  name: 'IssuesRelationTapd',
  props: {
    detail: {
      type: Object as PropType<IssueDetail>,
      default: () => ({}),
    },
  },

  setup(props) {
    const { t } = useI18n();

    const list = shallowRef<TapdRelationItem[]>([]);
    const loading = shallowRef(false);

    const { run: getTapdListApi, signal } = useRequestAbort<TapdRelationItem[]>(getTapdRelations);

    /** 获取 TAPD 关联列表 */
    const getTapdList = async () => {
      if (!props.detail?.id || !props.detail?.bk_biz_id) return;
      loading.value = true;
      const res = await getTapdListApi({
        bk_biz_id: props.detail.bk_biz_id,
        issue_id: props.detail.id,
      });
      if (signal?.aborted) return;
      list.value = Array.isArray(res) ? res : [];
      loading.value = false;
    };

    /** 渲染骨架屏 */
    const renderSkeleton = () =>
      ['first', 'second'].map(key => (
        <div
          key={key}
          class='tapd-item skeleton-element tapd-item-skeleton'
        />
      ));

    watch(
      () => props.detail?.id,
      id => {
        if (id) getTapdList();
      },
      { immediate: true }
    );

    return {
      t,
      list,
      loading,
      renderSkeleton,
    };
  },

  render() {
    const count = this.list.length;

    return (
      <BasicCard
        class='issues-detail-issues-relation-tapd'
        title={`${this.t('关联单据')} (${count})`}
      >
        {this.loading && this.renderSkeleton()}
        {!this.loading && count === 0 && <EmptyStatus />}

        {!this.loading &&
          this.list.map(item => (
            <div
              key={item.relation_id}
              class='tapd-item'
            >
              <div class='tapd-item-left'>
                <img
                  alt=''
                  src={tapdLogo}
                />
              </div>
              <div class='tapd-item-right'>
                <div class='tapd-item-right-top'>
                  <div class='tapd-id'>#TAPD-{item.tapd_id}</div>
                  <div class='tapd-name'>{item.tapd_title}</div>
                </div>
                <div class='tapd-item-right-bottom'>
                  <span class='link-mode'>
                    {`${item.link_mode === 'link' ? this.t('关联已有单据') : this.t('新建单据')} · `}
                    {item.sync_status ? undefined : this.t('状态不同步')}
                  </span>
                  {item.sync_status ? (
                    <>
                      <span class='icon-monitor icon-change' />
                      <span class='sync-status'>{this.t('状态同步')}</span>
                    </>
                  ) : undefined}
                </div>
              </div>
            </div>
          ))}
      </BasicCard>
    );
  },
});
