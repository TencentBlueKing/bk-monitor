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

import { Debounce, deepClone, transformDataKey } from '../../../../../../../monitor-common/utils/utils';
import ResizeContainer from '../../../../../../components/resize-container/resize-container';
import VerifyItem from '../../../../../../components/verify-item/verify-item';

import { IHeaderInfo, IHttpData, IParamsValueItem, ISelectListItem, ISetingValue, THeaderType, TMethod } from './types';
import { localDataConvertToRequest } from './utils';

import './http-editor.scss';

const { i18n } = window;

export type MethodType = 'GET' | 'POST' | 'DELETE' | 'PUT' | 'PATCH';
export type MethodListType = Array<MethodType>;
interface IHttpEditor {
  isEdit: boolean;
  needUrl?: boolean;
  value?: any;
  label?: string;
  methodList?: MethodListType;
  needSettings?: boolean;
  needSslCheckbox?: boolean;
  behavior?: InputType;
}

type InputType = 'normal' | 'simplicity';

// GET请求query参数匹配正则
const QUERY_REG = new RegExp(/\?(([^?&=]+)=([^?&=]*)&?)+/);

@Component
export default class HttpEditor extends tsc<IHttpEditor> {
  // 编辑状态
  @Prop({ default: false, type: Boolean }) readonly isEdit: boolean;
  @Prop({ default: null, type: Object }) readonly value: any;
  @Prop({ default: '', type: String }) readonly label: string;
  /** 请求方法 */
  @Prop({ type: Array }) methodList: MethodListType;
  /** 是否需要设置tab */
  @Prop({ default: true, type: Boolean }) needSettings: boolean;
  /** 是否需要ssl选项 */
  @Prop({ default: false, type: Boolean }) needSslCheckbox: boolean;
  @Prop({ default: true, type: Boolean }) needUrl: boolean;
  @Prop({ type: String, default: 'simplicity' }) behavior: InputType;

  oldValue: any = null;

  httpData: IHttpData = {
    method: 'GET',
    url: ''
  };

  tabActive: THeaderType = 'Params';

  errorMsg = {
    url: ''
  };
  rawErrorMsg = '';

  localHeaderInfo: IHeaderInfo[] = [
    {
      key: 'Params',
      name: `${i18n.t('参数')}`,
      enable: true,
      desc: '',
      value: [
        // { isEnabled: false, key: '', value: '', desc: '' }
      ]
    },
    {
      key: 'Authorization',
      name: `${i18n.t('认证')}`,
      enable: true,
      desc: '',
      type: 'none',
      bearer_token: { token: '' },
      basic_auth: { username: '', password: '' },
      insecure_skip_verify: false
    },
    {
      key: 'Headers',
      name: `${i18n.t('头信息')}`,
      enable: true,
      desc: '',
      hide: true,
      value: [
        // { isBuiltin: true, isEnabled: true, key: '默认1', value: '默认1', desc: '' },
        // { isBuiltin: true, isEnabled: true, key: '默认2', value: '默认2', desc: '' },
        // { isEnabled: false, key: '', value: '', desc: '' }
      ]
    },
    {
      key: 'Body',
      name: `${i18n.t('主体')}`,
      enable: true,
      desc: '',
      type: 'default',
      form_data: [
        // { isEnabled: false, key: '', value: '', desc: '' }
      ],
      x_www_form_urlencoded: [
        // { isEnabled: false, key: '', value: '', desc: '' }
      ],
      raw: { type: 'text', content: '' }
    },
    {
      key: 'Seting',
      name: '设置',
      enable: true,
      desc: '',
      value: {
        // interval: 60,
        timeout: 10,
        retryInterval: 2,
        maxRetryTimes: 2,
        needPoll: false,
        notifyInterval: 120
      }
    }
  ];

