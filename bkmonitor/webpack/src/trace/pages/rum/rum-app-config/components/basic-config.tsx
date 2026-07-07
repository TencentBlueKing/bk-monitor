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
import { type PropType, defineComponent, reactive, shallowRef, useTemplateRef } from 'vue';
import { computed } from 'vue';

import { Button, Form, Input, Message } from 'bkui-vue';
import { EditLine } from 'bkui-vue/lib/icon';
import { useI18n } from 'vue-i18n';

import { updateAppApdexConfig } from '../services/app-config';
import HistoryDialog from '@/components/history-dialog/history-dialog';

import type { IRumAppConfig } from '../../typings/rum-app-config';

import './basic-config.scss';

export default defineComponent({
  name: 'BasicConfig',
  props: {
    detail: {
      type: Object as PropType<IRumAppConfig>,
      default: () => ({}),
    },
  },
  emits: {
    applicationInfoChange: (_params: Pick<IRumAppConfig, 'application_apdex_config' | 'application_qps_config'>) =>
      true,
  },
  setup(props, { emit }) {
    const { t } = useI18n();
    /** 是否处于编辑状态 */
    const isEdit = shallowRef(false);

    /** 表单引用 */
    const formRef = useTemplateRef<InstanceType<typeof Form>>('form');
    /** 表单数据模型：页面加载阈值、API请求阈值、QPS限制 */
    const formData = reactive({
      load: 500,
      request: 500,
      qps: 10,
    });
    /** 保存加载状态 */
    const loading = shallowRef(false);

    /** 数字类型必填校验规则 */
    const numberRequired = [
      { required: true, message: t('必填项'), trigger: 'blur' },
      {
        validator: val => {
          return val > 0;
        },
        message: t('只能填写正整数'),
        trigger: 'blur',
      },
    ];

    /** 表单校验规则 */
    const rules = {
      load: [...numberRequired],
      request: [...numberRequired],
      qps: [...numberRequired],
    };

    /** 历史记录弹窗显示状态 */
    const historyShow = shallowRef(false);
    /** 历史记录列表（创建人/时间、更新人/时间） */
    const historyList = computed(() => {
      return [
        { label: t('创建人'), value: props.detail?.create_user },
        { label: t('创建时间'), value: props.detail?.create_time },
        { label: t('最近更新人'), value: props.detail?.update_user },
        { label: t('修改时间'), value: props.detail?.update_time },
      ];
    });

    /** 切换编辑状态，进入编辑时填充当前配置值 */
    const handleEditClick = (v: boolean) => {
      if (v) {
        formData.load = props.detail?.application_apdex_config?.apdex_view_load;
        formData.request = props.detail?.application_apdex_config?.apdex_api_request;
        formData.qps = props.detail?.application_qps_config;
      }
      formRef.value.clearValidate();
      isEdit.value = v;
    };

    /** 切换历史记录弹窗显示 */
    const handleHistoryShowChange = (v: boolean) => {
      historyShow.value = v;
    };

    /** Apdex 说明文案 */
    const apdexTips = [
      t(
        'Apdex（Application Performance Index）是由 Apdex 联盟开发的用于评估应用性能的工业标准。Apdex 标准从用户的角度出发，将对应用响应时间的表现，转为用户对于应用性能的可量化范围为 0-1 的满意度评价。'
      ),
      t(
        'Apdex 定义了应用响应时间的最优门槛为 T（即 Apdex 阈值，T 由性能评估人员根据预期性能要求确定），根据应用响应时间结合 T 定义了三种不同的性能表现：'
      ),
      `● Satisfied ${t('（满意）- 应用响应时间低于或等于')} T`,
      `● Tolerating ${t('（可容忍）- 应用响应时间大于 T，但同时小于或等于')} 4T`,
      `● Frustrated ${t('（烦躁期）- 应用响应时间大于')} 4T`,
    ];

    /** QPS 限制说明文案 */
    const qpsTips = [t('设置系统可承受的 qps 峰值，每秒最多处理 X 条请求，超出可以造成数据丢弃。')];

    /** 保存配置，调用 setupApplication 接口更新 Apdex 和 QPS 配置 */
    const handleSave = async () => {
      const isValid = formRef.value.validate().catch(() => false);
      if (!isValid) return;
      loading.value = true;
      updateAppApdexConfig({
        bk_biz_id: props.detail?.bk_biz_id,
        app_name: props.detail?.app_name,
        application_apdex_config: {
          apdex_view_load: formData.load,
          apdex_api_request: formData.request,
        },
        application_qps_config: formData.qps,
      })
        .then(() => {
          Message({
            message: t('保存成功'),
            theme: 'success',
          });
          handleEditClick(false);
          emit('applicationInfoChange', {
            application_apdex_config: {
              apdex_view_load: formData.load,
              apdex_api_request: formData.request,
            },
            application_qps_config: formData.qps,
          });
        })
        .finally(() => {
          loading.value = false;
        });
    };

    return {
      t,
      isEdit,
      formData,
      rules,
      loading,
      apdexTips,
      qpsTips,
      historyList,
      handleEditClick,
      handleSave,
      handleHistoryShowChange,
    };
  },
  render() {
    return (
      <div class='basic-config'>
        <div class='basic-config-left'>
          <Form
            ref='form'
            class={{ 'edit-form': this.isEdit }}
            labelPosition={this.isEdit ? 'right' : 'left'}
            labelWidth={65}
            model={this.formData}
            rules={this.rules}
          >
            <div class='section apdex'>
              <div class='section-title'>Apdex</div>
              <div class='section-body'>
                {this.apdexTips.map((tip, ind) => (
                  <div
                    key={ind}
                    class='tip-text'
                  >
                    {tip}
                  </div>
                ))}

                <div class='form-wrap'>
                  <div class='form-row'>
                    <Form.FormItem
                      label={this.t('页面加载')}
                      property='load'
                      required={this.isEdit}
                    >
                      {this.isEdit ? (
                        <Input
                          v-model={this.formData.load}
                          min={1}
                          showControl={false}
                          suffix='ms'
                          type='number'
                        />
                      ) : (
                        <span class='value-text'>
                          {this.detail?.application_apdex_config?.apdex_view_load === undefined
                            ? '--'
                            : `${this.detail?.application_apdex_config?.apdex_view_load}ms`}
                        </span>
                      )}
                    </Form.FormItem>
                    <Form.FormItem
                      label={this.t('API 请求')}
                      property='request'
                      required={this.isEdit}
                    >
                      {this.isEdit ? (
                        <Input
                          v-model={this.formData.request}
                          min={1}
                          showControl={false}
                          suffix='ms'
                          type='number'
                        />
                      ) : (
                        <span class='value-text'>
                          {this.detail?.application_apdex_config?.apdex_api_request === undefined
                            ? '--'
                            : `${this.detail?.application_apdex_config?.apdex_api_request}ms`}
                        </span>
                      )}
                    </Form.FormItem>
                  </div>
                </div>
              </div>
            </div>

            <div class='section qps'>
              <div class='section-title'>{this.t('限制')} QPS</div>
              <div class='section-body'>
                {this.qpsTips.map((tip, ind) => (
                  <div
                    key={ind}
                    class='tip-text'
                  >
                    {tip}
                  </div>
                ))}

                <div class='form-wrap'>
                  <div class='form-row'>
                    <Form.FormItem
                      label='QPS'
                      property='qps'
                      required={this.isEdit}
                    >
                      {this.isEdit ? (
                        <Input
                          v-model={this.formData.qps}
                          min={1}
                          showControl={false}
                          suffix={this.t('次/秒')}
                          type='number'
                        />
                      ) : (
                        <span class='value-text'>
                          {this.detail?.application_qps_config === undefined
                            ? '--'
                            : `${this.detail?.application_qps_config}${this.t('次/秒')}`}
                        </span>
                      )}
                    </Form.FormItem>
                  </div>
                </div>
              </div>
            </div>
          </Form>

          {this.isEdit && (
            <div class='btns'>
              <Button
                loading={this.loading}
                theme='primary'
                onClick={this.handleSave}
              >
                {this.t('保存')}
              </Button>
              <Button
                onClick={() => {
                  this.handleEditClick(false);
                }}
              >
                {this.t('取消')}
              </Button>
            </div>
          )}
        </div>
        <div class='basic-config-right'>
          {!this.isEdit && (
            <div class='header-tool'>
              <HistoryDialog
                key='history'
                list={this.historyList}
              />
              <Button
                key='edit'
                class='edit-btn'
                theme='primary'
                onClick={() => {
                  this.handleEditClick(true);
                }}
              >
                <EditLine />
                <span class='edit-text'>{this.t('编辑')}</span>
              </Button>
            </div>
          )}
        </div>
      </div>
    );
  },
});
