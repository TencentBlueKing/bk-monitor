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

import { Button, Form, Input } from 'bkui-vue';
import { EditLine } from 'bkui-vue/lib/icon';
import { useI18n } from 'vue-i18n';

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
  setup(props) {
    const { t } = useI18n();
    const isEdit = shallowRef(false);

    const formRef = useTemplateRef<InstanceType<typeof Form>>('form');
    const formData = reactive({
      load: 500,
      request: 500,
      qps: 10,
    });

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

    const rules = {
      load: [...numberRequired],
      request: [...numberRequired],
      qps: [...numberRequired],
    };

    const historyShow = shallowRef(false);
    const historyList = computed(() => {
      return [
        { label: t('创建人'), value: props.detail?.create_user },
        { label: t('创建时间'), value: props.detail?.create_time },
        { label: t('最近更新人'), value: props.detail?.update_user },
        { label: t('修改时间'), value: props.detail?.update_time },
      ];
    });

    const handleEditClick = (v: boolean) => {
      if (v) {
        formData.load = props.detail?.application_apdex_config?.load;
        formData.request = props.detail?.application_apdex_config?.request;
        formData.qps = props.detail?.application_qps_config?.qps;
      }
      formRef.value.clearValidate();
      isEdit.value = v;
    };

    const handleHistoryShowChange = (v: boolean) => {
      historyShow.value = v;
    };

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

    const qpsTips = [t('设置系统可承受的 qps 峰值，每秒最多处理 X 条请求，超出可以造成数据丢弃。')];

    const handleSave = () => {
      formRef.value.validate().then(() => {
        console.log(formData);
        handleEditClick(false);
      });
    };

    return {
      isEdit,
      formData,
      rules,
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
                      label={this.$t('页面加载')}
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
                        <span class='value-text'>{this.detail?.application_apdex_config?.load}</span>
                      )}
                    </Form.FormItem>
                    <Form.FormItem
                      label={this.$t('API 请求')}
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
                        <span class='value-text'>{this.detail?.application_apdex_config?.request}</span>
                      )}
                    </Form.FormItem>
                  </div>
                </div>
              </div>
            </div>

            <div class='section qps'>
              <div class='section-title'>{this.$t('限制')} QPS</div>
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
                          suffix={this.$t('次/秒')}
                          type='number'
                        />
                      ) : (
                        <span class='value-text'>{this.detail?.application_qps_config?.qps}</span>
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
                theme='primary'
                onClick={this.handleSave}
              >
                {this.$t('保存')}
              </Button>
              <Button
                onClick={() => {
                  this.handleEditClick(false);
                }}
              >
                {this.$t('取消')}
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
                <span class='edit-text'>{this.$t('编辑')}</span>
              </Button>
            </div>
          )}
        </div>
      </div>
    );
  },
});
