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
    class="step-issued-wrapper"
    v-bkloading="{ isLoading: loading | (hasRunning && !tableList.length) }"
    data-test-id="addNewCollectionItem_div_collectionDistribution"
  >
    <!-- 容器日志显示状态页信息 -->
    <template v-if="isContainer">
      <container-status :is-loading.sync="loading" />
    </template>
    <!-- 物理环境显示下发页信息 -->
    <template v-else>
      <div
        v-if="!curCollect.table_id"
        class="step-issued-notice notice-primary"
      >
        <i class="bk-icon icon-info-circle-shape notice-icon"></i>
        <span class="notice-text">{{ $t('采集完成后24小时内，没有配置第4步“存储”，任务会被强制停用。') }}</span>
      </div>
      <template v-if="!isShowStepInfo">
        <div class="step-issued-header">
          <div class="tab-only-compact fl">
            <template>
              <li
                v-for="tabItem in tabList"
                :class="['tab-item', { 'cur-tab': tabItem.type === curTab }]"
                :key="tabItem.type"
              >
                <a
                  class="tab-button"
                  href="javascript:void(0);"
                  @click="tabHandler(tabItem)"
                >
                  {{ `${tabItem.name}(${tabItem.num})` }}
                </a>
              </li>
            </template>
          </div>
          <bk-button
            v-if="hasFailed"
            class="fr"
            :disabled="hasRunning"
            :title="$t('失败批量重试')"
            data-test-id="collectionDistribution_button_refresh"
            icon="refresh"
            @click="issuedRetry"
            >{{ $t('失败批量重试') }}
          </bk-button>
        </div>
        <section
          v-if="tableList.length"
          class="cluster-collaspse"
        >
          <template v-for="cluster in tableList">
            <right-panel
              v-if="cluster.child.length"
              :class="['cluster-menu', { 'has-title-sign': cluster.is_label && isEdit }]"
              :collapse.sync="cluster.collapse"
              :collapse-color="'#313238'"
              :key="cluster.id"
              :need-border="true"
              :title="getRightPanelTitle(cluster)"
              :title-bg-color="'#F0F1F5'"
              @change="cluster.collapse = !cluster.collapse"
            >
              <template #pre-panel>
                <div
                  v-if="cluster.is_label && isEdit"
                  :class="`heder-title-sign sign-${cluster.label_name}`"
                >
                  {{
                    cluster.label_name === 'add'
                      ? $t('新增')
                      : cluster.label_name === 'modify'
                        ? $t('修改')
                        : $t('删除')
                  }}
                </div>
              </template>
              <template #title>
                <div class="header-info">
                  <div class="header-title fl">{{ cluster.node_path }}</div>
                  <!-- eslint-disable-next-line vue/no-v-html -->
                  <p
                    class="fl"
                    v-html="$xss(collaspseHeadInfo(cluster))"
                  ></p>
                  <!-- <span class="success">{{ cluster.success }}</span> 个成功
                <span v-if="cluster.failed" class="failed">，{{ cluster.failed }}</span> 个失败 -->
                </div>
              </template>
              <template #default>
                <div class="cluster-table-wrapper">
                  <bk-table
                    class="cluster-table"
                    v-bkloading="{ isLoading: loading }"
                    :data="cluster.child"
                    :empty-text="$t('暂无内容')"
                    :pagination="pagination"
                    :resizable="true"
                    :size="size"
                  >
                    <bk-table-column
                      width="180"
                      :label="$t('目标')"
                    >
                      <template #default="props">
                        <span>{{ getShowIp(props.row) }}</span>
                      </template>
                    </bk-table-column>
                    <bk-table-column
                      width="140"
                      :label="$t('运行状态')"
                    >
                      <template #default="props">
                        <span :class="['status', 'status-' + props.row.status]">
                          <i
                            v-if="props.row.status !== 'success' && props.row.status !== 'failed'"
                            style="display: inline-block; animation: button-icon-loading 1s linear infinite"
                            class="bk-icon icon-refresh"
                          >
                          </i>
                          {{
                            props.row.status === 'success'
                              ? $t('成功')
                              : props.row.status === 'failed'
                                ? $t('失败')
                                : $t('执行中')
                          }}
                        </span>
                      </template>
                    </bk-table-column>
                    <bk-table-column
                      :class-name="'row-detail'"
                      :label="$t('详情')"
                    >
                      <template #default="props">
                        <p>
                          <span
                            class="overflow-tips"
                            v-bk-overflow-tips
                            >{{ props.row.log }}</span
                          >
                          <a
                            class="more"
                            href="javascript: ;"
                            @click.stop="viewDetail(props.row)"
                          >
                            {{ $t('更多') }}
                          </a>
                        </p>
                      </template>
                    </bk-table-column>
                    <bk-table-column width="80">
                      <template #default="props">
                        <a
                          v-if="props.row.status === 'failed'"
                          class="retry"
                          href="javascript: ;"
                          @click.stop="issuedRetry(props.row, cluster)"
                        >
                          {{ $t('重试') }}
                        </a>
                      </template>
                    </bk-table-column>
                  </bk-table>
                </div>
              </template>
            </right-panel>
          </template>
        </section>
      </template>
      <template v-else>
        <div class="empty-view">
          <i class="bk-icon icon-info-circle-shape"></i>
          <div class="hint-text">{{ $t('采集目标未变更，无需下发') }}</div>
        </div>
      </template>
    </template>
    <div class="step-issued-footer">
      <bk-button
        v-if="isSwitch"
        :disabled="hasRunning"
        :loading="isHandle"
        theme="primary"
        @click="nextHandler"
      >
        {{ getNextPageStr }}
      </bk-button>
      <template v-else>
        <template v-if="!isFinishCreateStep">
          <bk-button
            data-test-id="collectionDistribution_button_previous"
            @click="prevHandler"
          >
            {{ $t('上一步') }}
          </bk-button>
          <bk-button
            data-test-id="collectionDistribution_button_nextStep"
            theme="primary"
            @click="nextHandler"
          >
            {{ $t('下一步') }}
          </bk-button>
        </template>
      </template>
      <bk-button
        data-test-id="collectionDistribution_button_cancel"
        @click="cancel"
      >
        {{ $t('返回列表') }}
      </bk-button>
    </div>
    <bk-sideslider
      :ext-cls="'issued-detail'"
      :is-show.sync="detail.isShow"
      :quick-close="true"
      :width="800"
      transfer
      @animation-end="closeSlider"
    >
      <template #header>
        <div class="header">
          <span>{{ detail.title }}</span>
          <bk-button
            class="header-refresh"
            :loading="detail.loading"
            theme="primary"
            @click="handleRefreshDetail"
          >
            {{ $t('刷新') }}
          </bk-button>
        </div>
      </template>
      <template #content>
        <div
          class="p20 detail-content"
          v-bkloading="{ isLoading: detail.loading }"
          v-html="$xss(detail.content)"
        ></div>
      </template>
    </bk-sideslider>
  </div>
