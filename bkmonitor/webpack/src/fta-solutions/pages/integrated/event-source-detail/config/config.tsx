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

import { getEventPluginToken } from '../../../../../monitor-api/modules/event_plugin';
import { copyText } from '../../../../../monitor-common/utils/utils';
import Viewer from '../../../../../monitor-ui/markdown-editor/viewer';
import RulesViewer from '../rules-viewer/rules-viewer';
import { EPluginType, IAlertConfigTable, INormalizationTable, IPushConfigData, TPluginType } from '../types';

import PullForm from './pull-form';

import './config.scss';

const { i18n } = window;

interface IConfig {
  id: string;
  httpData?: any;
  type: TPluginType;
  normalizationTable?: INormalizationTable[];
  alertConfigTable?: IAlertConfigTable[];
  pushConfigData?: IPushConfigData;
  tutorialMd: string;
  isShow: boolean;
  paramsSchema?: any[];
  instanceId?: number;
  isInstalled?: boolean;
}

interface ITableColumnsItem {
  label: string;
  prop: string;
  key?: string;
  width?: number;
  formatter?: Function;
}
/**
 * 事件源详情配置页
 */
@Component
export default class Config extends tsc<IConfig> {
  @Prop({ default: '', type: String }) readonly id: string;
  @Prop({ default: null, type: Object }) readonly httpData;
  @Prop({ default: '', type: String }) readonly type: TPluginType;
  @Prop({ default: () => [], type: Array }) readonly normalizationTable: INormalizationTable[];
  @Prop({ default: () => [], type: Array }) readonly alertConfigTable: IAlertConfigTable[];
  @Prop({ default: () => ({}), type: Object }) readonly pushConfigData: IPushConfigData;
  @Prop({ default: '', type: String }) readonly tutorialMd: string;
  @Prop({ default: false, type: Boolean }) readonly isShow: boolean;
  @Prop({ default: () => [], type: Array }) readonly paramsSchema: any[];
  @Prop({ default: 0, type: Number }) instanceId: number;
  @Prop({ default: false, type: Boolean }) isInstalled: boolean;

  isLoading = false;
  pushKeyLoading = false;
  isHidePushKey = true;
  pushKey = '';

  // 标准化事件-字段映射表格列数据
  fieldMapTableColumnlist: ITableColumnsItem[] = [
    {
      label: i18n.tc('字段'),
      prop: 'display_name',
      key: 'field',
      width: 180,
      formatter: row => (row.field ? `${row.display_name} (${row.field})` : row.display_name)
    },
    { label: i18n.tc('类型'), prop: 'type', key: 'type', width: 120 },
    { label: i18n.tc('说明'), prop: 'description', key: 'desc', formatter: row => row.description || '--' },
    { label: i18n.tc('源映字段规则'), prop: 'expr', key: 'rules', formatter: row => row.expr || '--' }
  ];
  // 告警名称列表
  noticeNameTableColumnlist: ITableColumnsItem[] = [
    { label: i18n.tc('告警名称'), prop: 'name', key: 'name', width: 200 },
    // { label: '', prop: 'type', key: 'type', width: 100 },
    { label: i18n.tc('匹配内容'), prop: 'rules', key: 'content' }
    // { label: i18n.tc('匹配模式'), prop: 'match', key: 'match' }
  ];

  get ingesterHost() {
    return this.pushConfigData.pushUrl || `${this.pushConfigData.ingesterHost}/event/${this.pushConfigData.pluginId}/`;
  }

  get isShowPullConfig() {
    return !!this.paramsSchema.length && !!this.instanceId;
  }

  @Watch('isShow')
  isShowChange(v) {
    if (v) {
      this.isHidePushKey = true;
      this.pushKey = '';
    }
  }

  handleCopy(text) {
    copyText(text, msg => {
      this.$bkMessage({
        message: msg,
        theme: 'error'
      });
      return;
    });
    this.$bkMessage({
      message: this.$t('复制成功'),
      theme: 'success'
    });
  }

  async getSecureKey() {
    if (this.pushKeyLoading) return;
    this.pushKeyLoading = true;
    const res = await getEventPluginToken(this.instanceId)
      .catch(() => {})
      .finally(() => (this.pushKeyLoading = false));
    this.isHidePushKey = false;
    this.pushKey = res.token;
  }

