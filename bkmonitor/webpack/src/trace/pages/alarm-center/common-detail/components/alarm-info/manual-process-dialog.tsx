/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 *
 * Copyright (C) 2017-2025 Tencent.  All rights reserved.
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

import { computed, ref as deepRef, defineComponent, shallowRef, useTemplateRef, watch } from 'vue';

import { Button, Dialog, Loading, Select } from 'bkui-vue';
import { batchCreate, getActionParams, getPluginTemplates } from 'monitor-api/modules/action';
import { listActionConfig } from 'monitor-api/modules/model';
import { random, transformDataKey } from 'monitor-common/utils/utils';
import { useI18n } from 'vue-i18n';
import { useRouter } from 'vue-router';

import { actionConfigGroupList } from '../../../utils';
import DynamicForm from '@/pages/failure/alarm-detail/dynamic-form/dynamic-form';
import GroupSelect from '@/pages/failure/alarm-detail/group-select';
import Container from '@/pages/failure/alarm-detail/set-meal/set-meal-add/components/container';
import HttpCallBack from '@/pages/failure/alarm-detail/set-meal/set-meal-add/meal-content/http-callback';
import {
  mealDataInit,
  transformMealContentParams,
} from '@/pages/failure/alarm-detail/set-meal/set-meal-add/meal-content/meal-content-data';

import type { MealInfo } from '../../../typings';

import './manual-process-dialog.scss';

interface IFormData {
  formModel: { [propsName: string]: any };
  formRules: { [propsName: string]: IFormRule };
  name: string;
  templateId: number | string;
  timeout: number;
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
}
interface IFormRule {
  message: string;
  required: boolean;
  trigger: string;
}

