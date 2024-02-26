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
import { Component, Emit, Model, Prop, Ref, Watch } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';
import { random } from 'monitor-common/utils/utils';

import TopoSelector from '../../../components/ip-selector/business/topo-selector-new.vue';
// import { handleSetTargetDesc } from './common';
import { CheckedData, HostInfo, HostValueItem, NotificationType, targetFieldMap } from '../types';

import './notification.scss';

const targetResult = {
  message: '',
  messageCount: 0,
  subMessage: '',
  subMessageCount: 0
};
interface NotificationProps {
  isEdit: boolean;
  hostInfo?: HostInfo;
  onChange?: void;
  onShowTargetDetail?: void;
}
@Component
export default class Notification extends tsc<NotificationProps> {
  @Model('change', { type: Array }) value: [HostValueItem[]];
  @Ref('targetContainer') targetContainerRef: HTMLDivElement;
  @Prop({ default: false, type: Boolean }) isEdit: boolean;
  @Prop({ default: () => targetResult, type: Object }) hostInfo: HostInfo;
  showTopoSelector = false;
  ipSelectKey = random(10);
  targetContainerHeight = 0;
  targetList: any = [];
  checkedData: CheckedData = {
    type: 'TOPO',
    data: []
  };

  @Emit('change')
  valueChange(val: [HostValueItem[]]) {
    return val;
  }

  @Watch('value', { immediate: true })
  handleValueChange(data: [HostValueItem[]]) {
    if (data?.[0]?.length) {
      this.checkedData.type = Object.keys(targetFieldMap).find(
        key => targetFieldMap[key] === data?.[0]?.[0]?.field
      ) as NotificationType;
      this.checkedData.data = data?.[0]?.[0]?.value || [];
      // this.hostInfo = handleSetTargetDesc(this.checkedData.data, this.checkedData.type);
    }
  }

  /**
   * 打开拓扑选择弹窗
   */
  handleShowSelect() {
    this.showTopoSelector = true;
    this.$nextTick(() => {
      this.targetContainerHeight = this.targetContainerRef?.clientHeight || 0;
    });
  }

  handleTargetCancel() {
    this.showTopoSelector = false;
  }

  handleTopoCheckedChange(value: CheckedData) {
    this.checkedData = value;
  }

  /**
   * 确认操作
   */
  handleConfirm() {
    const value =
      this.checkedData.type === 'INSTANCE'
        ? this.checkedData.data.map(item => ({
            ip: item.ip,
            bk_cloud_id: item.bk_cloud_id,
            bk_supplier_id: item.bk_supplier_id
          }))
        : this.checkedData.data.map(item => ({
            bk_inst_id: item.bk_inst_id,
            bk_obj_id: item.bk_obj_id
          }));
    // 监控目标格式转换
    const targets: [HostValueItem[]] = [
      [
        {
          field: targetFieldMap[this.checkedData.type],
          method: 'eq',
          value
        }
      ]
    ];

    this.valueChange(targets);
    this.showTopoSelector = false;
  }

  /**
   *  节点主机数目
   */
  renderHostInfo(count: number, message: string) {
    return count > 0 ? (
      <i18n path={message}>
        <span class='host-count'> {count} </span>
      </i18n>
    ) : undefined;
  }

  handleShowTargetDetail() {
    if (!this.isEdit) {
      this.$emit('showTargetDetail');
    }
  }

  render() {
    const { messageCount, message, subMessage, subMessageCount } = this.hostInfo || targetResult;

    return (
      <span class='ai-settings-notification-component'>
        {
          // eslint-disable-next-line no-nested-ternary
          this.value?.[0]?.[0]?.value?.length > 0 ? (
            <span
              class={['target-overview', { overview: !this.isEdit }]}
              onClick={this.handleShowTargetDetail}
            >
              <i class='icon-monitor icon-mc-tv notification-tv'></i>
              {this.renderHostInfo(messageCount, message) || '--'}
              {subMessageCount > 0 ? <span>({this.renderHostInfo(subMessageCount, subMessage)})</span> : null}
              {this.isEdit && (
                <i
                  class='icon-monitor icon-mc-edit mc-edit'
                  onClick={this.handleShowSelect}
                />
              )}
            </span>
          ) : this.isEdit ? (
            <span
              class='add-tag'
              onClick={this.handleShowSelect}
            >
              <span class='icon-monitor icon-mc-add'></span>
              <span class='add-tag-text'>{this.$t('关闭对象')}</span>
            </span>
          ) : (
            <span class='target-overview no-target'>
              <i class='icon-monitor icon-mc-tv notification-tv'></i>
              <span>--</span>
            </span>
          )
        }
        <bk-dialog
          width={1000}
          class='ai-settings-notification-component-dialog'
          value={this.showTopoSelector}
          render-directive='if'
          header-position='left'
          onChange={v => (this.showTopoSelector = v)}
          confirm-fn={this.handleConfirm}
          show-footer={this.isEdit}
          onCancel={this.handleTargetCancel}
        >
          <div slot='header'>
            {this.$t('添加对象')}
            <span class='icon-monitor icon-tishi'></span>
            <span class='sub-title-text'>{this.$t('被选对象将会关闭页面通知')}</span>
          </div>
          <div
            style='height: 653px'
            ref='targetContainer'
          >
            <TopoSelector
              height='653px'
              tree-height={this.targetContainerHeight}
              key={this.ipSelectKey}
              class='mt15'
              targetNodeType={this.checkedData.type}
              checked-data={this.checkedData.data || []}
              on-check-change={this.handleTopoCheckedChange}
            />
          </div>
        </bk-dialog>
      </span>
    );
  }
}
