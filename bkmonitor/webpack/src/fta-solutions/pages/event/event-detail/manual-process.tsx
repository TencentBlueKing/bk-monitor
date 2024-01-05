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

import { batchCreate, getActionParams, getPluginTemplates } from '../../../../monitor-api/modules/action';
import { listActionConfig } from '../../../../monitor-api/modules/model';
import { random, transformDataKey } from '../../../../monitor-common/utils/utils';
import { actionConfigGroupList } from '../../../../monitor-pc/pages/strategy-config/strategy-config-set-new/alarm-handling/alarm-handling';
import GroupSelect from '../../../../monitor-pc/pages/strategy-config/strategy-config-set-new/components/group-select';
import Container from '../../setting/set-meal/set-meal-add/components/container';
import DynamicForm from '../../setting/set-meal/set-meal-add/components/dynamic-form/dynamic-form';
import HttpCallBack from '../../setting/set-meal/set-meal-add/meal-content/http-callback';
import {
  mealDataInit,
  transformMealContentParams
} from '../../setting/set-meal/set-meal-add/meal-content/meal-content-data';

import './manual-process.scss';

interface IProps {
  show?: boolean;
  alertIds?: number[] | string[];
  bizIds?: number[];
}
interface IEvent {
  onShowChange?: boolean;
  onDebugStatus?: number[];
  onMealInfo?: { name: string };
}

interface IFormRule {
  message: string;
  required: boolean;
  trigger: string;
}
interface IFormData {
  formList: {
    formChildProps?: { placeholder?: string };
    formItemProps?: {
      help_text?: string;
      label?: string;
      property?: string;
      required?: boolean;
    };
    key?: string;
    rules?: IFormRule;
  }[];
  formModel: { [propsName: string]: any };
  formRules: { [propsName: string]: IFormRule };
  name: string;
  templateId: string | number;
  timeout: number;
}

export interface IStatusRes {
  content: {
    action_plugin_type: string;
    text: string;
    url: string;
  };
  is_finished: boolean;
  status: string;
}

@Component
export default class ManualProcess extends tsc<IProps, IEvent> {
  @Prop({ type: Boolean, default: false }) show: boolean; // 是否显示
  @Prop({ type: Array, default: 0 }) alertIds: number[] | string[]; // 告警id
  @Prop({ type: Array, default: 0 }) bizIds: number[]; // 业务id
  @Ref('dynamicform') dynamicformRef: DynamicForm;
  @Ref('httpCallBack') httpCallBackRef: HttpCallBack;

  /* 动态表单 */
  formData: IFormData = {
    formList: [],
    formModel: {},
    formRules: {},
    name: window.i18n.t('参数填写') as string,
    templateId: '',
    timeout: 0
  };
  /* http会回调数据 */
  webhookData = mealDataInit().webhook;
  webhookKey = random(8);
  /* 处理套餐列表 */
  mealList: {
    id: string | number;
    name: string;
    plugin_type: string;
    plugin_id: number;
  }[] = [];
  /* 当前套餐信息 */
  mealId = '';
  curMeal: {
    name: string;
    plugin_id: number;
    id: number;
    bk_biz_id: number;
    plugin_type: string;
  } = null;

  /* 当前执行方案 */
  templateData: {
    name: string;
    id: string;
    allList: { [pulginId: string]: any[] };
  } = {
    name: '',
    id: '',
    allList: {}
  };

  loading = false;
  /* 保存时的loading */
  confirmLoading = false;

  /* 分组选择器key */
  groupSelectKey = random(8);

  tempbizId = 0;

  /* 分组选择器数据 */
  get noNoticeActionConfigList() {
    return actionConfigGroupList(this.mealList as any).filter(item => item.id !== 'notice');
  }

  @Watch('show')
  async handleShow(v: boolean) {
    this.confirmLoading = false;
    if (v) {
      this.loading = true;
      if (this.tempbizId !== this.bizIds[0]) {
        // 切换不同的业务需要初始化数据
        this.mealList = [];
        this.mealId = '';
        this.curMeal = null;
        this.groupSelectKey = random(8);
        this.templateData = { name: '', id: '', allList: {} };
        this.formData = {
          formList: [],
          formModel: {},
          formRules: {},
          name: window.i18n.t('参数填写') as string,
          templateId: '',
          timeout: 0
        };
        this.webhookData = mealDataInit().webhook;
        this.webhookKey = random(8);
      }
      this.tempbizId = this.bizIds[0] || this.$store.getters.bizId;
      if (!this.mealList.length) {
        this.mealList = await listActionConfig({
          bk_biz_id: this.bizIds[0] || this.$store.getters.bizId
        })
          .then(data => data.filter(item => item.is_enabled))
          .catch(() => []);
      }
      if (!this.mealList.length) {
        this.loading = false;
        return;
      }
      this.mealId = this.mealList[0].id as string;
      this.curMeal = this.mealList[0] as any;
      this.groupSelectKey = random(8);
      const data = await getActionParams({
        bk_biz_id: this.bizIds[0] || this.$store.getters.bizId,
        alert_ids: this.alertIds.map(item => String(item)),
        config_ids: [String(this.mealId)]
      }).catch(() => null);
      if (data) {
        await this.getTemplateData(data);
        this.setData(data);
      }
      this.loading = false;
    }
  }