export default defineComponent({
  name: 'ManualProcessDialog',
  props: {
    show: {
      type: Boolean,
      default: false,
    },
    alarmIds: {
      type: Array,
      default: () => [],
    },
    alarmBizId: {
      type: Number,
      default: null,
    },
  },
  emits: {
    'update:show': (show: boolean) => typeof show === 'boolean',
    debugStatus: (res: number[]) => Array.isArray(res),
    mealInfo: (res: any) => typeof res === 'object',
  },
  setup(props, { emit }) {
    const { t } = useI18n();
    const router = useRouter();
    const dynamicform = useTemplateRef<InstanceType<typeof DynamicForm>>('dynamicform');
    const httpCallBack = useTemplateRef<InstanceType<typeof HttpCallBack>>('httpCallBack');
    /* 动态表单 */
    const formData = deepRef<IFormData>({
      formList: [],
      formModel: {},
      formRules: {},
      name: t('参数填写') as string,
      templateId: '',
      timeout: 0,
    });
    /* http会回调数据 */
    const webhookData = shallowRef(mealDataInit().webhook);
    const webhookKey = shallowRef(random(8));
    /* 处理套餐列表 */
    const mealList = shallowRef<
      {
        id: number | string;
        name: string;
        plugin_id: number;
        plugin_type: string;
      }[]
    >([]);

    const mealId = shallowRef('');
    const curMeal = shallowRef<MealInfo>(null);
    /* 当前执行方案 */
    const templateData = deepRef<{
      allList: { [pulginId: string]: any[] };
      id: string;
      name: string;
    }>({
      name: '',
      id: '',
      allList: {},
    });
    const loading = shallowRef(false);
    /* 保存时的loading */
    const confirmLoading = shallowRef(false);
    /* 分组选择器key */
    const groupSelectKey = shallowRef(random(8));
    const tempBizId = shallowRef(null);
    /* 分组选择器数据 */
    const noNoticeActionConfigList = computed(() =>
      actionConfigGroupList(mealList.value as any).filter(item => item.id !== 'notice')
    );

    const handleShowChange = (v?: boolean) => {
      emit('update:show', v);
    };

    const handleDebugStatus = (res: number[]) => {
      emit('debugStatus', res);
    };
    const handleMealInfo = () => {
      emit('mealInfo', curMeal.value);
    };
    // 处理动态表单所需数据
    const handleDynamicFormData = data => {
      try {
        const formModel = {};
        const formRules = {};
        const formList = [];
        for (const item of data) {
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
              formRules[item.key] = [{ message: t('必填项'), required: true, trigger: 'blur' }];
            }
            formList.push(item);
          }
        }
        formData.value.formModel = formModel;
        formData.value.formRules = formRules;
        formData.value.formList = formList.map(item => {
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
    };

    /* 选择处理套餐 */
    const handleSelected = async value => {
      const tempMealId = mealId.value;
      const tempCurMeal = curMeal.value;
      console.log(curMeal.value);
      mealId.value = value;
      curMeal.value = mealList.value.find(item => item.id === value) as any;
      loading.value = true;
      const data = await getActionParams({
        bk_biz_id: String(props.alarmBizId),
        alert_ids: props.alarmIds.map(item => String(item)),
        config_ids: [String(mealId.value)],
      }).catch(() => null);
      if (data) {
        await getTemplateData(data);
        setData(data);
      } else {
        mealId.value = tempMealId;
        curMeal.value = tempCurMeal;
      }
      loading.value = false;
    };
    /* 获取表单数据 */
    const setData = data => {
      if (curMeal.value?.plugin_type === 'webhook') {
        const { templateDetail } = transformDataKey(data[0].execute_config);
        webhookData.value = {
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
              timeout: templateDetail.failedRetry.timeout,
            },
            url: templateDetail.url,
            method: templateDetail.method,
          },
          // riskLevel: data.riskLevel,
          timeout: data[0].execute_config.timeout / 60,
        } as any;
        webhookKey.value = random(8);
      } else {
        handleDynamicFormData(data[0].params);
        formData.value.templateId = data[0].execute_config.template_id;
        formData.value.timeout = data[0].execute_config.timeout;
        if (data[0].execute_config.origin_template_detail) {
          const obj = data[0].execute_config.origin_template_detail;
          for (const item of formData.value.formList) {
            const value = obj?.[item.key] || '';
            const list = value.match(/\{\{(.*?)\}\}/g);
            const varList = list?.filter((item, index, arr) => arr.indexOf(item, 0) === index) || [];
            if (varList.length) {
              item.formItemProps.label = `${item.formItemProps.label}    ${varList.join(',')}`;
            }
          }
        }
      }
    };

    const handleWebhookData = data => {
      webhookData.value = data;
    };
    /* 保存 */
    const handleConfirm = async () => {
      if (!mealId.value) {
        return;
      }
      let paramsData = null;
      const commonParams = {
        ...curMeal.value,
        plugin_id: curMeal.value.plugin_id,
        config_id: mealId.value,
        bk_biz_id: props.alarmBizId,
        name: curMeal.value.name,
      };
      if (curMeal.value?.plugin_type === 'webhook') {
        const validate = httpCallBack.value.validator();
        if (!validate) return;
        const webhookParams = transformDataKey(
          transformMealContentParams({
            pluginType: curMeal.value.plugin_type,
            webhook: webhookData.value as any,
          }),
          true
        );
        paramsData = {
          execute_config: webhookParams,
          ...commonParams,
        };
      } else {
        const validate =
          formData.value.formList.length && Object.keys(formData.value.formModel).length
            ? dynamicform.value.validator()
            : true;

        if (!validate) return;
        paramsData = {
          execute_config: {
            template_detail: formData.value.formModel,
            template_id: formData.value.templateId,
            timeout: formData.value.timeout,
          },
          ...commonParams,
        };
      }
      const params = {
        operate_data_list: [
          {
            alert_ids: props.alarmIds,
            action_configs: [paramsData],
          },
        ],
        bk_biz_id: props.alarmBizId,
      };
      confirmLoading.value = true;
      const res = await batchCreate(params).catch(() => null);
      confirmLoading.value = false;
      if (res.actions) {
        handleMealInfo();
        handleShowChange(false);
        handleDebugStatus(res.actions);
      }
    };

    /* 取消 */
    const handleCancel = () => {
      handleShowChange(false);
    };
    const handleRefreshTemplate = async () => {
      loading.value = true;
      mealList.value = await listActionConfig({
        bk_biz_id: props.alarmBizId,
      })
        .then(data => data.filter(item => item.is_enabled))
        .catch(() => []);
      loading.value = false;
    };

    /* 获取作业列表与当前作业信息 */
    const getTemplateData = async data => {
      if (curMeal.value?.plugin_type !== 'webhook') {
        templateData.value.id = data[0].execute_config.template_id;
        if (!templateData.value.allList?.[curMeal.value?.plugin_id]?.length) {
          const res = await getPluginTemplates({
            bk_biz_id: props.alarmBizId,
            plugin_id: curMeal.value.plugin_id,
          }).catch(() => null);
          if (res) {
            templateData.value.allList[curMeal.value.plugin_id] = res.templates;
            templateData.value.name = res.name;
          }
        }
      }
    };

    watch(
      () => props.show,
      async v => {
        confirmLoading.value = false;
        if (v) {
          loading.value = true;
          if (tempBizId.value !== props.alarmBizId) {
            // 切换不同的业务需要初始化数据
            mealList.value = [];
            mealId.value = '';
            curMeal.value = null;
            groupSelectKey.value = random(8);
            templateData.value = { name: '', id: '', allList: {} };
            formData.value = {
              formList: [],
              formModel: {},
              formRules: {},
              name: t('参数填写') as string,
              templateId: '',
              timeout: 0,
            };
            webhookData.value = mealDataInit().webhook;
            webhookKey.value = random(8);
          }
          tempBizId.value = props.alarmBizId;
          if (!mealList.value.length) {
            mealList.value = await listActionConfig({
              bk_biz_id: props.alarmBizId, // || this.$store.getters.bizId
            })
              .then(data => data.filter(item => item.is_enabled))
              .catch(() => []);
          }
          if (!mealList.value.length) {
            loading.value = false;
            return;
          }
          mealId.value = mealList.value[0].id as string;
          curMeal.value = mealList.value[0] as any;
          groupSelectKey.value = random(8);
          const data = await getActionParams({
            bk_biz_id: props.alarmBizId, // || this.$store.getters.bizId,
            alert_ids: props.alarmIds.map(item => String(item)),
            config_ids: [String(mealId.value)],
          }).catch(() => null);
          if (data) {
            await getTemplateData(data);
            setData(data);
          }
          loading.value = false;
        }
      }
    );
    return {
      confirmLoading,
      httpCallBack,
      dynamicform,
      groupSelectKey,
      curMeal,
      webhookKey,
      formData,
      mealId,
      templateData,
      handleCancel,
      mealList,
      webhookData,
      noNoticeActionConfigList,
      loading,
      handleSelected,
      handleWebhookData,
      handleShowChange,
      handleConfirm,
      handleRefreshTemplate,
      t,
      router,
    };
  },
  render() {
    return (
      <Dialog
        width={800}
        class='manual-process-dialog-wrap'
        v-slots={{
          default: () => (
            <Loading loading={this.loading}>
              <div class='formdata-wrap'>
                <div class='meal-list'>
                  <div class='title'>{this.t('处理套餐')}</div>
                  <div class='wrap'>
                    <GroupSelect
                      key={this.groupSelectKey}
                      list={this.noNoticeActionConfigList}
                      placeholder={this.t('选择套餐')}
                      value={this.mealId}
                      onChange={this.handleSelected}
                    />
                    <i
                      class='icon-monitor icon-shuaxin'
                      onClick={this.handleRefreshTemplate}
                    />
                  </div>
                </div>
                {this.curMeal?.plugin_type !== 'webhook' && (
                  <div class='template-list'>
                    <div class='title'>{this.templateData.name}</div>
                    <Select
                      class='wrap-select'
                      v-model={this.templateData.id}
                      v-slots={{
                        default: () => {
                          return (this.templateData.allList?.[this.curMeal?.plugin_id] || []).map(item => {
                            return (
                              <Select.Option
                                id={Number(item.id)}
                                key={item.id}
                                name={item.name}
                              />
                            );
                          });
                        },
                      }}
                      behavior='simplicity'
                      disabled={true}
                      placeholder={this.t('请选择')}
                    />
                  </div>
                )}
                <div class='meal-content'>
                  {this.curMeal?.plugin_type === 'webhook' ? (
                    <HttpCallBack
                      key={this.webhookKey}
                      ref='httpCallBack'
                      isEdit={true}
                      isOnlyHttp={true}
                      value={this.webhookData}
                      onChange={this.handleWebhookData}
                    />
                  ) : (
                    <Container
                      v-slots={{
                        default: () => {
                          return this.formData.formList.length && Object.keys(this.formData.formModel).length ? (
                            <DynamicForm
                              ref='dynamicform'
                              formList={this.formData.formList}
                              formModel={this.formData.formModel}
                              formRules={this.formData.formRules}
                              labelWidth={500}
                              noAutoInput={true}
                            />
                          ) : (
                            [
                              <span
                                key='no-data'
                                class='nodata'
                              >
                                {this.t('当前无需填写参数')}
                              </span>,
                              <br key='line-break' />,
                            ]
                          );
                        },
                      }}
                      title={this.formData.name}
                    />
                  )}
                </div>
                {!this.mealList.length ? (
                  <div class='no-meal'>
                    <i18n-t keypath='当前业务下没有可使用的处理套餐，请前往{0}页面配置'>
                      <span
                        class='link'
                        onClick={() => {
                          this.router.push({ name: 'set-meal' });
                        }}
                      >
                        {this.t('处理套餐')}
                      </span>
                    </i18n-t>
                  </div>
                ) : undefined}
              </div>
            </Loading>
          ),
          footer: () => (
            <div class='manual-process-dialog-footer'>
              <Button
                key='confirm-button'
                loading={this.confirmLoading}
                theme='primary'
                onClick={() => !this.confirmLoading && this.handleConfirm()}
              >
                {this.t('确定')}
              </Button>
              <Button
                key='cancel-button'
                style={{ marginLeft: '10px' }}
                onClick={() => this.handleCancel()}
              >
                {this.t('取消')}
              </Button>
            </div>
          ),
        }}
        header-position='left'
        is-show={this.show}
        mask-close={true}
        title={this.t('手动处理')}
        onUpdate:isShow={this.handleShowChange}
      />
    );
  },
});
