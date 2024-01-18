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

import './plugin-selector.scss';

export const LOG_PLUGIN_ID = 'LOG_PLUGIN_ID'; // 只做为前端标识使用
export const PROCESS_PLUGIN_ID = 'default_process';
/* 插件类型名 */
const pluginTypeMap = {
  Exporter: 'Exporter',
  Script: 'Script',
  JMX: 'JMX',
  DataDog: 'DataDog',
  Pushgateway: 'BK-Pull',
  Log: 'Log',
  Process: 'Process',
  SNMP_Trap: 'SNMP Trap',
  SNMP: 'SNMP'
};

const colorMap = {
  Exporter: '#B6CAEC',
  Script: '#E3D5C2',
  JMX: '#A1CEAC',
  DataDog: '#F0D3A5',
  'Built-In': '#E3D5C2',
  Pushgateway: '#B6CAEC',
  SNMP: '#B6CAEC',
  SNMP_Trap: '#B6CAEC',
  Log: '#B6CAEC',
  Process: '#B6CAEC'
};
/* snmptrap类型插件(固定) */
const snmpTrapPluginList = [
  {
    plugin_id: 'snmp_v1',
    plugin_display_name: 'SNMP Trap V1',
    plugin_type: 'SNMP_Trap',
    logo: ''
  },
  {
    plugin_id: 'snmp_v2c',
    plugin_display_name: 'SNMP Trap V2c',
    plugin_type: 'SNMP_Trap',
    logo: ''
  },
  {
    plugin_id: 'snmp_v3',
    plugin_display_name: 'SNMP Trap V3',
    plugin_type: 'SNMP_Trap',
    logo: ''
  }
];
/* log类型插件(实际无此插件仅供展示) */
const logPluginList = [
  {
    plugin_id: LOG_PLUGIN_ID,
    plugin_display_name: window.i18n.tc('日志关键字采集'),
    plugin_type: 'Log',
    logo: ''
  }
];
/* 进程类型插件 */
const processPluginList = [
  {
    plugin_id: PROCESS_PLUGIN_ID,
    plugin_display_name: window.i18n.tc('进程采集插件'),
    plugin_type: 'Process',
    logo: ''
  }
];

export interface IPluginItem {
  logo: string;
  plugin_display_name: string; // 插件名
  plugin_id: string; // 插件id
  plugin_type: string; // 插件类型
  label_info?: {
    // 采集对象
    first_label: string;
    first_label_name: string;
    second_label: string;
    second_label_name: string;
  };
}

interface IProps {
  list?: IPluginItem[];
  id?: string;
  disabled?: boolean;
}
interface IEvents {
  onChange?: IPluginItem;
}

@Component
export default class PluginSelector extends tsc<IProps, IEvents> {
  @Prop({ type: Array, default: () => [] }) list: IPluginItem[];
  @Prop({ type: String, default: '' }) id: string;
  @Prop({ type: Boolean, default: false }) disabled: boolean;

  pluginId = '';
  realList: IPluginItem[] = [];

  created() {
    this.realList = [...this.list, ...snmpTrapPluginList, ...logPluginList, ...processPluginList];
    if (this.id) {
      this.pluginId = this.id;
    }
  }

  @Watch('id')
  handleIdChange(val) {
    if (val === this.pluginId) return;
    this.pluginId = val;
  }

  @Emit('change')
  handleSelector(pluginId) {
    const info = this.realList.find(item => item.plugin_id === pluginId);
    return info;
  }

  handleAddPlugin() {
    this.$router.push({
      name: 'plugin-add'
    });
  }

  render() {
    return (
      <div class='collector-plugin-selector-component'>
        <bk-select
          class='select-big'
          value={this.pluginId}
          ext-popover-cls='collector-plugin-selector-component-options'
          searchable
          clearable={false}
          disabled={this.disabled}
          on-selected={value => this.handleSelector(value)}
        >
          {this.realList.map(item => (
            <bk-option
              key={item.plugin_id}
              id={item.plugin_id}
              name={`${item.plugin_display_name || item.plugin_id}${
                ![LOG_PLUGIN_ID, PROCESS_PLUGIN_ID].includes(item.plugin_id) ? ` (${item.plugin_id})` : ''
              } - ${pluginTypeMap[item.plugin_type]}`}
            >
              <span class='plugin-option'>
                <div
                  class='plugin-logo'
                  style={{
                    'background-image': item.logo ? `url(data:image/gif;base64,${item.logo})` : 'none',
                    'background-color': item.logo ? '' : colorMap[item.plugin_type]
                  }}
                >
                  {item.logo ? '' : item.plugin_display_name.slice(0, 1).toLocaleUpperCase()}
                </div>
                <span class='name'>{item.plugin_display_name || item.plugin_id}</span>
                <span class='subtitle'>
                  {![LOG_PLUGIN_ID, PROCESS_PLUGIN_ID].includes(item.plugin_id) ? ` (${item.plugin_id})` : ''}
                </span>
                <span class='type'>{pluginTypeMap[item.plugin_type]}</span>
              </span>
            </bk-option>
          ))}
          <div
            slot='extension'
            onClick={() => this.handleAddPlugin()}
          >
            <div class='bottom-add'>
              <i
                class='bk-icon icon-plus-circle'
                style={{ marginRight: '5px' }}
              ></i>
              {window.i18n.tc('新建插件')}
            </div>
          </div>
        </bk-select>
      </div>
    );
  }
}