  @Emit('showChange')
  handleShowChange(v: boolean) {
    return v;
  }
  @Emit('debugStatus')
  handleDebugStatus(res: number[]) {
    return res;
  }
  @Emit('mealInfo')
  handleMealInfo() {
    return this.curMeal;
  }

  // 处理动态表单所需数据
  handleDynamicFormData(data) {
    try {
      const formModel = {};
      const formRules = {};
      const formList = [];
      data.forEach(item => {
        const { key } = item;
        if (key === 'ENABLED_NOTICE_WAYS') {
          console.error(item);
        } else if (key === 'MESSAGE_QUEUE_DSN') {
          console.error(item);
        } else {
          formModel[item.key] = item.value;
          if (item.rules?.length) {
            formRules[item.key] = item.rules;
          } else if (item.formItemProps.required) {
            formRules[item.key] = [{ message: this.$tc('必填项'), required: true, trigger: 'blur' }];
          }
          formList.push(item);
        }
      });
      this.formData.formModel = formModel;
      this.formData.formRules = formRules;
      this.formData.formList = formList.map(item => {
        if (item.type === 'tag-input') {
          item.formChildProps['allow-auto-match'] = true;
        } else if (item.type === 'switcher') {
          item.formChildProps.size = 'small';
        }
        return item;
      });
    } catch (error) {
      console.error(error);
    }
  }

  /* 选择处理套餐 */
  async handleSelected(value) {
    const tempMealId = this.mealId;
    const tempCurMeal = this.curMeal;
    this.mealId = value;
    this.curMeal = this.mealList.find(item => item.id === value) as any;
    this.loading = true;
    const data = await getActionParams({
      bk_biz_id: String(this.bizIds[0]) || this.$store.getters.bizId,
      alert_ids: this.alertIds.map(item => String(item)),
      config_ids: [String(this.mealId)]
    }).catch(() => null);
    if (data) {
      await this.getTemplateData(data);
      this.setData(data);
    } else {
      this.mealId = tempMealId;
      this.curMeal = tempCurMeal;
    }
    this.loading = false;
  }

  /* 获取表单数据 */
  setData(data) {
    if (this.curMeal?.plugin_type === 'webhook') {
      const { templateDetail } = transformDataKey(data[0].execute_config);
      this.webhookData = {
        res: {
          headers: templateDetail.headers,
          queryParams: templateDetail.queryParams,
          authorize: templateDetail.authorize,
          body: templateDetail.body,
          failedRetry: {
            maxRetryTimes: templateDetail.failedRetry.maxRetryTimes,
            needPoll: templateDetail.needPoll,
            notifyInterval: templateDetail.notifyInterval / 60,
            retryInterval: templateDetail.failedRetry.retryInterval,
            timeout: templateDetail.failedRetry.timeout
          },
          url: templateDetail.url,
          method: templateDetail.method
        },
        // riskLevel: data.riskLevel,
        timeout: data[0].execute_config.timeout / 60
      } as any;
      this.webhookKey = random(8);
    } else {
      this.handleDynamicFormData(data[0].params);
      this.formData.templateId = data[0].execute_config.template_id;
      this.formData.timeout = data[0].execute_config.timeout;
      if (data[0].execute_config.origin_template_detail) {
        const obj = data[0].execute_config.origin_template_detail;
        this.formData.formList.forEach(item => {
          const value = obj?.[item.key] || '';
          const list = value.match(/\{\{(.*?)\}\}/g);
          const varList = list?.filter((item, index, arr) => arr.indexOf(item, 0) === index) || [];
          if (varList.length) {
            item.formItemProps.label = `${item.formItemProps.label}    ${varList.join(',')}`;
          }
        });
      }
    }
  }

  handleWebhookData(data) {
    this.webhookData = data;
  }

