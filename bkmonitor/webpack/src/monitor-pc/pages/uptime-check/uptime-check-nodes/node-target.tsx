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
import { Component, Prop, Watch } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import MonitorIpSelector from '../../../components/monitor-ip-selector/monitor-ip-selector';
import AddBtn from '../uptime-check-task/uptime-check-form/add-btn';

import type { IHost, IIpV6Value } from '../../../components/monitor-ip-selector/typing';

import './node-target.scss';

interface INodeTargetProps {
  disableHostMethod: IHost;
  target: IIpV6Value;
}
@Component
export default class NodeTarget extends tsc<INodeTargetProps> {
  @Prop() disableHostMethod: (v: IHost) => void;
  @Prop() target: IIpV6Value;
  showAddNodeTarget = false;
  ipValue: IIpV6Value = {};
  @Watch('target', { immediate: true })
  onTargetChange() {
    this.ipValue = {
      host_list: this.target.host_list,
    };
  }
  addNodeTarget() {
    this.showAddNodeTarget = true;
  }
  handleIpChange(v: IIpV6Value) {
    this.ipValue = v;
    this.$emit('change', v);
  }
  closeDialog() {
    this.showAddNodeTarget = false;
  }
  render() {
    return (
      <div class='node-target'>
        <AddBtn
          text={this.$t('添加目标').toString()}
          onClick={this.addNodeTarget}
        />
        <MonitorIpSelector
          disableHostMethod={this.disableHostMethod}
          keepHostFieldOutput={true}
          mode='dialog'
          panelList={['staticTopo']}
          showDialog={this.showAddNodeTarget}
          showView={true}
          singleHostSelect={true}
          value={this.ipValue}
          onChange={this.handleIpChange}
          onCloseDialog={this.closeDialog}
        />
      </div>
    );
  }
}
