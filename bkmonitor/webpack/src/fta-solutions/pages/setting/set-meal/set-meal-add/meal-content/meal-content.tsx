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

import { createDemoAction, getDemoActionDetail } from '../../../../../../monitor-api/modules/action';
import { deepClone, transformDataKey } from '../../../../../../monitor-common/utils/utils';
import SetMealAddModule from '../../../../../store/modules/set-meal-add';
import CommonItem from '../components/common-item';
import SimpleForm from '../components/simple-form';

import AlertNotice from './alert-notice';
import HttpCallBack from './http-callback';
import {
  IMealData,
  INotice,
  IPeripheral,
  IWebhook,
  mealDataInit,
  transformMealContentParams
} from './meal-content-data';
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
  callback: 'webhook'
};

@Component({
  name: 'MealContentNew'
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
    peripheral: {}
  };
  // 调试状态数据
  debugStatusData: {
    status?: '' | 'success' | 'failure' | 'received' | 'running';
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
            templateDetail: {}
          },
          riskLevel: 2,
          timeout: 10
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
  handleDebug(type: 'webhook' | 'peripheral') {
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
      const subTitle = hasVar ? varList.join(',') : '';
      if (hasVar) {
        const varInfos = varList.map(v => templateListMap.get(v.replace(/{{|}}/g, '')));
        const variableMap = {};
        varInfos.forEach(vInfo => {
          if (vInfo) {
            variableMap[vInfo.id] = vInfo;
          }
        });
        v = `${value}`.replace(/\{\{(.*?)\}\}/g, (match, key) => variableMap[key]?.example || '');
      } else {
        v = value;
      }
      const obj = {
        key: item.key,
        value: v,
        lable: item.formItemProps.label,
        placeholder: item?.formChildProps?.placeholder || '',
        subTitle
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

  // 调试数据替换周边系统变量数据
  setDebugPeripheralData() {
    const variableMap = {};
    this.debugPeripheralForm.forEach(item => {
      variableMap[item.key] = item.value;
    });
    this.debugData.peripheral.data.templateDetail = variableMap;
  }

  handleCloseDebug() {
    this.isShowDebug = false;
  }

  handleDebugWebhookDataChange(data: IWebhook) {
    this.debugData.webhook = data;
  }
  // 开始调试
  async handleDebugStart() {
    let executeConfigData = null;
    switch (this.debugData.type) {
      case 'webhook':
        executeConfigData = transformDataKey(
          transformMealContentParams({
            pluginType: 'webhook',
            webhook: this.debugData.webhook as any
          }),
          true
        );
        break;
      case 'peripheral':
        executeConfigData = this.peripheralExecuteConfig();
        break;
    }
    this.debugActionLoading = true;
    const actionId = await createDemoAction({
      execute_config: executeConfigData,
      plugin_id: this.data.id,
      creator: 'username',
      name: this.name || undefined
    })
      .then(data => data.action_id)
      .catch(() => 0);
    this.debugActionLoading = false;
    if (actionId) {
      this.isShowDebug = false;
      this.debugActionId = actionId;
      this.isQueryStatus = true;
      this.debugStatusData = await this.getDebugStatus();
    }
  }

  // 周边系统调试参数
  peripheralExecuteConfig() {
    let executeConfigData = null;
    this.setDebugPeripheralData();
    const { templateDetail } = this.debugData.peripheral.data;
    executeConfigData = transformDataKey(
      transformMealContentParams({
        pluginType: 'peripheral',
        peripheral: this.debugData.peripheral
      }),
      true
    );
    executeConfigData.template_detail = templateDetail;
    return executeConfigData;
  }

  // 轮询调试状态
  getDebugStatus() {
    let timer = null;
    // eslint-disable-next-line @typescript-eslint/no-misused-promises
    return new Promise(async resolve => {
      if (!this.isQueryStatus) {
        resolve({});
        return;
      }
      this.debugStatusData = await getDemoActionDetail({ action_id: this.debugActionId })
        .then(res => (this.isQueryStatus ? res : {}))
        .catch(() => false);
      if (this.debugStatusData.is_finished || !this.debugStatusData) {
        resolve(this.debugStatusData);
      } else {
        timer = setTimeout(() => {
          clearTimeout(timer);
          if (!this.isQueryStatus) {
            resolve({});
            return;
          }
          this.getDebugStatus().then(data => {
            if (!this.isQueryStatus) {
              this.debugStatusData = {};
              resolve(this.debugStatusData);
              return;
            }
            this.debugStatusData = data as any;
            if (this.debugStatusData.is_finished) {
              resolve(this.debugStatusData);
            }
          });
        }, 2000);
      }
    });
  }

  /**
   * @description: 停止调试
   * @param {*} isRestart 是否重新调试
   * @return {*}
   */
  handleStopDebug(isRestart = false) {
    this.debugStatusData = {};
    this.isQueryStatus = false;
    if (isRestart) {
      this.isShowDebug = true;
      if (this.debugData.type === 'peripheral') {
        this.debugData.peripheral = deepClone(this.data.peripheral);
      }
    }
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
              value={this.data.id}
              placeholder={this.$tc('选择')}
              class='select input-width'
              clearable={false}
              searchable={true}
              ext-popover-cls='meal-select-popover-warp'
              behavior='simplicity'
              onSelected={this.mealTypeChange}
            >
              {this.mealTypeList.map(group => (
                <bk-option-group
                  key={group.id}
                  name={group.name}
                >
                  {group.children.map(option => (
                    <bk-option
                      key={option.id}
                      id={option.id}
                      name={option.name}
                    >
                      <div class='meal-options'>
                        <span>{option.name}</span>
                        {option.pluginSource === 'peripheral' && option?.newInfo?.url && (
                          <span
                            class='icon-monitor icon-fenxiang icon-meal'
                            onClick={(e: Event) => {
                              e.stopPropagation();
                              this.handleJumpToSurrounding(option?.newInfo?.url);
                            }}
                            v-bk-tooltips={{ content: option?.newInfo?.tips, allowHTML: false }}
                          ></span>
                        )}
                      </div>
                    </bk-option>
                  ))}
                </bk-option-group>
              ))}
            </bk-select>
          </CommonItem>
        </div>
        {this.getDebugDialog()}
        {this.data.id ? (
          <div class='wrapper'>
            {(() => {
              if (this.data.pluginType === mealType.notice) {
                return (
                  <AlertNotice
                    ref='alertNoticeRef'
                    noticeData={this.data.notice}
                    onChange={this.handleNoticeDataChange}
                  ></AlertNotice>
                );
              }
              if (this.data.pluginType === mealType.callback) {
                return (
                  <HttpCallBack
                    ref='httpCallBackRef'
                    isEdit={true}
                    value={this.data.webhook}
                    variableList={this.getMessageTemplateList}
                    validatorHasVariable={true}
                    pluginId={this.data.id}
                    onChange={data => this.handleHttpCallBackChange(data)}
                    onDebug={() => this.handleDebug('webhook')}
                  ></HttpCallBack>
                );
              }
              if (this.data.pluginType !== '') {
                return (
                  <PeripheralSystem
                    ref='peripheralSystemRef'
                    type={this.type}
                    isInit={this.isInit}
                    id={this.data.id}
                    peripheralData={this.data.peripheral}
                    onChange={data => this.handlePeripheralChange(data)}
                    onDebug={() => this.handleDebug('peripheral')}
                    onInit={(v: boolean) => (this.isInit = v)}
                  ></PeripheralSystem>
                );
              }
            })()}
          </div>
        ) : undefined}
      </div>
    );
  }

  /* 以下为调试内容 */
  debugStatusText(content) {
    if (!content) return undefined;
    const contentText = { text: '', link: '' };
    const arrContent = content?.text?.split('$');
    contentText.text = arrContent?.[0] || '';
    contentText.link = arrContent?.[1] || '';
    return (
      <div class='info-jtnr'>
        {contentText.text}
        {contentText.link ? (
          <span
            class='info-jtnr-link'
            onClick={() => content?.url && window.open(content.url)}
          >
            <span class='icon-monitor icon-copy-link'></span>
            {contentText.link}
          </span>
        ) : undefined}
      </div>
    );
  }

  debugStatusIcon() {
    const loading = (
      <svg
        class='loading-svg'
        viewBox='0 0 64 64'
      >
        <g>
          <path d='M20.7,15c1.6,1.6,1.6,4.1,0,5.7s-4.1,1.6-5.7,0l-2.8-2.8c-1.6-1.6-1.6-4.1,0-5.7s4.1-1.6,5.7,0L20.7,15z' />
          <path d='M12,28c2.2,0,4,1.8,4,4s-1.8,4-4,4H8c-2.2,0-4-1.8-4-4s1.8-4,4-4H12z' />
          <path d='M15,43.3c1.6-1.6,4.1-1.6,5.7,0c1.6,1.6,1.6,4.1,0,5.7l-2.8,2.8c-1.6,1.6-4.1,1.6-5.7,0s-1.6-4.1,0-5.7L15,43.3z' />
          <path d='M28,52c0-2.2,1.8-4,4-4s4,1.8,4,4v4c0,2.2-1.8,4-4,4s-4-1.8-4-4V52z' />
          <path d='M51.8,46.1c1.6,1.6,1.6,4.1,0,5.7s-4.1,1.6-5.7,0L43.3,49c-1.6-1.6-1.6-4.1,0-5.7s4.1-1.6,5.7,0L51.8,46.1z' />
          <path d='M56,28c2.2,0,4,1.8,4,4s-1.8,4-4,4h-4c-2.2,0-4-1.8-4-4s1.8-4,4-4H56z' />
          <path d='M46.1,12.2c1.6-1.6,4.1-1.6,5.7,0s1.6,4.1,0,5.7l0,0L49,20.7c-1.6,1.6-4.1,1.6-5.7,0c-1.6-1.6-1.6-4.1,0-5.7L46.1,12.2z' />
          <path d='M28,8c0-2.2,1.8-4,4-4s4,1.8,4,4v4c0,2.2-1.8,4-4,4s-4-1.8-4-4V8z' />
        </g>
      </svg>
    );
    const statusMap = {
      received: loading,
      running: loading,
      success: (
        <div class='success'>
          <span class='icon-monitor icon-mc-check-small'></span>
        </div>
      ),
      failure: (
        <div class='failure'>
          <span class='icon-monitor icon-mc-close'></span>
        </div>
      )
    };
    return statusMap[this.debugStatusData?.status];
  }

  debugStatusTitle() {
    const statusMap = {
      received: `${this.$t('调试中...')}...`,
      running: `${this.$t('调试中...')}...`,
      success: this.$t('调试成功'),
      failure: this.$t('调试失败')
    };
    return statusMap[this.debugStatusData?.status];
  }

  debugStatusOperate() {
    const statusMap = {
      success: (
        <div class='status-operate'>
          {/* <bk-button theme="primary" style={{ marginRight: '8px' }}>{this.$t('查看详情')}</bk-button> */}
          <bk-button onClick={() => this.handleStopDebug()}>{this.$t('button-完成')}</bk-button>
        </div>
      ),
      failure: (
        <div class='status-operate'>
          <bk-button
            theme='primary'
            onClick={() => this.handleStopDebug(true)}
          >
            {this.$t('再次调试')}
          </bk-button>
        </div>
      )
    };
    return statusMap[this.debugStatusData?.status];
  }

  // 调试窗口
  getDebugDialog() {
    return [
      <bk-dialog
        value={this.isShowDebug}
        width={this.debugData.type === 'webhook' ? 766 : 480}
        extCls={'meal-content-debug-dialog'}
        renderDirective={'if'}
        maskClose={false}
        headerPosition={'left'}
        title={this.$t('输入变量')}
        on-cancel={this.handleCloseDebug}
      >
        <div>
          {this.debugData.type === 'webhook' && (
            <HttpCallBack
              isEdit={true}
              value={this.debugData.webhook}
              isOnlyHttp={true}
              onChange={data => this.handleDebugWebhookDataChange(data)}
            ></HttpCallBack>
          )}
          {this.debugData.type === 'peripheral' && (
            <SimpleForm
              forms={this.debugPeripheralForm}
              onChange={data => (this.debugPeripheralForm = data)}
            ></SimpleForm>
          )}
        </div>
        <div slot='footer'>
          <bk-button
            theme='primary'
            style={{ marginRight: '8px' }}
            loading={this.debugActionLoading}
            onClick={() => this.handleDebugStart()}
          >
            {this.$t('调试')}
          </bk-button>
          <bk-button onClick={this.handleCloseDebug}>{this.$t('取消')}</bk-button>
        </div>
      </bk-dialog>,
      <bk-dialog
        extCls={'meal-content-running-dialog'}
        value={!!this.debugStatusData?.status}
        width={400}
        renderDirective={'if'}
        maskClose={false}
        showFooter={false}
        on-cancel={() => this.handleStopDebug()}
      >
        <div class='status-content'>
          <div class='spinner'>{this.debugStatusIcon()}</div>
          <div class='status-title'>{this.debugStatusTitle()}</div>
          <div class='status-text'>{this.debugStatusText(this.debugStatusData?.content)}</div>
          {this.debugStatusOperate()}
        </div>
      </bk-dialog>
    ];
  }
}
