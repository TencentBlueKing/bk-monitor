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
import { Component, Emit, Prop, Watch } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import { getBusinessTargetDetail } from 'monitor-api/modules/commons';
import { deepClone } from 'monitor-common/utils';

import MonitorIpSelector from '../../../components/monitor-ip-selector/monitor-ip-selector';
import { transformMonitorToValue, transformValueToMonitor } from '../../../components/monitor-ip-selector/utils';
import { type HostValueItem, targetFieldMap } from '../types';
import { handleSetTargetDesc } from './common';

import type { CoutIntanceName, IIpV6Value, INodeType } from '../../../components/monitor-ip-selector/typing';

import './ip-selector.scss';

interface IProps {
  value?: HostValueItem[][];
  onChange?: (v: HostValueItem[][]) => void;
}

@Component
export default class IpSelector extends tsc<IProps> {
  @Prop({ type: Array, default: () => [] }) value: HostValueItem[][];

  loading = false;
  /* 对象列表 */
  targetList = [];
  /* 是否显示弹窗 */
  showDialog = false;
  /* 当前选中的IP */
  ipCheckValue: IIpV6Value = {};
  /* 当前实例类型 */
  countInstanceType: CoutIntanceName = 'host';
  /* 当前选择的节点类型 */
  ipNodeType: INodeType = 'TOPO';
  /* 上一份数据 用于对比 */
  originValue: IIpV6Value = undefined;
  /* 对象概览 */
  desc = {
    messageCount: 0,
    subMessageCount: 0,
    message: '',
    subMessage: '',
  };
  watchFlag = false;

  @Watch('value', { immediate: true })
  handleWacthValue(v: HostValueItem[][]) {
    if (!this.watchFlag && v.length > 0) {
      this.handleSetTargetDesc(v, data => {
        this.ipCheckValue = transformMonitorToValue(data.target_detail, data.node_type);
        this.ipNodeType = data.node_type;
        this.targetList = data.target_detail;
      });
      this.watchFlag = true;
    }
  }

  /**
   * @description 点击确定按钮
   * @param v
   * @returns
   */
  @Emit('change')
  handleIpChange(v: IIpV6Value) {
    this.ipCheckValue = v;
    this.targetList = transformValueToMonitor(v, this.ipNodeType);
    const targets: HostValueItem[][] = [
      [
        {
          field: targetFieldMap[this.ipNodeType],
          method: 'eq',
          value: this.targetList,
        },
      ],
    ];
    this.handleSetTargetDesc(targets);
    this.showDialog = false;
    return targets;
  }

  /**
   * @description 获取对象概览
   * @param targets
   * @param callback
   */
  async handleSetTargetDesc(targets: HostValueItem[][], callback?: (data) => void) {
    this.loading = true;
    const data = targets[0][0].value.length
      ? await getBusinessTargetDetail({
          target: targets,
        }).catch(() => null)
      : null;
    this.countInstanceType = data?.instance_type || 'host';
    if (data) {
      const info = handleSetTargetDesc(
        data.target_detail,
        data.node_type,
        data.instance_type,
        data.node_count,
        data.instance_count
      );
      this.desc = info;
      callback?.(data);
    } else {
      this.desc = {
        messageCount: 0,
        subMessageCount: 0,
        message: '',
        subMessage: '',
      };
    }
    this.loading = false;
  }

  /**
   * @description 弹出弹窗
   */
  handleShowSelect() {
    this.ipCheckValue = transformMonitorToValue(this.targetList, this.ipNodeType);
    this.originValue = deepClone(this.ipCheckValue);
    this.showDialog = true;
  }

  /**
   * @description 关闭弹窗
   * @param v
   */
  closeDialog(v: boolean) {
    this.ipCheckValue = {};
    this.originValue = {};
    this.showDialog = v;
  }

  renderHostInfo(count: number, message: string) {
    return count > 0 ? (
      <i18n path={message}>
        <span class='host-count'> {count} </span>
      </i18n>
    ) : undefined;
  }

  render() {
    return (
      <div class='ai-settings-ip-selector'>
        {this.targetList.length > 0 ? (
          <span class='target-overview'>
            <i class='icon-monitor icon-mc-tv notification-tv' />
            {this.renderHostInfo(this.desc.messageCount, this.desc.message) || '--'}
            {this.desc.subMessageCount > 0 ? (
              <span>({this.renderHostInfo(this.desc.subMessageCount, this.desc.subMessage)})</span>
            ) : null}
            <i
              class='icon-monitor icon-bianji'
              onClick={this.handleShowSelect}
            />
          </span>
        ) : (
          <span
            class='add-tag'
            onClick={this.handleShowSelect}
          >
            <span class='icon-monitor icon-mc-plus-fill' />
            <span class='add-tag-text'>{this.$t('关闭对象')}</span>
          </span>
        )}

        {this.loading && <div class='skeleton-element' />}
        <MonitorIpSelector
          countInstanceType={this.countInstanceType}
          mode={'dialog'}
          originalValue={this.originValue}
          showDialog={this.showDialog}
          showViewDiff={!!this.originValue}
          value={this.ipCheckValue}
          onChange={this.handleIpChange}
          onCloseDialog={this.closeDialog}
          onTargetTypeChange={v => (this.ipNodeType = v)}
        />
      </div>
    );
  }
}