</template>

<script>
  import rightPanel from '@/components/ip-select/right-panel';
  import containerStatus from '@/views/manage/manage-access/log-collection/collection-item/manage-collection/components/container-status';
  import { mapGetters } from 'vuex';

  export default {
    name: 'StepIssued',
    components: {
      rightPanel,
      containerStatus,
    },
    props: {
      operateType: String,
      isSwitch: Boolean,
      isFinishCreateStep: {
        type: Boolean,
        default: false,
      },
    },
    data() {
      return {
        loading: false,
        notReady: false, // 节点管理准备好了吗
        detail: {
          isShow: false,
          title: this.$t('详情'),
          loading: false,
          content: '',
          log: '',
        },
        currentRow: null,
        timer: null,
        timerNum: 0,
        tableListAll: [],
        tableList: [],
        curTaskIdList: new Set(),
        curTab: 'all',
        tabList: [
          {
            type: 'all',
            name: this.$t('全部'),
            num: 0,
          },
          {
            type: 'success',
            name: this.$t('成功'),
            num: 0,
          },
          {
            type: 'failed',
            name: this.$t('失败'),
            num: 0,
          },
          {
            type: 'running',
            name: this.$t('执行中'),
            num: 0,
          },
        ],
        count: 0,
        size: 'small',
        pagination: {
          current: 1,
          count: 0,
          limit: 100,
        },
        isLeavePage: false,
        isShowStepInfo: false,
        isHandle: false,
        // operateInfo: {}
      };
    },
    computed: {
      ...mapGetters('collect', ['curCollect']),
      hasFailed() {
        return !!this.tabList[2].num;
      },
      hasRunning() {
        return !!this.tabList[3].num || this.notReady;
      },
      isEdit() {
        return this.operateType === 'edit';
      },
      isContainer() {
        return this.curCollect.environment === 'container';
      },
      getNextPageStr() {
        if (this.hasRunning) return this.$t('执行中');
        if (this.operateType === 'stop') return this.$t('停用');
        return this.$t('完成');
      },
      hostIdentifierPriority() {
        return this.$store.getters['globals/globalsData']?.host_identifier_priority ?? ['ip', 'host_name', 'ipv6'];
      },
    },
    watch: {
      hasRunning(newVal, val) {
        if (!val && newVal) {
          this.startStatusPolling();
        }
        if (!newVal) {
          this.stopStatusPolling();
        }
      },
      notReady(val) {
        if (!val) {
          const len = this.tableList.length;
          this.isShowStepInfo = this.tableList.filter(item => item.child.length === 0).length === len;
        }
      },
    },
    created() {
      if (this.isContainer) return; // 容器日志展示容器日志的内容
      this.curCollect.task_id_list.forEach(id => this.curTaskIdList.add(id));
    },
    mounted() {
      if (this.isContainer) return; // 容器日志展示容器日志的内容
      this.isLeavePage = false;
      this.isShowStepInfo = false;
      this.requestIssuedClusterList();
    },
    beforeDestroy() {
      this.isLeavePage = true;
      this.stopStatusPolling();
    },
    methods: {
      getRightPanelTitle(cluster) {
        return {
          type: cluster.bk_obj_name,
          number: cluster.success,
        };
      },
      tabHandler(tab, manual) {
        if (this.curTab === tab.type && !manual) {
          return false;
        }
        this.curTab = tab.type;
        if (this.curTab === 'all') {
          this.tableList = structuredClone(this.tableListAll);
        } else {
          const child = [];
          this.tableListAll.forEach(item => {
            const copyItem = structuredClone(item);
            copyItem.child = copyItem.child.filter(row => row.status === this.curTab);
            if (copyItem.child.length) {
              child.push(copyItem);
            }
          });
          const data = child.map((val, index) => {
            return {
              ...val,
              collapse: index < 5,
            };
          });
          this.tableList.splice(0, this.tableList.length, ...data);
        }
      },
      prevHandler() {
        if (this.operateType === 'add') {
          this.$store.commit('updateState', {'showRouterLeaveTip': true});
          this.$router.replace({
            name: 'collectEdit',
            params: {
              collectorId: this.curCollect.collector_config_id,
              notAdd: true,
            },
            query: {
              spaceUid: this.$store.state.spaceUid,
            },
          });
        }
        this.$emit('step-change', 1);
      },
      nextHandler() {
        if (this.operateType === 'stop') {
          // 停用操作
          this.isHandle = true;
          this.$http
            .request('collect/stopCollect', {
              params: {
                collector_config_id: this.curCollect.collector_config_id,
              },
            })
            .then(res => {
              if (res.result) {
                this.$emit('step-change');
              }
            })
            .catch(error => {
              console.warn(error);
            })
            .finally(() => {
              this.isHandle = false;
            });
          return;
        }
        this.$emit('step-change');
      },
      cancel() {
        if (this.isFinishCreateStep) {
          this.$emit('change-submit', true);
        }
        this.$router.push({
          name: 'collection-item',
          query: {
            spaceUid: this.$store.state.spaceUid,
          },
        });
      },
      viewDetail(row) {
        this.detail.isShow = true;
        this.currentRow = row;
        this.requestDetail(row);
      },
      handleRefreshDetail() {
        this.requestDetail(this.currentRow);
      },
      closeSlider() {
        this.detail.content = '';
        this.detail.loading = false;
      },
      calcTabNum() {
        const num = {
          all: 0,
          success: 0,
          failed: 0,
          running: 0,
        };
        this.tableListAll.forEach(cluster => {
          num.all += cluster.child.length;
          cluster.child.length &&
            cluster.child.forEach(row => {
              num[row.status] = num[row.status] + 1;
            });
        });
        this.tabList.forEach(tab => {
          tab.num = num[tab.type];
        });
      },
      collaspseHeadInfo(cluster) {
        const list = cluster.child;
        let success = 0;
        let failed = 0;
        list.forEach(row => {
          if (row.status === 'success') {
            success = success + 1;
          }
          if (row.status === 'failed') {
            failed = failed + 1;
          }
          // if (row.status === 'running') {
          //     running++
          // }
        });
        return `<span class="success">${success}</span> ${this.$t('个成功')}，<span class="failed">${failed}</span> ${this.$t('个失败')}`;
      },
      startStatusPolling() {
        this.timerNum += 1;
        this.stopStatusPolling();
        this.timer = setTimeout(() => {
          if (this.isLeavePage) {
            this.stopStatusPolling();
            return;
          }
          this.requestIssuedClusterList('polling');
        }, 500);
      },
      stopStatusPolling() {
        clearTimeout(this.timer);
      },
      /**
       *  集群list，与轮询共用
       */
      requestIssuedClusterList(isPolling = '') {
        if (!isPolling) {
          this.loading = true;
        }
        const params = {
          collector_config_id: this.curCollect.collector_config_id,
        };
        const { timerNum } = this;
        this.$http
          .request('collect/getIssuedClusterList', {
            params,
            query: { task_id_list: [...this.curTaskIdList.keys()].join(',') },
          })
          .then(res => {
            const data = res.data.contents || [];
            this.notReady = res.data.task_ready === false; // 如果没有该字段，默认准备好了
            if (isPolling === 'polling') {
              if (timerNum === this.timerNum) {
                // 之前返回的 contents 为空
                if (!this.tableListAll.length) {
                  let collapseCount = 0; // 展开前5个状态表格信息
                  data.forEach(cluster => {
                    cluster.collapse = cluster.child.length && collapseCount < 5;
                    if (cluster.child.length) collapseCount += 1;
                    cluster.child.forEach(host => {
                      host.status = host.status === 'PENDING' ? 'running' : host.status.toLowerCase(); // pending-等待状态，与running不做区分
                    });
                  });
                  this.tableListAll.splice(0, 0, ...data);
                  this.tableList.splice(0, 0, ...data);
                }
                this.syncHostStatus(data);
                this.tabHandler({ type: this.curTab }, true);
                this.calcTabNum();
                if (this.hasRunning) {
                  this.startStatusPolling();
                }
              }
            } else {
              let collapseCount = 0; // 展开前5个状态表格信息
              data.forEach(cluster => {
                cluster.collapse = cluster.child.length && collapseCount < 5;
                if (cluster.child.length) collapseCount += 1;
                cluster.child.forEach(host => {
                  host.status = host.status === 'PENDING' ? 'running' : host.status.toLowerCase(); // pending-等待状态，与running不做区分
                });
              });
              this.tableListAll.splice(0, 0, ...data);
              this.tableList.splice(0, 0, ...data);
              this.calcTabNum();
            }
          })
          .catch(err => {
            this.$bkMessage({
              theme: 'error',
              message: err.message,
            });
          })
          .finally(() => {
            setTimeout(() => {
              this.loading = false;
            }, 500);
          });
      },
      /**
       * 重试
       */
      issuedRetry(row, cluster) {
        const instanceIDList = [];
        if (cluster) {
          // 单条重试
          row.status = 'running';
          this.tableListAll.forEach(item => {
            if (cluster.bk_inst_id === item.bk_inst_id && cluster.bk_obj_name === item.bk_obj_name) {
              item.child?.forEach(itemRow => {
                if (itemRow.ip === row.ip && itemRow.bk_cloud_id === row.bk_cloud_id) {
                  itemRow.status = 'running';
                }
              });
            }
          });
          instanceIDList.push(row.instance_id);
        } else {
          // 失败批量重试
          this.tableListAll.forEach(item => {
            item.child?.forEach(itemRow => {
              if (itemRow.status === 'failed') {
                itemRow.status = 'running';
                instanceIDList.push(itemRow.instance_id);
              }
            });
          });
        }
        this.tabHandler({ type: this.curTab }, true);
        this.calcTabNum();
        this.$http
          .request('collect/retry', {
            // manualSchema: true,
            params: { collector_config_id: this.curCollect.collector_config_id },
            data: {
              instance_id_list: instanceIDList,
            },
          })
          .then(res => {
            if (res.data) {
              res.data.forEach(item => this.curTaskIdList.add(item));
              this.startStatusPolling();
            }
          })
          .catch(err => {
            this.$bkMessage({
              theme: 'error',
              message: err.message,
            });
          });
      },
      // 同步机器状态信息
      syncHostStatus(data) {
        this.tableListAll.forEach(table => {
          const cluster = data.find(item => {
            return item.bk_inst_id === table.bk_inst_id && item.bk_obj_name === table.bk_obj_name;
          });
          if (cluster?.child?.length && table.child?.length) {
            table.child.forEach(row => {
              const tarHost = cluster.child.find(item => {
                // 优先判断host_id 若没找到对应的host_id则对比ip_host_name_ipv6的组成的字符串
                const tableStrKey = `${item.ip}_${item.host_name}_${item.ipv6}`;
                const childStrKey = `${row.ip}_${row.host_name}_${row.ipv6}`;
                if (item?.host_id) return item.host_id === row.host_id || tableStrKey === childStrKey;
                return tableStrKey === childStrKey;
              });
              if (tarHost) {
                row.status = tarHost.status === 'PENDING' ? 'running' : tarHost.status.toLowerCase(); // pending-等待状态，与running不做区分
                row.task_id = tarHost.task_id;
              }
            });
          }
        });
      },
      requestDetail(row) {
        this.detail.loading = true;
        this.$http
          .request('collect/executDetails', {
            params: {
              collector_id: this.curCollect.collector_config_id,
            },
            query: {
              instance_id: row.instance_id,
              task_id: row.task_id,
            },
          })
          .then(res => {
            if (res.result) {
              this.detail.log = res.data.log_detail;
              this.detail.content = res.data.log_detail;
            }
          })
          .catch(err => {
            this.$bkMessage({
              theme: 'error',
              message: err.message || err,
            });
          })
          .finally(() => {
            this.detail.loading = false;
          });
      },
      getShowIp(row) {
        return row[this.hostIdentifierPriority.find(pItem => Boolean(row[pItem]))] ?? row.ip;
      },
    },
  };
