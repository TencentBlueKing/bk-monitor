<!-- eslint-disable vue/no-v-html -->
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
  <div class="config-deploy">
    <div
      class="config-deploy-description"
      v-if="$route.name === 'collect-config-operate-detail'"
    >
      <i class="icon-monitor icon-tips item-icon" />
      <i18n path="该内容是对{0}进行'{1}'操作的执行详情">
        {{ config.name }}
        <span class="operation-step-name">{{ operationStepName }}</span>
      </i18n>
    </div>
    <div
      class="config-deploy-header"
      v-if="isRunning"
    >
      <div class="header-filter">
        <div
          v-for="(item) in statusList"
          :key="item.id"
          :class="['header-filter-item', { active: item.id === header.status }]"
          @click="header.status = item.id"
        >
          <span
            v-if="item.color"
            class="point mr-3"
            :style="{ background: item.color[0] }"
          >
            <span
              class="s-point"
              :style="{ background: item.color[1] }"
            />
          </span>
          <span v-if="item.id === 'RUNNING'">
            <bk-spin
              size="mini"
              class="mr-3"
            />
          </span>
          <span class="mr-3">{{item.name}}</span>
          <span class="mt-2">{{item.count}}</span>
        </div>
      </div>
      <!-- <div class="bk-button-group">
        <bk-button
          @click="header.status = 'ALL'"
          :class="{ 'is-selected': header.status === 'ALL' }"
          size="normal"
        >
          {{ $t('全部') }}({{ header.data.total }})</bk-button>
        <bk-button
          @click="header.status = 'SUCCESS'"
          :class="{ 'is-selected': header.status === 'SUCCESS' }"
          size="normal"
        >
          {{ $t('成功') }}({{ header.data.successNum }})</bk-button>
        <bk-button
          @click="header.status = 'FAILED'"
          :class="{ 'is-selected': header.status === 'FAILED' }"
          size="normal"
        >
          {{ $t('失败') }}({{ header.data.failedNum }})</bk-button>
        <bk-button
          @click="header.status = 'RUNNING'"
          :class="{ 'is-selected': header.status === 'RUNNING' }"
          size="normal"
        >
          {{ $t('执行中') }}({{ header.data.pendingNum }})</bk-button>
      </div> -->
      <bk-button
        :icon="header.batchRetry ? 'loading' : ''"
        :disabled="header.batchRetry || !(header.data.failedNum > 0 && header.data.pendingNum === 0)"
        class="ml-auto header-retry"
        hover-theme="primary"
        @click="handleBatchRetry"
      >
        <i
          v-if="!header.batchRetry"
          class="icon-monitor icon-mc-retry"
        />
        {{ $t('批量重试') }}
      </bk-button>
      <bk-button
        :icon="disBatch ? 'loading' : ''"
        :disabled="!haveDeploying || disBatch"
        class="header-retry"
        hover-theme="primary"
        @click="handleBatchStop"
      >{{ $t('批量终止') }}
      </bk-button>
      <bk-button
        class="header-retry"
        hover-theme="primary"
        @click="handleCopyTargets"
      >{{ $t('复制目标') }}
      </bk-button>
    </div>
    <div
      class="config-deploy-content"
      v-if="content.length"
    >
      <right-panel
        class="content-panel"
        v-for="(item, index) in content"
        :key="index"
        need-border
        :collapse="item.expand"
        @change="handleCollapseChange(item, $event)"
        title-bg-color="#F0F1F5"
        :collapse-color="item.child.length ? '#313238' : '#C4C6CC'"
        :class="{ 'no-data': !item.child.length }"
        :style="{
          borderBottomWidth: item.expand ? '0' : '1px',
          marginBottom: index === content.length - 1 ? '20px' : '10px'
        }"
        :content-render="false"
      >
        <bk-table
          class="content-panel-table"
          :data="item.table"
          :empty-text="$t('无数据')"
          max-height="450"
        >
          <bk-table-column
            min-width="120"
            :label="$t('目标')"
            prop="instance_name"
          />
          <bk-table-column
            width="120"
            :label="$t('状态')"
          >
            <template slot-scope="props">
              <div class="col-status">
                <img
                  class="col-status-img"
                  v-if="isRunning && (props.row.status === 'RUNNING' || props.row.status === 'PENDING')"
                  src="../../../static/images/svg/spinner.svg"
                  alt=''
                >
                <div
                  class="col-status-radius"
                  v-if="['SUCCESS', 'FAILED'].includes(props.row.status)"
                  :style="{
                    background: statusMap[props.row.status].color,
                    'border-color': borderMap[props.row.status]
                  }"
                />
                <span v-if="isRunning">{{ statusMap[props.row.status].name }}</span>
                <span v-else>--</span>
              </div>
            </template>
          </bk-table-column>
          <bk-table-column
            width="90"
            :label="$t('版本')"
            prop="plugin_version"
          />
          <bk-table-column
            :label="$t('详情')"
            min-width="200"
          >
            <template slot-scope="props">
              <div class="col-detail">
                <span class="col-detail-data">{{ props.row.log || '--' }}</span>
                <span
                  class="col-detail-more"
                  v-if="isRunning && props.row.status === 'FAILED'"
                  @click="handleGetMoreDetail(props.row)"
                >
                  {{ $t('详情') }}
                </span>
              </div>
            </template>
          </bk-table-column>
          <bk-table-column
            width="100"
            label=""
          >
            <template slot-scope="props">
              <div
                class="col-retry"
                v-if="isRunning && props.row.status === 'FAILED'"
                @click="props.row.status === 'FAILED' && handleRetry(props.row, item)"
              >
                {{ $t('重试') }}
              </div>
              <div
                class="col-retry"
                v-if="isRunning && ['DEPLOYING', 'RUNNING', 'PENDING'].includes(props.row.status)"
                @click="['DEPLOYING', 'RUNNING', 'PENDING'].includes(props.row.status) && handleRevoke(props.row, item)"
              >
                {{ $t('终止') }}
              </div>
            </template>
          </bk-table-column>
        </bk-table>
        <template slot="pre-panel">
          <div
            class="pre-panel"
            v-if="item.is_label"
          >
            <!-- <div class="pre-panel"> -->
            <span
              class="pre-panel-name"
              :style="{ backgroundColor: labelMap[item.label_name].color }"
            >{{
              labelMap[item.label_name].name
            }}</span>
            <span
              class="pre-panel-mark"
              :style="{ borderColor: labelMap[item.label_name].color }"
            />
          </div>
        </template>
        <div
          slot="title"
          class="panel-title"
        >
          <span class="title-name">{{ item.node_path }}</span>
          <div class="total">
            <template v-if="isRunning">
              <span
                class="num"
                v-if="item.successNum"
              >
                <i18n path="{0}个成功">
                  <span style="color: #2dcb56">{{ item.successNum }}</span>
                </i18n>
                <span v-if="item.failedNum || item.pendingNum">,</span>
              </span>
              <span
                class="num"
                v-if="item.failedNum"
              >
                <i18n path="{0}个失败">
                  <span style="color: #ea3636">{{ item.failedNum }}</span>
                </i18n>
                <span v-if="item.pendingNum">,</span>
              </span>
              <span
                class="num"
                v-if="item.pendingNum"
              >
                <i18n path="{0}个执行中">
                  <span style="color: #3a84ff">{{ item.pendingNum }}</span>
                </i18n>
              </span>
              <span
                class="num"
                v-else-if="!item.child.length"
              >
                <i18n :path="`共{0}${config.target_object_type === 'HOST' ? '台主机' : '个实例'}`">
                  <span style="color: #63656e">0</span>
                </i18n>
              </span>
            </template>
            <span
              class="num"
              v-else
            >
              <i18n :path="`共{0}${config.target_object_type === 'HOST' ? '台主机' : '个实例'}`">
                {{ item.successNum + item.failedNum + item.pendingNum }}
              </i18n>
            </span>
          </div>
        </div>
      </right-panel>
    </div>
    <bk-sideslider
      :is-show.sync="side.show"
      :quick-close="true"
      :width="900"
      :title="side.title"
    >
      <div
        class="side-detail"
        slot="content"
        v-bkloading="{ isLoading: side.loading }"
      >
        <!-- eslint-disable-next-line vue/no-v-html -->
        <pre
          class="side-detail-code"
          v-html="transformJobUrl(side.detail)"
        />
      </div>
    </bk-sideslider>
  </div>
