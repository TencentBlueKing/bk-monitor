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
import { Component, Prop } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import './ip-status-tips.scss';

interface IIpStatusTips {
  hostId: number;
  ignoreMonitoring: boolean;
  isShielding: boolean;
}

/**
 * @description: 不监控、不告警提示数据 优先级：不监控 > 不告警
 * @param {boolean} ignoreMonitoring
 * @param {boolean} isShielding
 * @return {*}
 */
export const handleIpStatusData = (ignoreMonitoring: boolean, isShielding: boolean): { icon?: string; id?: string } => {
  const data = {
    icon: ignoreMonitoring ? 'icon-celvepingbi' : isShielding ? 'icon-menu-shield' : '',
    id: ignoreMonitoring ? '#ignore-monitoring' : isShielding ? '#is-shielding' : '',
  };
  return ignoreMonitoring || isShielding ? data : {};
};

@Component
export default class IpStatusTips extends tsc<IIpStatusTips> {
  /**
   * true 为不监控
   */
  @Prop({ default: false, type: Boolean }) ignoreMonitoring: boolean;
  /**
   * true 为告警
   */
  @Prop({ default: false, type: Boolean }) isShielding: boolean;
  /**
   * 主机id
   */
  @Prop({ default: null, type: Number }) hostId: number;

  /**
   * @description: 跳转cmdb
   * @param {*}
   * @return {*}
   */
  handleToCMDB() {
    const { cmdbUrl, bizId } = this.$store.getters;
    const url = `${cmdbUrl}#/business/${bizId}/index/host/${this.hostId}`;
    window.open(url);
  }

  render() {
    return (
      <div class='host-status-icon-tips-wrap'>
        {this.ignoreMonitoring ? (
          <i18n
            class='host-status-icon-tips'
            path='不监控，就是不进行告警策略判断。可在{0}进行设置。'
          >
            <span
              class='link'
              onClick={this.handleToCMDB}
            >
              CMDB
            </span>
          </i18n>
        ) : this.isShielding ? (
          <i18n
            class='host-status-icon-tips'
            path='不告警，会生成告警但不进行告警通知等处理。可在{0}进行设置'
          >
            <span
              class='link'
              onClick={this.handleToCMDB}
            >
              CMDB
            </span>
          </i18n>
        ) : undefined}
      </div>
    );
  }
}
