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
    class="config-delivery"
    v-bkloading="{ isLoading: loading }"
    :class="{ 'need-loading': loading }"
  >
    <template v-if="!isTencentCloudPlugin">
      <template v-if="taskReady.show">
        <task-ready
          :target="config.target"
          :task-ready="taskReady.status"
        />
      </template>
      <template v-else>
        <template v-if="tables && tables.contents && tables.contents.length">
          <config-deploy
            :all-data="tables"
            @can-polling="handlePolling"
            @refresh="handleRefreshData"
          />
        </template>
        <template v-else>
          <empty-target />
        </template>
        <div class="footer">
          <bk-button
            class="footer-btn"
            :disabled="hasRunning"
            theme="primary"
            @click="!hasRunning && $emit('next')"
            >{{ hasRunning ? $t('下发中...') : $t('button-完成') }}</bk-button
          >
          <bk-button
            v-if="showRollBack && allowRollBack"
            :disabled="hasRunning"
            @click="handleRollback"
          >
            {{ $t('回滚') }}
          </bk-button>
        </div>
      </template>
    </template>
    <template v-else>
      <div class="tencent-cloud-delivery">
        <bk-spin size="normal">{{ $tc('采集下发中， 请耐心等待') }}</bk-spin>
        <div class="btns">
          <bk-button
            class="stop-btn"
            :disabled="!deliveryLoading"
            size="normal"
            @click="handleDeliveryCancel"
          >
            {{ $tc('任务终止') }}
          </bk-button>
          <bk-button
            :disabled="deliveryLoading || !deliveryError"
            icon="refresh"
            @click="handleDelivery"
          >
            {{ $tc('失败重试') }}
          </bk-button>
        </div>
      </div>
    </template>
  </div>
</template>
<script>
import { CancelToken } from 'monitor-api/cancel';
import {
  collectTargetStatus,
  isTaskReady,
  rollbackDeploymentConfig,
  saveCollectConfig,
} from 'monitor-api/modules/collecting';

import { TARGET_TABEL_EXPAND_MAX } from '../../../../constant/constant';
import ConfigDeploy from '../../config-deploy/config-deploy';
import EmptyTarget from './empty-target';
import TaskReady from './task-ready';