  authRadioList: ISelectListItem[] = [
    { id: 'none', name: `${i18n.t('无需认证')}` },
    { id: 'bearer_token', name: 'Bearer Token' },
    { id: 'basic_auth', name: 'Basic Auth' }
  ];
  bodyRadioList: ISelectListItem[] = [
    { id: 'default', name: `${i18n.t('默认')}` },
    { id: 'form_data', name: 'form-data' },
    { id: 'x_www_form_urlencoded', name: 'x-www-form-urlencoded' },
    { id: 'raw', name: 'raw' }
  ];
  setingInputList: ISelectListItem[] = [
    // { id: 'interval', name: `${i18n.t('求间隔')}`, unit: 's' },
    { id: 'timeout', name: `${i18n.t('请求超时')}`, unit: 's' },
    { id: 'retryInterval', name: `${i18n.t('重试间隔')}`, unit: 's' },
    { id: 'maxRetryTimes', name: `${i18n.t('重试次数')}`, unit: `${i18n.t('次')}` },
    { id: 'needPoll', name: `${i18n.t('是否周期回调')}`, unit: '' },
    { id: 'notifyInterval', name: `${i18n.t('回调间隔')}`, unit: `${i18n.t('分钟')}` }
  ];
  paramTableColumns: any = [
    // { label: '', prop: '', width: 27 },
    { label: '', prop: 'isEnabled', width: 31 },
    { label: `${i18n.t('字段名')}`, prop: 'key' },
    { label: `${i18n.t('值')}`, prop: 'value' },
    { label: `${i18n.t('描述')}`, prop: 'desc' },
    { label: '', prop: 'handle', width: 48 }
  ];
  headersTableColumns: any = [
    { label: '', prop: 'isEnabled', width: 31, type: 'selection' },
    { label: `${i18n.t('字段名')}`, prop: 'key' },
    { label: `${i18n.t('值')}`, prop: 'value' },
    { label: `${i18n.t('描述')}`, prop: 'desc' },
    { label: '', prop: 'handle', width: 48 }
  ];

  headerHideTips = {
    true: {
      placement: 'top',
      content: `${i18n.t('点击展开全部')}`
    },
    false: {
      placement: 'top',
      content: `${i18n.t('点击隐藏默认')}`
    }
  };

  get localMethodList(): MethodListType {
    return this.methodList ?? ['POST', 'GET'];
  }
  /**
   * 当前选中的头信息
   */
  get curHeaderData(): IHeaderInfo {
    return this.localHeaderInfo.find(item => item.key === this.tabActive);
  }

