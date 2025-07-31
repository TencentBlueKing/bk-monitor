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
import { Component, Prop, Watch } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import { createDemoAction, getDemoActionDetail } from 'monitor-api/modules/action';
import { transformDataKey } from 'monitor-common/utils/utils';

import SimpleForm from '../components/simple-form';
import HttpCallBack from './http-callback';
import { type IPeripheral, type IWebhook, transformMealContentParams } from './meal-content-data';

import './meal-debug-dialog.scss';

interface IDebugData {
  peripheral: IPeripheral;
  type: string;
  webhook: IWebhook;
}
interface IDebugPeripheral {
  isVariable?: boolean; // 是否为变量
  key?: string; // 是变量的话此值有效
  label?: string; // 输入框title
  required?: boolean; // 是否必填
  value?: string; // 变量值
}

interface IProps {
  debugData: IDebugData;
  debugPeripheralForm: IDebugPeripheral[];
  mealName: string;
  pluginId: number | string;
  show: boolean;
  onDebugPeripheralDataChange?: (v: IDebugPeripheral[]) => void;
  onDebugPeripheralStop?: () => void;
  onDebugWebhookDataChange?: (v: IWebhook) => void;
  onShowChange?: (v: boolean) => void;
}

@Component
export default class MealDebugDialog extends tsc<IProps> {
  @Prop({ type: Boolean, default: false }) show: boolean;
  @Prop({ type: Object, default: () => null }) debugData: IDebugData;
  @Prop({ type: Array, default: () => [] }) debugPeripheralForm: IDebugPeripheral[];
  @Prop({ type: [String, Number], default: '' }) pluginId: string;
  @Prop({ type: String, default: '' }) mealName: string;

  debugActionLoading = false;
  // 调试状态数据
  debugStatusData: {
    content?: { action_plugin_type: string; text: string; url: string };
    is_finished?: boolean;
    status?: '' | 'failure' | 'received' | 'running' | 'success';
  } = {};
  // 是否正在轮询状态中
  isQueryStatus = false;
  // 校验表单
  isVerify = false;
  // 调试单据id
  debugActionId = 0;

  top = 130;

  @Watch('show')
  handleWatchShow(v: boolean) {
    if (v) {
      if (this.debugData.type === 'peripheral') {
        this.peripheralVerify();
      } else {
        this.isVerify = true;
      }
      setTimeout(() => {
        const dialogHeight = document.querySelector('.meal-content-debug-dialog .bk-dialog-content').clientHeight;
        this.top = (document.body.clientHeight - dialogHeight) / 2;
      }, 50);
    }
  }

  handleShowChange(v: boolean) {
    this.$emit('showChange', v);
  }
  handleDebugWebhookDataChange(data) {
    this.$emit('debugWebhookDataChange', data);
  }
  handleDebugPeripheralDataChange(data) {
    this.$emit('debugPeripheralDataChange', data);
    this.peripheralVerify();
  }
  handleDebugPeripheralStop() {
    this.$emit('debugPeripheralStop');
  }

  // 调试数据替换周边系统变量数据
  setDebugPeripheralData() {
    const variableMap = {};
    this.debugPeripheralForm.forEach(item => {
      variableMap[item.key] = item.value;
    });
    this.debugData.peripheral.data.templateDetail = variableMap;
  }

  // 周边系统调试参数
  peripheralExecuteConfig() {
    let executeConfigData = null;
    this.setDebugPeripheralData();
    const { templateDetail } = this.debugData.peripheral.data;
    executeConfigData = transformDataKey(
      transformMealContentParams({
        pluginType: 'peripheral',
        peripheral: this.debugData.peripheral,
      }),
      true
    );
    executeConfigData.template_detail = templateDetail;
    return executeConfigData;
  }

