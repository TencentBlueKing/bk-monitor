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
import { Component, Emit, Prop, Ref, Watch } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import { deepClone } from 'monitor-common/utils/utils';

import SetMealAddModule from '../../../../../store/modules/set-meal-add';
import CommonItem from '../components/common-item';
import AlertNotice from './alert-notice';
import HttpCallBack from './http-callback';
import { type IMealData, type INotice, type IPeripheral, type IWebhook, mealDataInit } from './meal-content-data';
import MealDebugDialog from './meal-debug-dialog';
import PeripheralSystem from './peripheral-system';
import { setVariableToString } from './utils';

import './meal-content.scss';

export interface IMealTypeList {
  id?: number | string;
  name?: string;
  children?: IMealTypeList[];
  hasChild?: boolean;
  pluginType?: 'notice' | 'webhook' | string;
  pluginSource?: string;
  newInfo?: {
    url: string;
    tips: string;
  };
}

interface IMealContentNewProps {
  mealTypeList?: IMealTypeList[];
  mealData?: IMealData;
  name?: string; // 套餐名
  type?: PageType;
  refreshKey?: string;
}
interface IMealContentNewEvent {
  onChange?: IMealData;
}

interface IDebugPeripheral {
  isVariable?: boolean; // 是否为变量
  key?: string; // 是变量的话此值有效
  value?: string; // 变量值
  label?: string; // 输入框title
}

type PageType = 'add' | 'edit';

const mealType = {
  notice: 'notice',
  callback: 'webhook',
};

@Component({
  name: 'MealContentNew',
})
export default class MealContentNew extends tsc<IMealContentNewProps, IMealContentNewEvent> {
  @Prop({ type: Object, default: () => ({}) }) mealData: IMealData;
  @Prop({ type: Array, default: () => [] }) mealTypeList: IMealTypeList[];
  @Prop({ type: String, default: '' }) name: string;
  @Prop({ type: String, default: 'add' }) type: PageType;
  @Prop({ type: String, default: '' }) refreshKey: string;
  @Ref('alertNoticeRef') alertNoticeRef: AlertNotice;
  @Ref('peripheralSystemRef') peripheralSystemRef: PeripheralSystem;
  @Ref('httpCallBackRef') httpCallBackRef: HttpCallBack;
  data: IMealData = mealDataInit();

  isLoadPeripheral = false;
  isShowDebug = false;

  // 调试数据
  debugData: { type: string; webhook: IWebhook; peripheral: IPeripheral } = {
    type: '',
    webhook: {},
    peripheral: {},
  };
  // 调试状态数据
  debugStatusData: {
    status?: '' | 'failure' | 'received' | 'running' | 'success';
    is_finished?: boolean;
    content?: { text: string; url: string; action_plugin_type: string };
  } = {};
  // 调试单据id
  debugActionId = 0;
  // 获取单据id时的loading
  debugActionLoading = false;
  // 是否正在轮询状态中
  isQueryStatus = false;
  // 周边系统调试的表单数据
  debugPeripheralForm: IDebugPeripheral[] = [];

  isInit = true;

  get getMessageTemplateList() {
    return SetMealAddModule.getMessageTemplateList;
  }

  destroyed() {
    this.isQueryStatus = false;
  }

  // @Watch('mealData', { immediate: true, deep: true })
  // async handleMealData(data: IMealData) {
  //   this.data = data;
  //   if (this.data.pluginType !== '' && ![mealType.notice, mealType.callback].includes(this.data.pluginType)
  //     && !this.peripheralSystemRef?.formTemplateId && !this.isLoadPeripheral
  //     && this.data.peripheral.data.formTemplateId) {
  //     this.isLoadPeripheral = true;
  //     await this.mealTypeChange(this.data.id, false);
  //     await this.$nextTick();
  //     this.peripheralSystemRef.handleFormDataChange(this.data.peripheral.data.formTemplateId);
  //   }
  // }

  @Watch('refreshKey')
  async updateDate() {
    this.data = this.mealData;
    await this.mealTypeChange(this.data.id, false);
    await this.$nextTick();
    this.peripheralSystemRef?.handleFormDataChange?.(this.data.peripheral.data.formTemplateId);
  }

