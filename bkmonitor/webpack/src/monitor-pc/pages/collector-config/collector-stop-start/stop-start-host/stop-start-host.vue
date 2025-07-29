<!--
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
-->
<template>
  <div
    ref="collectorHost"
    class="collector-host"
  >
    <div v-if="tables && tables.contents && tables.contents.length">
      <config-deploy
        :all-data="tables"
        :is-running="isRunning"
        @can-polling="handlePolling"
      />
    </div>
    <div v-else>
      <div>
        <div class="empty-data">
          <div style="text-align: center">
            <i class="icon-monitor icon-tishi hint-icon" />
            <p>{{ $t('未选择采集目标，无需下发') }}</p>
          </div>
        </div>
      </div>
    </div>
    <div
      v-if="!openDetail"
      class="footer"
    >
      <bk-button
        v-show="tables"
        theme="primary"
        :disabled="btnType === 'RUNNING'"
        @click="btnType !== 'RUNNING' && handleConfirm(btnType)"
        >{{ textObj[btnType] }}</bk-button
      >
      <!-- <bk-button v-show="type !== 'UPGRADE' && btnType !== 'RUNNING'" @click="handleCancel"> {{ $t('取消') }} </bk-button> -->
      <bk-button
        v-show="type === 'UPGRADE' && !rollBackSuccess"
        :disabled="btnType === 'RUNNING' || btnType === 'UPGRADE'"
        @click="handleRollback"
      >
        {{ $t('回滚') }}
      </bk-button>
    </div>
  </div>
</template>
<script>
import {
  collectRunningStatus,
  collectTargetStatus,
  isTaskReady,
  rollbackDeploymentConfig,
  toggleCollectConfigStatus,
  upgradeCollectPlugin,
} from 'monitor-api/modules/collecting';

import configDeploy from '../../config-deploy/config-deploy';

