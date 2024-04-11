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

import { Component, Prop } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';
import {
  collectRunningStatus,
  collectTargetStatus,
  isTaskReady,
  rollbackDeploymentConfig,
  toggleCollectConfigStatus,
  upgradeCollectPlugin
} from 'monitor-api/modules/collecting';

import ConfigDeploy from '../../config-deploy/config-deploy.vue';

import './stop-start-host.scss';

interface StopStartHostProps {
  data: { [key: string]: any };
  openDetail: boolean;
  upgradeParams: { [key: string]: any };
  type: string;
}

interface StopStartHostEvents {
  onIsRefreshConfigListChange: (val: boolean) => void;
  onLoadingChange: (val: boolean) => void;
}
@Component({
  components: {
    ConfigDeploy
  }
})
export default class StopStartHost extends tsc<StopStartHostProps, StopStartHostEvents> {
  @Prop({ default: () => ({}) }) data: StopStartHostProps['data'];
  @Prop({ default: false }) openDetail: boolean;
  @Prop({ default: () => ({}) }) upgradeParams: StopStartHostProps['upgradeParams'];
  @Prop({ default: 'STOPPED' }) type: string;

  id = null;
  btnType = 'STOPPED';
  operationType = '';
  nodeType = 'INSTANCE';
  version = '';
  tables = null;
  isRunning = false;
  operationCount = 0;
  // 定时器
  timer = null;
  // 定时器2
  timerTwo = null;
  textObj = {
    STOPPED: this.$t('启用'),
    STOPPING: this.$t('停用'),
    STARTED: this.$t('停用'),
    STARTING: this.$t('启用'),
    UPGRADE: this.$t('升级'),
    DONE: this.$t('button-完成'),
    RUNNING: this.$t('执行中'),
    CREATE: this.$t('新增'),
    ROLLBACK: this.$t('回滚')
  };
  rollBackSuccess = false;
  deffData = [];
  t = 10000;
  hostTotal = 0;
  ajaxMark = null;
  showRollback = false;

  async created() {
    this.id = this.data.id;
    this.nodeType = this.data.nodeType;
    this.btnType = this.type;
    this.operationType = this.type;
    this.version = `${this.data.updateParams.configVersion}.${this.data.updateParams.infoVersion}`;
    const ajaxFn = collectRunningStatus;
    if (this.openDetail) {
      this.isRunning = true;
      this.btnType = 'RUNNING';
      await this.getHosts(this.id);
      this.pollingStatus();
    } else {
      this.getHosts(this.id, ajaxFn);
    }
  }
  beforeDestroy() {
    clearTimeout(this.timer);
    clearTimeout(this.timerTwo);
  }