export default {
  name: 'ConfigDelivery',
  components: {
    ConfigDeploy,
    EmptyTarget,
    TaskReady,
  },
  props: {
    config: {
      type: Object,
      default: () => {},
    },
    hosts: Object,
  },
  data() {
    return {
      loading: false,
      hasRunning: true,
      showRollBack: false,
      tables: [],
      timer: null,
      taskReadyTimer: null,
      t: 10000,
      newDiffData: [],
      ajaxMark: false,
      taskReady: {
        show: true,
        status: {
          msg: this.$t('准备中...'),
        },
      },
      deliveryLoading: false,
      deliveryError: false,
      cancelFn: null,
    };
  },
  computed: {
    allowRollBack() {
      if (this.config.mode === 'edit' && this.config.select && this.config.select.others) {
        return !!this.config.select.others.allowRollback;
      }
      return true;
    },
    // 是否是腾讯云插件
    isTencentCloudPlugin() {
      return this.config.set.data.plugin.type === 'K8S';
    },
  },
  watch: {
    'taskReady.show': {
      handler(is) {
        if (!is) {
          this.init();
        }
      },
      immediate: true,
    },
  },
  async created() {
    if (this.isTencentCloudPlugin) {
      this.handleDelivery();
    } else {
      setTimeout(async () => {
        const show = await isTaskReady({ collect_config_id: this.config.data.id });
        this.taskReady.show = !show;
        if (this.taskReady.show) {
          this.taskReadyStatus();
        }
      }, 1000);
    }
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
          const show = await isTaskReady({ collect_config_id: this.config.data.id });
          this.taskReady.show = !show;
          this.taskReadyStatus();
        }
      }, 2000);
    },
    async init() {
      this.loading = true;
      await this.getHosts(this.config.data.id);
      this.showRollBack = this.config.mode === 'edit';
      this.pollingStatus();
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
      this.ajaxMark = false;
      return collectTargetStatus({ id }, { needMessage: false })
        .then(data => {
          this.tables = this.handleData(data);
          this.hasRunning = data.contents.some(item =>
            item.child.some(set => ['RUNNING', 'PENDING'].includes(set.status))
          );
          this.$emit('update:hosts', this.tables);
        })
        .catch(error => {
          this.bkMsg('error', error.message || this.$t('出错了'));
        })
        .finally(() => {
          this.loading = false;
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
          .catch(err => {
            reject(err);
          })
          .finally(() => {
            this.loading = false;
          });
      });
    },
    handleData(data) {
      const oldContent = this.tables.contents;
      const sumData = {
        failed: {},
        pending: {},
        success: {},
      };
      const content = data.contents;
      content.forEach((item, index) => {
        item.failedNum = 0;
        item.successNum = 0;
        item.pendingNum = 0;
        item.expand = item.child.length > 0 ? index <= TARGET_TABEL_EXPAND_MAX - 1 : false;
        item.expand = oldContent?.length && oldContent[index] ? oldContent[index].expand : item.expand;
        item.table = [];
        item.child.forEach(set => {
          if (set.status === 'SUCCESS') {
            sumData.success[set.instance_id] = set.instance_id;
            item.successNum += 1;
          } else if (['RUNNING', 'PENDING'].includes(set.status)) {
            sumData.pending[set.instance_id] = set.instance_id;
            item.pendingNum += 1;
          } else {
            sumData.failed[set.instance_id] = set.instance_id;
            item.failedNum += 1;
          }
        });
      });
      const headerData = {};
      headerData.failedNum = Object.keys(sumData.failed).length;
      headerData.pendingNum = Object.keys(sumData.pending).length;
      headerData.successNum = Object.keys(sumData.success).length;
      headerData.total = headerData.successNum + headerData.failedNum + headerData.pendingNum;
      data.headerData = headerData;
      return data;
    },
    bkMsg(theme, message) {
      this.$bkMessage({
        theme,
        message,
        ellipsisLine: 0,
      });
    },
    async handleRollback() {
      this.$bkInfo({
        title: this.$t('回滚操作'),
        subTitle: this.$t('将回滚本次的所有配置变更和目标机器的内容。回滚只能回滚上一次的状态，并且只能进行一次。'),
        okText: this.$t('确认回滚'),
        confirmFn: () => {
          // this.$parent.pageLoading = true
          this.loading = true;
          this.showRollBack = false;
          this.hasRunning = true;
          this.$emit('update:type', 'ROLLBACK');
          rollbackDeploymentConfig({ id: this.config.data.id }, { needMessage: false })
            .then(async () => {
              const isReady = await this.taskReadyStatusPromise(this.config.data.id);
              if (isReady) {
                this.getHosts(this.config.data.id);
                this.pollingStatus();
              }
            })
            .catch(err => {
              this.showRollBack = true;
              this.loading = false;
              this.bkMsg('error', err.message || this.$t('出错了'));
            });
        },
      });
    },
    pollingStatus() {
      this.timer = setTimeout(() => {
        clearTimeout(this.timer);
        if (this.hasRunning) {
          this.getHosts(this.config.data.id).finally(() => {
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
        await this.getHostData(this.config.data.id)
          .then(data => {
            if (this.ajaxMark) {
              this.tables = this.handleData(data);
              this.hasRunning = data.contents.some(item =>
                item.child.some(set => set.status === 'RUNNING' || set.status === 'PENDING')
              );
              this.$emit('update:hosts', this.tables);
            }
          })
          .finally(() => {
            this.pollingStatus();
          });
      } else {
        clearTimeout(this.timer);
      }
    },
    async taskReadyStatusPromise(id) {
      clearTimeout(this.timer);
      let timer = null;
      // biome-ignore lint/suspicious/noAsyncPromiseExecutor: <explanation>
      return new Promise(async resolve => {
        const isShow = await isTaskReady({ collect_config_id: id }).catch(() => false);
        if (isShow) {
          resolve(true);
          return undefined;
        }
        timer = setTimeout(() => {
          this.taskReadyStatusPromise(id).then(res => {
            resolve(res);
          });
        }, 2000);
      });
    },
    // 开始下发
    async handleDelivery() {
      const params = this.getParams();
      this.deliveryLoading = true;
      // 保存配置
      await saveCollectConfig(params, { cancelToken: new CancelToken(c => (this.cancelFn = c)) })
        .then(() => {
          this.deliveryError = false;
          this.deliveryLoading = false;
          this.$emit('next');
        })
        .catch(() => {
          this.deliveryError = true;
          this.deliveryLoading = false;
        });
    },
    handleDeliveryCancel() {
      this.cancelFn?.();
    },
    // 获取要保存的数据
    getParams() {
      const setData = this.config.set.data;
      const pluginData = setData.plugin;
      const param = {
        collector: {
          period: setData.period,
          timeout: setData.timeout,
        },
        plugin: {},
      };
      pluginData.configJson.forEach(item => {
        param.plugin[item.field || item.name] = item.default;
      });

      const params = {
        name: setData.name,
        bk_biz_id: setData.bizId,
        collect_type: setData.collectType,
        target_object_type: 'CLUSTER',
        plugin_id: pluginData.id,
        params: param,
        label: setData.objectId,
        target_node_type: 'CLUSTER',
        target_nodes: [],
        remote_collecting_host: null,
      };
      if (this.config.mode === 'edit' && setData.id) {
        // 编辑时，增加 `id` 字段
        params.id = setData.id;
      }
      return params;
    },
  },
};
</script>

<style lang="scss" scoped>
.config-delivery {
  display: flex;
  flex-direction: column;
  padding: 41px 60px;

  &.need-loading {
    min-height: calc(100vh - 80px);
  }

  .footer-btn {
    margin-right: 8px;
  }
}

.tencent-cloud-delivery {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 300px;

  .btns {
    margin-top: 50px;

    .stop-btn {
      margin-right: 15px;
    }
  }
}
</style>