  /* 保存 */
  async handleConfirm() {
    if (!Boolean(this.mealId)) {
      return;
    }
    let paramsData = null;
    const commonParams = {
      ...this.curMeal,
      plugin_id: this.curMeal.plugin_id,
      config_id: this.mealId,
      bk_biz_id: this.bizIds[0],
      name: this.curMeal.name
    };
    if (this.curMeal?.plugin_type === 'webhook') {
      const validate = this.httpCallBackRef.validator();
      if (!validate) return;
      const webhookParams = transformDataKey(
        transformMealContentParams({
          pluginType: this.curMeal.plugin_type,
          webhook: this.webhookData as any
        }),
        true
      );
      paramsData = {
        execute_config: webhookParams,
        ...commonParams
      };
    } else {
      const validate =
        this.formData.formList.length && Object.keys(this.formData.formModel).length
          ? this.dynamicformRef.validator()
          : true;
      // eslint-disable-next-line @typescript-eslint/no-misused-promises
      if (!validate) return;
      paramsData = {
        execute_config: {
          template_detail: this.formData.formModel,
          template_id: this.formData.templateId,
          timeout: this.formData.timeout
        },
        ...commonParams
      };
    }
    const params = {
      operate_data_list: [
        {
          alert_ids: this.alertIds,
          action_configs: [paramsData]
        }
      ],
      bk_biz_id: this.bizIds[0] || this.$store.getters.bizId
    };
    this.confirmLoading = true;
    const res = await batchCreate(params).catch(() => null);
    this.confirmLoading = false;
    if (res.actions) {
      this.handleMealInfo();
      this.handleShowChange(false);
      this.handleDebugStatus(res.actions);
    }
  }
  /* 取消 */
  handleCancel() {
    this.handleShowChange(false);
  }
  async handleRefreshTemplate() {
    this.loading = true;
    this.mealList = await listActionConfig({
      bk_biz_id: this.bizIds[0] || this.$store.getters.bizId
    })
      .then(data => data.filter(item => item.is_enabled))
      .catch(() => []);
    this.loading = false;
  }

  /* 获取作业列表与当前作业信息 */
  async getTemplateData(data) {
    if (this.curMeal?.plugin_type !== 'webhook') {
      this.templateData.id = data[0].execute_config.template_id;
      if (!this.templateData.allList?.[this.curMeal?.plugin_id]?.length) {
        const res = await getPluginTemplates({
          bk_biz_id: this.bizIds[0] || this.$store.getters.bizId,
          plugin_id: this.curMeal.plugin_id
        }).catch(() => null);
        if (res) {
          this.templateData.allList[this.curMeal.plugin_id] = res.templates;
          this.templateData.name = res.name;
        }
      }
    }
  }

  render() {
    return (
      <bk-dialog
        ext-cls='manual-process-dialog-wrap'
        value={this.show}
        mask-close={true}
        header-position='left'
        width={800}
        title={this.$t('手动处理')}
        loading={this.confirmLoading}
        on-value-change={this.handleShowChange}
      >
        <div
          class='formdata-wrap'
          v-bkloading={{ isLoading: this.loading }}
        >
          <div class='meal-list'>
            <div class='title'>{this.$t('处理套餐')}</div>
            <div class='wrap'>
              <GroupSelect
                key={this.groupSelectKey}
                value={this.mealId}
                list={this.noNoticeActionConfigList}
                placeholder={this.$tc('选择套餐')}
                // eslint-disable-next-line @typescript-eslint/no-misused-promises
                onChange={this.handleSelected}
              ></GroupSelect>
              {/* eslint-disable-next-line @typescript-eslint/no-misused-promises */}
              <i
                class='icon-monitor icon-shuaxin'
                onClick={this.handleRefreshTemplate}
              ></i>
            </div>
          </div>
          {this.curMeal?.plugin_type !== 'webhook' && (
            <div class='template-list'>
              <div class='title'>{this.templateData.name}</div>
              <bk-select
                class='wrap-select'
                v-model={this.templateData.id}
                behavior='simplicity'
                readonly
              >
                {(this.templateData.allList?.[this.curMeal?.plugin_id] || []).map(item => (
                  <bk-option
                    key={item.id}
                    id={item.id}
                    name={item.name}
                  ></bk-option>
                ))}
              </bk-select>
            </div>
          )}
          <div class='meal-content'>
            {this.curMeal?.plugin_type === 'webhook' ? (
              <HttpCallBack
                ref='httpCallBack'
                key={this.webhookKey}
                value={this.webhookData}
                isEdit={true}
                isOnlyHttp={true}
                onChange={this.handleWebhookData}
              ></HttpCallBack>
            ) : (
              <Container title={this.formData.name}>
                {this.formData.formList.length && Object.keys(this.formData.formModel).length ? (
                  <DynamicForm
                    ref='dynamicform'
                    labelWidth={500}
                    formList={this.formData.formList}
                    formModel={this.formData.formModel}
                    formRules={this.formData.formRules}
                    noAutoInput={true}
                  ></DynamicForm>
                ) : (
                  [<span class='nodata'>{this.$t('当前无需填写参数')}</span>, <br />]
                )}
              </Container>
            )}
          </div>
          {!this.mealList.length ? (
            <div class='no-meal'>
              <i18n path='当前业务下没有可使用的处理套餐，请前往{0}页面配置'>
                <span
                  class='link'
                  onClick={() => {
                    this.$router.push({ name: 'set-meal' });
                  }}
                >
                  {this.$t('处理套餐')}
                </span>
              </i18n>
            </div>
          ) : undefined}
        </div>
        <div slot='footer'>
          <bk-button
            theme='primary'
            loading={this.confirmLoading}
            onClick={() => !this.confirmLoading && this.handleConfirm()}
          >
            {window.i18n.t('确定')}
          </bk-button>
          <bk-button
            style={{ marginLeft: '10px' }}
            onClick={() => this.handleCancel()}
          >
            {window.i18n.t('取消')}
          </bk-button>
        </div>
      </bk-dialog>
    );
  }
}
