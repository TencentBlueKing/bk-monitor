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
import { Component, Emit, Prop } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';
import { deepClone } from 'monitor-common/utils';

import MoreConfig from './components/more-config';
import { validatePort } from './utils';

import './influxdb-group.scss';

// 连通性测试状态
enum ConnectionStatus {
  default = '',
  success = 'success',
  fail = 'fail'
}
// 表单模板，用于初始化数据
const formDataTemplate = {
  influxdbGroupName: '',
  influxdbGroupList: [
    {
      title: '组1',
      instanceName: '', // 实例名称
      host: '', // 主机IP
      port: '', // 端口
      userName: '', // 用户名
      password: '' // 密码
    }
  ],
  backupRecoverySpeed: '', // 备份恢复速率
  disabled: true, // 禁用
  readonly: true, // 只读
  responsible: '', // 负责人
  description: '' // 描述
};
// 错误信息模板
const formErrMsgTemplate = {
  influxdbGroupName: '',
  formList: [
    {
      instanceName: '',
      host: '',
      port: '',
      userName: '',
      password: ''
    }
  ]
};

@Component
export default class InfluxdbTest extends tsc<{}> {
  @Prop({ type: Boolean, default: false }) isShow;
  @Prop({ type: String, default: '新增' }) influxdbGroupTitle;
  connectionStatus = ConnectionStatus.default; // 当前资源类别下进行连通性测试的状态，空字符串为初始状态（未进行连通性测试）
  connectTestButtonLoading = false; // 连通性测试按钮loading
  submitButtonLoading = false; // 提交/提交并再次新增 按钮的loading
  localFormData = deepClone(formDataTemplate);
  localFormErrMsg = deepClone(formErrMsgTemplate);
  /* 用于记录新增组的名字尾数 */
  localGroupCount = 1;

  localFormRules = {
    influxdbGroupName: [{ validator: value => !!value, message: window.i18n.tc('必填项') }],
    instanceName: [{ validator: value => !!value, message: window.i18n.tc('必填项') }],
    host: [{ validator: value => !!value, message: window.i18n.tc('必填项') }],
    port: [
      { validator: value => !!value, message: window.i18n.tc('必填项') },
      { validator: value => validatePort.test(value), message: window.i18n.tc('请输入合法端口') }
    ],
    userName: [{ validator: value => !!value, message: window.i18n.tc('必填项') }],
    password: [{ validator: value => !!value, message: window.i18n.tc('必填项') }]
  };
  @Emit('show-change')
  emitShowChange(val: boolean) {
    return val;
  }
  /* 表单校验 */
  formValidate() {
    return new Promise((resolve, reject) => {
      // 存放校验失败项的数组
      const validateArray: Array<any> = [];
      Object.keys(this.localFormRules).forEach((key: any, index) => {
        if (!index) {
          const value = this.localFormData[key];
          this.localFormRules[key]?.find(item => {
            const res = !item.validator(value);
            if (res) {
              this.localFormErrMsg[key] = item.message;
              validateArray.push(item);
            }
            return res;
          });
        } else {
          this.localFormData.influxdbGroupList.forEach((group, groupIndex) => {
            const value = group[key];
            this.localFormRules[key]?.find(item => {
              const res = !item.validator(value);
              if (res) {
                this.localFormErrMsg.formList[groupIndex][key] = item.message;
                validateArray.push(item);
              }
              return res;
            });
          });
        }
      });
      validateArray.length ? reject(false) : resolve(true);
    });
  }
  /* 连通性测试 */
  handleConnectTest() {
    this.formValidate()
      .then(() => {
        // TODO 调用连通性测试接口
        this.connectTestButtonLoading = true;
        setTimeout(() => {
          this.connectionStatus = ConnectionStatus.success;
        }, 500);
      })
      .finally(() => {
        setTimeout(() => {
          this.connectTestButtonLoading = false;
        }, 500);
      });
  }