  /**
   * @description: 切换套餐
   * @param {number} id
   * @return {*}
   */
  async mealTypeChange(id: number, isPeripheralDataInit = true) {
    const mealTypes = [];
    this.mealTypeList.forEach(item => {
      mealTypes.push(...item.children);
    });
    const mealTypeItem = mealTypes.find(item => item.id === id);
    this.data.id = id;
    this.data.name = mealTypeItem.name;
    this.data.pluginType = mealTypeItem.pluginType;
    const isPeripheral = ![mealType.callback, mealType.notice].includes(mealTypeItem.pluginType);
    await this.$nextTick();
    if (this.peripheralSystemRef && isPeripheral) {
      if (isPeripheralDataInit) {
        this.data.peripheral = {
          data: {
            formTemplateId: '',
            templateDetail: {},
          },
          riskLevel: 2,
          timeout: 10,
        };
      }
      this.peripheralSystemRef.formTemplateId = '';
      this.peripheralSystemRef.formTitle = '';
      await this.peripheralSystemRef.getPluginTemplates(id);
    }
  }

  @Emit('change')
  handleChange() {
    return this.data;
  }
  /**
   * @description: 告警通知数据
   * @param {INotice} data
   * @return {*}
   */
  handleNoticeDataChange(data: INotice) {
    this.data.notice = data;
    this.handleChange();
  }
  /**
   * @description: http回调数据
   * @param {IWebhook} data
   * @return {*}
   */
  handleHttpCallBackChange(data: IWebhook) {
    this.data.webhook = data;
    this.handleChange();
  }
  /**
   * @description: 周边系统数据
   * @param {IPeripheral} data
   * @return {*}
   */
  handlePeripheralChange(data: IPeripheral) {
    this.data.peripheral = data;
    this.handleChange();
  }

  // 校验
  async validator() {
    if (this.data.pluginType === mealType.notice) {
      const is = await this.alertNoticeRef.validator();
      return is;
    }
    if (this.data.pluginType === mealType.callback) {
      return this.httpCallBackRef.validator();
    }
    if (this.data.pluginType !== '') {
      const is = await this.peripheralSystemRef.validator().catch(() => false);
      return is;
    }
    return true;
  }

  /* 调试内容start */
  handleDebug(type: 'peripheral' | 'webhook') {
    switch (type) {
      case 'peripheral':
        this.debugData.peripheral = deepClone(this.data.peripheral);
        this.getVariableItems();
        break;
      case 'webhook':
        this.debugData.webhook = deepClone(this.data.webhook);
        this.getHttpCallbackVariables();
        break;
    }
    this.debugData.type = type;
    this.isShowDebug = true;
  }

  /* 获取http回调变量数据 */
  getHttpCallbackVariables() {
    const templateListMap = new Map();
    this.getMessageTemplateList.forEach(template => {
      templateListMap.set(template.id, template);
    });
    const setVariable = obj => {
      const tempObj = {};
      const objKeys = Object.keys(obj);
      objKeys.forEach(key => {
        if (typeof obj[key] === 'string') {
          tempObj[key] = setVariableToString(templateListMap, obj[key]);
        } else if (typeof obj[key] === 'object') {
          if (Array.isArray(obj[key])) {
            tempObj[key] = [];
            obj[key].forEach(item => {
              tempObj[key].push(setVariable(item));
            });
          } else {
            tempObj[key] = setVariable(obj[key]);
          }
        } else {
          tempObj[key] = obj[key];
        }
      });
      return tempObj;
    };
    this.debugData.webhook = setVariable(this.debugData.webhook);
  }

  // 获取调试变量数据
  getVariableItems() {
    const formList = deepClone(this.peripheralSystemRef.formList);
    const peripheralData = deepClone(this.data.peripheral.data.templateDetail);
    const variableList = [];
    const templateListMap = new Map();
    this.getMessageTemplateList.forEach(template => {
      templateListMap.set(template.id, template);
    });
    formList.forEach(item => {
      let v = '';
      const value = peripheralData[item.key];
      const varList = this.getVariableStrList(value); // 字符串内的变量
      const hasVar = !!varList.length; // 是否含有变量
      // const subTitle = hasVar ? varList.join(',') : '';
      if (hasVar) {
        const varInfos = varList.map(v => templateListMap.get(v.replace(/{{|}}/g, '')));
        const variableMap = {};
        varInfos.forEach(vInfo => {
          if (vInfo) {
            variableMap[vInfo.id] = vInfo;
          }
        });
        v = `${value}`.replace(/\{\{(.*?)\}\}/g, (_match, key) => variableMap[key]?.example || '');
      } else {
        v = value;
      }
      const vPlaceholder = v ? `${this.$t('案例')} : ${v}` : '';
      const obj = {
        key: item.key,
        value: '',
        lable: item.formItemProps.label,
        placeholder: vPlaceholder || item?.formChildProps?.placeholder || '',
        subTitle: '',
        required: !!item?.formItemProps?.required,
      };
      variableList.push(obj);
    });
    this.debugPeripheralForm = variableList;
  }

