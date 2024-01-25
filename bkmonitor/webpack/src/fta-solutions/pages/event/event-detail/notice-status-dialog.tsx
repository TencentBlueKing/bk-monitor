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

import { subActionDetail } from '../../../../monitor-api/modules/alert';
import { getNoticeWay } from '../../../../monitor-api/modules/notice_group';

import NoticeStatusTable from './notice-status-table';

import './notice-status-dialog.scss';

interface INoticeStatusDialog {
  value?: boolean;
  actionId: string;
}
interface IEvent {
  onShowChange?: boolean;
}

@Component
export default class NoticeStatusDialog extends tsc<INoticeStatusDialog, IEvent> {
  @Prop({ default: '', type: String }) actionId: string;
  @Model('show-change', { type: Boolean }) readonly value;

  loading = false;
  tableData = [];
  tableClounms = [];
  classMap = {
    失败: 'failed',
    成功: 'success'
  };
  hasColumns = [];
  @Emit('show-change')
  emitShowChange(v: boolean) {
    return v;
  }

  @Watch('value')
  valueChange(isShow: boolean) {
    if (isShow) this.getNoticeStatusData();
  }

  // 关闭弹窗
  handleClose(v: boolean) {
    if (v) return;
    this.emitShowChange(v);
  }

  async getNoticeStatusData() {
    this.loading = true;
    if (!this.tableClounms.length) {
      this.tableClounms = await getNoticeWay()
        .then(res =>
          res.map(item => ({
            label: item.label,
            prop: item.type
          }))
        )
        .catch(() => []);
    }
    await subActionDetail({ parent_action_id: this.actionId })
      .then(data => {
        this.tableData = Object.keys(data || {}).map(key => {
          const temp: any = { target: key };
          Object.keys(data[key] || {}).forEach(subKey => {
            if (!this.hasColumns.includes(subKey)) {
              this.hasColumns.push(subKey);
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
  }

  render() {
    return (
      <bk-dialog
        ext-cls='notice-status-dialog-wrap'
        value={this.value}
        mask-close={true}
        header-position='left'
        width={800}
        title={this.$t('通知状态')}
        {...{ on: { 'value-change': this.handleClose } }}
      >
        <div
          class='notice-status-content'
          v-bkloading={{ isLoading: this.loading }}
        >
          <NoticeStatusTable
            tableData={this.tableData}
            tableColumns={this.tableClounms}
            hasColumns={this.hasColumns}
          ></NoticeStatusTable>
        </div>
      </bk-dialog>
    );
  }
}