  /* 表单单个字段校验 */
  singleFieldValidate(value: any, field: string, listIndex?: number) {
    if (listIndex !== undefined) {
      this.localFormErrMsg.formList[listIndex][field] = '';
      this.localFormRules[field]?.find(item => {
        const res = !item.validator(value);
        if (res) this.localFormErrMsg.formList[listIndex][field] = item.message;
        return res;
      });
    } else {
      this.localFormErrMsg[field] = '';
      this.localFormRules[field]?.find(item => {
        const res = !item.validator(value);
        if (res) this.localFormErrMsg[field] = item.message;
        return res;
      });
    }
  }

  clearError(type, field?, listIndex?) {
    if (type === 'all') {
      Object.keys(this.localFormErrMsg).forEach(key => {
        this.localFormErrMsg[key] = '';
      });
    } else {
      if (listIndex !== undefined) this.localFormErrMsg.formList[listIndex][field] = '';
      else this.localFormErrMsg[field] = '';
    }
  }
  /* (新增/删除/克隆)influxdb组 */
  handleGroupOperation(type, index?: number, e?: Event) {
    // 阻止事件冒泡
    e?.stopPropagation();
    switch (type) {
      case 'add':
        this.localGroupCount += 1;
        this.localFormData.influxdbGroupList.push({
          title: `组${this.localGroupCount}`,
          instanceName: '', // 实例名称
          host: '', // 主机IP
          port: '', // 端口
          userName: '', // 用户名
          password: '' // 密码
        });
        this.localFormErrMsg.formList.push({
          instanceName: '',
          host: '',
          port: '',
          userName: '',
          password: ''
        });
        break;
      case 'delete':
        this.localFormData.influxdbGroupList.splice(index, 1);
        break;
      case 'copy':
        this.localGroupCount += 1;
        this.localFormData.influxdbGroupList.push({
          ...this.localFormData.influxdbGroupList[index],
          title: `组${this.localGroupCount}`
        });
        this.localFormErrMsg.formList.push(this.localFormErrMsg.formList[index]);
    }
  }

