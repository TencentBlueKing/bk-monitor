/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台社区版 (BlueKing PaaS Community Edition) available.
 *
 * Copyright (C) 2017-2025 THL A29 Limited, a Tencent company.  All rights reserved.
 *
 * 蓝鲸智云PaaS平台社区版 (BlueKing PaaS Community Edition) is licensed under the MIT License.
 *
 * License for 蓝鲸智云PaaS平台社区版 (BlueKing PaaS Community Edition):
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

import { defineComponent, shallowReactive, shallowRef, useTemplateRef, watch } from 'vue';

import { Alert, Button, Form, Input, Select, Sideslider } from 'bkui-vue';
import { Message } from 'bkui-vue';
import { checkDuplicateAppName, createApplication } from 'monitor-api/modules/rum_meta';
import { useI18n } from 'vue-i18n';

import './create-app.scss';

export default defineComponent({
  name: 'CreateApp',
  props: {
    show: {
      type: Boolean,
      default: false,
    },
  },
  emits: {
    showChange: (_v: boolean) => true,
    success: (_info: any) => true,
  },
  setup(props, { emit }) {
    const { t } = useI18n();
    const formRef = useTemplateRef<InstanceType<typeof Form>>('form');

    const formData = shallowReactive({
      app_name: '',
      app_alias: '',
      description: '',
      client_type: 'web',
    });

    // form组件异步校验无效，加一层判断
    const isCheckAppDuplicate = shallowRef(false);

    const rules = {
      app_name: [
        {
          required: true,
          message: t('应用名称不能为空'),
          trigger: 'blur',
        },
        {
          validator: val => !/(\ud83c[\udf00-\udfff])|(\ud83d[\udc00-\ude4f\ude80-\udeff])|[\u2600-\u2B55]/g.test(val),
          message: t('不能输入emoji表情'),
          trigger: 'blur',
        },
        {
          validator: checkAppDuplicate,
          message: t('应用名称已存在'),
          trigger: 'blur',
        },
      ],
      app_alias: [
        {
          required: true,
          message: t('应用别名不能为空'),
          trigger: 'blur',
        },
      ],
    };
    const submitLoading = shallowRef(false);

    /** 侧栏关闭时重置表单数据与错误状态 */
    watch(
      () => props.show,
      v => {
        formRef.value?.clearValidate();
        if (!v) {
          formData.app_alias = '';
          formData.app_name = '';
          formData.description = '';
          isCheckAppDuplicate.value = false;
        }
      }
    );

    const handleShowChange = (show: boolean) => {
      emit('showChange', show);
    };

    /**
     * 检查应用名称是否已存在
     * @param appName 待检查的应用名称
     * @returns 是否重复（true=已存在）
     */
    async function checkAppDuplicate(appName: string) {
      return new Promise((resolve, reject) => {
        checkDuplicateAppName({ app_name: appName })
          .then(res => {
            if (res.exists) {
              isCheckAppDuplicate.value = false;
              reject(t('应用名称已存在'));
            } else {
              isCheckAppDuplicate.value = true;
              resolve(true);
            }
          })
          .catch(err => {
            reject(JSON.stringify(err));
            isCheckAppDuplicate.value = false;
          });
      });
    }

    /** 提交创建应用：校验重名 → 表单验证 → 调用创建接口 → 触发成功回调 */
    const handleSubmit = async () => {
      if (submitLoading.value) return; // 防重复点击

      const valid = await formRef.value?.validate().catch(() => false);

      if (valid && isCheckAppDuplicate.value) {
        const params = {
          app_name: formData.app_name,
          app_alias: formData.app_alias,
          description: formData.description,
          client_type: formData.client_type,
        };
        const res = await createApplication(params).catch(() => null);
        if (!res) {
          Message({ theme: 'error', message: t('创建失败') });
          submitLoading.value = false;
          return;
        }
        emit('success', res);
      }
      submitLoading.value = false;
    };

    return {
      formRef,
      formData,
      rules,
      submitLoading,
      t,
      handleShowChange,
      handleSubmit,
    };
  },
  render() {
    return (
      <Sideslider
        width={800}
        class='rum-create-app-sideslider'
        isShow={this.show}
        title={this.t('创建应用')}
        onUpdate:isShow={this.handleShowChange}
      >
        <div class='rum-create-app-content'>
          <Alert
            theme='info'
            title={this.t('应用将创建在当前业务 「蓝鲸」 下，创建后进入 SDK 接入引导')}
          />
          <Form
            ref='form'
            class='mt-24'
            form-type='vertical'
            model={this.formData}
            rules={this.rules}
          >
            <Form.FormItem
              label={`${this.t('应用名称')}（${this.t('域名')}）`}
              property={'app_name'}
              required
            >
              <Input
                v-model={this.formData.app_name}
                placeholder={`www.example.com（${this.t('作为唯一标识，创建后不可修改')}）`}
              />
            </Form.FormItem>
            <Form.FormItem
              label={this.t('应用别名')}
              property={'app_alias'}
              required
            >
              <Input
                v-model={this.formData.app_alias}
                placeholder={this.t('请输入可用于识别的别名，可随时修改')}
              />
            </Form.FormItem>
            <Form.FormItem
              label={this.t('应用类型')}
              property='client_type'
              required
            >
              <Select
                v-model={this.formData.client_type}
                disabled={true}
                multipleMode={'tag'}
              >
                {{
                  default: () => (
                    <Select.Option
                      id={'web'}
                      name={'Web 应用'}
                    >
                      {this.$t('Web 应用')}
                    </Select.Option>
                  ),
                  tag: () => {
                    return (
                      <div>
                        <span>
                          <span class='select-tag-title'>{this.t('Web 应用')}</span>
                          <span class='select-tag-subtitle'>{this.t('PC/移动端网页')}</span>
                        </span>
                        <span class='select-tag-tip'>
                          <span>{this.t('当前仅支持')}</span>
                        </span>
                      </div>
                    );
                  },
                }}
              </Select>
            </Form.FormItem>
            <Form.FormItem
              label={this.t('应用描述')}
              property={'description'}
            >
              <Input
                v-model={this.formData.description}
                maxlength={100}
                rows={3}
                type={'textarea'}
              />
            </Form.FormItem>
          </Form>
          <div>
            <Button
              class='mr-8'
              loading={this.submitLoading}
              theme={'primary'}
              onClick={this.handleSubmit}
            >
              {this.t('创建并进入下一步')}
            </Button>
            <Button onClick={() => this.handleShowChange(false)}>{this.t('取消')}</Button>
          </div>
        </div>
      </Sideslider>
    );
  },
});
