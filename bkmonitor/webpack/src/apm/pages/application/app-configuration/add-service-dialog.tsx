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

import {
  customServiceConfig,
  customServiceDataSource,
  customServiceMatchList
} from '../../../../monitor-api/modules/apm_meta';

import { ICustomServiceInfo } from './type';

interface IProps {
  value?: boolean;
  appName: string;
  serviceInfo?: ICustomServiceInfo | null;
}

interface IEvents {
  onRefresh: void;
}

@Component
export default class AddServiceDialog extends tsc<IProps, IEvents> {
  @Model('change', { type: Boolean, default: false }) value: IProps['value'];
  @Prop({ default: '', type: String }) appName: IProps['appName'];
  @Prop({ default: null, required: false }) serviceInfo: ICustomServiceInfo | null;

  @Ref() domainDropdown: HTMLElement;
  @Ref() uriDropdown: HTMLElement;
  @Ref() addServiceForm: any;

  isLoading = false;
  isDebugging = false;
  isDomainDropdownShow = false;
  isUriDropdownShow = false;
  urlListLoading = false;
  debugged = false;
  /** 远程服务类型 */
  serviceTypeList = [{ id: 'http', name: 'HTTP' }];
  /** 操作 */
  operatorMaps = {
    eq: window.i18n.tc('相等'),
    nq: window.i18n.tc('不相等'),
    reg: window.i18n.tc('正则')
  };
  formData = {
    type: '', // 远程服务类型
    name: '', // 服务名
    match_type: 'manual', // manual | auto
    regex: '',
    rules: {
      host: { operator: 'eq', value: '' },
      path: { operator: 'eq', value: '' },
      params: [{ name: '', operator: '', value: '' }]
    }
  };
  rules = {
    type: [
      {
        required: true,
        message: window.i18n.tc('必填项'),
        trigger: 'blur'
      }
    ],
    name: [
      {
        required: true,
        message: window.i18n.tc('必填项'),
        trigger: 'blur'
      }
    ],
    regex: [
      {
        required: true,
        message: window.i18n.tc('必填项'),
        trigger: 'blur'
      }
    ]
  };
  /** 调试结果列表 */
  debuggerResult: string[] | null = null;
  /** uri源 */
  urlResource = '';

  @Emit('change')
  handleShowChange(val?: boolean) {
    return val ?? !this.value;
  }

  @Watch('value')
  handleValueChange(val: boolean) {
    if (val) {
      if (this.serviceInfo) {
        // serviceInfo不为null 则说明当前弹窗是编辑
        this.setFormData();
      }
    } else {
      this.formData = {
        type: '',
        name: '',
        regex: '',
        match_type: 'manual',
        rules: {
          host: { operator: 'eq', value: '' },
          path: { operator: 'eq', value: '' },
          params: [{ name: '', operator: '', value: '' }]
        }
      };
      this.addServiceForm.clearError();
      this.debugged = false;
      this.debuggerResult = [];
    }
  }

  created() {
    this.getUriSourceData();
  }

  /**
   * @desc 获取uri源数据
   */
  async getUriSourceData() {
    this.urlListLoading = true;
    const data = await customServiceDataSource({
      app_name: this.appName,
      type: 'http' // 暂时只有一种类型
    }).catch(() => []);
    this.urlResource = data.join('\n');
    this.urlListLoading = false;
  }
  /**
   * @desc 切换匹配模式
   * @param { string } val
   */
  handleChangeMatchType(val) {
    this.addServiceForm.clearError();
    this.formData.match_type = val;
  }
  handleDropdownShow(option: string, isShow: boolean) {
    if (option === 'domain') {
      this.isDomainDropdownShow = isShow;
      return;
    }

    this.isUriDropdownShow = isShow;
  }
  triggerHandler(elem: string, val: string) {
    (this.$refs[elem] as any).hide();
    if (elem === 'domainDropdown') {
      this.formData.rules.host.operator = val;
    } else {
      this.formData.rules.path.operator = val;
    }
  }
  /** 增/删参数 */
  handleChangeParam(handle: string, index: number) {
    if (handle === 'add') {
      this.formData.rules.params.push({ name: '', operator: '', value: '' });
      return;
    }

    if (this.formData.rules.params.length === 1) {
      return;
    }

    this.formData.rules.params.splice(index, 1);
  }
  /**
   * @desc 编辑弹窗数据回填
   */
  setFormData() {
    const { name, type, match_type: matchType, rule } = this.serviceInfo;
    Object.assign(this.formData, {
      name,
      type,
      match_type: matchType,
      rules: Object.assign(this.formData.rules, rule)
    });
    if (matchType === 'auto') {
      this.formData.regex = rule.regex;
    }
  }
  /**
   * @desc 获取请求参数
   */
  getParams() {
    const { name, type, match_type: matchType, ...rest } = this.formData;
    const payload: any = {
      app_name: this.appName,
      type,
      match_type: matchType,
      rule: {}
    };

    if (matchType === 'auto') {
      // 自动匹配
      const { regex } = rest;
      payload.rule.regex = regex;
    } else {
      // 手动匹配
      payload.name = name; // 服务名称

      const { host, path, params } = rest.rules;
      if (host.value) payload.rule.host = host;
      if (path.value) payload.rule.path = path;

      // 参数name、operator、value均不为空
      const list = [];
      params.forEach(val => {
        if (Object.keys(val).every(item => val[item].trim?.() !== '')) {
          list.push(val);
        }
      });
      if (list.length) payload.rule.params = list;
    }

    if (!Object.keys(payload.rule).length) {
      this.$bkMessage({
        message: this.$t('至少填写一项过滤规则'),
        theme: 'error'
      });
      return false;
    }

    return payload;
  }
  /** 提交保存 */
  async handleConfirm() {
    this.addServiceForm.validate().then(async () => {
      const params = this.getParams();
      if (params) {
        const isEdit = !!this.serviceInfo;
        if (isEdit) params.id = this.serviceInfo.id;
        this.isLoading = true;
        await customServiceConfig(params)
          .then(() => {
            this.$bkMessage({
              message: this.$t('保存成功'),
              theme: 'success'
            });
            this.handleCancel();
            this.$emit('refresh');
          })
          .finally(() => {
            this.isLoading = false;
          });
      }
    });
  }
  handleCancel() {
    this.handleShowChange(false);
  }
  /** 调试 */
  handlDebugger() {
    this.addServiceForm.validate().then(async () => {
      const params = this.getParams();
      if (params) {
        const urlSourceList = this.urlResource.split(/[(\r\n)\r\n]+/).filter(val => val);
        params.urls_source = urlSourceList || [];
        this.isDebugging = true;
        this.debugged = true;
        await customServiceMatchList(params)
          .then(data => {
            this.debuggerResult = data || [];
          })
          .catch(() => {
            this.debuggerResult = null;
          })
          .finally(() => {
            this.isDebugging = false;
          });
      }
    });
  }

