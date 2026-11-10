<!--
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
-->
<template>
  <div
    v-bkloading="{ isLoading: loading }"
    class="config-delivery"
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
        <bk-spin
          v-if="deliveryLoading || !deliveryError"
          size="normal"
          >{{ $tc('采集下发中， 请耐心等待') }}</bk-spin
        >
        <div
          v-else
          class="delivery-error-title"
        >
          {{ $tc('采集下发失败') }}
        </div>
        <ul
          v-if="deliveryMessages.length && !deliveryLoading"
          class="delivery-errors"
        >
          <li
            v-for="(msg, index) in deliveryMessages"
            :key="index"
            class="delivery-error-item"
          >
            {{ msg }}
          </li>
        </ul>
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
            :disabled="retryDisabled"
            icon="refresh"
            @click="handleDelivery"
          >
            {{ $tc('失败重试') }}
          </bk-button>
          <bk-button
            v-if="deliveryError && !deliveryLoading"
            class="back-btn"
            @click="handleBack"
          >
            {{ isBlocked ? $t('返回列表') : $t('返回修改') }}
          </bk-button>
        </div>
      </div>
    </template>
  </div>
</template>
<script>
import { CancelToken } from 'monitor-api/cancel';
import {
  batchRetryConfig,
  collectTargetStatus,
  isTaskReady,
  rollbackDeploymentConfig,
  saveCollectConfig,
} from 'monitor-api/modules/collecting';

import { TARGET_TABEL_EXPAND_MAX } from '../../../../constant/constant';
import ConfigDeploy from '../../config-deploy/config-deploy';
import {
  COLLECT_CONFIG_PARAMS_ERROR,
  CONFIG_VERSION_CHANGED,
  LEGACY_CONVERSION_FAILED,
  parseApiError,
} from '../config-set/components/multi-file-upload/utils/multi-file-upload-utils';
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
      /** 保存失败但已持久化的配置 ID：后续重试走原配置，不再重复保存 */
      failedConfigId: null,
      /** 失败原因（逐条展示） */
      deliveryMessages: [],
      /** 阻断类失败：unknown 结果未知 / version 源版本已变 / legacy 无法转换 / invalid 静态复验失败 */
      deliveryBlock: '',
    };
  },
  computed: {
    isConfigMapFlow() {
      return this.config.set.data.plugin.configMode === 'configmap';
    },
    /** 阻断后需离开本页（刷新/核对）而不是直接修改重试 */
    isBlocked() {
      // 新建已产生失败配置时，返回修改会再次按新建保存而重复创建，只能重试或回到列表处理
      const createdByFailedSave = !!this.failedConfigId && this.config.mode !== 'edit';
      return createdByFailedSave || ['unknown', 'version', 'legacy'].includes(this.deliveryBlock);
    },
    retryDisabled() {
      return this.deliveryLoading || !this.deliveryError || !!this.deliveryBlock;
    },
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
      if (this.deliveryLoading) return;
      this.deliveryLoading = true;
      this.deliveryError = false;
      this.deliveryBlock = '';
      this.deliveryMessages = [];
      const requestConfig = { cancelToken: new CancelToken(c => (this.cancelFn = c)), needMessage: false };
      // 已有失败的配置 ID 时，重试原配置，不能再次按新建调用保存
      const request = this.failedConfigId
        ? batchRetryConfig({ id: this.failedConfigId }, requestConfig)
        : saveCollectConfig(this.getParams(), requestConfig);
      await request
        .then(data => {
          if (!this.failedConfigId) this.syncSavedIdentity(data?.id, data?.deployment_id);
          this.deliveryLoading = false;
          this.$emit('next');
        })
        .catch(error => {
          this.handleDeliveryError(error);
          this.deliveryError = true;
          this.deliveryLoading = false;
        });
    },
    /** 保存/重试成功或失败后，沿用服务端返回的配置身份与目标版本（编辑后续不再复用旧源版本号） */
    syncSavedIdentity(id, deploymentId) {
      if (id) this.config.data.id = id;
      if (deploymentId) this.config.set.data.deploymentId = deploymentId;
    },
    handleDeliveryError(error) {
      const parsed = parseApiError(error);
      const fileErrors = parsed.files.flatMap(file => (file.errors || []).map(item => ({ ...item, file })));
      const codes = [...parsed.errors, ...fileErrors].map(item => item.code);
      const messages = [
        ...parsed.errors.map(item => item.message),
        ...fileErrors.map(item => `${item.file.filename}：${item.message}`),
      ];
      if (parsed.id) {
        this.failedConfigId = parsed.id;
        this.syncSavedIdentity(parsed.id, parsed.deploymentId);
      }
      if (codes.includes(CONFIG_VERSION_CHANGED)) {
        this.deliveryBlock = 'version';
      } else if (codes.includes(LEGACY_CONVERSION_FAILED)) {
        this.deliveryBlock = 'legacy';
      } else if (!parsed.hasResponse) {
        // 超时/断线/取消：新建时结果未知，不能直接重新新建；编辑沿用源版本校验，可重试
        if (this.config.mode !== 'edit' && !this.failedConfigId) {
          this.deliveryBlock = 'unknown';
          messages.push(this.$t('请求已中断或未收到响应，结果未知。请先到采集配置列表核对，避免重复新建'));
        }
      } else if (!parsed.id && parsed.code === COLLECT_CONFIG_PARAMS_ERROR) {
        this.deliveryBlock = 'invalid';
      }
      if (!messages.length && parsed.message) messages.push(parsed.message);
      this.deliveryMessages = messages;
    },
    handleBack() {
      if (this.isBlocked) {
        this.$router.push({ name: 'collect-config' });
        return;
      }
      this.$emit('tencentCloudPrevious');
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
      if (this.isConfigMapFlow) {
        // 多文件（ConfigMap）配置：声明 config_mode，文件字段已是完整目标集合 [{ uid, filename, content }]
        param.plugin.config_mode = 'configmap';
      }

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
        // 编辑所依据的源部署版本
        if (setData.deploymentId && this.isConfigMapFlow) {
          params.deployment_id = setData.deploymentId;
        }
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

    .back-btn {
      margin-left: 15px;
    }
  }

  .delivery-error-title {
    font-size: 16px;
    color: #313238;
  }

  .delivery-errors {
    max-width: 640px;
    margin-top: 12px;
    text-align: left;

    .delivery-error-item {
      line-height: 22px;
      color: #ea3636;
      word-break: break-all;
    }
  }
}
</style>
