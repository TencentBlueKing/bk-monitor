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
    ref="addDel"
    class="collector-host"
  >
    <template v-if="taskReady.show">
      <task-ready
        :task-ready="taskReady.status"
        :target="target"
      />
    </template>
    <template v-else>
      <div v-if="tables && tables.contents && tables.contents.length">
        <config-deploy
          :is-running="isRunning"
          :all-data="tables"
          @can-polling="handlePolling"
          @refresh="handleRefreshData"
        />
      </div>
      <div v-else>
        <div class="empty-tips">
          <span class="icon-monitor icon-tips" />
          <span class="text"> {{ $t('未选择采集目标，但并不影响本次操作') }} </span>
        </div>
        <div class="empty-data">
          <div style="text-align: center">
            <i class="icon-monitor icon-tishi hint-icon" />
            <p>{{ $t('未选择采集目标，无需下发') }}</p>
          </div>
        </div>
      </div>
      <div class="footer">
        <bk-button
          theme="primary"
          :disabled="hasRunning"
          @click="handleDone"
          >{{ hasRunning ? $t('button-执行中') : $t('button-完成') }}</bk-button
        >
        <bk-button
          v-if="showRollBack"
          :disabled="hasRunning"
          @click="handleRollback"
        >
          {{ $t('回滚') }}
        </bk-button>
      </div>
    </template>
  </div>
</template>
<script>
import { collectTargetStatus, isTaskReady, rollbackDeploymentConfig } from 'monitor-api/modules/collecting';

import { TARGET_TABEL_EXPAND_MAX } from '../../../../constant/constant';
import TaskReady from '../../collector-add/config-delivery/task-ready';
import ConfigDeploy from '../../config-deploy/config-deploy';