  render() {
    const paramsList = this.formData.rules.params || [];
    const getResultContent = () => {
      if (!this.debugged || !this.debuggerResult) return '';

      if (this.debuggerResult?.length)
        return this.debuggerResult.map(item => (
          <span>
            {item}
            <br />
          </span>
        ));

      return (
        <bk-exception
          class='empty-result'
          type='empty'
          scene='part'
        >
          <span>{this.$t('暂无匹配')}</span>
        </bk-exception>
      );
    };

    return (
      <bk-dialog
        value={this.value}
        title={this.$t('新建自定义服务')}
        header-position='left'
        close-icon={false}
        ext-cls='add-service-dialog'
        mask-close={false}
        width={640}
        value-change={() => this.handleShowChange}
      >
        <span
          class='icon-monitor icon-mc-close'
          slot='tools'
          onClick={() => this.handleCancel()}
        ></span>
        <div class='add-dialog-main'>
          <div
            class='uri-source-content'
            v-bkloading={{ isLoading: this.urlListLoading }}
          >
            <div class='header-tool'>
              <label>{this.$t('URI源')}</label>
              {/* eslint-disable-next-line @typescript-eslint/no-misused-promises */}
              <span
                class='right-btn-wrap'
                slot='headerTool'
                onClick={() => this.getUriSourceData()}
              >
                <i class='icon-monitor icon-shuaxin'></i>
                {this.$t('button-刷新')}
              </span>
            </div>
            <div class='source-box'>
              <bk-input
                class='source-input'
                type='textarea'
                placeholder=' '
                v-model={this.urlResource}
              />
            </div>
          </div>
          <bk-form
            class='add-form'
            ref='addServiceForm'
            form-type='vertical'
            {...{
              props: {
                model: this.formData,
                rules: this.rules
              }
            }}
          >
            <bk-form-item
              label={this.$t('远程服务类型')}
              required
              property='type'
              error-display-type='normal'
            >
              <bk-select
                z-index={3001}
                vModel={this.formData.type}
                clearable={false}
              >
                {this.serviceTypeList.map(option => (
                  <bk-option
                    key={option.id}
                    id={option.id}
                    name={option.name}
                  ></bk-option>
                ))}
              </bk-select>
            </bk-form-item>
            <bk-form-item>
              <div class='bk-button-group match-type-select'>
                <bk-button
                  class={`${this.formData.match_type === 'manual' ? 'is-selected' : ''}`}
                  onClick={() => this.handleChangeMatchType('manual')}
                >
                  {this.$t('手动')}
                </bk-button>
                <bk-button
                  class={`${this.formData.match_type === 'auto' ? 'is-selected' : ''}`}
                  onClick={() => this.handleChangeMatchType('auto')}
                >
                  {this.$t('自动匹配')}
                </bk-button>
              </div>
            </bk-form-item>
            {this.formData.match_type === 'manual' ? (
              <div class='manual-match-wrap'>
                <bk-form-item
                  label={this.$t('服务名')}
                  required
                  property='name'
                  error-display-type='normal'
                >
                  <bk-input vModel={this.formData.name} />
                </bk-form-item>
                <bk-form-item label={this.$t('域名')}>
                  <bk-input vModel={this.formData.rules.host.value}>
                    <bk-dropdown-menu
                      class='group-text'
                      onShow={() => this.handleDropdownShow('domain', true)}
                      onHide={() => this.handleDropdownShow('domain', false)}
                      ref='domainDropdown'
                      trigger='click'
                      slot='prepend'
                      font-size="'medium'"
                    >
                      <bk-button
                        type='primary'
                        slot='dropdown-trigger'
                      >
                        <span>{this.operatorMaps[this.formData.rules.host.operator]}</span>
                        <i class={['bk-icon icon-angle-down', { 'icon-flip': this.isDomainDropdownShow }]} />
                      </bk-button>
                      <ul
                        class='bk-dropdown-list'
                        slot='dropdown-content'
                      >
                        {Object.keys(this.operatorMaps).map(operator => (
                          <li>
                            <a
                              href='javascript:;'
                              onClick={() => this.triggerHandler('domainDropdown', operator)}
                            >
                              {this.operatorMaps[operator]}
                            </a>
                          </li>
                        ))}
                      </ul>
                    </bk-dropdown-menu>
                  </bk-input>
                </bk-form-item>
                <bk-form-item label='PATH'>
                  <bk-input vModel={this.formData.rules.path.value}>
                    <bk-dropdown-menu
                      class='group-text'
                      onShow={() => this.handleDropdownShow('path', true)}
                      onHide={() => this.handleDropdownShow('path', false)}
                      ref='uriDropdown'
                      trigger='click'
                      slot='prepend'
                      font-size="'medium'"
                    >
                      <bk-button
                        type='primary'
                        slot='dropdown-trigger'
                      >
                        <span>{this.operatorMaps[this.formData.rules.path.operator]}</span>
                        <i class={['bk-icon icon-angle-down', { 'icon-flip': this.isUriDropdownShow }]} />
                      </bk-button>
                      <ul
                        class='bk-dropdown-list'
                        slot='dropdown-content'
                      >
                        {Object.keys(this.operatorMaps).map(operator => (
                          <li>
                            <a
                              href='javascript:;'
                              onClick={() => this.triggerHandler('uriDropdown', operator)}
                            >
                              {this.operatorMaps[operator]}
                            </a>
                          </li>
                        ))}
                      </ul>
                    </bk-dropdown-menu>
                  </bk-input>
                </bk-form-item>
                <bk-form-item label={this.$t('参数')}>
                  {paramsList.map((param, index) => (
                    <div
                      class='params-list'
                      key={index}
                    >
                      <bk-input
                        class='name-input'
                        vModel={param.name}
                      />
                      <bk-select
                        vModel={param.operator}
                        z-index={3001}
                      >
                        {Object.keys(this.operatorMaps).map(operator => (
                          <bk-option
                            key={operator}
                            id={operator}
                            name={this.operatorMaps[operator]}
                          />
                        ))}
                      </bk-select>
                      <bk-input
                        class='value-input'
                        vModel={param.value}
                      />
                      <i
                        class='icon-monitor icon-mc-plus-fill'
                        onClick={() => this.handleChangeParam('add', index)}
                      />
                      <i
                        class={['icon-monitor icon-mc-minus-plus', { disabled: paramsList.length === 1 }]}
                        onClick={() => this.handleChangeParam('delete', index)}
                      />
                    </div>
                  ))}
                </bk-form-item>
              </div>
            ) : (
              <div class='auto-match-wrap'>
                <div class='desc-contnet'>{this.$t('说明文案')}</div>
                <bk-form-item
                  label={this.$t('匹配规则')}
                  required
                  property='regex'
                  error-display-type='normal'
                >
                  <bk-input vModel={this.formData.regex} />
                </bk-form-item>
              </div>
            )}
          </bk-form>
          <div class='debugging-content'>
            <div class='header-tool'>
              <bk-button
                outline
                theme='primary'
                loading={this.isDebugging}
                onClick={() => this.handlDebugger()}
              >
                {this.$t('调试')}
              </bk-button>
              {this.debugged && (
                <div>
                  {this.isDebugging ? (
                    <span class='status-wrap'>
                      <bk-spin></bk-spin>
                      <span style='margin-left:6px;'>{this.$t('调试中')}</span>
                    </span>
                  ) : (
                    <span class='status-wrap'>
                      <i
                        class={`icon-monitor ${this.debuggerResult ? 'icon-mc-check-fill' : 'icon-mc-close-fill'}`}
                      ></i>
                      <span>{this.debuggerResult ? this.$t('调试成功') : this.$t('调试失败')}</span>
                    </span>
                  )}
                </div>
              )}
            </div>
            <div class='result-box'>{getResultContent()}</div>
          </div>
        </div>
        <div slot='footer'>
          <bk-button
            theme='primary'
            class='mr10'
            loading={this.isLoading}
            onClick={() => this.handleConfirm()}
          >
            {this.$t('确定')}
          </bk-button>
          <bk-button
            disabled={this.isLoading}
            onClick={() => this.handleCancel()}
          >
            {this.$t('取消')}
          </bk-button>
        </div>
      </bk-dialog>
    );
  }
}
