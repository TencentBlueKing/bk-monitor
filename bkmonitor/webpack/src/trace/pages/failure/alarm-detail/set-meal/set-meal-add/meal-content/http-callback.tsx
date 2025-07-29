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
import { computed, defineComponent, onMounted, ref, watch } from 'vue';

import { PrimaryTable } from '@blueking/tdesign-ui';
import { Button, Checkbox, Input, Radio, Select, Switcher } from 'bkui-vue';
import { debounce, deepClone, transformDataKey } from 'monitor-common/utils/utils';
import { useI18n } from 'vue-i18n';

import CommonItem from '../components/common-item';
import { localDataConvertToRequest } from '../components/http-editor/utils';
import ResizeContainer from '../components/resize-container/resize-container';
import VerifyItem from '../components/verify-item/verify-item';

import type {
  IHeaderInfo,
  IHttpData,
  IParamsValueItem,
  ISelectListItem,
  ISetingValue,
  THeaderType,
  TMethod,
} from '../components/http-editor/types';
import type { IWebhook } from './meal-content-data';

import './http-callback.scss';

// GET请求query参数匹配正则
const QUERY_REG = new RegExp(/\?(([^?&=]+)=([^?&=]*)&?)+/);

export default defineComponent({
  props: {
    isEdit: { default: false, type: Boolean },
    value: { default: null, type: Object },
    label: { default: '', type: String },
    isOnlyHttp: { default: false, type: Boolean },
  },
  emits: ['change', 'debug'],
  setup(props, { emit }) {
    const { t } = useI18n();
    const data = ref<IWebhook>({});
    const oldValue = ref(null);
    const httpData = ref<IHttpData>({
      method: 'GET',
      url: '',
    });
    const tabActive = ref<THeaderType>('Params');
    const errorMsg = ref({
      url: '',
    });
    const rawErrorMsg = ref('');
    const localHeaderInfo = ref<IHeaderInfo[]>([
      {
        key: 'Params',
        name: `${t('参数')}`,
        desc: '',
        value: [],
      },
      {
        key: 'Authorization',
        name: `${t('认证')}`,
        desc: '',
        type: 'none',
        bearer_token: { token: '' },
        basic_auth: { username: '', password: '' },
      },
      {
        key: 'Headers',
        name: `${t('头信息')}`,
        desc: '',
        hide: true,
        value: [],
      },
      {
        key: 'Body',
        name: `${t('主体')}`,
        desc: '',
        type: 'default',
        form_data: [],
        x_www_form_urlencoded: [],
        raw: { type: 'text', content: '' },
      },
      {
        key: 'Seting',
        name: `${t('设置')}`,
        desc: '',
        value: {
          timeout: 10,
          retryInterval: 2,
          maxRetryTimes: 2,
          needPoll: false,
          notifyInterval: 120,
        },
      },
    ]);

    const methodList = ref(['POST', 'GET']);
    const authRadioList = ref<ISelectListItem[]>([
      { id: 'none', name: `${t('无需认证')}` },
      { id: 'bearer_token', name: 'Bearer Token' },
      { id: 'basic_auth', name: 'Basic Auth' },
    ]);
    const BodyRadioList = ref<ISelectListItem[]>([
      { id: 'default', name: `${t('默认')}` },
      { id: 'form_data', name: 'form-data' },
      { id: 'x_www_form_urlencoded', name: 'x-www-form-urlencoded' },
      { id: 'raw', name: 'raw' },
    ]);

    const setingInputList = ref<ISelectListItem[]>([
      { id: 'timeout', name: `${t('请求超时')}`, unit: 's' },
      { id: 'retryInterval', name: `${t('重试间隔')}`, unit: 's' },
      { id: 'maxRetryTimes', name: `${t('重试次数')}`, unit: `${t('次')}` },
      { id: 'needPoll', name: `${t('是否周期回调')}`, unit: '' },
      { id: 'notifyInterval', name: `${t('回调间隔')}`, unit: `${t('分钟')}` },
    ]);

    const paramTableColumns = ref([
      { title: '', field: 'isEnabled', colKey: 'isEnabled', width: 31, minWidth: 31 },
      { title: `${t('字段名')}`, colKey: 'key', field: 'key' },
      { title: `${t('值')}`, colKey: 'value', field: 'value' },
      { title: `${t('描述')}`, colKey: 'desc', field: 'desc' },
      { title: '', colKey: 'handle', width: 48, minWidth: 48, field: 'handle' },
    ]);
    const headersTableColumns = ref([
      { title: '', colKey: 'isEnabled', field: 'isEnabled', width: 31, minWidth: 31, type: 'selection' },
      { title: `${t('字段名')}`, colKey: 'key', field: 'key' },
      { title: `${t('值')}`, colKey: 'value', field: 'value' },
      { title: `${t('描述')}`, colKey: 'desc', field: 'desc' },
      { title: '', colKey: 'handle', width: 48, minWidth: 48, field: 'handle' },
    ]);

    const headerHideTips = ref({
      true: {
        placement: 'top',
        content: `${t('点击展开全部')}`,
      },
      false: {
        placement: 'top',
        content: `${t('点击隐藏默认')}`,
      },
    });
    /**
     * 当前选中的头信息
     */
    const curHeaderData = computed((): IHeaderInfo => localHeaderInfo.value.find(item => item.key === tabActive.value));

    const checkUrl = computed(() =>
      /^(((ht|f)tps?):\/\/)[\w-]+(\.[\w-]+)+([\w.,@?^=%&:/~+#-{}]*[\w@?^=%&/~+#-{}])?$/.test(httpData.value.url)
    );

    const emitLocalHeaderInfo = () => {
      oldValue.value = localDataConvertToRequest(localHeaderInfo.value);
      const res = {
        method: httpData.value.method,
        url: httpData.value.url,
        ...oldValue.value,
      };
      emit('change', {
        riskLevel: data.value.riskLevel,
        timeout: data.value.timeout,
        res,
      });
    };
    onMounted(() => emitLocalHeaderInfo());

    const validator = () => {
      if (!checkUrl.value) {
        errorMsg.value.url = t('输入合法URL');
        return false;
      }
      return true;
    };

    /**
     * @description: 回显示数据
     * @param {any} data
     * @return {*}
     */
    const convertToLocalValue = (data: any) => {
      try {
        let { body = { dataType: 'default' }, authorize = { authType: 'none' } } = data;
        const { queryParams = [], headers = [], method, url, failedRetry } = data;
        body = transformDataKey(body, true);
        authorize = transformDataKey(authorize, true);
        // method url
        httpData.value.method = method;
        httpData.value.url = url;
        // 参数
        const paramsData = localHeaderInfo.value.find(item => item.key === 'Params');
        props.isEdit && queryParams.push({ isEnabled: true, key: '', value: '', desc: '' });
        paramsData.value = queryParams;
        // 认证
        const authData = localHeaderInfo.value.find(item => item.key === 'Authorization');
        const authType = authorize.auth_type;
        if (authType !== 'none') {
          authData[authType] = authorize.auth_config;
        }
        authData.type = authType;
        // 头部数据
        const headersData = localHeaderInfo.value.find(item => item.key === 'Headers');
        props.isEdit && headers.push({ isEnabled: true, key: '', value: '', desc: '' });
        headersData.value = headers;
        // body
        const bodyData = localHeaderInfo.value.find(item => item.key === 'Body');
        const bodyType = body.data_type;
        if (!['default', 'raw'].includes(bodyType)) {
          bodyData[bodyType] = transformDataKey(body.params);
        }
        if (bodyType === 'raw') {
          bodyData[bodyType] = { type: 'text', content: '' };
          bodyData[bodyType].content = body.content;
          bodyData[bodyType].type = body.content_type;
        }
        if (['form_data', 'x_www_form_urlencoded'].includes(bodyType)) {
          props.isEdit && bodyData[bodyType].push({ isEnabled: true, key: '', value: '', desc: '' });
        }
        bodyData.type = bodyType;
        // 重试配置
        const configData = localHeaderInfo.value.find(item => item.key === 'Seting');
        configData.value = failedRetry || { maxRetryTimes: 2, retryInterval: 60, timeout: 10 };
      } catch (error) {
        console.error('http 数据格式错误', error);
      }
    };
    watch(
      () => props.value,
      v => {
        data.value = v;
        if (JSON.stringify(v.data) === JSON.stringify(oldValue.value)) return;
        v.res && convertToLocalValue(deepClone(v.res));
      },
      { immediate: true, deep: true }
    );
    const methodChange = (v: TMethod) => {
      httpData.value.method = v;
      // 处理url query
      if (v === 'POST') httpData.value.url = httpData.value.url.replace(QUERY_REG, '');
      emitLocalHeaderInfo();
    };
    /**
     * @description: 处理url query
     * @param {*}
     * @return {*}
     */
    // const displayParamsToUrl = () => {
    //   if (httpData.value.method !== 'GET') return;
    //   const paramsData = localHeaderInfo.value.find(item => item.key === 'Params');
    //   const list = (paramsData.value as IParamsValueItem[]).filter(item => item.key && item.value);
    //   const { url } = httpData.value;
    //   const host = url.replace(QUERY_REG, '');
    //   if (!list.length) {
    //     httpData.value.url = host;
    //     return;
    //   }
    //   const strArr = list.map(item => `${item.key}=${item.value}`);
    //   const queryStr = `?${strArr.join('&')}`;
    //   httpData.value.url = host + queryStr;
    // };

    /**
     * @description: 表格输入添加空行
     * @param {*} tableData
     * @param {*} tplData
     * @return {*}
     */
    const handleAddRowIntoTable = (tableData, tplData = { isEnabled: true, key: '', value: '', desc: '' }) => {
      const temp = deepClone(tplData);
      const leng = tableData.length;
      const lastRow = tableData[leng - 1];
      const hasEmpty = rowIsEmpty(lastRow);
      !hasEmpty && tableData.push(temp);
      const secondLast = tableData[leng - 2];
      if (secondLast) {
        const isEmpty = rowIsEmpty(secondLast);
        if (isEmpty) tableData.splice(leng - 2, 1);
      }
    };
    const rowIsEmpty = (row: IParamsValueItem): boolean => {
      const keyMap = ['key', 'value', 'desc'];
      if (!row) return true;
      return Object.keys(row)
        .filter(key => keyMap.includes(key))
        .every(key => !row[key]);
    };
    const urlFocus = () => {
      errorMsg.value.url = '';
    };

    const urlChange = debounce(
      () => {
        if (checkUrl.value) errorMsg.value.url = '';
        emitLocalHeaderInfo();
      },
      300,
      false
    );

    const paramInput = debounce(
      () => {
        const tableData = curHeaderData.value.value;
        handleAddRowIntoTable(tableData);
        emitLocalHeaderInfo();
      },
      300,
      false
    );

    const bodyParamInput = debounce(
      () => {
        // 表格输入添加空行
        const { key } = curHeaderData.value;
        const { type } = curHeaderData.value;
        const typeMap = ['form_data', 'x_www_form_urlencoded'];
        if (key === 'Body' && typeMap.includes(type)) {
          let tableData = null;
          if (type === 'form_data') {
            tableData = curHeaderData.value.form_data;
          }
          if (type === 'x_www_form_urlencoded') {
            tableData = curHeaderData.value.x_www_form_urlencoded;
          }
          handleAddRowIntoTable(tableData);
        }

        emitLocalHeaderInfo();
      },
      300,
      false
    );

    const authParamInput = debounce(
      () => {
        emitLocalHeaderInfo();
      },
      300,
      false
    );

    const headersChange = debounce(
      () => {
        const tableData = curHeaderData.value.value;
        handleAddRowIntoTable(tableData);
        emitLocalHeaderInfo();
      },
      300,
      false
    );

    const setingChange = debounce(
      () => {
        emitLocalHeaderInfo();
      },
      300,
      false
    );

    const tabChange = (key: THeaderType) => {
      if (tabActive.value === key) return;
      tabActive.value = key;
    };

    /**
     * @description: 校验raw 的 json html xml格式
     * @param {*} type
     * @param {*} content
     * @return {*}
     */
    const handleRawBlur = (type, content) => {
      let errorMsg = '';
      const typeNameMap = {
        json: 'JSON',
        xml: 'XML',
        html: 'HTML',
      };
      if (content && type === 'json') {
        try {
          JSON.parse(content);
        } catch {
          errorMsg = t('文本不符合 {type} 格式', { type: typeNameMap[type] }) as string;
        }
      }
      if (content && ['html', 'xml'].includes(type)) {
        const parser = new DOMParser();
        const res = parser.parseFromString(content, 'application/xhtml+xml');
        const error = res.querySelector('parsererror');
        if (error) {
          errorMsg = t('文本不符合 {type} 格式', { type: typeNameMap[type] }) as string;
        }
      }
      rawErrorMsg.value = errorMsg;
      emitLocalHeaderInfo();
    };

    const handleDebug = () => {
      emit('debug');
    };

    /**
     * @description: 表格输入的作用域插槽
     * @param {*} data
     * @param {Function} changeFn
     * @param {*} deleteFn
     * @return {*}
     */
    const paramInputScopedSlots = (data, changeFn?, deleteFn?) => {
      return {
        default: (_, { rowIndex: index, col }) => {
          const prop = col.field;
          const item = data[index];
          const isEmpty = rowIsEmpty(item);
          const handleChecked = () => {
            emitLocalHeaderInfo();
          };
          if (!item) return undefined;
          if (prop === 'isEnabled') {
            return !isEmpty ? (
              <div class='table-checked'>
                <Checkbox
                  v-model={item[prop]}
                  disabled={item.isBuiltin || !props.isEdit}
                  onChange={handleChecked}
                />
              </div>
            ) : undefined;
          }
          if (prop === 'handle' && props.isEdit) {
            if ((isEmpty && index === data.length - 1) || item.isBuiltin) return undefined;
            return (
              <div class='table-handle'>
                <i
                  class='icon-monitor icon-mc-close'
                  onClick={() => deleteFn(index, item)}
                />
              </div>
            );
          }
          return (
            <span>
              {props.isEdit && prop ? (
                <Input
                  class='table-input'
                  v-model={item[prop]}
                  behavior='simplicity'
                  disabled={item.isBuiltin === undefined ? false : item.isBuiltin}
                  placeholder='请输入'
                  onChange={changeFn}
                />
              ) : (
                item[prop]
              )}
            </span>
          );
        },
      };
    };

    /**
     * @description: 头认证信息模版
     * @param {*}
     * @return {*}
     */
    const tplAuthorization = () => {
      const data = curHeaderData.value[curHeaderData.value.type];
      const radioChange = () => {
        emitLocalHeaderInfo();
      };
      const { type } = curHeaderData.value;
      return (
        <div class='header-content header-auth'>
          <Radio.Group
            v-model={curHeaderData.value.type}
            onChange={radioChange}
          >
            {authRadioList.value.map(item => (
              <Radio
                key={item.id}
                disabled={!props.isEdit}
                label={item.id}
                name={item.id}
              >
                {item.name}
              </Radio>
            ))}
          </Radio.Group>
          {type === 'bearer_token' ? (
            <div class='auth-params-wrap'>
              <div class='auth-params-label'>Token</div>
              <Input
                style={{ width: !props.isEdit ? 'none' : '520px' }}
                class='input'
                v-model={data.token}
                behavior='simplicity'
                disabled={!props.isEdit}
                onInput={authParamInput}
              />
            </div>
          ) : undefined}
          {type === 'basic_auth' ? (
            <div class='auth-params-wrap horizontal'>
              <div class='input-item'>
                <div class='auth-params-label'>{t('用户名')}</div>
                <Input
                  class='input'
                  v-model={data.username}
                  behavior='simplicity'
                  disabled={!props.isEdit}
                  onInput={authParamInput}
                />
              </div>
              <div class='input-item'>
                <div class='auth-params-label'>{t('密码')}</div>
                <Input
                  class='input'
                  v-model={data.password}
                  behavior='simplicity'
                  disabled={!props.isEdit}
                  type='password'
                  onInput={authParamInput}
                />
              </div>
            </div>
          ) : undefined}
          {type === 'none' ? <div class='header-tips'>{t('该请求不需要任何认证。')}</div> : undefined}
        </div>
      );
    };

    /**
     * @description: 头参数模板
     * @param {*}
     * @return {*}
     */
    const tplParams = () => {
      const data = curHeaderData.value.value as IParamsValueItem[];
      const handleDel = index => {
        (data as IParamsValueItem[]).splice(index, 1);
        emitLocalHeaderInfo();
      };
      const scopedSlots = paramInputScopedSlots(data, paramInput, handleDel);
      const columns = [];
      for (const item of paramTableColumns.value) {
        columns.push({ ...item, cell: scopedSlots.default });
      }
      return (
        <div class='header-content header-params'>
          <PrimaryTable
            columns={columns}
            data={data}
          />
        </div>
      );
    };

    /**
     * @description: 头信息模板
     * @param {*}
     * @return {*}
     */
    const tplHeaders = () => {
      const data = curHeaderData.value.value as IParamsValueItem[];
      let temp = [];
      data.forEach((item, index) => {
        item.index = index;
      });
      const isHide = curHeaderData.value.hide;
      const hideCount = data.filter(item => item.isBuiltin).length;
      temp = isHide ? data.filter(item => !item.isBuiltin) : data;
      const handleDel = (i, item) => {
        const { index } = item;
        data.splice(index, 1);
        emitLocalHeaderInfo();
      };
      const scopedSlots = paramInputScopedSlots(temp, headersChange, handleDel);
      const columns = [];
      for (const item of headersTableColumns.value) {
        columns.push({ ...item, render: scopedSlots.default });
      }
      return (
        <div class='header-content header-headers'>
          {hideCount ? (
            <div class='handle-hide-defult'>
              <i
                class={['icon-monitor', isHide ? 'icon-mc-invisible' : 'icon-mc-visual']}
                v-bk-tooltips={headerHideTips.value[`${isHide}`]}
                onClick={() => {
                  curHeaderData.value.hide = !isHide;
                }}
              />
              {isHide ? <span>{t('已隐藏{count}项', { count: hideCount })}</span> : <span>{t('已展开全部')}</span>}
            </div>
          ) : undefined}
          <PrimaryTable
            columns={columns}
            data={temp}
          />
        </div>
      );
    };

    /**
     * @description: body信息模板
     * @param {*}
     * @return {*}
     */
    const tplBody = () => {
      const rowTypeList = [
        { id: 'text', name: 'Text' },
        { id: 'json', name: 'JSON' },
        { id: 'html', name: 'HTML' },
        { id: 'xml', name: 'XML' },
      ];
      const radioChange = () => {
        emitLocalHeaderInfo();
      };
      const data = curHeaderData.value[curHeaderData.value.type];
      let scopedSlots = null;
      const columns = [];
      const isTable = ['form_data', 'x_www_form_urlencoded'].includes(curHeaderData.value.type);
      if (isTable) {
        const handleDel = index => {
          (data as IParamsValueItem[]).splice(index, 1);
          emitLocalHeaderInfo();
        };
        scopedSlots = paramInputScopedSlots(data, bodyParamInput, handleDel);
        paramTableColumns.value.forEach(column => {
          columns.push({ ...column, render: scopedSlots.default });
        });
      }
      return (
        <div class='header-content header-body'>
          <div class={['header-body-type', { readonly: !props.isEdit }]}>
            <Radio.Group
              class='body-radio-group'
              v-model={curHeaderData.value.type}
              onChange={radioChange}
            >
              {BodyRadioList.value.map(item => (
                <Radio
                  key={item.id}
                  disabled={!props.isEdit}
                  label={item.id}
                >
                  <span>{item.name}</span>
                </Radio>
              ))}
            </Radio.Group>
            {curHeaderData.value.type === 'raw' ? (
              <Select
                class='select select-wrap'
                v-model={data.type}
                behavior='simplicity'
                clearable={false}
                disabled={!props.isEdit}
                popover-min-width={100}
                onSelect={() => handleRawBlur(data.type, data.content)}
              >
                {rowTypeList.map(option => (
                  <Select.Option
                    id={option.id}
                    key={option.id}
                    name={option.name}
                  />
                ))}
              </Select>
            ) : undefined}
          </div>
          {}
          {curHeaderData.value.type === 'raw' ? (
            <div class='textarea-wrap'>
              <ResizeContainer
                v-slots={{
                  default: () => {
                    return [
                      <Input
                        key='content-textarea'
                        class='textarea'
                        v-model={data.content}
                        disabled={!props.isEdit}
                        type={'textarea'}
                        onBlur={() => handleRawBlur(data.type, data.content)}
                        onFocus={() => {
                          rawErrorMsg.value = '';
                        }}
                        onInput={bodyParamInput}
                      />,
                      rawErrorMsg.value && <p style='margin: 0; color: #ff5656;'>{rawErrorMsg.value}</p>,
                    ];
                  },
                }}
                minHeight={80}
                minWidth={200}
              />
            </div>
          ) : undefined}
          {isTable ? (
            <PrimaryTable
              class='table'
              columns={columns}
              data={data}
            />
          ) : undefined}
        </div>
      );
    };
    // 设置模板
    const tplSeting = () => {
      const valueKeyMap = curHeaderData.value.value;
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
          {setingInputList.value.map(item => {
            if (item.id === 'needPoll') {
              return content(
                item,
                <Switcher
                  class='switch'
                  v-model={valueKeyMap[item.id]}
                  disabled={!props.isEdit}
                  size='small'
                  theme='primary'
                  on-change={setingChange}
                />
              );
            }
            if (item.id === 'notifyInterval') {
              return content(
                item,
                <Input
                  class='input'
                  v-model={valueKeyMap[item.id]}
                  v-bk-tooltips={{ content: t('开启周期回调'), disabled: (valueKeyMap as ISetingValue).needPoll }}
                  behavior='simplicity'
                  disabled={!(valueKeyMap as ISetingValue).needPoll || !props.isEdit}
                  type='number'
                  onInput={setingChange}
                />
              );
            }
            return content(
              item,
              <Input
                class='input'
                v-model={valueKeyMap[item.id]}
                behavior='simplicity'
                disabled={!props.isEdit}
                type='number'
                onInput={setingChange}
              />
            );
          })}
        </div>
      );
    };

    // tab的label模板
    const tplTabLabel = (tab: IHeaderInfo) => {
      const { key } = tab;
      let tips: number | undefined;
      if (['Params', 'Headers'].includes(key)) {
        const value = (tab.value as IParamsValueItem[]).filter(item => item.isEnabled && !rowIsEmpty(item));
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
    };
    return {
      data,
      validator,
      httpData,
      errorMsg,
      methodList,
      curHeaderData,
      localHeaderInfo,
      tabActive,
      tabChange,
      handleDebug,
      tplSeting,
      tplBody,
      tplHeaders,
      tplParams,
      tplAuthorization,
      tplTabLabel,
      emitLocalHeaderInfo,
      urlFocus,
      urlChange,
      methodChange,
      t,
    };
  },
  render() {
    return (
      <div
        class={[
          'http-editor-wrap',
          {
            'http-editor-is-edit': this.isEdit,
            'http-editor-has-label': this.label,
          },
        ]}
      >
        {
          // http方法/url
          this.isEdit ? (
            <div class='http-method-url'>
              <Select
                class='select'
                v-model={this.httpData.method}
                behavior='simplicity'
                clearable={false}
                onChange={this.methodChange}
              >
                {this.methodList.map(option => (
                  <Select.Option
                    id={option}
                    key={option}
                    name={option}
                  />
                ))}
              </Select>
              <VerifyItem
                class='verify-url'
                v-slots={{
                  default: (
                    <Input
                      class='url-input'
                      v-model={this.httpData.url}
                      behavior='simplicity'
                      placeholder={this.t('输入请求 URL')}
                      onChange={this.urlChange}
                      onFocus={this.urlFocus}
                    />
                  ),
                }}
                errorMsg={this.errorMsg.url}
              />
            </div>
          ) : (
            <div class='dispaly-method-url'>
              {this.label ? <span class='label'>{this.label}</span> : undefined}
              <span class='method'>{this.httpData.method}</span>
              <span class='border' />
              <span class='url'>{this.httpData.url}</span>
            </div>
          )
        }
        {/* http头信息区域 */}
        <div class='http-header-wrap'>
          <div class='arrow' />
          <div class='http-header-main'>
            <div class='tab-select-wrap'>
              {this.localHeaderInfo.map((tab, i) => (
                <span
                  key={i}
                  class={['tab-item-wrap', { 'tab-item-active': tab.key === this.tabActive }]}
                  onClick={() => this.tabChange(tab.key)}
                >
                  {this.tplTabLabel(tab)}
                </span>
              ))}
            </div>
            {!!this.curHeaderData.desc && (
              <div class='header-desc'>
                <i class='icon-monitor icon-bangzhu' />
                <span class='desc-text'>{this.curHeaderData.desc}</span>
              </div>
            )}
            {
              // 头信息内容区
              this[`tpl${this.tabActive}`]()
            }
          </div>
        </div>
        {!this.isOnlyHttp && (
          <div>
            {this.isEdit && (
              <Button
                style={{ marginTop: '16px' }}
                theme='primary'
                outline
                onClick={this.handleDebug}
              >
                {this.t('调试')}
              </Button>
            )}
            {this.isEdit ? (
              <div class='sensitivity-failure-judgment'>
                <CommonItem
                  class='failure'
                  title={this.t('失败判断')}
                >
                  <i18n
                    class='failure-text'
                    path='当执行{0}分钟未结束按失败处理。'
                  >
                    <Input
                      class='input-inline'
                      v-model={this.data.timeout}
                      behavior={'simplicity'}
                      type={'number'}
                      on-change={() => this.emitLocalHeaderInfo()}
                    />
                  </i18n>
                </CommonItem>
              </div>
            ) : (
              <div class='sensitivity-failure-judgment'>
                <div
                  style={{ marginTop: '16px' }}
                  class='content-form-item'
                >
                  <div class='form-item-label'>{this.t('失败处理')}</div>
                  <div class='form-item-content'>
                    <i18n
                      class='failure-text'
                      path='当执行{0}分钟未结束按失败处理。'
                    >
                      {this.data.timeout}
                    </i18n>
                  </div>
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    );
  },
});
