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

import MonitorIpSelector from '../../../../components/monitor-ip-selector/monitor-ip-selector';

import type { IIpV6Value } from '../../../../components/monitor-ip-selector/typing';

interface IAlarmShieldIpv6Props {
  checkedValue?: IIpV6Value;
  originCheckedValue?: IIpV6Value;
  shieldDimension: string;
  showDialog: boolean;
  showViewDiff?: boolean;
}
export const Ipv6FieldMap = {
  ip: 'host_list',
  node: 'node_list',
  instance: 'service_instance_list',
};
export const ShieldDimension2NodeType = {
  ip: 'INSTANCE',
  node: 'TOPO',
  instance: 'SERVICE_INSTANCE',
};
export const ShieldDetailTargetFieldMap = {
  ip: 'bk_target_ip',
  node: 'bk_topo_node',
  instance: 'service_instance_id',
};
@Component
export default class AlarmShieldIpv6 extends tsc<IAlarmShieldIpv6Props> {
  // 是否显示弹窗
  @Prop({ default: false, type: Boolean }) showDialog: boolean;
  @Prop({ default: false, type: Boolean }) showViewDiff: boolean;
  @Prop({ default: '', type: String }) shieldDimension: string;
  @Prop({ default: () => ({}), type: Object }) checkedValue: IIpV6Value;
  @Prop({ default: () => ({}), type: Object }) originCheckedValue: IIpV6Value;
  panelList: string[] = [];
  ipCheckValue: IIpV6Value = {};
  initialized = false;
  @Watch('shieldDimension', { immediate: true })
  async handleShieldDimensionChange(v: string) {
    this.panelList = [];
    this.initialized = false;
    await this.$nextTick();

    this.ipCheckValue = {
      [Ipv6FieldMap[this.shieldDimension]]: this.checkedValue?.[Ipv6FieldMap[this.shieldDimension]],
    };
    this.panelList = this.getPanelListByDimension(v);
    setTimeout(() => (this.initialized = true), 100);
  }
  async handleIpChange(v: IIpV6Value) {
    this.$emit('change', { value: v });
  }
  @Emit('closeDialog')
  closeDialog(v: boolean) {
    return v;
  }
  getPanelListByDimension(v: string) {
    if (v === 'instance') return ['serviceInstance'];
    if (v === 'ip') return ['staticTopo', 'manualInput'];
    if (v === 'node') return ['dynamicTopo'];
    return [];
  }
  render() {
    return (
      <div>
        {this.panelList.length > 0 && (
          <MonitorIpSelector
            mode={'dialog'}
            originalValue={this.originCheckedValue}
            panelList={this.panelList}
            showDialog={this.initialized && this.showDialog}
            showView={true}
            showViewDiff={this.showViewDiff}
            value={this.ipCheckValue}
            onChange={this.handleIpChange}
            onCloseDialog={this.closeDialog}
          />
        )}
      </div>
    );
  }
}