  get checkUrl(): boolean {
    return /^(((ht|f)tps?):\/\/)[\w-]+(\.[\w-]+)+([\w.,@?^=%&:/~+#-{}]*[\w@?^=%&/~+#-{}])?$/.test(this.httpData.url);
  }

  /** HTTPS需要展示ssl配置 */
  get showSSLCheckbox(): boolean {
    return /^https/.test(this.httpData.url);
  }

  @Watch('value', { immediate: true, deep: true })
  valueChange(v) {
    if (JSON.stringify(v) === JSON.stringify(this.oldValue)) return;
    v && this.convertToLocalValue(deepClone(v));
  }

  @Emit('change')
  emitLocalHeaderInfo() {
    this.oldValue = localDataConvertToRequest(this.localHeaderInfo);
    if (!this.needSslCheckbox) delete this.oldValue.authorize.insecure_skip_verify;
    const res = {
      method: this.httpData.method,
      url: this.httpData.url,
      ...this.oldValue
    };
    return res;
  }

  created() {
    this.handleShowSettings();
    this.emitLocalHeaderInfo();
  }

  handleShowSettings() {
    const settings = this.localHeaderInfo.find(item => item.key === 'Seting');
    settings.enable = this.needSettings;
  }

  validator() {
    if (!this.checkUrl) {
      this.errorMsg.url = this.$tc('输入合法URL');
      return false;
    }
    return true;
  }

  /**
   * @description: 回显示数据
   * @param {any} data
   * @return {*}
   */
  convertToLocalValue(data: any) {
    try {
      let { body = { dataType: 'default' }, authorize = { authType: 'none' } } = data;
      const { queryParams = [], headers = [], method, url, failedRetry } = data;
      body = transformDataKey(body, true);
      authorize = transformDataKey(authorize, true);
      // method url
      this.httpData.method = method;
      this.httpData.url = url;
      // 参数
      const paramsData = this.localHeaderInfo.find(item => item.key === 'Params');
      this.isEdit && queryParams.push({ isEnabled: true, key: '', value: '', desc: '' });
      paramsData.value = queryParams;
      // 认证
      const authData = this.localHeaderInfo.find(item => item.key === 'Authorization');
      const authType = authorize.auth_type;
      authType !== 'none' && (authData[authType] = authorize.auth_config);
      authData.type = authType;
      authData.insecure_skip_verify = authorize.insecure_skip_verify ?? false;
      // 头部数据
      const headersData = this.localHeaderInfo.find(item => item.key === 'Headers');
      this.isEdit && headers.push({ isEnabled: true, key: '', value: '', desc: '' });
      headersData.value = headers;
      // body
      const bodyData = this.localHeaderInfo.find(item => item.key === 'Body');
      const bodyType = body.data_type;
      !['default', 'raw'].includes(bodyType) && (bodyData[bodyType] = transformDataKey(body.params));
      if (bodyType === 'raw') {
        bodyData[bodyType] = { type: 'text', content: '' };
        bodyData[bodyType].content = body.content;
        bodyData[bodyType].type = body.content_type;
        // bodyData[bodyType] = body[bodyType]
        // bodyData[bodyType].type = body[bodyType].content_type
      }
      if (['form_data', 'x_www_form_urlencoded'].includes(bodyType)) {
        this.isEdit && bodyData[bodyType].push({ isEnabled: true, key: '', value: '', desc: '' });
        // bodyData[bodyType].push({ isEnabled: false, key: '', value: '', desc: '' })
      }
      bodyData.type = bodyType;
      // 重试配置
      const configData = this.localHeaderInfo.find(item => item.key === 'Seting');
      configData.value = failedRetry || { maxRetryTimes: 2, retryInterval: 60, timeout: 10 };
    } catch (error) {
      console.error('http 数据格式错误', error);
    }
  }

  methodChange(v: TMethod) {
    this.httpData.method = v;
    // 处理url query
    if (v === 'POST') this.httpData.url = this.httpData.url.replace(QUERY_REG, '');
    // this.displayParamsToUrl()

    this.emitLocalHeaderInfo();
  }

  /**
   * @description: 处理url query
   * @param {*}
   * @return {*}
   */
  displayParamsToUrl() {
    if (this.httpData.method !== 'GET') return;
    const paramsData = this.localHeaderInfo.find(item => item.key === 'Params');
    const list = (paramsData.value as IParamsValueItem[]).filter(item => item.key && item.value);
    const { url } = this.httpData;
    const host = url.replace(QUERY_REG, '');
    if (!list.length) {
      this.httpData.url = host;
      return;
    }
    const strArr = list.map(item => `${item.key}=${item.value}`);
    const queryStr = `?${strArr.join('&')}`;
    this.httpData.url = host + queryStr;
  }

  /**
   * @description: 表格输入添加空行
   * @param {*} tableData
   * @param {*} tplData
   * @return {*}
   */
  handleAddRowIntoTable(tableData, tplData = { isEnabled: true, key: '', value: '', desc: '' }) {
    const temp = deepClone(tplData);
    const leng = tableData.length;
    const lastRow = tableData[leng - 1];
    const hasEmpty = this.rowIsEmpty(lastRow);
    !hasEmpty && tableData.push(temp);
    const secondLast = tableData[leng - 2];
    if (secondLast) {
      const isEmpty = this.rowIsEmpty(secondLast);
      if (isEmpty) tableData.splice(leng - 2, 1);
    }
  }
  rowIsEmpty(row: IParamsValueItem): boolean {
    const keyMap = ['key', 'value', 'desc'];
    if (!row) return true;
    return Object.keys(row)
      .filter(key => keyMap.includes(key))
      .every(key => !row[key]);
  }
  urlFocus() {
    this.errorMsg.url = '';
  }

  @Debounce(300)
  urlChange() {
    if (this.checkUrl) this.errorMsg.url = '';
    this.emitLocalHeaderInfo();
  }
  @Debounce(300)
  paramInput() {
    const tableData = this.curHeaderData.value;
    this.handleAddRowIntoTable(tableData);
    // this.displayParamsToUrl()
    this.emitLocalHeaderInfo();
  }
  @Debounce(300)
  bodyParamInput() {
    // 表格输入添加空行
    const { key } = this.curHeaderData;
    const { type } = this.curHeaderData;
    const typeMap = ['form_data', 'x_www_form_urlencoded'];
    if (key === 'Body' && typeMap.includes(type)) {
      let tableData = null;
      type === 'form_data' && (tableData = this.curHeaderData.form_data);
      type === 'x_www_form_urlencoded' && (tableData = this.curHeaderData.x_www_form_urlencoded);
      this.handleAddRowIntoTable(tableData);
    }

    this.emitLocalHeaderInfo();
  }
  @Debounce(300)
  authParamInput() {
    this.emitLocalHeaderInfo();
  }
  @Debounce(300)
  headersChange() {
    const tableData = this.curHeaderData.value;
    this.handleAddRowIntoTable(tableData);
    this.emitLocalHeaderInfo();
  }
  @Debounce(300)
  setingChange() {
    this.emitLocalHeaderInfo();
  }

  tabChange(key: THeaderType) {
    if (this.tabActive === key) return;
    this.tabActive = key;
  }

  /**
   * @description: 校验raw 的 json html xml格式
   * @param {*} type
   * @param {*} content
   * @return {*}
   */
  handleRawBlur(type, content) {
    let errorMsg = '';
    const typeNameMap = {
      json: 'JSON',
      xml: 'XML',
      html: 'HTML'
    };
    if (content && type === 'json') {
      try {
        JSON.parse(content);
      } catch (error) {
        errorMsg = this.$t('文本不符合 {type} 格式', { type: typeNameMap[type] }) as string;
      }
    }
    if (content && ['html', 'xml'].includes(type)) {
      const parser = new DOMParser();
      const res = parser.parseFromString(content, 'application/xhtml+xml');
      const parsererror = res.querySelector('parsererror');
      parsererror && (errorMsg = this.$t('文本不符合 {type} 格式', { type: typeNameMap[type] }) as string);
    }
    this.rawErrorMsg = errorMsg;
  }

  //  表格输入的作用域插槽
  paramInputScopedSlots(data, changeFn?: Function, deleteFn?) {
    return {
      default: props => {
        const index = props.$index;
        const prop = props.column.property;
        const item = data[index];
        const isEmpty = this.rowIsEmpty(item);
        const handleChecked = () => {
          this.emitLocalHeaderInfo();
        };
        if (!item) return undefined;
        if (prop === 'isEnabled') {
          return !isEmpty ? (
            <div class='table-checked'>
              <bk-checkbox
                v-model={item[prop]}
                disabled={item.isBuiltin || !this.isEdit}
                onChange={handleChecked}
              />
            </div>
          ) : undefined;
        }
        if (prop === 'handle' && this.isEdit) {
          if ((isEmpty && index === data.length - 1) || item.isBuiltin) return undefined;
          return (
            <div class='table-handle'>
              <i
                class='icon-monitor icon-mc-close'
                onClick={() => deleteFn(index, item)}
              ></i>
            </div>
          );
        }
        return (
          <span>
            {this.isEdit && prop ? (
              <bk-input
                class='table-input'
                behavior='simplicity'
                placeholder={this.$t('输入')}
                disabled={item.isBuiltin === undefined ? false : item.isBuiltin}
                v-model={item[prop]}
                onChange={changeFn}
              />
            ) : (
              item[prop]
            )}
          </span>
        );
      }
    };
  }

  // 头认证信息模版
  tplAuthorization() {
    const { curHeaderData } = this;
    const data = curHeaderData[curHeaderData.type];
    const radioChange = () => {
      this.emitLocalHeaderInfo();
    };
    const { type } = curHeaderData;
    return (
      <div class='header-content header-auth'>
        <bk-radio-group
          v-model={curHeaderData.type}
          onChange={radioChange}
        >
          {this.authRadioList.map(item => (
            <bk-radio
              key={item.id}
              value={item.id}
              disabled={!this.isEdit}
            >
              {item.name}
            </bk-radio>
          ))}
          {this.needSslCheckbox && this.showSSLCheckbox && (
            <bk-checkbox
              v-model={curHeaderData.insecure_skip_verify}
              onChnage={this.authParamInput}
            >
              {this.$t('SSL证书校验')}
            </bk-checkbox>
          )}
        </bk-radio-group>
        {type === 'bearer_token' ? (
          <div class='auth-params-wrap'>
            <div class='auth-params-label'>Token</div>
            <bk-input
              class='input'
              style='width: 520px'
              v-model={data.token}
              behavior='simplicity'
              disabled={!this.isEdit}
              onInput={this.authParamInput}
            ></bk-input>
          </div>
        ) : undefined}
        {type === 'basic_auth' ? (
          <div class='auth-params-wrap horizontal'>
            <div class='input-item'>
              <div class='auth-params-label'>{this.$t('用户名')}</div>
              <bk-input
                class='input'
                v-model={data.username}
                behavior='simplicity'
                disabled={!this.isEdit}
                onInput={this.authParamInput}
              ></bk-input>
            </div>
            <div class='input-item'>
              <div class='auth-params-label'>{this.$t('密码')}</div>
              <bk-input
                class='input'
                type='password'
                v-model={data.password}
                behavior='simplicity'
                disabled={!this.isEdit}
                onInput={this.authParamInput}
              ></bk-input>
            </div>
          </div>
        ) : undefined}
        {type === 'none' ? <div class='header-tips'>{this.$t('该请求不需要任何认证。')}</div> : undefined}
      </div>
    );
  }
  // 头参数模板
  tplParams() {
    const data = this.curHeaderData.value;
    const handleDel = index => {
      (data as IParamsValueItem[]).splice(index, 1);
      //   this.displayParamsToUrl()
      this.emitLocalHeaderInfo();
    };
    const scopedSlots = this.paramInputScopedSlots(data, this.paramInput, handleDel);
    return (
      <div class='header-content header-params'>
        <bk-table data={data}>
          {this.paramTableColumns.map((item, i) => (
            <bk-table-column
              key={i}
              label={item.label}
              prop={item.prop}
              width={item.width}
              {...{ scopedSlots }}
            ></bk-table-column>
          ))}
        </bk-table>
      </div>
    );
  }
  // 头信息模板
  tplHeaders() {
    const data = this.curHeaderData.value as IParamsValueItem[];
    let temp = [];
    data.forEach((item, index) => {
      item.index = index;
    });
    const isHide = this.curHeaderData.hide;
    const hideCount = data.filter(item => item.isBuiltin).length;
    temp = isHide ? data.filter(item => !item.isBuiltin) : data;
    const handleDel = (i, item) => {
      const { index } = item;
      data.splice(index, 1);
      this.emitLocalHeaderInfo();
    };
    const scopedSlots = this.paramInputScopedSlots(temp, this.headersChange, handleDel);
    return (
      <div class='header-content header-headers'>
        {hideCount ? (
          <div class='handle-hide-defult'>
            <i
              v-bk-tooltips={{
                content: this.headerHideTips[`${isHide}`],
                allowHTML: false
              }}
              class={['icon-monitor', isHide ? 'icon-mc-invisible' : 'icon-mc-visual']}
              onClick={() => (this.curHeaderData.hide = !isHide)}
            ></i>
            {isHide ? (
              <span>
                {this.$t('已隐藏')} {hideCount} {this.$t('项')}
              </span>
            ) : (
              <span>{this.$t('已展开全部')}</span>
            )}
          </div>
        ) : undefined}
        <bk-table data={temp}>
          {this.headersTableColumns.map((item, i) => (
            <bk-table-column
              key={i}
              label={item.label}
              prop={item.prop}
              width={item.width}
              {...{ scopedSlots }}
            ></bk-table-column>
          ))}
        </bk-table>
      </div>
    );
  }
  // body信息模板
  tplBody() {
    const rowTypeList = [
      { id: 'text', name: 'Text' },
      { id: 'json', name: 'JSON' },
      { id: 'html', name: 'HTML' },
      { id: 'xml', name: 'XML' }
    ];
    const { curHeaderData } = this;
    const radioChange = () => {
      this.emitLocalHeaderInfo();
    };
    const data = curHeaderData[curHeaderData.type];
    let scopedSlots = null;
    const isTable = ['form_data', 'x_www_form_urlencoded'].includes(curHeaderData.type);
    if (isTable) {
      const handleDel = index => {
        (data as IParamsValueItem[]).splice(index, 1);
        this.emitLocalHeaderInfo();
      };
      scopedSlots = this.paramInputScopedSlots(data, this.bodyParamInput, handleDel);
    }
    return (
      <div class='header-content header-body'>
        <div class='header-body-type'>
          <bk-radio-group
            class='body-radio-group'
            v-model={curHeaderData.type}
            onChange={radioChange}
          >
            {this.bodyRadioList.map(item => (
              <bk-radio
                key={item.id}
                value={item.id}
                disabled={!this.isEdit}
              >
                <span>{item.name}</span>
              </bk-radio>
            ))}
          </bk-radio-group>
          {curHeaderData.type === 'raw' ? (
            <bk-select
              class='select select-wrap'
              v-model={data.type}
              clearable={false}
              disabled={!this.isEdit}
              popover-min-width={100}
              behavior='simplicity'
              onSelected={() => this.handleRawBlur(data.type, data.content)}
            >
              {rowTypeList.map(option => (
                <bk-option
                  key={option.id}
                  id={option.id}
                  name={option.name}
                ></bk-option>
              ))}
            </bk-select>
          ) : undefined}
        </div>
        {curHeaderData.type === 'default' ? <div class='header-tips'>{this.$t('该请求不含主体。')}</div> : undefined}
        {curHeaderData.type === 'raw' ? (
          <div class='textarea-wrap'>
            <ResizeContainer
              minHeight={80}
              // width={ 568 }
              minWidth={200}
            >
              <bk-input
                class='textarea'
                type={'textarea'}
                disabled={!this.isEdit}
                onInput={this.bodyParamInput}
                v-model={data.content}
                onBlur={() => this.handleRawBlur(data.type, data.content)}
                onFocus={() => (this.rawErrorMsg = '')}
              ></bk-input>
              {this.rawErrorMsg && <p style='margin: 0; color: #ff5656;'>{this.rawErrorMsg}</p>}
            </ResizeContainer>
          </div>
        ) : undefined}
        {isTable ? (
          <bk-table
            class='table'
            data={data}
          >
            {this.paramTableColumns.map((item, i) => (
              <bk-table-column
                key={i}
                label={item.label}
                prop={item.prop}
                width={item.width}
                {...{ scopedSlots }}
              ></bk-table-column>
            ))}
          </bk-table>
        ) : undefined}
      </div>
    );
  }
  // 设置模板
  tplSeting() {
    const valueKeyMap = this.curHeaderData.value;
    const content = (item, template) => (
      <div
        key={item.id}
        class='seting-item'
      >
        <div class='seting-title'>{item.name}</div>
        <div class='input-wrap'>
          {template}
          <span class='unit'>{item.unit}</span>
        </div>
      </div>
    );
    return (
      <div class='header-content header-seting'>
        {this.setingInputList.map(item => {
          if (item.id === 'needPoll') {
            return content(
              item,
              <bk-switcher
                class='switch'
                theme='primary'
                size='small'
                disabled={!this.isEdit}
                vModel={valueKeyMap[item.id]}
                on-change={this.setingChange}
              />
            );
          }
          if (item.id === 'notifyInterval') {
            return content(
              item,
              <bk-input
                class='input'
                behavior='simplicity'
                onInput={this.setingChange}
                type='number'
                showControls={false}
                vModel={valueKeyMap[item.id]}
                disabled={!(valueKeyMap as ISetingValue).needPoll || !this.isEdit}
                v-bk-tooltips={{ content: this.$t('开启周期回调'), disabled: (valueKeyMap as ISetingValue).needPoll }}
              />
            );
          }
          return content(
            item,
            <bk-input
              class='input'
              behavior='simplicity'
              onInput={this.setingChange}
              type='number'
              showControls={false}
              disabled={!this.isEdit}
              vModel={valueKeyMap[item.id]}
            />
          );
        })}
      </div>
    );
  }

  // tab的label模板
  tplTabLabel(tab: IHeaderInfo) {
    const { key } = tab;
    let tips = undefined;
    if (['Params', 'Headers'].includes(key)) {
      const value = (tab.value as IParamsValueItem[]).filter(item => item.isEnabled && !this.rowIsEmpty(item));
      const num = value.length;
      tips = num ? num : undefined;
    }
    if (['Authorization', 'Body'].includes(key)) {
      const value = tab.type;
      tips = ['none', 'default'].includes(value) ? undefined : true;
    }
    const tpl = (
      <div class='tab-label-wrap'>
        <span>{tab.name}</span>
        <span
          style={{ display: tips === undefined ? 'none' : '' }}
          class={['tips', { 'is-select': tips && typeof tips === 'boolean' }]}
        >
          {typeof tips === 'number' ? tips : undefined}
        </span>
      </div>
    );
    return tpl;
  }

  protected render() {
    return (
      <div
        class={[
          'http-editor-wrap',
          {
            'http-editor-is-edit': this.isEdit,
            'http-editor-has-label': this.label
          }
        ]}
      >
        {
          // http方法/url
          this.isEdit ? (
            <div class='http-method-url'>
              <bk-select
                class='select'
                v-model={this.httpData.method}
                clearable={false}
                behavior={this.behavior}
                popover-width={100}
                onChange={this.methodChange}
              >
                {this.localMethodList.map(option => (
                  <bk-option
                    key={option}
                    id={option}
                    name={option}
                  ></bk-option>
                ))}
              </bk-select>
              <VerifyItem
                class='verify-url'
                errorMsg={this.errorMsg.url}
              >
                <bk-input
                  class='url-input'
                  v-model={this.httpData.url}
                  onChange={this.urlChange}
                  onFocus={this.urlFocus}
                  placeholder={this.$i18n.tc('输入请求 URL')}
                  behavior={this.behavior}
                ></bk-input>
              </VerifyItem>
            </div>
          ) : (
            <div class='dispaly-method-url'>
              {this.label ? <span class='label'>{this.label}</span> : undefined}
              <span class='method'>{this.httpData.method}</span>
              <span class='border'></span>
              <span class='url'>{this.httpData.url}</span>
            </div>
          )
        }
        {/* http头信息区域 */}
        <div class='http-header-wrap'>
          <div class='arrow'></div>
          <div class='http-header-main'>
            <div class='tab-select-wrap'>
              {this.localHeaderInfo.map((tab, i) => {
                if (!tab.enable) return;
                return (
                  <span
                    key={i}
                    class={['tab-item-wrap', { 'tab-item-active': tab.key === this.tabActive }]}
                    onClick={() => this.tabChange(tab.key)}
                  >
                    {this.tplTabLabel(tab)}
                  </span>
                );
              })}
            </div>
            {!!this.curHeaderData.desc && (
              <div class='header-desc'>
                <i class='icon-monitor icon-bangzhu'></i>
                <span class='desc-text'>{this.curHeaderData.desc}</span>
              </div>
            )}
            {
              // 头信息内容区
              this[`tpl${this.tabActive}`](this)
            }
          </div>
        </div>
      </div>
    );
  }
}