  // 获取字符串里面的变量
  getVariableStrList(value: string) {
    const list = value.match(/\{\{(.*?)\}\}/g); // .*?非贪婪匹配模式
    return list?.filter((item, index, arr) => arr.indexOf(item, 0) === index) || []; // 去重
  }

  handleDebugWebhookDataChange(data: IWebhook) {
    this.debugData.webhook = data;
  }

  /* 跳转周边系统 */
  handleJumpToSurrounding(url: string) {
    if (url) window.open(url);
  }

  /* 调试内容end */

  render() {
    return (
      <div class='meal-content-new'>
        <div class='header'>
          <div class='header-title'>{this.$t('套餐信息')}</div>
          <CommonItem
            title={this.$tc('套餐类型')}
            required
          >
            <bk-select
              class='select input-width'
              behavior='simplicity'
              clearable={false}
              ext-popover-cls='meal-select-popover-warp'
              placeholder={this.$tc('选择')}
              searchable={true}
              value={this.data.id}
              onSelected={this.mealTypeChange}
            >
              {this.mealTypeList.map(group => (
                <bk-option-group
                  key={group.id}
                  name={group.name}
                >
                  {group.children.map(option => (
                    <bk-option
                      id={option.id}
                      key={option.id}
                      name={option.name}
                    >
                      <div class='meal-options'>
                        <span>{option.name}</span>
                        {option.pluginSource === 'peripheral' && option?.newInfo?.url && (
                          <span
                            class='icon-monitor icon-fenxiang icon-meal'
                            v-bk-tooltips={{ content: option?.newInfo?.tips, allowHTML: false }}
                            onClick={(e: Event) => {
                              e.stopPropagation();
                              this.handleJumpToSurrounding(option?.newInfo?.url);
                            }}
                          />
                        )}
                      </div>
                    </bk-option>
                  ))}
                </bk-option-group>
              ))}
            </bk-select>
          </CommonItem>
        </div>
        {this.data.id ? (
          <div class='wrapper'>
            {(() => {
              if (this.data.pluginType === mealType.notice) {
                return (
                  <AlertNotice
                    ref='alertNoticeRef'
                    noticeData={this.data.notice}
                    onChange={this.handleNoticeDataChange}
                  />
                );
              }
              if (this.data.pluginType === mealType.callback) {
                return (
                  <HttpCallBack
                    ref='httpCallBackRef'
                    isEdit={true}
                    pluginId={this.data.id}
                    validatorHasVariable={true}
                    value={this.data.webhook}
                    variableList={this.getMessageTemplateList}
                    onChange={data => this.handleHttpCallBackChange(data)}
                    onDebug={() => this.handleDebug('webhook')}
                  />
                );
              }
              if (this.data.pluginType !== '') {
                return (
                  <PeripheralSystem
                    id={this.data.id}
                    ref='peripheralSystemRef'
                    isInit={this.isInit}
                    peripheralData={this.data.peripheral}
                    type={this.type}
                    onChange={data => this.handlePeripheralChange(data)}
                    onDebug={() => this.handleDebug('peripheral')}
                    onInit={(v: boolean) => (this.isInit = v)}
                  />
                );
              }
            })()}
          </div>
        ) : undefined}
        <MealDebugDialog
          debugData={this.debugData}
          debugPeripheralForm={this.debugPeripheralForm}
          mealName={this.name}
          pluginId={this.data.id}
          show={this.isShowDebug}
          onDebugPeripheralDataChange={v => (this.debugPeripheralForm = v)}
          onDebugPeripheralStop={() => (this.debugData.peripheral = deepClone(this.data.peripheral))}
          onDebugWebhookDataChange={v => this.handleDebugWebhookDataChange(v)}
          onShowChange={v => (this.isShowDebug = v)}
        />
      </div>
    );
  }
}
