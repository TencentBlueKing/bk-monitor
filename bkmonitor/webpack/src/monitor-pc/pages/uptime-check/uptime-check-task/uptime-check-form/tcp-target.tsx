import type { CreateElement } from 'vue';

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

import { domain } from 'monitor-common/regex/domain';
import { v4, v6 } from 'monitor-common/regex/ip';
import { copyText } from 'monitor-common/utils';
import MonitorDialog from 'monitor-ui/monitor-dialog';

import MonitorIpSelector from '../../../../components/monitor-ip-selector/monitor-ip-selector';
import { transformMonitorToValue, transformValueToMonitor } from '../../../../components/monitor-ip-selector/utils';
import AddBtn from './add-btn';
import CommonAddDialog from './common-add-dialog';
import CommonCollapse from './common-collapse';
import HttpUrlInput from './http-url-input';

import type { IIpV6Value } from '../../../../components/monitor-ip-selector/typing';

import './tcp-target.scss';

export interface CommonItem {
  id: string;
  name: string;
}
export type DomainSelectType = 'record' | 'type';
interface IDomainItem {
  record: string;
  type: string[];
  value: string;
}
const RecordList: CommonItem[] = [
  {
    id: 'all',
    name: window.i18n.tc('全部'),
  },
  {
    id: 'single',
    name: window.i18n.tc('随机'),
  },
];
const IpTypeList: CommonItem[] = [
  {
    id: 'IPv4',
    name: 'IPv4',
  },
  {
    id: 'IPv6',
    name: 'IPv6',
  },
];
export const OutputFiledsMap = {
  bk_host_innerip: 'ip',
  bk_host_innerip_v6: 'ipv6',
  bk_host_outerip_v6: 'outer_ipv6',
  bk_host_outerip: 'outer_ip',
  ip: 'bk_host_innerip',
  ipv6: 'bk_host_innerip_v6',
  outer_ipv6: 'bk_host_outerip_v6',
  outer_ip: 'bk_host_outerip',
};
export type DnsCheckMode = 'all' | 'single';
export type TargetIpType = 0 | 4 | 6;
export const NodeTypeMap = {
  host_list: 'INSTANCE',
  node_list: 'TOPO',
  service_template_list: 'SERVICE_TEMPLATE',
  set_template_list: 'SET_TEMPLATE',
};
interface ITcpTargetProps {
  defaultValue: {
    dns_check_mode?: DnsCheckMode;
    ip_list?: string[];
    node_list?: any[];
    output_fields?: string[];
    target_ip_type?: TargetIpType;
    url_list?: string[];
  };
}
@Component
export default class TcpTarget extends tsc<ITcpTargetProps> {
  @Prop({ type: Object }) defaultValue: ITcpTargetProps['defaultValue'];
  showAddIp = false;
  showAddDomain = false;
  showAddCmdbIp = false;
  ips: string[] = [];
  defaultIp = '';
  domainRecord = 'all';
  domainIpTypes: string[] = ['IPv4'];
  domains: string[] = [];
  defaultDomain: IDomainItem;
  outputFieldList: string[] = ['ip', 'ipv6'];
  cmdIpValue: IIpV6Value = {};
  defaultOutFields = window.uptimecheck_output_fields?.map(key => OutputFiledsMap[key]);
  hostTableCustomColumnList = [];
  // ip 校验
  showIpValidateTips = false;
  // domain 校验
  showValidateDomainTips = false;
  created() {
    this.defaultDomain = this.getDefaultDomainItem();
    // 自定义输出字段
    this.hostTableCustomColumnList = [
      {
        key: 'outer_ip',
        index: 2,
        width: '100px',
        label: `${this.$t('外网')} IPv4`,
        renderHead: (h: CreateElement) => h('span', `${this.$t('外网')} IPv4`),
        field: 'outer_ip',
        renderCell: (h: CreateElement, row: Record<string, any>) => h('span', row.outer_ip || '--'),
      },
      {
        key: 'outer_ipv6',
        index: 3,
        width: '100px',
        label: `${this.$t('外网')} IPv6`,
        renderHead: (h: CreateElement) => h('span', `${this.$t('外网')} IPv6`),
        field: 'outer_ipv6',
        renderCell: (h: CreateElement, row: Record<string, any>) => h('span', row.outer_ipv6 || '--'),
      },
    ];
  }
  // 初始化值
  @Watch('defaultValue', { immediate: true })
  onValueChange() {
    this.ips = this.defaultValue.ip_list?.slice() || [];
    if (this.defaultValue.url_list?.length) {
      this.domains = this.defaultValue.url_list.slice();
      let types = ['IPv4'];
      if (this.defaultValue.target_ip_type === 0) {
        types = ['IPv4', 'IPv6'];
      } else if (this.defaultValue.target_ip_type === 6) {
        types = ['IPv6'];
      }
      this.domainIpTypes = types;
      this.domainRecord = this.defaultValue.dns_check_mode;
    }
    if (this.defaultValue.node_list?.length) {
      this.outputFieldList = (this.defaultValue.output_fields || window.uptimecheck_output_fields).map(
        key => OutputFiledsMap[key]
      );
      const nodeItem = this.defaultValue.node_list.find(item => item.bk_obj_id);
      if (!nodeItem) {
        this.cmdIpValue = transformMonitorToValue(this.defaultValue.node_list, 'INSTANCE');
      } else if (nodeItem.bk_obj_id === 'SET_TEMPLATE') {
        this.cmdIpValue = transformMonitorToValue(this.defaultValue.node_list, 'SET_TEMPLATE');
      } else if (nodeItem.bk_obj_id === 'SERVICE_TEMPLATE') {
        this.cmdIpValue = transformMonitorToValue(this.defaultValue.node_list, 'SERVICE_TEMPLATE');
      } else {
        this.cmdIpValue = transformMonitorToValue(this.defaultValue.node_list, 'TOPO');
      }
    }
  }
  // 获取组件内 传入 api 数据
  getValue() {
    const data: ITcpTargetProps['defaultValue'] = {};
    const hostList = Object.keys(this.cmdIpValue).reduce((pre, cur) => {
      if (this.cmdIpValue[cur]?.length) {
        let data: any = transformValueToMonitor(this.cmdIpValue, NodeTypeMap[cur]);
        if (data?.length && NodeTypeMap[cur] !== 'INSTANCE') {
          data = data.map(item => ({ ...item, bk_biz_id: this.$store.getters.bizId }));
        } else {
          data = data.map(item => ({ bk_host_id: item.bk_host_id }));
        }
        return data;
      }
      return pre;
    }, []);
    if (hostList?.length) {
      data.node_list = hostList;
      data.output_fields = this.outputFieldList.map(key => OutputFiledsMap[key]);
    }
    if (this.domains.length) {
      data.url_list = this.domains.slice();
      let ipType: TargetIpType = 4;
      if (this.domainIpTypes.length === 2) {
        ipType = 0;
      } else if (this.domainIpTypes.includes('IPv6')) {
        ipType = 6;
      }
      data.target_ip_type = ipType;
      data.dns_check_mode = this.domainRecord as DnsCheckMode;
    }
    if (this.ips.length) {
      data.ip_list = this.ips.slice();
    }
    return data;
  }
  // 默认域名弹窗数据
  getDefaultDomainItem(): IDomainItem {
    return {
      record: this.domainRecord || 'all',
      type: this.domainIpTypes?.slice() || ['IPv4'],
      value: this.domains?.join('\n') || '',
    };
  }
  // 点击添加ip
  handleAddIpShow() {
    this.defaultIp = this.ips.join('\n');
    this.showAddIp = true;
  }
  // 添加ip
  handleAddIp(v: string) {
    const ipList = v.split('\n').filter(Boolean);
    if (ipList.every(v => this.validateIp(v))) {
      this.ips = v.split('\n').filter(Boolean);
      this.showAddIp = false;
      this.showIpValidateTips = false;
      this.$emit('addTarget');
      return;
    }
    this.showIpValidateTips = true;
  }
  // ip show change
  handleShowIpChange(v: boolean) {
    this.showAddIp = v;
    if (!v) {
      this.showIpValidateTips = false;
    }
  }
  // domain show change
  handleShowDomainChange(v: boolean) {
    this.showAddDomain = v;
  }
  handleDomainCancel() {
    this.handleShowDomainChange(false);
  }
  handleDomainConfirm() {
    const list = this.defaultDomain?.value?.split('\n').filter(Boolean);
    if (list?.every(v => this.validateDomain(v))) {
      this.handleShowDomainChange(false);
      this.domains = list;
      this.domainRecord = this.defaultDomain.record;
      this.domainIpTypes = this.defaultDomain.type.slice();
      this.showValidateDomainTips = false;
      this.$emit('addTarget');
      return;
    }
    this.showValidateDomainTips = true;
  }
  handleIpChange(v: IIpV6Value) {
    this.cmdIpValue = v;
    this.$emit('addTarget');
  }
  closeDialog() {
    this.showAddCmdbIp = false;
  }
  handleDeleteIp(i: number) {
    this.ips.splice(i, 1);
  }
  /**
   *
   * @param v ip
   * @param i 索引
   */
  handleIpEdit(v: string, i: number) {
    this.ips.splice(i, 1, v);
  }
  handleDeleteDomain(i: number) {
    this.domains.splice(i, 1);
  }
  handleEditDomain(v: string, i: number) {
    this.domains.splice(i, 1, v);
  }
  handleAddDoamin() {
    this.showAddDomain = true;
    this.defaultDomain = this.getDefaultDomainItem();
    this.showValidateDomainTips = false;
  }
  handleOutputFieldChange(v: string[]) {
    this.outputFieldList = v;
  }
  /**
   * @description:
   * @param {string} id
   * @param {*} type
   * @return {*}
   */
  handleDomainMenuSelect(id: string, type: 'domain' | 'ip') {
    if (id === 'clear-all') {
      if (type === 'domain') {
        this.domains = [];
        return;
      }
      this.ips = [];
    } else if (id === 'copy-all') {
      const text = type === 'ip' ? this.ips.join('\n') : this.domains.join('\n');
      copyText(text);
      this.$bkMessage({
        message: this.$t('复制成功'),
        theme: 'success',
      });
    }
  }
  validateIp(v: string) {
    return !!(v4.is(v) || v6.is(v));
  }
  validateDomain(v: string) {
    return !!domain.is(v);
  }
  createDomainSettings(selectType: DomainSelectType) {
    return (
      <div class='setting-wrap'>
        {`${this.$t(selectType === 'record' ? 'DNS查询模式' : 'IP类型')}：`}
        <div class='setting-text'>
          {selectType === 'record'
            ? RecordList.find(item => item.id === this.domainRecord)?.name
            : IpTypeList.filter(item => this.domainIpTypes.includes(item.id))
                .map(item => item.name)
                .join(',')}
        </div>
      </div>
    );
  }
  createRecordItem() {
    return (
      <div class='domain-item'>
        <span class='domain-item-title'>{this.$t('DNS查询模式')}</span>
        <div class='domain-item-content'>
          <bk-radio-group vModel={this.defaultDomain.record}>
            {RecordList.map(item => (
              <bk-radio
                key={item.id}
                value={item.id}
              >
                {item.name}
              </bk-radio>
            ))}
          </bk-radio-group>
        </div>
      </div>
    );
  }
  createIpTypeItem() {
    return (
      <div class='domain-item'>
        <span class='domain-item-title'>{this.$t('IP类型')}</span>
        <div class='domain-item-content'>
          <bk-checkbox-group vModel={this.defaultDomain.type}>
            {IpTypeList.map(item => (
              <bk-checkbox
                key={item.id}
                value={item.id}
              >
                {item.name}
              </bk-checkbox>
            ))}
          </bk-checkbox-group>
        </div>
      </div>
    );
  }
  createDomainInput() {
    return (
      <div class='domain-item'>
        <span class='domain-item-title'>{this.$t('域名输入')}</span>
        <div class='domain-item-content'>
          <bk-input
            class={`domain-input ${this.showValidateDomainTips ? 'is-error' : ''}`}
            vModel={this.defaultDomain.value}
            placeholder={this.$tc('输入域名说明/校验规则，可通过回车区隔多个域名')}
            type='textarea'
            onFocus={() => {
              this.showValidateDomainTips = false;
            }}
          />
          {this.showValidateDomainTips && <div class='validate-tips'>{this.$t('输入正确的域名')}</div>}
        </div>
      </div>
    );
  }
  render() {
    return (
      <div class='tcp-target'>
        {/* 添加按钮 */}
        <div class='tcp-target-btns'>
          <AddBtn
            text={this.$t('添加静态IP')}
            onClick={this.handleAddIpShow}
          />
          <AddBtn
            text={this.$t('添加域名')}
            onClick={this.handleAddDoamin}
          />
          <AddBtn
            text={this.$t('基于CMDB添加')}
            onClick={() => {
              this.showAddCmdbIp = true;
            }}
          />
        </div>
        <div class='tcp-target-details'>
          {!!this.ips.length && (
            <CommonCollapse onMenuSelect={id => this.handleDomainMenuSelect(id, 'ip')}>
              <span slot='headerLeft'>
                <span style='fontWeight: bold'>【{this.$t('固定IP')}】</span>-{' '}
                <i18n path='共 {0} 个'>
                  <span class='collapse-header-count'>{this.ips.length}</span>
                </i18n>
              </span>
              <template slot='headerRight'>
                <i
                  class='icon-monitor icon-bianji domain-edit'
                  onClick={this.handleAddIpShow}
                />
              </template>
              <div slot='content'>
                {this.ips.map((url, index) => (
                  <HttpUrlInput
                    key={index}
                    errorTips={this.$t('输入正常的IP')}
                    validateFn={this.validateIp}
                    value={url}
                    onChange={v => this.handleIpEdit(v, index)}
                    onDelete={() => this.handleDeleteIp(index)}
                  />
                ))}
              </div>
            </CommonCollapse>
          )}
          {!!this.domains.length && (
            <CommonCollapse onMenuSelect={id => this.handleDomainMenuSelect(id, 'domain')}>
              <template slot='headerLeft'>
                <span style='fontWeight: bold'>【{this.$t('域名')}】</span>-{' '}
                <i18n path='共 {0} 个'>
                  <span class='collapse-header-count'>{this.domains.length}</span>
                </i18n>
                <div class='domain-select'>
                  {this.createDomainSettings('record')}
                  {this.createDomainSettings('type')}
                </div>
              </template>
              <template slot='headerRight'>
                <i
                  class='icon-monitor icon-bianji domain-edit'
                  onClick={this.handleAddDoamin}
                />
              </template>
              <div slot='content'>
                {this.domains.map((domain, index) => (
                  <HttpUrlInput
                    key={index}
                    errorTips={this.$t('输入正确的域名')}
                    validateFn={this.validateDomain}
                    value={domain}
                    onChange={v => this.handleEditDomain(v, index)}
                    onDelete={() => this.handleDeleteDomain(index)}
                  />
                ))}
              </div>
            </CommonCollapse>
          )}
          {/* 添加CMD IP */}
          <MonitorIpSelector
            hostTableRenderColumnList={[
              'ip',
              'ipv6',
              'outer_ip',
              'outer_ipv6',
              'cloudArea',
              'alive',
              'hostName',
              'osName',
              'coludVerdor',
              'osType',
              'hostId',
              'agentId',
            ]}
            defaultOutputFieldList={this.defaultOutFields}
            hostTableCustomColumnList={this.hostTableCustomColumnList}
            mode='dialog'
            outputFieldList={this.outputFieldList}
            outputFieldOptionalHostTableColumn={['ip', 'ipv6', 'outer_ip', 'outer_ipv6']}
            showDialog={this.showAddCmdbIp}
            showView={true}
            value={this.cmdIpValue}
            onChange={this.handleIpChange}
            onCloseDialog={this.closeDialog}
            onOutputFieldChange={this.handleOutputFieldChange}
          />
        </div>
        {/* 添加IP */}
        <CommonAddDialog
          defaultValue={this.defaultIp}
          placeholder={this.$t('输入IP，可通过回车区隔多个IP')}
          show={this.showAddIp}
          showValidateTips={this.showIpValidateTips}
          title={this.$t('添加/编辑IP')}
          validateTips={this.$t('输入正常的IP')}
          onConfirm={this.handleAddIp}
          onFocus={() => {
            this.showIpValidateTips = false;
          }}
          onShowChange={this.handleShowIpChange}
        />
        {/* 添加域名 */}
        <MonitorDialog
          width='488'
          class='common-add-dialog domain-dialog'
          title={this.$t('添加/编辑域名').toString()}
          value={this.showAddDomain}
          onCancel={this.handleDomainCancel}
          onChange={this.handleShowDomainChange}
          onConfirm={this.handleDomainConfirm}
        >
          <div class='domain-header'>
            {this.createRecordItem()}
            {this.createIpTypeItem()}
          </div>
          <div
            style='marginTop: 22px'
            class='domain-content'
          >
            {this.createDomainInput()}
          </div>
        </MonitorDialog>
      </div>
    );
  }
}