</script>

<style scoped lang="scss">
  @import '@/scss/mixins/scroller.scss';
  @import '@/scss/mixins/clearfix';
  @import '@/scss/conf';
  @import '@/scss/mixins/overflow-tips.scss';

  /* stylelint-disable no-descending-specificity */
  .step-issued-wrapper {
    position: relative;
    max-height: 100%;
    padding: 30px 60px;
    overflow-x: hidden;
    overflow-y: auto;

    .step-issued-notice {
      height: 36px;
      padding: 9px 12px;
      margin-bottom: 20px;
      font-size: 12px;
      line-height: 16px;
      color: #63656e;
      border-radius: 2px;

      .notice-text {
        margin-left: 10px;
      }

      .notice-icon {
        font-size: 14px;
        vertical-align: text-bottom;
      }

      &.notice-primary {
        background: #f0f8ff;
        border: 1px solid #a3c5fd;

        .notice-icon {
          color: #3a84ff;
        }
      }
    }

    .step-issued-header {
      margin-bottom: 20px;

      @include clearfix;
    }

    .cur-tab {
      background: #3a84ff;
    }

    .cluster-collaspse {
      max-width: 100%;
    }

    .cluster-menu {
      max-width: 100%;
      margin-bottom: 10px;

      &.has-title-sign .right-panel-title {
        padding-left: 0;
      }
    }

    .header-title {
      margin-right: 20px;
      font-weight: bold;
      color: #63656e;
    }

    .heder-title-sign {
      position: relative;
      height: 24px;
      padding: 0 12px 0 7px;
      margin-right: 16px;
      margin-left: -1px;
      font-size: 12px;
      line-height: 23px;
      color: #fff;
      background: #3a84ff;

      &.sign-add {
        background: #3a84ff;
      }

      &.sign-modify {
        background: #414871;
      }

      &.sign-delete {
        background: #6c3aff;
      }

      &:after {
        position: absolute;
        top: 0;
        right: 0;
        display: block;
        content: '';
        border-top: 12px solid transparent;
        border-right: 6px solid #f0f1f5;
        border-bottom: 12px solid transparent;
        border-left: 6px solid transparent;
      }
    }

    .header-info {
      font-size: 12px;
      color: #979ba5;

      .success {
        color: $successColor;
      }

      .failed {
        color: $failColor;
      }
    }

    .cluster-table {
      &.bk-table th :hover {
        background: #fff;
      }

      &::before {
        display: none;
      }

      tr:last-child td {
        border-bottom: none;
      }

      .status-running {
        color: $primaryColor;
      }

      .status-success {
        color: $successColor;
      }

      .status-failed {
        color: $failColor;
      }

      .retry {
        color: #3a84ff;
      }

      .row-detail {
        .more {
          display: inline;
        }

        p {
          position: relative;
          display: inline-block;
          max-width: 100%;
          padding-right: 30px;
          overflow: hidden;
          text-overflow: ellipsis;
          white-space: nowrap;

          .detail-text {
            display: inline-block;
            width: 100%;
            overflow: hidden;
            text-overflow: ellipsis;
          }
        }
      }

      .more {
        position: absolute;
        top: 0;
        right: 0;
        display: none;
        color: #3a84ff;
      }
    }

    .tab-only-compact {
      overflow: visible;

      @include clearfix;

      .tab-item {
        .tab-button {
          height: 32px;
          line-height: 30px;
        }

        &.cur-tab {
          .tab-button {
            color: #fff;
            background: #3a84ff;
          }
        }
      }
    }

    .step-issued-footer {
      margin-top: 20px;

      button {
        margin-right: 10px;
      }
    }

    .empty-view {
      position: relative;
      display: flexbox;
      display: flex;
      justify-content: center;
      height: 452px;
      background: #fff;
      border: 1px dashed #dcdee5;
      border-radius: 2px;

      /* stylelint-disable-next-line property-no-unknown */
      box-pack: center;

      /* stylelint-disable-next-line property-no-unknown */
      flex-pack: center;

      .hint-text {
        position: absolute;
        top: 186px;
        min-width: 144px;
        height: 16px;
        font-size: 12px;
        line-height: 16px;
        color: #979ba5;
      }

      .icon-info-circle-shape {
        position: absolute;
        top: 142px;
        left: calc(50% - 16px);
        font-size: 32px;
        color: #dcdee5;
      }
    }
  }

  :deep(.bk-sideslider-wrapper) {
    padding-bottom: 0;

    .bk-sideslider-content {
      color: #c4c6cc;
      background-color: #313238;
    }

    .header {
      display: flex;
      align-items: center;
      justify-content: space-between;
    }

    .header-refresh {
      margin-right: 8px;
    }

    .detail-content {
      min-height: calc(100vh - 60px);
      font-size: 12px;
      white-space: pre-wrap;

      a {
        color: #3a84ff;
      }
    }
  }
</style>
