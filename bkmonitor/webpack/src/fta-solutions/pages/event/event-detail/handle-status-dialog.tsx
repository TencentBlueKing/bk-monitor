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
import { Component, Emit, Model, Prop, Watch } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';
import dayjs from 'dayjs';

import { subActionDetail } from '../../../../monitor-api/modules/alert';
import { getNoticeWay } from '../../../../monitor-api/modules/notice_group';
import { deepClone } from '../../../../monitor-common/utils/utils';

import NoticeStatusTable from './notice-status-table';

import './handle-status-dialog.scss';

const NOTICE = 'notice';
interface IHandleStatusDialog {
  value?: boolean;
  actions?: any[];
  alertId?: string;
}
interface IEvent {
  onShowChange?: boolean;
}

// 事件详情 | 处理记录详情
export type TType = 'eventDetail' | 'handleDetail';

@Component
export default class HandleStatusDialog extends tsc<IHandleStatusDialog, IEvent> {
  @Prop({ type: Array, default: () => [] }) actions: any[];

  @Model('show-change', { type: Boolean }) readonly value;

  localActions: any[] = []; // 告警列表
  actionStatusMap = {
    success: window.i18n.t('成功'),
    failure: window.i18n.t('失败')
  };
  curHandleData = {
    operator: [],
    type: '',
    check: '',
    operateTargetString: '',
    statusTip: ''
  };
  loading = false;
  checkedCount = 0; // 当前选中的
  isNotice = false;
  noticeData = {
    // 通知类型表格数据
    tableData: [],
    tableColumns: [],
    hasColumns: []
  };

  get list() {
    return this.localActions
      .map((item, index) => ({
        id: item.id,
        name: `${this.$t('第 {n} 次', { n: index + 1 })}（${dayjs
          .tz(item.create_time * 1000)
          .format('YYYY-MM-DD HH:mm:ss')}）`
      }))
      .reverse();
  }

  // 表格数据
  get curTableTable() {
    return [
      {
        operator: this.curHandleData.operator, // 负责人
        check: this.curHandleData.check, // 执行状态
        operateTargetString: this.curHandleData.operateTargetString, // 执行对象
        type: this.curHandleData.type, // 套餐类型
        statusTip: this.curHandleData.statusTip // 失败是展示tips
      }
    ];
  }

  @Watch('actions')
  actionsChange(actions) {
    // 获取处理记录列表（用于缓存数据）
    if (actions.length) {
      this.checkedCount = actions[actions.length - 1].id;
      this.localActions = deepClone(actions);
      this.getCurHandleData();
    }
  }

  @Emit('show-change')
  emitShowChange(v: boolean) {
    return v;
  }

  handleSelected(id) {
    const temp = this.localActions.find(item => item.id === id);
    if (temp.action_plugin_type === NOTICE) {
      // 如果是通知数据需显示通知状态明细（流转记录的查看明细）
      this.getNoticeStatusData(id);
      return;
    }
    this.getCurHandleData();
    this.isNotice = false;
  }

  // 获取通知状态明细
  async getNoticeStatusData(actionId) {
    this.loading = true;
    if (!this.noticeData.tableColumns.length) {
      this.noticeData.tableColumns = await getNoticeWay()
        .then(res =>
          res.map(item => ({
            label: item.label,
            prop: item.type
          }))
        )
        .catch(() => []);
    }
    await subActionDetail({ parent_action_id: actionId })
      .then(data => {
        this.noticeData.tableData = Object.keys(data || {}).map(key => {
          const temp: any = { target: key };
          Object.keys(data[key] || {}).forEach(subKey => {
            if (!this.noticeData.hasColumns.includes(subKey)) {
              this.noticeData.hasColumns.push(subKey);
            }
            const statusData = data?.[key]?.[subKey] || {};
            temp[subKey] = {
              label: statusData?.status_display || '',
              tip: statusData?.status_tips || ''
            };
          });
          return temp;
        });
      })
      .finally(() => (this.loading = false));
    this.isNotice = true;
  }

  getCurHandleData() {
    // 获取当前字段
    const temp = this.localActions.find(item => item.id === this.checkedCount);
    this.curHandleData = {
      operator: temp?.operator, // 负责人
      type: temp?.action_plugin.name, // 套餐类型
      check: temp?.status, // 执行状态   operate_target_string
      operateTargetString: temp?.operate_target_string, // 执行对象
      statusTip: temp?.status_tips || ''
    };
    if (temp.action_plugin_type === NOTICE) {
      this.getNoticeStatusData(temp.id);
    } else {
      this.isNotice = false;
    }
  }

  // 关闭弹窗
  handleClose(v: boolean) {
    if (v) return;
    this.emitShowChange(v);
  }

  // table
  getTableComponent() {
    const typeSlot = {
      default: ({ row }) => row.type
    };
    const operateTargetStringSlot = {
      default: ({ row }) => row.operateTargetString
    };
    const operatorSlot = {
      default: ({ row }) => row.operator?.join(';')
    };
    const checkSlot = {
      default: ({ row }) => (
        <span
          class={['action-status', row.check]}
          v-bk-tooltips={{
            content: row.statusTip,
            disabled: row.check !== 'failure',
            width: 200,
            allowHtml: false,
            html: false,
            allowHTML: false
          }}
        >
          {this.actionStatusMap[row.check]}
        </span>
      )
    };
    return (
      <bk-table
        data={this.curTableTable}
        class='table-wrap'
        border={false}
        outer-border={false}
      >
        <bk-table-column
          label={this.$t('套餐类型')}
          scopedSlots={typeSlot}
        ></bk-table-column>
        <bk-table-column
          label={this.$t('执行对象')}
          scopedSlots={operateTargetStringSlot}
        ></bk-table-column>
        <bk-table-column
          label={this.$t('负责人')}
          scopedSlots={operatorSlot}
        ></bk-table-column>
        <bk-table-column
          label={this.$t('执行状态')}
          scopedSlots={checkSlot}
        ></bk-table-column>
      </bk-table>
    );
  }

  render() {
    return (
      <bk-dialog
        ext-cls='handle-status-dialog-wrap'
        value={this.value}
        mask-close={true}
        header-position='left'
        width={800}
        title={this.$t('处理状态详情')}
        {...{ on: { 'value-change': this.handleClose } }}
      >
        <div
          class='handle-status-content'
          v-bkloading={{ isLoading: this.loading }}
        >
          <div class='handle-row'>
            <div class='handel-label'>{this.$t('处理次数')}</div>
            <bk-select
              class='count-select'
              clearable={false}
              v-model={this.checkedCount}
              on-selected={v => this.handleSelected(v)}
            >
              {this.list.map((item, index) => (
                <bk-option
                  key={index}
                  id={item.id}
                  name={item.name}
                ></bk-option>
              ))}
            </bk-select>
          </div>
          <div class='handle-label mb16'>{this.$t('处理明细')}</div>
          {this.isNotice ? (
            <NoticeStatusTable
              tableData={this.noticeData.tableData}
              tableColumns={this.noticeData.tableColumns}
              hasColumns={this.noticeData.hasColumns}
            ></NoticeStatusTable>
          ) : (
            this.getTableComponent()
          )}
        </div>
      </bk-dialog>
    );
  }
}
