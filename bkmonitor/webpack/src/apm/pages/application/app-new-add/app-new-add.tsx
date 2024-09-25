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
import { Component, Emit, Prop, Watch, Ref } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import { checkDuplicateName } from 'monitor-api/modules/apm_meta';

import './app-new-add.scss';

interface IProps {
  isShow: boolean;
}

interface IEvent {
  onShowChange?: boolean;
  onSaveSuccess?: () => void;
  onDelSuccess?: () => void;
}

interface FormData {
  ID: string;
  name: string;
  desc: string;
  target: boolean;
  log: boolean;
  callChain: boolean;
  performance: boolean;
}

@Component
export default class DebuggingResult extends tsc<IProps, IEvent> {
  @Prop({ default: false, type: Boolean }) isShow: boolean;

  @Ref() addForm: any;

  localShow = false;
  /** 应用名是否重名 */
  existedName = false;

  list = [
    {
      id: 'target',
      title: '指标',
      content: '通过持续上报服务的关键性能指标，可以实时了解服务的运行状态，如响应时间、吞吐量等',
      icon: 'icon-zhibiao',
    },
    {
      id: '2',
      title: 'log',
      content: '服务日志提供了详细的错误信息和上下文，有助于快速定位和解决问题',
      icon: 'icon-rizhi',
    },
    {
      id: 'callChain',
      title: '调用链',
      content: '从用户发起请求到服务响应的全链路追踪，追踪请求在多个服务之间的调用情况，帮助业务识别性能瓶颈和延迟原因',
      icon: 'icon-tiaoyonglian',
    },
    {
      id: 'performance',
      title: '性能分析',
      content: '通过分析函数调用栈和内存分配情况，找出性能瓶颈并进行针对性优化',
      icon: 'icon-profiling',
    },
  ];

  formData: FormData = {
    ID: '',
    name: '',
    desc: '',
    target: false,
    log: false,
    callChain: false,
    performance: false,
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
        validator: val => /^[a-z0-9_-]+$/.test(val),
        message: window.i18n.t('仅支持小写字母、数字、_- 中任意一条件即可'),
        trigger: ['change', 'blur'],
      },
    ],
  };
  created() {
    this.initData();
  }

  @Watch('isShow', { immediate: true })
  handleShow(v: boolean) {
    setTimeout(() => {
      this.localShow = v;
    }, 50);
  }

  @Emit('showChange')
  emitIsShow(v: boolean) {
    return v;
  }

  /** 初始化页面数据 */
  initData() {
    this.rules.name.push({
      message: window.i18n.tc('注意: 名字冲突'),
      trigger: 'none',
      validator: val => !this.existedName && !!val,
    });
  }

  /** 检查 应用名 是否重名 */
  handleCheckDuplicateName() {
    return new Promise((resolve, reject) => {
      if (!this.formData.name) return resolve(true);
      if (this.formData.name.length < 1) return reject(false);

      setTimeout(async () => {
        const { exists } = await checkDuplicateName({ app_name: this.formData.name });
        if (exists) {
          this.existedName = exists;
          this.addForm.validateField('name');
          reject(false);
        } else {
          resolve(true);
        }
      }, 100);
    });
  }

  /* 保存 */
  async handleSave(isAccess = false) {
    const noExistedName = await this.handleCheckDuplicateName();
    if (noExistedName) {
      const isPass = await this.addForm.validate();
      if (isPass) {
        // 保存接口
        // const res = await save(params).catch(() => false);
        // if (res) {
        //   this.$bkMessage({
        //     theme: 'success',
        //     message: this.$t('保存成功'),
        //   });
        //   this.emitIsShow(false);
        if (isAccess) {
          // 跳转到接入服务页面
          const routeData = this.$router.resolve({
            name: 'service-add',
            params: {
              appName: this.formData.name,
            },
          });
          window.location.href = routeData.href;
        }
        // }
        this.emitIsShow(false);
      }
    }
  }

  render() {
    return (
      <bk-sideslider
        class='new-add-application'
        isShow={this.localShow}
        quickClose={true}
        showMask={true}
        {...{ on: { 'update:isShow': this.emitIsShow } }}
        width={960}
      >
        <div slot='header'>{this.$t('新建应用')}</div>
        <div
          class='content-main'
          slot='content'
        >
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
                placeholder={this.$t('1-50字符，由小写字母、数字、下划线(_)、中划线(-)组成')}
                onBlur={() => this.handleCheckDuplicateName()}
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
                      theme='primary'
                    />
                  </div>
                </div>
              ))}
            </bk-form-item>
          </bk-form>
          <div class='footer-wrap'>
            <bk-button
              class='mr8'
              theme='primary'
              onClick={this.handleSave}
            >
              {this.$t('保存')}
            </bk-button>
            <bk-button
              class='mr8'
              theme='primary'
              onClick={() => this.handleSave(true)}
            >
              {this.$t('保存并接入服务')}
            </bk-button>
            <bk-button
              onClick={() => {
                this.emitIsShow(false);
              }}
            >
              {this.$t('取消')}
            </bk-button>
          </div>
        </div>
      </bk-sideslider>
    );
  }
}
