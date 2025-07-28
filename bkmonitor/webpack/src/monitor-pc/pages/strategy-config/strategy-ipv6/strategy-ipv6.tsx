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

import { bulkEditStrategy, getTargetDetail } from 'monitor-api/modules/strategies';
import { deepClone } from 'monitor-common/utils';

import MonitorIpSelector from '../../../components/monitor-ip-selector/monitor-ip-selector';
import {
  getPanelListByObjectType,
  transformMonitorToValue,
  transformValueToMonitor,
} from '../../../components/monitor-ip-selector/utils';

import type {
  CoutIntanceName,
  IIpV6Value,
  INodeType,
  TargetObjectType,
} from '../../../components/monitor-ip-selector/typing';

interface IStrategyIpv6Events {
  onChange: { nodeType: INodeType; objectType: TargetObjectType; value: IIpV6Value };
  onCloseDialog: boolean;
  onSave: boolean;
}
interface IStrategyIpv6Props {
  bizId?: number | string;
  checkedNodes?: any[];
  nodeType?: INodeType;
  objectType?: TargetObjectType;
  showDialog: boolean;
  strategyIds?: string[];
}
const HostTargetFieldMap = {
  TOPO: 'host_topo_node',
  INSTANCE: 'ip',
  SERVICE_TEMPLATE: 'host_service_template',
  SET_TEMPLATE: 'host_set_template',
};
const ServiceTargetFieldMap = {
  TOPO: 'service_topo_node',
  SERVICE_TEMPLATE: 'service_service_template',
  SET_TEMPLATE: 'service_set_template',
};
@Component
export default class StrategyIpv6 extends tsc<IStrategyIpv6Props, IStrategyIpv6Events> {
  // 是否显示弹窗
  @Prop({ default: false, type: Boolean }) showDialog: boolean;
  // 策略id
  @Prop({ type: Array, default: () => [] }) strategyIds: string[];
  @Prop({ type: Array, default: () => [] }) checkedNodes: any[];

  @Prop({ type: String }) objectType: TargetObjectType;
  @Prop({ type: String }) nodeType: INodeType;
  @Prop({ type: [String, Number] }) bizId: number | string;
  ipCheckValue: IIpV6Value = {};
  panelList: string[] = [];
  ipNodeType: INodeType = 'TOPO';
  ipObjectType: TargetObjectType = null;
  loading = false;
  initialized = false;
  originValue: IIpV6Value = undefined;
  countInstanceType: CoutIntanceName = 'host';
  get hasStrategy() {
    return this.strategyIds?.length > 0;
  }
  // created() {
  //   if (this.objectType) {
  //     this.panelList = getPanelListByObjectType(this.objectType);
  //   }
  // }
  get serviceInstanceColumnList() {
    if (this.countInstanceType === 'service_instance') {
      return [
        {
          renderHead: h => h('span', this.$t('服务实例数')),
          renderCell: (h, row) => h('span', row.node.count || '--'),
        },
      ];
    }
    return undefined;
  }
  @Watch('showDialog', { immediate: true })
  async onShowDialogChange(v: boolean) {
    if (v) {
      this.initialized = false;
      if (this.hasStrategy) {
        // 策略增删目标
        await this.getStrategyConfigTargets();
      } else {
        // 新增策略
        this.ipNodeType = this.nodeType;
        this.ipObjectType = this.objectType;
      }
      if (this.checkedNodes?.length) {
        this.ipCheckValue = transformMonitorToValue(this.checkedNodes, this.ipNodeType) as IIpV6Value;
        this.originValue = deepClone(this.ipCheckValue);
      }
      this.countInstanceType = this.ipObjectType === 'SERVICE' ? 'service_instance' : 'host';
      this.panelList = getPanelListByObjectType(this.ipObjectType);
      setTimeout(() => (this.initialized = true), 100);
    }
  }
  @Emit('closeDialog')
  closeDialog(v: boolean) {
    this.ipCheckValue = {};
    this.originValue = {};
    this.panelList = [];
    return v;
  }
  async getStrategyConfigTargets() {
    this.loading = false;
    const [strategyId] = this.strategyIds;
    const data = await getTargetDetail({ strategy_ids: [strategyId] }).catch(() => []);
    if (typeof strategyId !== 'undefined') {
      const { target_detail, node_type, instance_type } = data[strategyId];
      // 单策略增删目标
      if (this.strategyIds.length === 1) {
        this.ipCheckValue = transformMonitorToValue(target_detail, node_type) as any;
        this.originValue = deepClone(this.ipCheckValue);
      }
      this.ipNodeType = node_type;
      this.ipObjectType = instance_type;
    }
    this.loading = false;
  }
  async handleIpChange(v: IIpV6Value) {
    this.ipCheckValue = v;
    if (this.hasStrategy) {
      const data = transformValueToMonitor(v, this.ipNodeType);
      const nodeType = !data.length ? this.nodeType : this.ipNodeType;
      const success = await bulkEditStrategy({
        id_list: this.strategyIds,
        edit_data: {
          target: data.length
            ? [
                [
                  {
                    field:
                      this.ipObjectType === 'HOST' ? HostTargetFieldMap[nodeType] : ServiceTargetFieldMap[nodeType],
                    method: 'eq',
                    value: data,
                  },
                ],
              ]
            : [],
        },
      })
        .then(() => true)
        .catch(() => false);
      success && this.$bkMessage({ theme: 'success', message: this.$t('修改成功') });
      this.$emit('save', success);
    } else {
      this.$emit('change', { value: v, nodeType: this.ipNodeType, objectType: this.ipObjectType });
    }
  }
  render() {
    return (
      <div v-bkloading={{ isLoading: this.loading }}>
        {this.panelList.length > 0 && (
          <MonitorIpSelector
            class={this.countInstanceType === 'service_instance' ? 'service-instance-selector' : ''}
            countInstanceType={this.countInstanceType}
            mode={'dialog'}
            originalValue={this.originValue}
            panelList={this.panelList}
            showDialog={this.initialized && this.showDialog}
            showViewDiff={!!this.originValue}
            value={this.ipCheckValue}
            onChange={this.handleIpChange}
            onCloseDialog={this.closeDialog}
            onTargetTypeChange={v => (this.ipNodeType = v)}
          />
        )}
      </div>
    );
  }
}
