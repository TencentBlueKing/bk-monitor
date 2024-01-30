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
    <!-- <div class="config-deploy-description" v-if="$route.name === 'collect-config-operate-detail'">
            <i class="icon-monitor icon-tips item-icon"></i><span>该内容是对{{config.name}}进行 "<span class="operation-step-name">{{operationStepName}}</span>" 操作的执行详情</span>
        </div> -->
    <div
      class="config-deploy-header"
      v-if="isRunning"
    >
      <div class="bk-button-group">
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
          {{ $t('正常') }}({{ header.data.successNum }})</bk-button>
        <bk-button
          @click="header.status = 'FAILED'"
          :class="{ 'is-selected': header.status === 'FAILED' }"
          size="normal"
        >
          {{ $t('异常') }}({{ header.data.failedNum }})</bk-button>
        <bk-button
          @click="header.status = 'RUNNING'"
          :class="{ 'is-selected': header.status === 'RUNNING' }"
          size="normal"
        >
          {{ $t('执行中') }}({{ header.data.pendingNum }})</bk-button>
      </div>
      <bk-button
        v-authority="{ active: !authority.MANAGE_AUTH }"
        :icon="header.batchRetry ? 'loading' : ''"
        :disabled="header.batchRetry || !(header.data.failedNum > 0 && header.data.pendingNum === 0)"
        class="header-retry header-retry-p"
        hover-theme="primary"
        @click="authority.MANAGE_AUTH ? handleBatchRetry() : handleShowAuthorityDetail()"
      >
        <i
          v-if="!header.batchRetry"
          class="icon-monitor icon-mc-retry"
        />
        {{ $t('批量重试') }}
      </bk-button>
      <bk-button
        v-authority="{ active: !authority.MANAGE_AUTH }"
        :icon="disBatch ? 'loading' : ''"
        :disabled="!haveDeploying || disBatch"
        class="header-retry header-retry-p"
        hover-theme="primary"
        @click="authority.MANAGE_AUTH ? handleBatchStop() : handleShowAuthorityDetail()"
      >
        {{ $t('批量终止') }}
      </bk-button>
      <bk-button
        class="header-retry header-retry-p"
        hover-theme="primary"
        @click="handleCopyTargets"
      >
        {{ $t('复制目标') }}
      </bk-button>
    </div>
    <div
      class="config-deploy-content"
      v-if="content.length"
    >
      <right-panel
        v-for="(item, index) in content"
        :key="index"
        :collapse="item.expand"
        class="content-panel content-panel-p"
        need-border
        title-bg-color="#F0F1F5"
        @change="handleCollapseChange(item, $event)"
        :class="{ 'no-data': !item.child.length }"
        :collapse-color="item.child.length ? '#313238' : '#C4C6CC'"
        :style="{ borderBottomWidth: item.expand ? '0' : '1px' }"
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
                  v-if="isRunning && statusList.includes(props.row.status)"
                  src="../../../static/images/svg/spinner.svg"
                  alt=''
                >
                <div
                  class="col-status-radius"
                  v-if="isRunning && ['FAILED', 'WARNING', 'SUCCESS', 'STOPPED'].includes(props.row.status)"
                  :style="{
                    'border-color': statusMap[props.row.status].border,
                    background: statusMap[props.row.status].color
                  }"
                />
                <span
                  class="content-panel-span"
                  v-if="isRunning"
                >{{ statusMap[props.row.status].name }}</span>
                <span v-else>--</span>
              </div>
            </template>
          </bk-table-column>
          <bk-table-column
            class="fix-same-code"
            width="92"
            :label="$t('版本')"
            prop="plugin_version"
          />
          <bk-table-column
            class="fix-same-code"
            :label="$t('详情')"
            min-width="200"
          >
            <template slot-scope="props">
              <div class="col-detail">
                <span class="col-detail-data">{{ props.row.log || '--' }}</span>
                <span
                  v-if="isRunning && props.row.status === 'FAILED'"
                  class="col-detail-more fix-same-code"
                  @click="handleGetMoreDetail(props.row)"
                >
                  {{ $t('详情') }}
                </span>
              </div>
            </template>
          </bk-table-column>
          <bk-table-column
            width="80"
            label=""
            fix-same-code
          >
            <template slot-scope="props">
              <div
                v-authority="{ active: !authority.MANAGE_AUTH }"
                class="col-retry"
                v-if="isRunning && props.row.status === 'FAILED'"
                @click="authority.MANAGE_AUTH ? handleRetry(props.row, item) : handleShowAuthorityDetail()"
              >
                {{ $t('重试') }}
              </div>
              <div
                v-if="isRunning && ['DEPLOYING', 'RUNNING', 'PENDING'].includes(props.row.status)"
                class="col-retry fix-same-code"
                v-authority="{ active: !authority.MANAGE_AUTH }"
                @click="authority.MANAGE_AUTH ? handleRevoke(props.row, item) : handleShowAuthorityDetail()"
              >
                {{ $t('终止') }}
              </div>
            </template>
          </bk-table-column>
        </bk-table>
        <template slot="pre-panel">
          <div
            class="pre-panel fix-same-code"
            v-if="item.is_label"
          >
            <span
              class="pre-panel-name fix-same-code"
              :style="{ backgroundColor: labelMap[item.label_name].color }"
            >{{
              labelMap[item.label_name].name
            }}</span>
            <span
              class="pre-panel-mark fix-same-code"
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
                class="num fix-same-code"
                v-if="item.successNum && header.status !== 'FAILED'"
              ><span style="color: #2dcb56;">{{item.successNum}}</span> {{ $t('个成功') }} <span v-if="(item.failedNum && ['ALL', 'FAILED'].includes(header.status)) || item.pendingNum">,</span></span>
              <span
                class="num fix-same-code"
                v-if="item.failedNum && ['ALL', 'FAILED'].includes(header.status)"
              ><span style="color: #ea3636;">{{item.failedNum}}</span> {{ $t('个失败') }} <span v-if="item.pendingNum">,</span></span>
              <span
                class="num fix-same-code"
                v-if="item.pendingNum"
              ><span style="color: #3a84ff;">{{item.pendingNum}}</span> {{ $t('个执行中') }} </span>
              <span
                class="num"
                v-else-if="!item.child.length"
              >共 <span style="color: #63656e;">0</span> {{config.target_object_type === 'HOST' ? $t('台主机') : $t('个实例')}}</span>
            </template>
            <span
              class="num fix-same-code"
              v-else
            >{{$t('共')}} {{ item.successNum + item.failedNum + item.pendingNum }}
              {{ config.target_object_type === 'HOST' ? $t('台主机') : $t('个实例') }}</span>
          </div>
        </div>
      </right-panel>
    </div>
    <bk-sideslider
      class="fix-same-code"
      :is-show.sync="side.show"
      :quick-close="true"
      :width="900"
      :title="side.title"
    >
      <div
        class="side-detail fix-same-code"
        slot="content"
        v-bkloading="{ isLoading: side.loading }"
      >
        <!-- eslint-disable-next-line vue/no-v-html -->
        <pre
          class="side-detail-code fix-same-code"
          v-html="transformJobUrl(side.detail)"
        />
      </div>
    </bk-sideslider>
  </div>
