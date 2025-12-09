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

import { type PropType, computed, defineComponent, reactive, shallowRef, watch } from 'vue';

import { type TdPrimaryTableProps, PrimaryTable } from '@blueking/tdesign-ui';
import { Dialog, Loading, Select } from 'bkui-vue';
import dayjs from 'dayjs';
import { subActionDetail } from 'monitor-api/modules/alert_v2';
import { getNoticeWay } from 'monitor-api/modules/notice_group';
import { useI18n } from 'vue-i18n';

import NoticeStatusTable from './notice-status-table';

import type { ActionTableItem } from '../../../typings';

import './alarm-status-dialog.scss';
const NOTICE = 'notice';
export default defineComponent({
  name: 'AlarmStatusDialog',
  props: {
    show: {
      type: Boolean,
      default: false,
    },
    actions: {
      type: Array as PropType<ActionTableItem[]>,
      default: () => [],
    },
    total: {
      type: Number,
      default: 0,
    },
  },
  emits: {
    'update:show': (val: boolean) => typeof val === 'boolean',
  },
  setup(props, { emit }) {
    const { t } = useI18n();
    const localActions = shallowRef<ActionTableItem[]>([]); // 告警列表
    const actionStatusMap = {
      success: window.i18n.t('成功'),
      failure: window.i18n.t('失败'),
    };
    const curHandleData = reactive({
      operator: [],
      type: '',
      check: '',
      operateTargetString: '',
      statusTip: '',
    });
    const loading = shallowRef(false);
    const checkedCount = shallowRef<number | string>(''); // 当前选中的
    const isNotice = shallowRef(false);
    const noticeData = reactive({
      // 通知类型表格数据
      tableData: [],
      tableColumns: [],
      hasColumns: [],
    });

    const list = computed(() => {
      return localActions.value.map((item, index) => ({
        id: item.id,
        name: `${t('第 {n} 次', { n: props.total - index })}（${dayjs
          .tz(item.create_time * 1000)
          .format('YYYY-MM-DD HH:mm:ss')}）`,
      }));
    });

    const curTableTable = computed(() => {
      return [
        {
          operator: curHandleData.operator, // 负责人
          check: curHandleData.check, // 执行状态
          operateTargetString: curHandleData.operateTargetString, // 执行对象
          type: curHandleData.type, // 套餐类型
          statusTip: curHandleData.statusTip, // 失败是展示tips
        },
      ];
    });

    watch(
      () => props.actions,
      val => {
        // 获取处理记录列表（用于缓存数据）
        if (val.length) {
          checkedCount.value = val[val.length - 1].id;
          localActions.value = structuredClone(val);
          getCurHandleData();
        }
      }
    );

    const handleSelected = id => {
      const temp = localActions.value.find(item => item.id === id);
      if (temp.action_plugin_type === NOTICE) {
        // 如果是通知数据需显示通知状态明细（流转记录的查看明细）
        getNoticeStatusData(id);
        return;
      }
      getCurHandleData();
      isNotice.value = false;
    };

    // 获取通知状态明细
    const getNoticeStatusData = async actionId => {
      loading.value = true;
      if (!noticeData.tableColumns.length) {
        noticeData.tableColumns = await getNoticeWay()
          .then(res =>
            res.map(item => ({
              label: item.label,
              prop: item.type,
            }))
          )
          .catch(() => []);
      }
      await subActionDetail({ parent_action_id: actionId })
        .then(data => {
          noticeData.tableData = Object.keys(data || {}).map(key => {
            const temp: any = { target: key };
            for (const subKey of Object.keys(data[key] || {})) {
              if (!noticeData.hasColumns.includes(subKey)) {
                noticeData.hasColumns.push(subKey);
              }
              const statusData = data?.[key]?.[subKey] || {};
              temp[subKey] = {
                label: statusData?.status_display || '',
                tip: statusData?.status_tips || '',
              };
            }
            return temp;
          });
        })
        .finally(() => {
          loading.value = false;
        });
      isNotice.value = true;
    };

    const getCurHandleData = () => {
      // 获取当前字段
      const temp = localActions.value.find(item => item.id === checkedCount.value);
      curHandleData.operator = temp?.operator; // 负责人
      curHandleData.type = temp?.action_plugin.name; // 套餐类型
      curHandleData.check = temp?.status; // 执行状态   operate_target_string
      curHandleData.operateTargetString = temp?.operate_target_string; // 执行对象
      curHandleData.statusTip = temp?.status_tips || '';
      if (temp.action_plugin_type === NOTICE) {
        getNoticeStatusData(temp.id);
      } else {
        isNotice.value = false;
      }
    };

    const tableColumns = shallowRef<TdPrimaryTableProps['columns']>([
      {
        colKey: 'type',
        title: t('套餐类型'),
      },
      {
        colKey: 'operateTargetString',
        title: t('执行对象'),
      },
      {
        colKey: 'operator',
        title: t('负责人'),
        cell: (_h, { row }) => {
          return row.operator?.map?.((id, index) => [
            <bk-user-display-name
              key={id}
              user-id={id}
            />,
            index < row?.operator?.length - 1 ? ';' : '',
          ]);
        },
      },
      {
        colKey: 'check',
        title: t('执行状态'),
        cell: (_h, { row }) => {
          return (
            <span
              class={['action-status', row.check]}
              v-bk-tooltips={{
                content: row.statusTip,
                disabled: row.check !== 'failure',
                width: 200,
                allowHtml: false,
                html: false,
                allowHTML: false,
              }}
            >
              {actionStatusMap[row.check]}
            </span>
          );
        },
      },
    ]);
    const getTableComponent = () => {
      return (
        <PrimaryTable
          class='table-wrap'
          bordered={false}
          columns={tableColumns.value}
          data={curTableTable.value}
        />
      );
    };

    const handleShowChange = (val: boolean) => {
      emit('update:show', val);
    };

    return {
      localActions,
      curHandleData,
      loading,
      checkedCount,
      isNotice,
      noticeData,
      list,
      handleShowChange,
      handleSelected,
      getTableComponent,
    };
  },
  render() {
    return (
      <Dialog
        width={800}
        class='alarm-status-dialog-wrap'
        header-position='left'
        isShow={this.show}
        mask-close={true}
        title={this.$t('告警状态详情')}
        onUpdate:isShow={this.handleShowChange}
      >
        <Loading loading={this.loading}>
          <div class='handle-status-content'>
            <div class='handle-row'>
              <div class='handel-label'>{this.$t('处理次数')}</div>
              <Select
                class='count-select'
                v-model={this.checkedCount}
                clearable={false}
                displayKey='name'
                idKey='id'
                list={this.list}
                onChange={v => this.handleSelected(v)}
              />
            </div>
            <div class='handle-label mb16'>{this.$t('处理明细')}</div>
            {this.isNotice ? (
              <NoticeStatusTable
                hasColumns={this.noticeData.hasColumns}
                tableColumns={this.noticeData.tableColumns}
                tableData={this.noticeData.tableData}
              />
            ) : (
              this.getTableComponent()
            )}
          </div>
        </Loading>
      </Dialog>
    );
  },
});
