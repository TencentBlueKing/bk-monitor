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

import { customServiceConfig, customServiceDataSource, customServiceMatchList } from 'monitor-api/modules/apm_meta';

import type { ICustomServiceInfo } from './type';

interface IEvents {
  onRefresh: () => any;
}

interface IProps {
  appName: string;
  serviceInfo?: ICustomServiceInfo | null;
  value?: boolean;
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
    reg: window.i18n.tc('正则'),
  };
  formData = {
    type: '', // 远程服务类型
    name: '', // 服务名
    match_type: 'manual', // manual | auto
    regex: '',
    rules: {
      host: { operator: 'eq', value: '' },
      path: { operator: 'eq', value: '' },
      params: [{ name: '', operator: '', value: '' }],
    },
  };
  rules = {
    type: [
      {
        required: true,
        message: window.i18n.tc('必填项'),
        trigger: 'blur',
      },
    ],
    name: [
      {
        required: true,
        message: window.i18n.tc('必填项'),
        trigger: 'blur',
      },
    ],
    regex: [
      {
        required: true,
        message: window.i18n.tc('必填项'),
        trigger: 'blur',
      },
    ],
  };
  /** 调试结果列表 */
  debuggerResult: null | string[] = null;
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
          params: [{ name: '', operator: '', value: '' }],
        },
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
      type: 'http', // 暂时只有一种类型
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
      rules: Object.assign(this.formData.rules, rule),
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
      rule: {},
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
        theme: 'error',
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
              theme: 'success',
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
  handleDebugger() {
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
          <span key={item}>
            {item}
            <br />
          </span>
        ));

      return (
        <bk-exception
          class='empty-result'
          scene='part'
          type='empty'
        >
          <span>{this.$t('暂无匹配')}</span>
        </bk-exception>
      );
    };

    return (
      <bk-dialog
        width={640}
        ext-cls='add-service-dialog'
        close-icon={false}
        header-position='left'
        mask-close={false}
        title={this.$t('新建自定义服务')}
        value={this.value}
        value-change={() => this.handleShowChange}
      >
        <span
          class='icon-monitor icon-mc-close'
          slot='tools'
          onClick={() => this.handleCancel()}
        />
        <div class='add-dialog-main'>
          <div
            class='uri-source-content'
            v-bkloading={{ isLoading: this.urlListLoading }}
          >
            <div class='header-tool'>
              <label>{this.$t('URI源')}</label>
              <span
                class='right-btn-wrap'
                slot='headerTool'
                onClick={() => this.getUriSourceData()}
              >
                <i class='icon-monitor icon-shuaxin' />
                {this.$t('button-刷新')}
              </span>
            </div>
            <div class='source-box'>
              <bk-input
                class='source-input'
                v-model={this.urlResource}
                placeholder=' '
                type='textarea'
              />
            </div>
          </div>
          <bk-form
            ref='addServiceForm'
            class='add-form'
            form-type='vertical'
            {...{
              props: {
                model: this.formData,
                rules: this.rules,
              },
            }}
          >
            <bk-form-item
              error-display-type='normal'
              label={this.$t('远程服务类型')}
              property='type'
              required
            >
              <bk-select
                vModel={this.formData.type}
                clearable={false}
              >
                {this.serviceTypeList.map(option => (
                  <bk-option
                    id={option.id}
                    key={option.id}
                    name={option.name}
                  />
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
                  error-display-type='normal'
                  label={this.$t('服务名')}
                  property='name'
                  required
                >
                  <bk-input vModel={this.formData.name} />
                </bk-form-item>
                <bk-form-item label={this.$t('域名')}>
                  <bk-input vModel={this.formData.rules.host.value}>
                    <bk-dropdown-menu
                      ref='domainDropdown'
                      class='group-text'
                      slot='prepend'
                      font-size="'medium'"
                      trigger='click'
                      onHide={() => this.handleDropdownShow('domain', false)}
                      onShow={() => this.handleDropdownShow('domain', true)}
                    >
                      <bk-button
                        slot='dropdown-trigger'
                        type='primary'
                      >
                        <span>{this.operatorMaps[this.formData.rules.host.operator]}</span>
                        <i class={['bk-icon icon-angle-down', { 'icon-flip': this.isDomainDropdownShow }]} />
                      </bk-button>
                      <ul
                        class='bk-dropdown-list'
                        slot='dropdown-content'
                      >
                        {Object.keys(this.operatorMaps).map((operator, index) => (
                          <li key={`operator_${this.operatorMaps[operator]}_${index}`}>
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
                <bk-form-item label='URL'>
                  <bk-input vModel={this.formData.rules.path.value}>
                    <bk-dropdown-menu
                      ref='uriDropdown'
                      class='group-text'
                      slot='prepend'
                      font-size="'medium'"
                      trigger='click'
                      onHide={() => this.handleDropdownShow('path', false)}
                      onShow={() => this.handleDropdownShow('path', true)}
                    >
                      <bk-button
                        slot='dropdown-trigger'
                        type='primary'
                      >
                        <span>{this.operatorMaps[this.formData.rules.path.operator]}</span>
                        <i class={['bk-icon icon-angle-down', { 'icon-flip': this.isUriDropdownShow }]} />
                      </bk-button>
                      <ul
                        class='bk-dropdown-list'
                        slot='dropdown-content'
                      >
                        {Object.keys(this.operatorMaps).map((operator, index) => (
                          <li key={`operator_${this.operatorMaps[operator]}_${index}`}>
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
                      key={`${param.name}_${index}`}
                      class='params-list'
                    >
                      <bk-input
                        class='name-input'
                        vModel={param.name}
                      />
                      <bk-select vModel={param.operator}>
                        {Object.keys(this.operatorMaps).map(operator => (
                          <bk-option
                            id={operator}
                            key={operator}
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
                <div class='desc-contnet'>
                  {`${this.$t('匹配规则支持通过在正则表达式中配置 `peer_service` 和 `span_name` 参数来提取自定义服务名称和 span_name。例如配置正则：')}`}
                  <br />
                  {'https://(?P<peer_service>[^/]+)/(?P<span_name>.*)'}
                  <br />
                  {this.$t(
                    '当出现了 HTTP 类型的 span 并且调用的 Url(attributes.http.url) 为 `https://example.com/path/to/docs`，将会匹配出 `example.com` 自定义服务，以及此 span 的 span_name 将会覆盖为`path/to/docs`'
                  )}
                </div>
                <bk-form-item
                  error-display-type='normal'
                  label={this.$t('匹配规则')}
                  property='regex'
                  required
                >
                  <bk-input vModel={this.formData.regex} />
                </bk-form-item>
              </div>
            )}
          </bk-form>
          <div class='debugging-content'>
            <div class='header-tool'>
              <bk-button
                loading={this.isDebugging}
                theme='primary'
                outline
                onClick={() => this.handleDebugger()}
              >
                {this.$t('调试')}
              </bk-button>
              {this.debugged && (
                <div>
                  {this.isDebugging ? (
                    <span class='status-wrap'>
                      <bk-spin />
                      <span style='margin-left:6px;'>{this.$t('调试中')}</span>
                    </span>
                  ) : (
                    <span class='status-wrap'>
                      <i class={`icon-monitor ${this.debuggerResult ? 'icon-mc-check-fill' : 'icon-mc-close-fill'}`} />
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
            class='mr10'
            loading={this.isLoading}
            theme='primary'
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