  protected render() {
    const typeColumnScopedSlots = {
      default: ({ row }) => {
        if (!row.type) return undefined;
        return <span class='type-label'>{row.type}</span>;
      }
    };
    const rulesColumnScopedSlots = {
      default: ({ row: { rules } }) => <RulesViewer value={rules}></RulesViewer>
    };
    const scopedSlots = key => {
      if (key === 'type') return typeColumnScopedSlots;
      if (key === 'content') return rulesColumnScopedSlots;
      return null;
    };
    return (
      <div
        class='detail-config-wrap'
        v-bkloading={{ isLoading: this.isLoading }}
      >
        {(this.type === EPluginType.pull ? this.isShowPullConfig : true) && (
          <div class='content-title-h1'>{this.$t('配置')}</div>
        )}
        <div class='config-handle-wrap'>
          {
            // email 类型
            this.type === EPluginType.email ? (
              <table class='info-table'>
                <tbody>
                  <tr>
                    <td
                      class='label right'
                      style='width: 80px'
                    >
                      {this.$t('用户名')}
                    </td>
                    <td class='value'>Lucky2021</td>
                    <td class='label right'>{this.$t('IMAP地址')}</td>
                    <td class='value'>imap.qq.com</td>
                    <td class='label right'>{this.$t('IMAP端口')}</td>
                    <td class='value'>993</td>
                  </tr>
                  <tr>
                    <td
                      class='label right'
                      style='width: 80px'
                    >
                      {this.$t('使用SSL')}
                    </td>
                    <td class='value'>是</td>
                    <td class='label right'>{this.$t('拉取频率')}</td>
                    <td class='value'>30分钟</td>
                    <td class='label right'></td>
                    <td class='value'></td>
                  </tr>
                </tbody>
              </table>
            ) : undefined
          }
          {
            // pull 类型
            this.isShowPullConfig ? (
              <PullForm
                formData={this.paramsSchema}
                instanceId={this.instanceId}
              ></PullForm>
            ) : undefined
          }
          {
            // push 类型
            this.type === EPluginType.push ? (
              <div class='push-config-wrap'>
                <div class='push-config-row'>
                  <span class='push-label'>Token</span>
                  <span class='push-content'>
                    <span class={['text', { 'hide-key': this.isHidePushKey }]}>
                      {!this.isHidePushKey && this.pushKey}
                    </span>
                    {this.isHidePushKey && this.isInstalled && (
                      // eslint-disable-next-line @typescript-eslint/no-misused-promises
                      <span
                        class={['btn', { 'btn-loading': this.pushKeyLoading }]}
                        onClick={this.getSecureKey}
                      >
                        {this.pushKeyLoading && <span class='loading'></span>}
                        {this.$t('点击查看')}
                      </span>
                    )}
                  </span>
                </div>
                <div class='push-config-row'>
                  <span class='push-label'>Push URL</span>
                  <span class='push-content'>
                    <span class='text'>{this.ingesterHost}</span>
                    <i
                      class='icon-monitor icon-mc-copy'
                      onClick={() => this.handleCopy(this.ingesterHost)}
                    ></i>
                  </span>
                </div>
              </div>
            ) : undefined
          }
          <div class={['content-title-h1', { mt32: this.type === EPluginType.pull ? this.isShowPullConfig : true }]}>
            {this.$t('接入指引')}
          </div>
          {this.tutorialMd ? (
            <Viewer
              class='md-viewer'
              value={this.tutorialMd}
              flowchartStyle={true}
            ></Viewer>
          ) : (
            <div style='margin-bottom: 16px;'>{this.$t('暂无')}</div>
          )}
          <div class='data-table-wrap'>
            <div class='content-title-h1'>{this.$t('标准化事件-字段映射')}</div>
            <div class='data-table-desc'>
              <span class='label'>{this.$t('数据源格式')}</span>
              <span class='value'>{this.pushConfigData.sourceFormat}</span>
            </div>
            <bk-table
              key={`${this.normalizationTable.length || 0}${this.id}normalization`}
              class='table-wrap'
              data={this.normalizationTable}
              border={false}
              outer-border={false}
            >
              {this.fieldMapTableColumnlist.map(item => (
                <bk-table-column
                  key={item.key}
                  label={item.label}
                  prop={item.prop}
                  width={item.width}
                  formatter={item.formatter}
                  scopedSlots={item.key === 'type' ? typeColumnScopedSlots : null}
                ></bk-table-column>
              ))}
              {/* <bk-table-column label={this.$t('操作')} width="180" scopedSlots={oprateScopedSlots}/> */}
            </bk-table>
            <div class='content-title-h1'>
              {this.$t('告警名称列表')}
              <span class='desc'>
                {this.$t('告警名称通过字段映射可以自动获取到，也可以手动新增。手动新增优先级高于自动获取。')}
              </span>
            </div>
            <bk-table
              key={`${this.alertConfigTable.length || 0}${this.id}alertConfig`}
              class='table-wrap'
              data={this.alertConfigTable}
              outer-border={false}
            >
              {this.noticeNameTableColumnlist.map(item => (
                <bk-table-column
                  key={item.key}
                  label={item.label}
                  prop={item.prop}
                  width={item.width}
                  scopedSlots={scopedSlots(item.key)}
                ></bk-table-column>
              ))}
            </bk-table>
          </div>
        </div>
      </div>
    );
  }
}
