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

import { defineComponent, onScopeDispose, shallowRef, watch } from 'vue';

import { type TdPrimaryTableProps, PrimaryTable } from '@blueking/tdesign-ui';
import { Dialog } from 'bkui-vue';
import { subActionDetail } from 'monitor-api/modules/alert_v2';
import { getNoticeWay } from 'monitor-api/modules/notice_group';
import { DetailTableSkeleton, DetailLoadStatus } from '@/pages/alarm-center/common-detail/detail-loading';
import { useI18n } from 'vue-i18n';

import './notice-status-dialog.scss';

interface ITableData {
  label?: string;
  target?: string;
  tip?: string;
}

const ClassMap = {
  失败: 'failed',
  成功: 'success',
};

export default defineComponent({
  name: 'NoticeStatusDialog',
  props: {
    show: {
      type: Boolean,
      default: false,
    },
    actionId: {
      type: String,
      default: '',
    },
    alarmBizId: {
      type: Number,
      default: null,
    },
  },
  emits: {
    showChange: (_val: boolean) => true,
  },
  setup(props, { emit }) {
    const { t } = useI18n();

    const handleShowChange = (val: boolean) => {
      emit('showChange', val);
    };
    const tableColumns = shallowRef<TdPrimaryTableProps['columns']>([]);
    const tableData = shallowRef<ITableData[]>([]);
    const hasColumns = shallowRef<string[]>([]);

    const loading = shallowRef(false);
    let requestId = 0;
    const error = shallowRef(false);
    onScopeDispose(() => { ++requestId; });
    const getNoticeStatusData = async () => {
      const current = ++requestId;
      error.value = false;
      try {
      loading.value = true;
      if (!tableColumns.value.length) {
        const columns = await getNoticeWay({ bk_biz_id: props.alarmBizId })
          .then(res =>
            res.map(item => ({
              colKey: item.type,
              title: item.label,
              resizable: false,
              cell: (_h, { row }) => {
                return !Object.keys(ClassMap).includes(row?.[item.type]?.label) ? (
                  <span
                    v-bk-tooltips={{
                      content: <div style='max-width: 200px; word-break: break-word;'>{row[item.type]?.tip}</div>,
                      placements: ['top'],
                      disabled: !row[item.type]?.tip,
                    }}
                  >
                    {row?.[item.type]?.label || '--'}
                  </span>
                ) : (
                  <span
                    class={`notice-${ClassMap[row[item.type].label]}`}
                    v-bk-tooltips={{
                      content: <div style='max-width: 200px;word-break: break-word;'>{row[item.type]?.tip}</div>,
                      placements: ['top'],
                      disabled: !row[item.type]?.tip,
                    }}
                  />
                );
              },
            }))
          )
          ;
        if (current !== requestId) return;
        tableColumns.value = [
          {
            colKey: 'target',
            title: t('通知方式'),
            resizable: false,
            cell: (_h, { row }) => {
              return row.target ? <bk-user-display-name user-id={row.target} /> : '--';
            },
          },
          ...columns,
        ];
      }
      await subActionDetail({ parent_action_id: props.actionId, bk_biz_id: props.alarmBizId })
        .then(data => {
          if (current !== requestId) return;
          tableData.value = Object.keys(data || {}).map(key => {
            const temp = { target: key };
            for (const subKey of Object.keys(data[key] || {})) {
              if (!hasColumns.value.includes(subKey)) {
                hasColumns.value = [...hasColumns.value, subKey];
              }
              const statusData = data?.[key]?.[subKey] || {};
              temp[subKey] = {
                label: statusData?.status_display || '',
                tip: Array.isArray(statusData?.status_tips)
                  ? statusData?.status_tips?.[0] || ''
                  : statusData?.status_tips || '',
              };
            }

            return temp;
          });
        })
        ;
      } catch {
        if (current === requestId) error.value = true;
      } finally {
        if (current === requestId) loading.value = false;
      }
    };

    watch(
      () => [props.show, props.actionId, props.alarmBizId],
      () => {
        ++requestId;
        tableColumns.value = [];
        hasColumns.value = [];
        if (props.show) {
          getNoticeStatusData();
        } else {
          loading.value = false;
          tableData.value = [];
          hasColumns.value = [];
        }
      },
      { immediate: true }
    );

    return {
      error, retry: getNoticeStatusData,
      tableColumns,
      tableData,
      hasColumns,
      loading,
      t,
      handleShowChange,
    };
  },
  render() {
    return (
      <Dialog
        width={800}
        headerAlign='left'
        isShow={this.show}
        quickClose={true}
        title={this.t('通知状态')}
        onUpdate:isShow={this.handleShowChange}
      >
        <div class='notice-status-dialog-content'>
          {this.loading ? (
            <DetailTableSkeleton columns={this.tableColumns.length ? this.tableColumns : [{ colKey: 'target', title: this.t('通知方式') }]} />
          ) : this.error ? <DetailLoadStatus error onRetry={this.retry} /> : (
            <PrimaryTable
              columns={this.tableColumns.filter(
                item => this.hasColumns.includes(item.colKey) || item.colKey === 'target'
              )}
              bordered={false}
              data={this.tableData}
            />
          )}
        </div>
      </Dialog>
    );
  },
});