</template>
<script>
import {
  batchRetryConfig,
  batchRevokeTargetNodes,
  getCollectLogDetail,
  isTaskReady,  retryTargetNodes,
  revokeTargetNodes } from '../../../../monitor-api/modules/collecting';
import { copyText } from '../../../../monitor-common/utils/utils.js';
import RightPanel from '../../../components/ip-select/right-panel';
import { transformJobUrl } from '../../../utils/index';

export default {
  name: 'ConfigDeploy',
  components: {
    RightPanel
  },
  props: {
    allData: {
      type: Object,
      required: true
    },
    isRunning: {
      type: Boolean,
      default: true
    }
  },
  data() {
    return {
      transformJobUrl,
      disBatch: false,
      header: {
        status: 'ALL',
        batchRetry: false,
        data: {
          successNum: 0,
          failedNum: 0,
          pendingNum: 0,
          total: 0
        }
      },
      content: null,
      config: null,
      refresh: true,
      operationStepName: '',
      labelMap: {
        ADD: {
          color: '#3A84FF',
          name: this.$t('新增')
        },
        REMOVE: {
          color: '#6C3AFF',
          name: this.$t('删除')
        },
        UPDATE: {
          color: '#FF9C01',
          name: this.$t('变更')
        },
        RETRY: {
          color: '#414871',
          name: this.$t('重试')
        }
      },
      statusMap: {
        SUCCESS: {
          color: '#94F5A4',
          name: this.$t('成功')
        },
        FAILED: {
          color: '#FD9C9C',
          name: this.$t('失败')
        },
        PENDING: {
          color: '#3A84FF',
          name: this.$t('等待中')
        },
        RUNNING: {
          color: '#3A84FF',
          name: this.$t('执行中')
        }
      },
      borderMap: {
        SUCCESS: '#2DCB56',
        FAILED: '#EA3636'
      },
      side: {
        show: false,
        title: '',
        detail: '',
        loading: false
      }
    };
  },
  computed: {
    haveDeploying() {
      const resArr = [];
      this.content.forEach((item) => {
        const res = item.child.some(one => ['DEPLOYING', 'RUNNING', 'PENDING'].includes(one.status));
        resArr.push(res);
      });
      return resArr.some(item => item);
    },
    statusList() {
      return [
        { id: 'ALL', name: window.i18n.t('全部'), count: this.header.data.total },
        { id: 'SUCCESS', color: ['#3fc06d29', '#3FC06D'], name: window.i18n.t('正常'), count: this.header.data.successNum },
        { id: 'FAILED', color: ['#ea363629', '#EA3636'], name: window.i18n.t('异常'), count: this.header.data.failedNum },
        { id: 'RUNNING', name: window.i18n.t('执行中'), count: this.header.data.pendingNum }
      ];
    }
  },
  watch: {
    allData: {
      handler(v) {
        if (this.refresh) {
          this.handleData(v);
        }
      },
      immediate: true
    },
    'header.status': {
      handler: 'handleStatusChange'
    }
  },
  methods: {
    handleData(data) {
      this.config = data.config_info;
      const { status } = this.header;
      this.header.data = data.headerData;
      this.content = data.contents;
      this.content.forEach((item) => {
        item.child.forEach((set) => {
          if (set.status === 'RUNNING' || set.status === 'PENDING' || set.status === status || status === 'ALL') {
            item.table.push(set);
          }
        });
      });
      const operationStepMap = {
        ADD_DEL: this.$t('增删目标'),
        UPGRADE: this.$t('升级'),
        CREATE: this.$t('创建'),
        EDIT: this.$t('编辑'),
        START: this.$t('启用'),
        STOP: this.$t('停用'),
        ROLLBACK: this.$t('回滚')
      };
      this.operationStepName = operationStepMap[this.config.last_operation];
    },
    handleRetry(data, table) {
      this.refresh = false;
      if (this.side.title === data.instance_name) {
        this.side.title = '';
      }
      this.content.forEach((item) => {
        if (item.child?.length) {
          const setData = item.child.find(set => set.instance_id === data.instance_id && set.status === 'FAILED');
          if (setData) {
            setData.status = 'PENDING';
            item.pendingNum += 1;
            item.failedNum -= 1;
          }
        }
      });
      this.header.data.pendingNum += 1;
      this.header.data.failedNum -= 1;
      this.handlePolling(false);
      retryTargetNodes({
        id: this.config.id,
        instance_id: data.instance_id
      })
        .then(async () => {
          const isReady = await this.taskReadyStatus(this.config.id);
          if (isReady) {
            this.refresh = true;
            this.handlePolling();
          }
        })
        .catch(() => {
          data.status = 'FAILED';
          table.pendingNum -= 1;
          table.failedNum += 1;
          this.header.data.pendingNum -= 1;
          this.header.data.failedNum += 1;
          this.refresh = true;
          this.handlePolling();
          // this.bkMsg('error', res.responseText || '出错了')
        });
    },
    handleRevoke(data, table) {
      revokeTargetNodes({
        id: this.config.id,
        instance_ids: [data.instance_id]
      }).finally(() => {
        data.status = 'FAILED';
        table.pendingNum -= 1;
        table.failedNum += 1;
        this.header.data.pendingNum -= 1;
        this.header.data.failedNum += 1;
        this.refresh = true;
        this.handlePolling();
      });
    },
    async handleBatchRetry() {
      const failed = [];
      this.refresh = false;
      this.header.batchRetry = true;
      this.side.title = '';
      this.content.forEach((item) => {
        item.child.forEach((set) => {
          if (set.status === 'FAILED') {
            set.status = 'PENDING';
            failed.push(set);
          }
        });
        item.pendingNum += item.failedNum;
        item.failedNum = 0;
      });
      this.header.data.pendingNum += this.header.data.failedNum;
      this.header.data.failedNum = 0;
      this.handlePolling(false);
      batchRetryConfig({
        id: this.config.id
      })
        .then(async () => {
          const isReady = await this.taskReadyStatus(this.config.id);
          if (isReady) {
            this.header.batchRetry = false;
            this.refresh = true;
            this.handlePolling();
          }
        })
        .catch(() => {
          failed.forEach((item) => {
            item.status = 'FAILED';
          });
          this.header.data.pendingNum = 0;
          this.header.data.failedNum = failed.length;
          this.header.batchRetry = false;
          this.refresh = true;
          this.handlePolling();
        });
    },
    handleBatchStop() {
      this.refresh = false;
      this.disBatch = true;
      batchRevokeTargetNodes({
        id: this.config.id
      }).finally(() => {
        this.disBatch = false;
        this.header.batchRetry = false;
        this.refresh = true;
        this.$emit('refresh', this.config.id);
      });
    },
    bkMsg(theme, message) {
      this.$bkMessage({
        theme,
        message,
        ellipsisLine: 0
      });
    },
    handlePolling(v = true) {
      this.$emit('can-polling', v);
    },
    handleStatusChange(status) {
      this.content.forEach((item) => {
        item.table = [];
        item.child.forEach((set) => {
          if (
            (status === 'RUNNING' && (set.status === 'RUNNING' || set.status === 'PENDING'))
            || set.status === status
            || status === 'ALL'
          ) {
            item.table.push(set);
          }
        });
      });
    },
    handleCollapseChange(item, v) {
      if (item.child.length) {
        item.expand = v;
      }
    },
    handleGetMoreDetail(data) {
      this.side.show = true;
      if (this.side.title !== data.instance_name) {
        this.side.title = data.instance_name;
        this.side.loading = true;
        getCollectLogDetail(
          {
            id: this.config.id,
            instance_id: data.instance_id,
            task_id: data.task_id
          },
          { needMessage: false }
        )
          .then((data) => {
            this.side.detail = data.log_detail;
            this.side.loading = false;
          })
          .catch((err) => {
            this.bkMsg('error', err.message || this.$t('获取更多数据失败'));
            this.side.show = false;
            this.side.loading = false;
          });
      }
    },
    async taskReadyStatus(id) {
      let timer = null;
      clearTimeout(timer);
      // eslint-disable-next-line @typescript-eslint/no-misused-promises
      return new Promise(async (resolve) => {
        const show = await isTaskReady({ collect_config_id: id });
        if (show) {
          resolve(true);
        } else {
          timer = setTimeout(() => {
            this.taskReadyStatus(id).then((res) => {
              resolve(res);
            });
          }, 2000);
        }
      });
    },
    handleCopyTargets() {
      let copyStr = '';
      this.content.forEach((item) => {
        item.table.forEach((tableItem) => {
          copyStr += `${tableItem.instance_name}\n`;
        });
      });
      copyText(copyStr, (msg) => {
        this.$bkMessage({
          message: msg,
          theme: 'error'
        });
        return;
      });
      this.$bkMessage({
        message: this.$t('复制成功'),
        theme: 'success'
      });
    }
  }
};
</script>
<style lang="scss" scoped>
.mr-3 {
  margin-right: 3px;
}