  /* 用于回显通过 (克隆/编辑) 进入influxdb组的数据 */
  dataEcho(val) {
    const { operationType, data } = val;
    data?.length &&
      data.forEach((item, index) => {
        // 默认数据已有一项，因此当index为0时无需执行新增操作
        if (index) this.handleGroupOperation('add');
        const target = this.localFormData.influxdbGroupList[index];
        Object.assign(target, item);
      });
    if (operationType === 'clone') {
      // TODO 克隆的情况
    } else if (operationType === 'edit') {
      // TODO 编辑的情况
    }
  }
  /* 提交表单 */
  handleSubmit(again: boolean) {
    // TODO 构建传参、调用接口
    this.submitButtonLoading = true;
    setTimeout(() => {
      this.$bkMessage({
        message: this.$t('提交成功'),
        theme: 'success'
      });
      this.submitButtonLoading = false;
      this.emitShowChange(false);
    }, 500);
    if (!again) return; // 提交并再次新增
    setTimeout(() => {
      this.emitShowChange(true);
      this.initData();
    }, 1000);
  }
  initData() {
    this.localFormData = deepClone(formDataTemplate);
    this.localFormErrMsg = deepClone(formErrMsgTemplate);
    this.connectionStatus = ConnectionStatus.default;
  }
  /* 侧栏关闭回调，初始化数据 */
  handleSliderHidden() {
    this.initData();
  }
  render() {
    return (
      <div class='influxdb-test'>
        <bk-sideslider
          isShow={this.isShow}
          quick-close={true}
          width={640}
          transfer={true}
          on={{ 'update:isShow': this.emitShowChange }}
          on-hidden={this.handleSliderHidden}
        >
          <div
            slot='header'
            class='cluster-operation-title'
          >
            {this.$tc(`${this.influxdbGroupTitle}influxdb组`)}
          </div>
          <div
            slot='content'
            class='cluster-operation-content'
          >
            <div class='influxdb-group'>
              <div class='info-title'>{this.$tc('基础信息')}</div>
              {
                <div class='group-form-item mb24'>
                  <div class='group-form-item-content required mb6'>{this.$tc('Influx组名称')}</div>
                  <bk-input
                    class={this.localFormErrMsg.influxdbGroupName && 'error-item'}
                    v-model={this.localFormData.influxdbGroupName}
                    onFocus={() => this.clearError('single', 'influxdbGroupName')}
                    onBlur={() => this.singleFieldValidate(this.localFormData.influxdbGroupName, 'influxdbGroupName')}
                    onChange={() => (this.localFormErrMsg.influxdbGroupName = '')}
                  />
                  <div class='group-form-item-error-msg'>{this.localFormErrMsg.influxdbGroupName}</div>
                </div>
              }
              {
                <div class='influxdb-group-list'>
                  {this.localFormData.influxdbGroupList.map((group, index) => (
                    <div
                      class='group-item'
                      key={group.instanceName + index}
                    >
                      <div class='group-header'>
                        <div class='group-title'>{group.title}</div>
                        <div class='group-operation'>
                          <i
                            class='icon-monitor icon-mc-copy operation-icon mr20'
                            onClick={e => this.handleGroupOperation('copy', index, e)}
                          />
                          <i
                            class={[
                              'icon-monitor',
                              'icon-mc-delete-line',
                              'operation-icon',
                              !index && this.localFormData.influxdbGroupList.length < 2 && 'disabled-icon'
                            ]}
                            onClick={e => this.handleGroupOperation('delete', index, e)}
                          />
                        </div>
                      </div>
                      <div class='group-content'>
                        <div class='group-form-item mb24'>
                          <div class='group-form-item-content required mb6'>{this.$tc('实例名称')}</div>
                          <bk-input
                            class={this.localFormErrMsg.formList[index].instanceName && 'error-item'}
                            v-model={group.instanceName}
                            onFocus={() => this.clearError('single', 'instanceName', index)}
                            onBlur={() =>
                              this.singleFieldValidate(
                                this.localFormData.influxdbGroupList[index].instanceName,
                                'instanceName',
                                index
                              )
                            }
                            onChange={() => (this.localFormErrMsg.formList[index].instanceName = '')}
                          />
                          <div class='group-form-item-error-msg'>
                            {this.localFormErrMsg.formList[index].instanceName}
                          </div>
                        </div>
                        <div class='group-flex'>
                          <div class='group-form-item half-form-item mb24'>
                            <div class='group-form-item-content required mb6'>{this.$tc('主机IP')}</div>
                            <bk-input
                              class={this.localFormErrMsg.formList[index].host && 'error-item'}
                              v-model={group.host}
                              onFocus={() => this.clearError('single', 'host', index)}
                              onBlur={() =>
                                this.singleFieldValidate(
                                  this.localFormData.influxdbGroupList[index].host,
                                  'host',
                                  index
                                )
                              }
                              onChange={() => (this.localFormErrMsg.formList[index].host = '')}
                            />
                            <div class='group-form-item-error-msg'>{this.localFormErrMsg.formList[index].host}</div>
                          </div>
                          <div class='group-form-item half-form-item mb24'>
                            <div class='group-form-item-content required mb6'>{this.$tc('端口')}</div>
                            <bk-input
                              class={this.localFormErrMsg.formList[index].port && 'error-item'}
                              v-model={group.port}
                              onFocus={() => this.clearError('single', 'port', index)}
                              onBlur={() =>
                                this.singleFieldValidate(
                                  this.localFormData.influxdbGroupList[index].port,
                                  'port',
                                  index
                                )
                              }
                              onChange={() => (this.localFormErrMsg.formList[index].port = '')}
                            />
                            <div class='group-form-item-error-msg'>{this.localFormErrMsg.formList[index].port}</div>
                          </div>
                        </div>
                        <div class='group-flex'>
                          <div class='group-form-item half-form-item'>
                            <div class='group-form-item-content required mb6'>{this.$tc('用户名')}</div>
                            <bk-input
                              class={this.localFormErrMsg.formList[index].userName && 'error-item'}
                              v-model={group.userName}
                              onFocus={() => this.clearError('single', 'userName', index)}
                              onBlur={() =>
                                this.singleFieldValidate(
                                  this.localFormData.influxdbGroupList[index].userName,
                                  'userName',
                                  index
                                )
                              }
                              onChange={() => (this.localFormErrMsg.formList[index].userName = '')}
                            />
                            <div class='group-form-item-error-msg'>{this.localFormErrMsg.formList[index].userName}</div>
                          </div>
                          <div class='group-form-item half-form-item'>
                            <div class='group-form-item-content required mb6'>{this.$tc('密码')}</div>
                            <bk-input
                              class={this.localFormErrMsg.formList[index].password && 'error-item'}
                              v-model={group.password}
                              type='password'
                              onFocus={() => this.clearError('single', 'password', index)}
                              onBlur={() =>
                                this.singleFieldValidate(
                                  this.localFormData.influxdbGroupList[index].password,
                                  'password',
                                  index
                                )
                              }
                              onChange={() => (this.localFormErrMsg.formList[index].password = '')}
                            />
                            <div class='group-form-item-error-msg'>{this.localFormErrMsg.formList[index].password}</div>
                          </div>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              }
              {
                <div
                  class='add-group-button'
                  onClick={e => this.handleGroupOperation('add', this.localGroupCount, e)}
                >
                  <div>
                    <i class='icon-monitor icon-plus-line plus-icon' />
                    {this.$tc('新增组')}
                  </div>
                </div>
              }
              {
                <div class='connection-test'>
                  <bk-button
                    theme='primary'
                    loading={this.connectTestButtonLoading}
                    outline={this.connectionStatus === ConnectionStatus.success}
                    onClick={this.handleConnectTest}
                  >
                    {this.$tc('连通性测试')}
                  </bk-button>
                  {this.connectionStatus && (
                    <div class='connection-tips'>
                      <i
                        class={[
                          'icon-monitor',
                          this.connectionStatus === ConnectionStatus.success
                            ? 'icon-mc-check-fill'
                            : 'icon-mc-close-fill',
                          `${this.connectionStatus}-icon`
                        ]}
                      />
                      <span
                        class={
                          this.connectionStatus === ConnectionStatus.success &&
                          `connection-${this.connectionStatus} tips`
                        }
                      >
                        {this.$tc(`测试${this.connectionStatus === ConnectionStatus.success ? '通过' : '失败'}`)}
                      </span>
                    </div>
                  )}
                </div>
              }
            </div>
            <MoreConfig
              card-title={window.i18n.tc('更多配置')}
              responsible={this.localFormData.responsible}
              description={this.localFormData.description}
              on-data-change={val => Object.assign(this.localFormData, val)}
            >
              <div class='influxdb-group-config'>
                <div class='half-item mb24'>
                  <div class='influxdb-form-item-content mb6'>{this.$tc('备份恢复速率')}</div>
                  <bk-input
                    v-model={this.localFormData.backupRecoverySpeed}
                    type='number'
                    placeholder={this.$t('0')}
                  />
                </div>
                <div class='one-fourth-item mb24'>
                  <div class='influxdb-form-item-content mb6'>{this.$tc('是否禁用')}</div>
                  <bk-switcher
                    v-model={this.localFormData.disabled}
                    theme='primary'
                  />
                </div>
                <div class='mb24'>
                  <div class='influxdb-form-item-content mb6'>{this.$tc('是否可读')}</div>
                  <bk-switcher
                    v-model={this.localFormData.readonly}
                    theme='primary'
                  />
                </div>
              </div>
            </MoreConfig>
          </div>
          <div
            slot='footer'
            class='footer-operation-wrapper'
          >
            <div class='button-wrapper'>
              <bk-button
                theme='primary'
                class='footer-button'
                disabled={this.connectionStatus !== ConnectionStatus.success}
                loading={this.submitButtonLoading}
                onClick={() => this.handleSubmit(false)}
              >
                {this.$tc('提交')}
              </bk-button>
              <bk-button
                class='footer-button'
                disabled={this.connectionStatus !== ConnectionStatus.success}
                loading={this.submitButtonLoading}
                onClick={() => this.handleSubmit(true)}
              >
                {this.$tc('提交并再次新增')}
              </bk-button>
              <bk-button
                class='footer-button'
                onClick={() => this.emitShowChange(false)}
              >
                {this.$tc('取消')}
              </bk-button>
            </div>
          </div>
        </bk-sideslider>
      </div>
    );
  }
}
