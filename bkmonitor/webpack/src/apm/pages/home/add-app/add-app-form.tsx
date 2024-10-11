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
import { Component, Ref } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import { checkDuplicateName, createApplication } from 'monitor-api/modules/apm_meta';

import { ETelemetryDataType } from '../../application/app-configuration/type';

import './add-app-form.scss';

interface FormData {
  ID: string;
  name: string;
  desc: string;
}

interface IProps {
  onCancel?: () => void;
  onSuccess?: () => void;
}

@Component
export default class AddAppForm extends tsc<IProps> {
  @Ref() addForm: any;
  list = [
    {
      id: ETelemetryDataType.metric,
      title: window.i18n.tc('指标'),
      content: window.i18n.tc('通过持续上报服务的关键性能指标，可以实时了解服务的运行状态，如响应时间、吞吐量等'),
      icon: 'icon-zhibiao',
    },
    {
      id: ETelemetryDataType.log,
      title: window.i18n.tc('日志'),
      content: window.i18n.tc('服务日志提供了详细的错误信息和上下文，有助于快速定位和解决问题'),
      icon: 'icon-rizhi',
    },
    {
      id: ETelemetryDataType.trace,
      title: window.i18n.tc('调用链'),
      content: window.i18n.tc(
        '从用户发起请求到服务响应的全链路追踪，追踪请求在多个服务之间的调用情况，帮助业务识别性能瓶颈和延迟原因'
      ),
      icon: 'icon-tiaoyonglian',
    },
    {
      id: ETelemetryDataType.profiling,
      title: window.i18n.tc('性能分析'),
      content: window.i18n.tc('通过分析函数调用栈和内存分配情况，找出性能瓶颈并进行针对性优化'),
      icon: 'icon-profiling',
    },
  ];

  formData: FormData | Record<string, boolean> = {
    ID: '',
    name: '',
    desc: '',
    [ETelemetryDataType.metric]: false,
    [ETelemetryDataType.log]: false,
    [ETelemetryDataType.trace]: false,
    [ETelemetryDataType.profiling]: false,
  };
  rules = {
    ID: [
      {
        required: true,
        validator: val => val.length >= 1 && val.length <= 50,
        message: window.i18n.tc('输入1-50个字符'),
        trigger: 'blur',
      },
      {
        validator: val => /^[a-z0-9_-]+$/.test(val),
        message: window.i18n.t('仅支持小写字母、数字、_- 中任意一条件即可'),
        trigger: ['change', 'blur'],
      },
    ],
    name: [
      {
        validator: val => val.length >= 1 && val.length <= 50,
        message: window.i18n.t('输入1-50个字符'),
        trigger: 'blur',
      },
      {
        validator: this.handleCheckDuplicateName,
        message: window.i18n.tc('注意: 名字冲突'),
        trigger: ['blur'],
      },
    ],
  };
  saveLoading = false;

  /** 检查 应用名 是否重名 */
  async handleCheckDuplicateName(val: string) {
    const { exists } = await checkDuplicateName({ app_name: val }).catch(() => ({ exists: true }));
    return !exists;
  }

  initForm() {
    this.formData = {
      ID: '',
      name: '',
      desc: '',
      [ETelemetryDataType.metric]: false,
      [ETelemetryDataType.log]: true,
      [ETelemetryDataType.trace]: false,
      [ETelemetryDataType.profiling]: false,
    };
    this.addForm?.clearError?.();
  }

  /* 保存 */
  async handleSave(isAccess = false) {
    this.saveLoading = true;
    const isPass = await this.addForm.validate();
    if (isPass) {
      // 保存接口
      const params = {
        app_name: this.formData.ID,
        app_alias: this.formData.name,
        description: this.formData.desc,
        enabled_profiling: this.formData[ETelemetryDataType.profiling],
        enabled_trace: this.formData[ETelemetryDataType.trace],
        enabled_metric: this.formData[ETelemetryDataType.metric],
        enabled_log: this.formData[ETelemetryDataType.log],
        es_storage_config: null,
      };
      const res = await createApplication(params)
        .then(() => true)
        .catch(() => false);
      if (res) {
        this.$bkMessage({
          theme: 'success',
          message: this.$t('保存成功'),
        });
        this.initForm();
        this.$emit('success');
        if (isAccess) {
          // 跳转到接入服务页面
          const routeData = this.$router.resolve({
            name: 'service-add',
            params: {
              appName: this.formData.name as string,
            },
          });
          window.location.href = routeData.href;
        }
      }
    }
    this.saveLoading = false;
  }

  handleCancel() {
    this.initForm();
    this.$emit('cancel');
  }

  render() {
    return (
      <div class='add-app-form-component'>
        <bk-form
          ref='addForm'
          class='form-wrap'
          form-type='vertical'
          {...{
            props: {
              model: this.formData,
              rules: this.rules,
            },
          }}
        >
          <bk-form-item
            class='cluster-select-item'
            error-display-type='normal'
            label={this.$t('应用ID')}
            property='ID'
            required
          >
            <bk-input
              class='input'
              v-model={this.formData.ID}
              maxlength={50}
              placeholder={this.$t('1-50字符，由小写字母、数字、下划线(_)、中划线(-)组成')}
            />
          </bk-form-item>
          <bk-form-item
            error-display-type='normal'
            label={this.$t('应用名')}
            property='name'
            required
          >
            <bk-input
              class='input'
              v-model={this.formData.name}
              placeholder={this.$t('1-50字符')}
            />
          </bk-form-item>
          <bk-form-item label={this.$t('描述')}>
            <bk-input
              class='input'
              v-model={this.formData.desc}
              maxlength='100'
              type='textarea'
            />
          </bk-form-item>
          <bk-form-item label={this.$t('数据上报')}>
            {this.list.map(item => (
              <div
                key={item.id}
                class='report-type-wrap'
              >
                <div class='report-left-content'>
                  <i class={['icon-monitor', item.icon]} />
                </div>
                <div class='report-middle-content'>
                  <span class='middle-content-title'>{item.title}</span>
                  <span class='middle-content-text'>{item.content}</span>
                </div>
                <div class='report-right-content'>
                  <bk-switcher
                    v-model={this.formData[item.id]}
                    size='small'
                    theme='primary'
                  />
                </div>
              </div>
            ))}
          </bk-form-item>
          <bk-form-item>
            <bk-button
              class='mr-8'
              loading={this.saveLoading}
              theme='primary'
              onClick={() => this.handleSave()}
            >
              {this.$t('保存')}
            </bk-button>
            <bk-button
              class='mr-8'
              loading={this.saveLoading}
              theme='primary'
              onClick={() => this.handleSave(true)}
            >
              {this.$t('保存并接入服务')}
            </bk-button>
            <bk-button onClick={this.handleCancel}>{this.$t('取消')}</bk-button>
          </bk-form-item>
        </bk-form>
      </div>
    );
  }
}