export default {
  name: 'StopStartHost',
  components: {
    configDeploy,
  },
  props: {
    data: {
      type: Object,
      default: () => ({}),
    },
    openDetail: Boolean,
    upgradeParams: Object,
    type: {
      type: String,
      default: 'STOPPED',
    },
  },
  data() {
    return {
      id: null,
      btnType: 'STOPPED',
      operationType: '',
      nodeType: 'INSTANCE',
      version: '',
      tables: null,
      isRunning: false,
      operationCount: 0,
      timer: null,
      textObj: {
        STOPPED: this.$t('启用'),
        STOPPING: this.$t('停用'),
        STARTED: this.$t('停用'),
        STARTING: this.$t('启用'),
        UPGRADE: this.$t('升级'),
        DONE: this.$t('button-完成'),
        RUNNING: this.$t('执行中'),
        CREATE: this.$t('新增'),
        ROLLBACK: this.$t('回滚'),
      },
      rollBackSuccess: false,
      deffData: [],
      t: 10000,
      hostTotal: 0,
      ajaxMark: null,
      showRollback: false,
    };
  },
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
      await this.getHosts(this.id, this.nodeType);
      this.pollingStatus();
    } else {
      this.getHosts(this.id, this.nodeType, ajaxFn);
    }
  },
  beforeDestroy() {
    clearTimeout(this.timer);
  },
  methods: {
    bkMsg(theme, message) {
      this.$bkMessage({
        theme,
        message,
        ellipsisLine: 0,
      });
    },
    handleRollback() {
      this.$bkInfo({
        title: this.$t('回滚操作'),
        subTitle: this.$t('将回滚本次的所有配置变更和目标机器的内容。回滚只能回滚上一次的状态，并且只能进行一次。'),
        okText: this.$t('确认回滚'),
        confirmFn: () => {
          this.$parent.pageLoading = true;
          this.operationType = 'ROLLBACK';
          this.btnType = 'RUNNING';
          this.$emit('update:type', 'ROLLBACK');
          rollbackDeploymentConfig({ id: this.id })
            .then(() => {
              this.getHosts(this.id, this.nodeType);
              this.pollingStatus();
              this.rollBackSuccess = true;
            })
            .catch(() => {
              this.$parent.pageLoading = false;
            });
        },
      });
    },
    handleConfirm(type) {
      if (type === 'DONE') {
        this.handleDone();
      } else {
        this.handleOperatorAll();
      }
    },
    async handleOperatorAll() {
      this.$parent.pageLoading = true;
      this.btnType = 'RUNNING';
      const action = this.type === 'STOPPED' ? 'enable' : 'disable';
      let ajaxMethod = toggleCollectConfigStatus;
      let params = { id: this.id, action };
      if (this.type === 'UPGRADE') {
        ajaxMethod = upgradeCollectPlugin;
        params = this.upgradeParams;
      }
      ajaxMethod(params)
        .then(async () => {
          const isReady = await this.taskReadyStatusPromise(this.id).catch(() => true);
          if (isReady) {
            this.$parent.isRefreshConfigList = true;
            await this.getHosts(this.id, this.nodeType).catch(() => {});
            this.isRunning = true;
            this.pollingStatus();
            this.$parent.pageLoading = false;
          }
        })
        .catch(() => {
          this.$parent.pageLoading = false;
        });
      // const type = {
      //     STOPPED: this.$t('确认启用所有机器吗'),
      //     STARTED: this.$t('确认停用所有机器吗'),
      //     UPGRADE: this.$t('确认升级所有机器吗')
      // }
      // this.$bkInfo({
      //     title: type[this.type],
      //     maskClose: true,
      //     confirmFn: async () => {

      //     }
      // })
    },
    getHosts(id, type, ajaxFn) {
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
            this.$parent.pageLoading = false;
          });
      });
    },
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
            this.$parent.pageLoading = false;
          });
      });
    },
    handleData(data) {
      const oldContent = this.tables ? this.tables.contents : [];
      const content = data.contents;
      const sumData = {
        success: {},
        failed: {},
        pending: {},
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
      const headerData = {};
      headerData.successNum = Object.keys(sumData.success).length;
      headerData.failedNum = Object.keys(sumData.failed).length;
      headerData.pendingNum = Object.keys(sumData.pending).length;
      headerData.total = headerData.successNum + headerData.failedNum + headerData.pendingNum;
      data.headerData = headerData;
      return data;
    },
    pollingStatus() {
      this.timer = setTimeout(() => {
        clearTimeout(this.timer);
        if (this.btnType === 'RUNNING') {
          this.getHosts(this.id, this.nodeType).finally(() => {
            this.pollingStatus();
          });
        }
      }, this.t);
    },
    async handlePolling(v) {
      this.btnType = 'RUNNING';
      this.ajaxMark = true;
      if (v) {
        clearTimeout(this.timer);
        await this.getHostData(this.id, this.nodeType)
          .then(data => {
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
    },
    handleDone() {
      this.$emit('update:step', 1);
    },
    handleCancel() {
      this.$router.back();
    },
    async taskReadyStatusPromise(collect_config_id) {
      clearTimeout(timer);
      let timer = null;

      return new Promise(async resolve => {
        const show = await isTaskReady({ collect_config_id });
        if (show) {
          resolve(true);
          return;
        }
        timer = setTimeout(() => {
          this.taskReadyStatusPromise(collect_config_id).then(res => {
            resolve(res);
          });
        }, 2010);
      });
    },
  },
};
</script>
<style lang="scss" scoped>
.collector-host {
  padding: 30px 60px;

  .empty-data {
    display: flex;
    align-items: center;
    justify-content: center;
    height: 452px;
    margin-bottom: 20px;
    color: #979ba5;
    border: 1px dashed #dcdee5;
    border-radius: 2px;

    .hint-icon {
      font-size: 32px;
      color: #dcdee5;
    }

    p {
      margin-top: 12px;
      line-height: 1;
    }
  }

  .bk-button-text[disabled] {
    color: #c4c6cc;
  }

  .footer {
    font-size: 0;

    :deep(.bk-button) {
      margin-right: 10px;

      &.is-disabled {
        color: #fff;
        background-color: #dcdee5;
      }
    }
  }

  :deep(.bk-button-text) {
    padding-left: 0;
  }
}
</style>