  async handleDebugStart() {
    let executeConfigData = null;
    switch (this.debugData.type) {
      case 'webhook':
        executeConfigData = transformDataKey(
          transformMealContentParams({
            pluginType: 'webhook',
            webhook: this.debugData.webhook as any,
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
      plugin_id: this.pluginId,
      creator: 'username',
      name: this.mealName || undefined,
    })
      .then(data => data.action_id)
      .catch(() => 0);
    this.debugActionLoading = false;
    if (actionId) {
      this.handleShowChange(false);
      this.debugActionId = actionId;
      this.isQueryStatus = true;
      this.debugStatusData = await this.getDebugStatus();
    }
  }

  // 轮询调试状态
  getDebugStatus() {
    let timer = null;

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
      this.handleShowChange(true);
      if (this.debugData.type === 'peripheral') {
        // this.debugData.peripheral = deepClone(this.data.peripheral);
        this.handleDebugPeripheralStop();
      }
    }
  }

  peripheralVerify() {
    this.isVerify = this.debugPeripheralForm.every(item => {
      if (item.required) {
        return !!item.value;
      }
      return true;
    });
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
          <span class='icon-monitor icon-mc-check-small' />
        </div>
      ),
      failure: (
        <div class='failure'>
          <span class='icon-monitor icon-mc-close' />
        </div>
      ),
    };
    return statusMap[this.debugStatusData?.status];
  }

  debugStatusTitle() {
    const statusMap = {
      received: `${this.$t('调试中...')}...`,
      running: `${this.$t('调试中...')}...`,
      success: this.$t('调试成功'),
      failure: this.$t('调试失败'),
    };
    return statusMap[this.debugStatusData?.status];
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
            <span class='icon-monitor icon-copy-link' />
            {contentText.link}
          </span>
        ) : undefined}
      </div>
    );
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
      ),
    };
    return statusMap[this.debugStatusData?.status];
  }

  render() {
    return (
      <div>
        <bk-dialog
          width={this.debugData.type === 'webhook' ? 766 : 640}
          extCls={'meal-content-debug-dialog'}
          position={{
            top: this.top,
          }}
          headerPosition={'left'}
          maskClose={false}
          renderDirective={'if'}
          title={this.debugData.type === 'peripheral' ? this.$t('测试执行') : this.$t('调试')}
          value={this.show}
          on-cancel={() => this.handleShowChange(false)}
        >
          {this.debugData.type === 'peripheral' && (
            <bk-alert
              class='mb-24'
              title={this.$t('注意，该功能会调实际套餐去执行，请确认测试变量后再进行测试执行。')}
              type='warning'
              closable
            />
          )}
          <div>
            {this.debugData.type === 'webhook' && (
              <HttpCallBack
                isEdit={true}
                isOnlyHttp={true}
                value={this.debugData.webhook}
                onChange={data => this.handleDebugWebhookDataChange(data)}
              />
            )}
            {this.debugData.type === 'peripheral' && (
              <SimpleForm
                forms={this.debugPeripheralForm}
                onChange={data => this.handleDebugPeripheralDataChange(data)}
              />
            )}
          </div>
          <div slot='footer'>
            <bk-button
              style={{ marginRight: '8px' }}
              disabled={!this.isVerify}
              loading={this.debugActionLoading}
              theme='primary'
              onClick={() => this.handleDebugStart()}
            >
              {this.debugData.type === 'peripheral' ? this.$t('测试执行') : this.$t('调试')}
            </bk-button>
            <bk-button onClick={() => this.handleShowChange(false)}>{this.$t('取消')}</bk-button>
          </div>
        </bk-dialog>
        <bk-dialog
          width={400}
          extCls={'meal-content-running-dialog'}
          maskClose={false}
          renderDirective={'if'}
          showFooter={false}
          value={!!this.debugStatusData?.status}
          on-cancel={() => this.handleStopDebug()}
        >
          <div class='status-content'>
            <div class='spinner'>{this.debugStatusIcon()}</div>
            <div class='status-title'>{this.debugStatusTitle()}</div>
            <div class='status-text'>{this.debugStatusText(this.debugStatusData?.content)}</div>
            {this.debugStatusOperate()}
          </div>
        </bk-dialog>
      </div>
    );
  }
}