.ml-auto {
  margin-left: auto !important;
}

.mt-2 {
  margin-top: 2px;
}

@mixin pointStatus() {
  .point {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 13px;
    height: 13px;
    border-radius: 50%;

    .s-point {
      width: 7px;
      height: 7px;
      border-radius: 50%;
    }
  }
}

@mixin filterList() {
  .header-filter {
    display: flex;
    align-items: center;
    height: 32px;
    padding: 0 4px;
    color: #63656e;
    background: #f0f1f5;
    border-radius: 2px;

    .header-filter-item {
      position: relative;
      display: flex;
      align-items: center;
      justify-content: center;
      height: 24px;
      padding: 0 12px;
      cursor: pointer;

      @include pointStatus();

      &:not(:last-of-type) {
        &::after {
          position: absolute;
          top: 6px;
          right: 0px;
          width: 1px;
          height: 12px;
          content: '';
          background: #dcdee5;
        }
      }

      &.active {
        color: #3a84ff;
        background: #fff;

        &::after {
          display: none;
        }

        &::before {
          position: absolute;
          top: 6px;
          left: -1px;
          width: 1px;
          height: 12px;
          content: '';
          background: #f0f1f5;
        }
      }
    }
  }
}

.config-deploy {
  &-description {
    height: 16px;
    margin-bottom: 20px;
    font-size: 12px;
    line-height: 16px;
    color: #63656e;

    .icon-tips {
      margin-right: 7px;
      color: #979ba5;
    }

    .operation-step-name {
      font-weight: bold;
    }
  }

  &-header {
    display: flex;
    align-items: center;
    margin-bottom: 20px;

    @include filterList();

    .header-retry {
      margin-left: 10px;

      .icon-monitor {
        display: inline-block;
        margin-right: 6px;
      }
    }

    :deep(.icon-loading) {
      margin-right: 4px;

      &::before {
        display: none;
      }
    }
  }

  &-content {
    .no-data {
      :deep(.right-panel-title) {
        cursor: not-allowed;
      }
    }

    .pre-panel {
      display: flex;
      align-items: center;
      height: 24px;
      margin-right: 10px;
      margin-left: -17px;
      font-size: 12px;
      color: #fff;

      &-name {
        z-index: 2;
        display: flex;
        align-items: center;
        height: 24px;
        padding-left: 6px;
        background: #3a84ff;
      }

      &-mark {
        flex: 0 0 0px;
        border-color: #3a84ff transparent #3a84ff #3a84ff;
        border-style: solid;
        border-width: 6px;

        /* stylelint-disable-next-line declaration-no-important */
        border-right-color: transparent !important;
        transform: scaleY(2);
      }
    }

    .panel-title {
      display: flex;
      align-items: center;

      .title-name {
        margin-right: 24px;
        font-weight: bold;
        color: #63656e;
      }
    }

    .content-panel {
      margin-bottom: 10px;

      &-table {
        background-color: #fff;
      }

      .col-status {
        display: flex;
        align-items: center;

        &-img {
          width: 16px;
          margin-right: 5px;
        }

        &-radius {
          width: 8px;
          height: 8px;
          margin: 4px 10px 4px 4px;
          border: 1px solid;
          border-radius: 50%;
        }
      }

      .col-retry {
        color: #3a84ff;
        cursor: pointer;
      }

    }
  }

  :deep(.bk-sideslider-wrapper) {
    padding-bottom: 0;

    .bk-sideslider-header {
      height: 52px;

      .bk-sideslider-closer {
        height: 52px;
        line-height: 52px;
      }

      .bk-sideslider-title {
        height: 52px;
        line-height: 52px;
      }
    }

    .bk-sideslider-content {
      height: calc(100% - 52px - var(--notice-alert-height));
      background: #fafbfd;
    }
  }

  .side-detail {
    max-height: calc(100vh - 120px);
    padding: 10px 30px 10px 16px;
    margin: 28px 40px 20px 40px;
    overflow-y: auto;
    color: #fff;
    background: #000;

    &-code {
      word-break: break-all;
      white-space: pre-wrap;
    }
  }

  .col-detail-more {
    margin-left: 8px;
    color: #3a84ff;
    cursor: pointer;
  }
}
</style>
