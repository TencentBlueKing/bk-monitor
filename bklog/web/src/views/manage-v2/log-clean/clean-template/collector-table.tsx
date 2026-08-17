/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 *
 * Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
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

import { computed, defineComponent, type PropType } from 'vue';

import BklogPopover from '@/components/bklog-popover';
import useLocale from '@/hooks/use-locale';
import useStore from '@/hooks/use-store';
import { useRouter } from 'vue-router/composables';

import './collector-table.scss';
import type { CleanTemplateCollector, RelatedIndexSet } from './use-template-collectors';

export interface CleanTemplateCollectorTableRow extends CleanTemplateCollector {
  sync_result_message?: string;
  sync_result_status?: 'FAILED' | 'SUCCESS';
}

export default defineComponent({
  name: 'CleanTemplateCollectorTable',
  props: {
    data: {
      type: Array as PropType<CleanTemplateCollectorTableRow[]>,
      default: () => [],
    },
    keyword: {
      type: String,
      default: '',
    },
    showSyncResult: {
      type: Boolean,
      default: false,
    },
  },
  setup(props) {
    const { t } = useLocale();
    const store = useStore();
    const router = useRouter();

    const currentBizName = computed(() => store.state.space?.name || store.state.space?.space_name || '--');
    const tableData = computed(() => {
      const searchValue = props.keyword.trim().toLowerCase();
      if (!searchValue) {
        return props.data;
      }
      return props.data.filter((item) => {
        return `${item.collector_config_id}`.includes(searchValue)
          || item.collector_config_name?.toLowerCase().includes(searchValue);
      });
    });
    const relatedIndexSetFilters = computed(() => {
      const filterMap = new Map<number, string>();
      props.data.forEach((collector) => {
        (collector.related_index_set_list || []).forEach((indexSet) => {
          if (!filterMap.has(indexSet.index_set_id)) {
            filterMap.set(indexSet.index_set_id, indexSet.index_set_name);
          }
        });
      });
      return Array.from(filterMap, ([value, text]) => ({ text, value }));
    });

    const handleCollectionClick = (row: CleanTemplateCollectorTableRow) => {
      const routeData = router.resolve({
        name: 'manage-collection',
        params: { collectorId: `${row.collector_config_id}` },
        query: {
          bizId: `${row.bk_biz_id}`,
          spaceUid: store.state.spaceUid,
          typeKey: row.log_access_type,
        },
      });
      window.open(routeData.href, '_blank', 'noopener,noreferrer');
    };
    const handleIndexSetClick = (indexSetId: number) => {
      const routeData = router.resolve({
        name: 'collection-item-list',
        query: {
          indexSetId: `${indexSetId}`,
          spaceUid: store.state.spaceUid,
        },
      });
      window.open(routeData.href, '_blank', 'noopener,noreferrer');
    };
    const filterRelatedIndexSet = (indexSetId: number, row: CleanTemplateCollectorTableRow) => (
      (row.related_index_set_list || []).some(item => item.index_set_id === indexSetId)
    );
    const getSyncStatusText = (row: CleanTemplateCollectorTableRow) => {
      if (!row.sync_result_status) {
        return '--';
      }
      if (row.sync_result_status === 'SUCCESS') {
        return t('成功');
      }
      return `${t('失败')}：${row.sync_result_message}`;
    };
    const handleIndexSetPopoverShow = (instance: { reference: Element }) => {
      const trigger = instance.reference.querySelector<HTMLElement>('.related-index-sets');
      if (!trigger || trigger.scrollWidth <= trigger.clientWidth) {
        return false;
      }
    };
    const renderIndexSetLink = (indexSet: RelatedIndexSet) => (
      <span
        class='related-index-set'
        on-click={() => handleIndexSetClick(indexSet.index_set_id)}
      >
        <span class='index-set-name'>{indexSet.index_set_name || '--'}</span>
        <i class='bklog-icon bklog-jump jump-icon' />
      </span>
    );
    const renderRelatedIndexSets = (row: CleanTemplateCollectorTableRow) => {
      const indexSetList = row.related_index_set_list || [];
      if (!indexSetList.length) {
        return <span>--</span>;
      }
      return (
        <BklogPopover
          contentClass='related-index-set-popover'
          options={{
            appendTo: document.body,
            onShow: handleIndexSetPopoverShow,
            placement: 'bottom-start',
            theme: 'bklog-basic-light',
            zIndex: 9999,
          }}
          trigger='hover'
          {...{
            scopedSlots: {
              content: () => (
                <div class='related-index-set-popover-list'>
                  {indexSetList.map(indexSet => (
                    <div
                      key={indexSet.index_set_id}
                      class='related-index-set-popover-item'
                    >
                      {renderIndexSetLink(indexSet)}
                    </div>
                  ))}
                </div>
              ),
            },
          }}
        >
          <div class='related-index-sets'>
            {indexSetList.map(indexSet => (
              <span key={indexSet.index_set_id}>{renderIndexSetLink(indexSet)}</span>
            ))}
          </div>
        </BklogPopover>
      );
    };

    return () => (
      <bk-table
        class='clean-template-collector-table'
        data={tableData.value}
        outer-border={true}
      >
        <bk-table-column
          label={t('采集项 ID')}
          min-width='100'
          prop='collector_config_id'
          resizable={false}
          sortable
        />
        <bk-table-column
          label={t('采集项名称')}
          min-width='160'
          resizable={false}
          scopedSlots={{
            default: ({ row }: { row: CleanTemplateCollectorTableRow }) => (
              <span
                class='collector-name'
                on-click={() => handleCollectionClick(row)}
              >
                {row.collector_config_name || '--'}<i class='bklog-icon bklog-jump jump-icon' />
              </span>
            ),
          }}
        />
        <bk-table-column
          column-key='related_index_set_list'
          filter-method={filterRelatedIndexSet}
          filter-multiple={false}
          filters={relatedIndexSetFilters.value}
          label={t('关联索引集')}
          min-width='160'
          prop='related_index_set_list'
          resizable={false}
          scopedSlots={{
            default: ({ row }: { row: CleanTemplateCollectorTableRow }) => renderRelatedIndexSets(row),
          }}
        />
        {props.showSyncResult ? (
          <bk-table-column
            label={t('同步情况')}
            min-width='150'
            resizable={false}
            scopedSlots={{
              default: ({ row }: { row: CleanTemplateCollectorTableRow }) => (
                <span class={[
                  row.sync_result_status && 'sync-status',
                  row.sync_result_status && (row.sync_result_status === 'FAILED' ? 'is-failed' : 'is-success'),
                ]}>
                  {getSyncStatusText(row)}
                </span>
              ),
            }}
          />
        ) : (
          <bk-table-column
            label={t('所属项目')}
            min-width='150'
            resizable={false}
            scopedSlots={{
              default: () => <span>{currentBizName.value}</span>,
            }}
          />
        )}
      </bk-table>
    );
  },
});