</template>
<script>
import {
  batchRetry,
  batchRevokeTargetNodes,
  getCollectLogDetail,
  isTaskReady,  retryTargetNodes,
  revokeTargetNodes } from '../../../../monitor-api/modules/collecting';
import { copyText } from '../../../../monitor-common/utils/utils.js';
import RightPanel from '../../../components/ip-select/right-panel';
import { SET_NAV_ROUTE_LIST } from '../../../store/modules/app';
import { transformJobUrl } from '../../../utils/index';

export default {
  name: 'CollectorHostStatus',
  components: {
    RightPanel
  },
  inject: ['authority', 'handleShowAuthorityDetail'],
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
      statusList: ['PENDING', 'RUNNING', 'DEPLOYING', 'STARTING', 'STOPPING'],
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
          border: '#2DCB56',
          name: this.$t('正常')
        },
        FAILED: {
          color: '#FD9C9C',
          border: '#EA3636',
          name: this.$t('异常')
        },
        PENDING: {
          color: '#3A84FF',
          name: this.$t('等待中')
        },
        RUNNING: {
          color: '#3A84FF',
          name: this.$t('执行中')
        },
        DEPLOYING: {
          color: '#3A84FF',
          name: this.$t('部署中')
        },
        STARTING: {
          color: '#3A84FF',
          name: this.$t('启用中')
        },
        STOPPING: {
          color: '#F0F1F5',
          border: '#C4C6CC',
          name: this.$t('停用中')
        }
      },
      side: {
        show: false,
        title: '',
        detail: '',
        loading: false
      },
      statusStatusMap: {
        ALL: this.$tc('全部'),
        SUCCESS: this.$tc('正常'),
        FAILED: this.$tc('异常'),
        RUNNING: this.$tc('执行中')
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
    // 正常 || 异常状态时过滤空的数据
    contentFilter() {
      const needFilter = ['SUCCESS', 'FAILED'].includes(this.header.status);
      return needFilter ? this.content.filter(item => !!item.table.length) : this.content;
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
  mounted() {
    this.handleUpdateTabAcitve(this.$route.params);
  },
  methods: {
    /**
     * @description: 处理跳转的参数选中相应的状态
     * @param {*} params 路由参数
     */
    handleUpdateTabAcitve(params) {
      let status = 'ALL';
      if (params.taskStatus === 'SUCCESS') {
        status = 'SUCCESS';
      } else if (['WARNING', 'FAILED'].includes(params.taskStatus)) {
        status = 'FAILED';
      }
      this.header.status = status;
    },
    handleData(data) {
      this.config = data.config_info;
      const { status } = this.header;
      this.header.data = data.headerData;
      this.content = data.contents;
      this.content.forEach((item) => {
        item.child.forEach((set) => {
          if (this.statusList.includes(set.status) || set.status === status || status === 'ALL') {
            item.table.push(set);
          }
        });
      });
      const operationMap = {
        ADD_DEL: this.$t('增删目标'),
        CREATE: this.$t('创建'),
        UPGRADE: this.$t('升级'),
        START: this.$t('启用'),
        EDIT: this.$t('编辑'),
        ROLLBACK: this.$t('回滚'),
        STOP: this.$t('停用')
      };
      this.operationStepName = operationMap[this.config.last_operation];
      this.updateNavData();
    },
    /** 更新面包屑 */
    updateNavData(statusName = this.$t('采集状态')) {
      const oldRouteList = this.$store.getters.navRouteList;
      const routeList = [
        oldRouteList[0]
      ];
      routeList.push({
        name: this.allData.config_info.name,
        id: ''
      }, {
        name: statusName,
        id: ''
      });
      this.$store.commit(`app/${SET_NAV_ROUTE_LIST}`, routeList);
    },
    async handleRetry(data, table) {
      const retryContent = this.content;
      this.refresh = false;
      if (this.side.title === data.instance_name) {
        this.side.title = '';
      }
      retryContent.forEach((content) => {
        if (content.child?.length) {
          const setData = content.child
            .find(set => set.instance_id === data.instance_id && set.status === 'FAILED');
          if (setData) {
            setData.status = 'PENDING';
            content.pendingNum += 1;
            content.failedNum -= 1;
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
          const isReady = await this.taskReadyStatus(this.config.id).catch(() => false);
          if (isReady) {
            this.refresh = true;
            this.handlePolling();
          }
        })
        .catch(() => {
          data.status = 'FAILED';
          table.failedNum += 1;
          table.pendingNum -= 1;
          this.header.data.failedNum += 1;
          this.header.data.pendingNum -= 1;
          this.refresh = true;
          this.handlePolling();
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
        this.handleRefreshData();
      });
    },
    async handleBatchRetry() {
      const failedList = [];
      this.refresh = false;
      this.header.batchRetry = true;
      this.side.title = '';
      this.content.forEach((item) => {
        item.child.forEach((set) => {
          if ('FAILED' === set.status) {
            set.status = 'PENDING';
            failedList.push(set);
          }
        });
        item.pendingNum += item.failedNum;
        item.failedNum = 0;
      });
      this.header.data.pendingNum += this.header.data.failedNum;
      this.header.data.failedNum = 0;
      this.handlePolling(false);
      batchRetry({ id: this.config.id })
        .then(async () => {
          const isStatusReady = await this.taskReadyStatus(this.config.id);
          if (isStatusReady) {
            this.refresh = true;
            this.header.batchRetry = false;
            this.handlePolling();
          }
        })
        .catch(() => {
          failedList.forEach(item => item.status = 'FAILED');
          this.header.data.pendingNum = 0;
          this.header.batchRetry = false;
          this.header.data.failedNum = failedList.length;
          this.refresh = true;
          this.handlePolling();
        });
    },
    handleBatchStop() {
      this.disBatch = true;
      this.refresh = false;
      batchRevokeTargetNodes({ id: this.config.id })
        .finally(() => {
          this.header.batchRetry = false;
          this.refresh = true;
          this.disBatch = false;
          this.handleRefreshData();
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
    handleRefreshData() {
      this.$emit('refresh');
    },
    handleStatusChange(status) {
      this.content.forEach((item) => {
        item.table = [];
        item.child.forEach((set) => {
          if (
            (status === 'RUNNING' && this.statusList.includes(set.status))
            || set.status === status
            || status === 'ALL'
          ) {
            item.table.push(set);
          }
        });
      });
    },
    handleCollapseChange(item, v) {
      if (!item?.child?.length) return;
      item.expand = v;
    },
    handleGetMoreDetail(data) {
      this.side.show = true;
      const { instance_name } = data;
      if (instance_name !== this.side.title) {
        this.side.title = instance_name;
        this.side.loading = true;
        getCollectLogDetail(
          {
            instance_id: data.instance_id,
            task_id: data.task_id,
            id: this.config.id
          },
          { needMessage: false }
        )
          .then((data) => {
            this.side.detail = data.log_detail;
            this.side.loading = false;
          })
          .catch((error) => {
            this.bkMsg('error', error.message || this.$t('获取更多数据失败'));
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
        const isShow = await isTaskReady({ collect_config_id: id }).catch(() => false);
        if (isShow) {
          resolve(true);
          return;
        }
        timer = setTimeout(() => {
          this.taskReadyStatus(id).then((res) => {
            resolve(res);
          });
        }, 2000);
      });
    },
    handleCopyTargets() {
      let copyStr = '';
      this.content.forEach((ct) => {
        ct.table.forEach(item => copyStr += `${item.instance_name}\n`);
      });
      copyText(copyStr, (msg) => {
        this.$bkMessage({
          theme: 'error',
          message: msg
        });
        return;
      });
      this.$bkMessage({
        theme: 'success',
        message: this.$t('复制成功')
      });
    }
  }
};
</script>
<style lang="scss" scoped>
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

      :deep(a) {
        color: #3a84ff;
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
      flex-direction: row;
      align-items: center;

      .title-name {
        margin-right: 24px;
        font-weight: bold;
        color: #63656e;
      }
    }

    .content-panel {
      margin-bottom: 20px;

      &-table {
        background-color: #fff;
      }

      .col-status {
        display: flex;
        flex-direction: row;
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

  .col-detail-more {
    margin-left: 8px;
    color: #3a84ff;
    cursor: pointer;
  }
}
</style>