export default {
  name: 'AddDell',
  components: {
    ConfigDeploy,
    TaskReady,
  },
  props: {
    data: {
      type: Object,
      default: () => ({}),
    },
    pageLoading: Boolean,
    openDetail: Boolean,
    step: {
      type: Number,
      default: 1,
    },
    type: {
      type: String,
      default: 'ADD_DEL',
    },
    diffData: {
      type: Object,
      default: () => ({}),
    },
    needRollback: {
      type: Boolean,
      default: true,
    },
    target: {
      type: Object,
      default: () => {},
    },
  },
  data() {
    return {
      tables: [],
      newDiffData: [],
      objType: 'HOST',
      isRunning: true,
      nodeType: 'INSTANCE',
      operationType: '',
      hasRunning: true,
      id: null,
      showRollBack: true,
      t: 10000,
      hasChange: false,
      timer: null,
      ajaxMark: null,
      taskReadyTimer: null,
      taskReady: {
        show: true,
        status: {
          msg: this.$t('准备中...'),
        },
      },
    };
  },
  computed: {
    isInstance() {
      return this.nodeType === 'INSTANCE';
    },
    hostTotal() {
      let total = 0;
      this.tables.forEach(item => {
        total += item.len;
      });
      return total;
    },
  },
  watch: {
    'taskReady.show': {
      handler(is) {
        if (!is) {
          this.$emit('update:pageLoading', true);
          this.init();
        }
      },
      immediate: true,
    },
  },
  async created() {
    this.$emit('update:pageLoading', false);

    setTimeout(async () => {
      const show = await isTaskReady({ collect_config_id: this.data.id });
      this.taskReady.show = !show;
      if (this.taskReady.show) {
        this.taskReadyStatus();
      }
    }, 1000);
  },
  mounted() {
    this.$emit('update:pageLoading', false);
  },
  beforeDestroy() {
    clearTimeout(this.timer);
    clearTimeout(this.taskReadyTimer);
  },
  methods: {
    async taskReadyStatus() {
      this.taskReadyTimer = setTimeout(async () => {
        clearTimeout(this.taskReadyTimer);
        if (this.taskReady.show) {
          const show = await isTaskReady({ collect_config_id: this.data.id });
          this.taskReady.show = !show;
          this.taskReadyStatus();
        }
      }, 2000);
    },
    async init() {
      this.id = this.data.id;
      this.nodeType = this.data.target_node_type;
      this.objType = this.data.target_object_type;
      this.operationType = this.type;
      await this.getHosts(this.id, this.nodeType).catch(() => {});
      this.pollingStatus();
      this.showRollBack = this.needRollback;
    },
    handleData(data) {
      const oldContent = this.tables.contents;
      const content = data.contents;
      const sumData = {
        success: {},
        failed: {},
        pending: {},
      };
      content.forEach((item, index) => {
        item.successNum = 0;
        item.failedNum = 0;
        item.pendingNum = 0;
        item.table = [];
        item.expand = item.child.length > 0 ? index <= TARGET_TABEL_EXPAND_MAX - 1 : false;
        item.expand = oldContent?.length && oldContent[index] ? oldContent[index].expand : item.expand;
        item.child.forEach(set => {
          if (set.status === 'SUCCESS') {
            sumData.success[set.instance_id] = set.instance_id;
            item.successNum += 1;
          } else if (set.status === 'PENDING' || set.status === 'RUNNING') {
            item.pendingNum += 1;
            sumData.pending[set.instance_id] = set.instance_id;
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
    handleDone() {
      if (this.openDetail) {
        this.$bus.$emit('back');
      } else {
        this.$emit('update:step', 2);
        this.$emit('step-change', true, 1);
      }
    },
    async handleRollback() {
      this.$bkInfo({
        title: this.$t('回滚操作'),
        subTitle: this.$t('将回滚本次的所有配置变更和目标机器的内容。回滚只能回滚上一次的状态，并且只能进行一次。'),
        okText: this.$t('确认回滚'),
        confirmFn: () => {
          this.$emit('update:pageLoading', true);
          this.operationType = 'ROLLBACK';
          this.$emit('update:type', 'ROLLBACK');
          rollbackDeploymentConfig({ id: this.id }, { needMessage: false })
            .then(async () => {
              const isReady = await this.taskReadyStatusPromise(this.id);
              if (isReady) {
                this.showRollBack = false;
                this.hasRunning = true;
                this.getHosts(this.id, this.nodeType);
                this.pollingStatus();
              }
            })
            .catch(err => {
              this.bkMsg('error', err.message || this.$t('出错了'));
              this.$emit('update:pageLoading', false);
            });
        },
      });
    },
    bkMsg(theme, message) {
      this.$bkMessage({
        theme,
        message,
        ellipsisLine: 0,
      });
    },
    handleRefreshData(id) {
      collectTargetStatus({ id })
        .then(data => {
          this.tables = this.handleData(data);
          this.$emit('update:hosts', this.tables);
        })
        .catch(err => {
          this.bkMsg('error', err.message || this.$t('出错了'));
        });
    },
    getHosts(id) {
      return collectTargetStatus({ id }, { needMessage: false })
        .then(data => {
          this.tables = this.handleData(data);
          this.hasRunning = data.contents.some(item =>
            item.child.some(set => set.status === 'RUNNING' || set.status === 'PENDING')
          );
          this.$emit('update:hosts', this.tables);
        })
        .catch(err => {
          this.bkMsg('error', err.message || this.$t('出错了'));
        })
        .finally(() => {
          this.$emit('update:pageLoading', false);
        });
    },
    getHostData(id) {
      return new Promise((resolve, reject) => {
        this.ajaxMark = false;
        collectTargetStatus({ id })
          .then(data => {
            if (this.ajaxMark) {
              reject(data);
            } else {
              resolve(data);
            }
          })
          .catch(data => {
            reject(data);
          })
          .finally(() => {
            this.$emit('update:pageLoading', false);
          });
      });
    },
    pollingStatus() {
      this.timer = setTimeout(() => {
        clearTimeout(this.timer);
        if (this.hasRunning) {
          this.getHosts(this.id, this.nodeType).finally(() => {
            this.pollingStatus();
          });
        }
      }, this.t);
    },
    async handlePolling(v) {
      this.hasRunning = true;
      this.ajaxMark = true;
      if (v) {
        clearTimeout(this.timer);
        await this.getHostData(this.id, this.nodeType)
          .then(data => {
            if (this.ajaxMark) {
              this.tables = this.handleData(data);
              this.hasRunning = data.contents.some(item =>
                item.child.some(set => set.status === 'RUNNING' || set.status === 'PENDING')
              );
              this.$emit('update:hosts', this.tables);
            }
          })
          .catch(() => {})
          .finally(() => {
            this.pollingStatus();
          });
      } else {
        clearTimeout(this.timer);
      }
    },
    async taskReadyStatusPromise(id) {
      let timer = null;
      clearTimeout(timer);

      return new Promise(async resolve => {
        const show = await isTaskReady({ collect_config_id: id });
        if (show) {
          resolve(true);
        } else {
          timer = setTimeout(() => {
            this.taskReadyStatusPromise(id).then(res => {
              resolve(res);
            });
          }, 2000);
        }
      });
    },
  },
};
</script>
<style lang="scss" scoped>
.collector-host {
  padding: 40px 60px;

  .table-item {
    margin-top: 20px;

    &:first-child {
      margin-top: 0;
    }

    &:hover {
      background-color: #f0f1f5;
    }
  }

  .empty-tips {
    height: 36px;
    padding-left: 12px;
    margin-bottom: 10px;
    line-height: 36px;
    background-color: #f0f8ff;
    border: 1px solid #a3c5fd;
    border-radius: 2px;

    .icon-tips {
      padding-right: 5px;
      font-size: 14px;
      color: #3a84ff;
    }

    .text {
      font-size: 12px;
      color: #63656e;
    }
  }

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