  bkMsg(theme, message) {
    this.$bkMessage({
      theme,
      message,
      ellipsisLine: 0
    });
  }
  handleRollback() {
    this.$bkInfo({
      title: this.$t('回滚操作'),
      subTitle: this.$t('将回滚本次的所有配置变更和目标机器的内容。回滚只能回滚上一次的状态，并且只能进行一次。'),
      okText: this.$t('确认回滚'),
      confirmFn: () => {
        this.handleLoadingChange(true);
        this.operationType = 'ROLLBACK';
        this.btnType = 'RUNNING';
        this.$emit('update:type', 'ROLLBACK');
        rollbackDeploymentConfig({ id: this.id })
          .then(() => {
            this.getHosts(this.id);
            this.pollingStatus();
            this.rollBackSuccess = true;
          })
          .catch(() => {
            this.handleLoadingChange(false);
          });
      }
    });
  }
  /** 确认按钮事件 */
  handleConfirm(type) {
    if (type === 'DONE') {
      this.handleDone();
    } else {
      this.handleOperatorAll();
    }
  }
  async handleOperatorAll() {
    this.handleLoadingChange(true);
    this.btnType = 'RUNNING';
    const action = this.type === 'STOPPED' ? 'enable' : 'disable';
    let ajaxMethod = toggleCollectConfigStatus;
    let params: { [key: string]: any } = { id: this.id, action };
    if (this.type === 'UPGRADE') {
      ajaxMethod = upgradeCollectPlugin;
      params = this.upgradeParams;
    }
    ajaxMethod(params)
      .then(async () => {
        const isReady = await this.taskReadyStatusPromise(this.id).catch(() => true);
        if (isReady) {
          this.$emit('isRefreshConfigListChange', true);
          await this.getHosts(this.id).catch(() => {});
          this.isRunning = true;
          this.pollingStatus();
          this.handleLoadingChange(false);
        }
      })
      .catch(() => {
        this.handleLoadingChange(false);
      });
  }
  getHosts(id, ajaxFn?) {
    return new Promise((resolve, reject) => {
      const ajaxMethod = ajaxFn || collectTargetStatus;
      ajaxMethod({ id, is_auto: this.data.autoStatus })
        .then(data => {
          this.tables = this.handleData(data);
          const hasRunning = data.contents.some(item =>
            item.child.some(set => set.status === 'RUNNING' || set.status === 'PENDING')
          );
          if (this.isRunning) {
            this.btnType = hasRunning ? 'RUNNING' : 'DONE';
          }
          this.$emit('update:hosts', this.tables);
          resolve(data);
        })
        .catch(err => {
          reject(err);
        })
        .finally(() => {
          this.handleLoadingChange(false);
        });
    });
  }
  getHostData(id) {
    return new Promise((resolve, reject) => {
      this.ajaxMark = false;
      collectTargetStatus({ id, is_auto: this.data.autoStatus })
        .then(data => {
          if (this.ajaxMark) {
            reject(data);
          } else {
            resolve(data);
          }
        })
        .catch(err => {
          reject(err);
        })
        .finally(() => {
          this.handleLoadingChange(false);
        });
    });
  }
  handleData(data) {
    const oldContent = this.tables ? this.tables.contents : [];
    const content = data.contents;
    const sumData = {
      success: {},
      failed: {},
      pending: {}
    };
    content.forEach((item, index) => {
      item.expand = oldContent?.length && oldContent[index] ? oldContent[index].expand : item.child.length > 0;
      item.successNum = 0;
      item.failedNum = 0;
      item.table = [];
      item.pendingNum = 0;
      item.child.forEach(set => {
        if (set.status === 'RUNNING' || set.status === 'PENDING') {
          sumData.pending[set.instance_id] = set.instance_id;
          item.pendingNum += 1;
        } else if (set.status === 'SUCCESS') {
          sumData.success[set.instance_id] = set.instance_id;
          item.successNum += 1;
        } else {
          item.failedNum += 1;
          sumData.failed[set.instance_id] = set.instance_id;
        }
      });
    });
    const headerData: any = {};
    headerData.successNum = Object.keys(sumData.success).length;
    headerData.failedNum = Object.keys(sumData.failed).length;
    headerData.pendingNum = Object.keys(sumData.pending).length;
    headerData.total = headerData.successNum + headerData.failedNum + headerData.pendingNum;
    data.headerData = headerData;
    return data;
  }
  pollingStatus() {
    this.timer = setTimeout(() => {
      clearTimeout(this.timer);
      if (this.btnType === 'RUNNING') {
        this.getHosts(this.id).finally(() => {
          this.pollingStatus();
        });
      }
    }, this.t);
  }
  async handlePolling(v) {
    this.btnType = 'RUNNING';
    this.ajaxMark = true;
    if (v) {
      clearTimeout(this.timer);
      await this.getHostData(this.id)
        .then((data: any) => {
          if (this.ajaxMark) {
            this.tables = this.handleData(data);
            const hasRunning = data.contents.some(item =>
              item.child.some(set => set.status === 'RUNNING' || set.status === 'PENDING')
            );
            if (this.isRunning) {
              this.btnType = hasRunning ? 'RUNNING' : 'DONE';
            }
            this.$emit('update:hosts', this.tables);
          }
        })
        .catch(err => {
          console.error(err);
        })
        .finally(() => {
          this.pollingStatus();
        });
    } else {
      clearTimeout(this.timer);
    }
  }
  handleDone() {
    this.$emit('update:step', 1);
  }
  handleCancel() {
    this.$router.back();
  }
  async taskReadyStatusPromise(collect_config_id) {
    clearTimeout(this.timerTwo);
    // eslint-disable-next-line @typescript-eslint/no-misused-promises
    return new Promise(async resolve => {
      const show = await isTaskReady({ collect_config_id });
      if (show) {
        resolve(true);
        return;
      }
      this.timerTwo = setTimeout(() => {
        this.taskReadyStatusPromise(collect_config_id).then(res => {
          resolve(res);
        });
      }, 2010);
    });
  }

  /**
   * 切换loading状态
   * @param val loading状态
   */
  handleLoadingChange(val: boolean) {
    this.$emit('loadingChange', val);
  }

  render() {
    return (
      <div
        class='collector-host'
        ref='collectorHost'
      >
        {this.tables?.contents?.length ? (
          <div>
            <config-deploy
              all-data={this.tables}
              is-running={this.isRunning}
              on-can-polling={this.handlePolling}
            />
          </div>
        ) : (
          <div>
            <div>
              <div class='empty-data'>
                <div style='text-align: center'>
                  <i class='icon-monitor icon-tishi hint-icon' />
                  <p>{this.$t('未选择采集目标，无需下发')}</p>
                </div>
              </div>
            </div>
          </div>
        )}
        {!this.openDetail && (
          <div class='footer'>
            <bk-button
              style={{ display: !!this.tables ? 'inline-block' : 'none' }}
              theme='primary'
              disabled={this.btnType === 'RUNNING'}
              onClick={() => this.btnType !== 'RUNNING' && this.handleConfirm(this.btnType)}
            >
              {this.textObj[this.btnType]}
            </bk-button>
            <bk-button
              style={{ display: this.type === 'UPGRADE' && !this.rollBackSuccess ? 'inline-block' : 'none' }}
              disabled={this.btnType === 'RUNNING' || this.btnType === 'UPGRADE'}
              onClick={this.handleRollback}
            >
              {this.$t('回滚')}
            </bk-button>
          </div>
        )}
      </div>
    );
  }
}
