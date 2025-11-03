<template>
  <div>
    <div
      v-if="!isStopCollection"
      :style="hasFailed ? 'border: 1px solid #ea3939' : ''"
      class="issued-btn-wrap"
      @click.stop="viewDetail()"
    >
      <div
        v-if="hasFailed"
        class="issued-btn-dot"
      ></div>
      <i class="issued-icon bklog-icon bklog-jincheng"> </i>
    </div>
    <bk-sideslider
      :ext-cls="'issued-detail'"
      :is-show.sync="detail.isShow"
      :quick-close="true"
      :width="800"
      transfer
      @animation-end="closeSlider"
      @shown="showSlider"
    >
      <template #header>
        <div>
          <div
            v-if="isStopCollection"
            class="collect-link"
          >
            {{ $t('编辑采集项') }}
            <span style="padding: 3px 9px; background-color: #f0f1f5">
              <span class="bk-icon bklog-icon bklog-position"></span>
              {{ collectionName }}
            </span>
          </div>
          <div v-else>
            {{ $t('采集下发') }}
          </div>
        </div>
      </template>
      <template #content>
        <!-- 当采集下发 -->
        <div
          v-if="!isFinishStep"
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
              <div
                v-if="hasRunning"
                style="display: flex"
              >
                <i
                  style="
                    display: inline-block;
                    line-height: 16px;
                    color: #3a84ff;
                    animation: button-icon-loading 1s linear infinite;
                  "
                  class="bk-icon icon-refresh"
                ></i>
                <span class="notice-text">{{ $t('正在下发...') }}</span>
                <i18n
                  class="notice-time"
                  path="已耗时{0}秒"
                >
                  <span>{{ displaySeconds }}</span>
                </i18n>
              </div>
              <div v-else>
                <i class="bk-icon icon-info-circle-shape notice-icon"></i>
                <span class="notice-text"
                  ><span style="color: #34d97b">{{ $t('执行成功') }}{{ tabList[1].num }}/{{ tabList[0].num }};</span>
                  <span
                    v-if="tabList[2].num"
                    style="color: #ff5656"
                    >{{ $t('执行失败') }}{{ tabList[2].num }}/{{ tabList[0].num }}</span
                  ></span
                >
              </div>
            </div>
            <template v-if="!isShowStepInfo">
              <div class="nav-section">
                <div class="nav-btn-box">
                  <div
                    v-for="tabItem in tabList"
                    :class="`nav-btn ${tabItem.type === curTab ? 'active' : ''}`"
                    :key="tabItem.type"
                    href="javascript:void(0);"
                    @click="tabHandler(tabItem)"
                  >
                    <div
                      v-if="tabItem.type === 'failed'"
                      style="margin-top: 6px"
                      class="ip-status-cicle"
                    ></div>
                    <div
                      v-else-if="tabItem.type === 'success'"
                      style="margin-top: 6px; border: 1px solid #34d97b"
                      class="ip-status-cicle"
                    ></div>
                    <i
                      v-else-if="tabItem.type === 'running'"
                      style="margin: 4px 4px 0 0; color: #3a84ff"
                      class="bk-icon icon-refresh"
                    >
                    </i>
                    <div>{{ `${tabItem.name}(${tabItem.num})` }}</div>
                  </div>
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
              <div class="step-issued-content">
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
                        </div>
                      </template>
                      <template #default>
                        <div class="cluster-table-wrapper">
                          <bk-table
                            class="cluster-table"
                            v-bkloading="{ isLoading: loading }"
                            :cell-class-name="tableRowClassName"
                            :data="cluster.child"
                            :empty-text="$t('暂无内容')"
                            :pagination="pagination"
                            :resizable="true"
                            :show-header="false"
                            :size="size"
                          >
                            <bk-table-column>
                              <template #default="props">
                                <div
                                  style="display: flex"
                                  @click="requestDetail(props.row)"
                                >
                                  <div
                                    v-if="props.row.status === 'failed'"
                                    class="ip-status-cicle"
                                  ></div>
                                  <div
                                    v-if="props.row.status === 'success'"
                                    style="border: 1px solid #34d97b"
                                    class="ip-status-cicle"
                                  ></div>
                                  <i
                                    v-if="props.row.status !== 'success' && props.row.status !== 'failed'"
                                    style="
                                      display: inline-block;
                                      margin: 4px 5px 0 0;
                                      color: #3a84ff;
                                      animation: button-icon-loading 1s linear infinite;
                                    "
                                    class="bk-icon icon-refresh"
                                  >
                                  </i>
                                  <div style="width: 100px">{{ getShowIp(props.row) }}</div>
                                  <a
                                    v-if="props.row.status === 'failed'"
                                    class="retry"
                                    href="javascript: ;"
                                    @click.stop="issuedRetry(props.row, cluster)"
                                  >
                                    {{ $t('重试') }}
                                  </a>
                                </div>
                              </template>
                            </bk-table-column>
                          </bk-table>
                        </div>
                      </template>
                    </right-panel>
                  </template>
                </section>
                <bk-exception
                  v-else
                  class="exception-wrap-item exception-part"
                  scene="part"
                  style="margin-top: 240px;"
                  type="empty"
                >
                </bk-exception>
                <div
                  v-if="tableList.length"
                  class="detail-wrap"
                  v-bkloading="{ isLoading: detail.loading }"
                >
                  <div class="detail-header">
                    <div class="detail-title">{{ $t('采集详情') }}</div>
                    <bk-button
                      class="header-refresh"
                      :loading="detail.loading"
                      size="small"
                      @click="handleRefreshDetail"
                    >
                      {{ $t('刷新') }}
                    </bk-button>
                  </div>
                  <div
                    class="detail-content"
                    v-html="$xss(detail.content)"
                  ></div>
                </div>
              </div>
            </template>
            <template v-else>
              <div class="empty-view">
                <i class="bk-icon icon-info-circle-shape"></i>
                <div class="hint-text">{{ $t('采集目标未变更，无需下发') }}</div>
              </div>
            </template>
          </template>

          <!-- 当停用按钮打开的抽屉并且非完成步骤时再显示 -->
          <div
            v-if="isStopCollection && !isFinishStep"
            class="step-issued-footer"
          >
            <bk-button
              v-if="isSwitch"
              :disabled="hasRunning"
              :loading="isHandle"
              theme="primary"
              @click="nextHandler"
            >
              {{ getNextPageStr }}
            </bk-button>
            <bk-button
              data-test-id="collectionDistribution_button_cancel"
              @click="cancel"
            >
              {{ $t('返回列表') }}
            </bk-button>
          </div>
        </div>
        <div v-else>
          <step-result
            :apply-data="applyData"
            :index-set-id="indexSetId"
            :is-switch="isSwitch"
            :operate-type="operateType"
            @step-result-back="cancel"
          ></step-result>
        </div>
      </template>
    </bk-sideslider>
  </div>
</template>
<script>
  import rightPanel from '@/components/ip-select/right-panel';
  import containerStatus from '@/views/manage/manage-access/log-collection/collection-item/manage-collection/components/container-status';
  import { mapGetters } from 'vuex';

  import stepResult from './step-result';

  export default {
    name: 'IssuedSlider',
    components: {
      rightPanel,
      containerStatus,
      stepResult,
    },
    props: {
      operateType: String,
      isSwitch: Boolean,
      isFinishCreateStep: {
        type: Boolean,
        default: false,
      },
      // 此抽屉有两种情况使用，一种是编辑、新建采集项时步骤右下方悬浮按钮打开采集下发抽屉，一种是停用时打开采集下发抽屉并显示停用逻辑
      isStopCollection: {
        type: Boolean,
        default: false,
      },
      currentRowCollectorConfigId: {
        type: String,
        default: '',
      },
      indexSetId: {
        type: [String, Number],
        default: '',
      },
      applyData: {
        type: Object,
        default: () => {},
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
        currentActiveRow: '',
        elapsedSeconds: 0,
        displaySeconds: 0,
        collectionName: '',
        isFinishStep: false,

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
      this.curCollect?.task_id_list?.forEach(id => this.curTaskIdList.add(id));
      this.collectionName = this.curCollect?.collector_config_name ?? '';
    },
    mounted() {
      if (this.isContainer) return; // 容器日志展示容器日志的内容
      this.isLeavePage = false;
      this.isShowStepInfo = false;
      if (!this.isStopCollection) this.requestIssuedClusterList();
    },
    beforeUnmount() {
      this.isLeavePage = true;
      this.isFinishStep = false;
      this.stopStatusPolling();
    },
    methods: {
      tableRowClassName({ row }) {
        return row.ip === this.currentActiveRow ? 'selected-row' : '';
      },
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
                this.isFinishStep = true;
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
        this.detail.isShow = false;
        // 如果已经点击停止操作，那么回到列表页需要重新刷新页面
        if (this.isFinishStep) {
          location.reload();
        }
      },
      viewDetail() {
        this.isFinishStep = false;
        this.collectionName = this.curCollect?.collector_config_name ?? '';
        this.detail.isShow = true;
        if (this.tableList?.length && this.tableList[0].child?.length) {
          this.currentRow = this.tableList[0].child[0];
        }
        this.requestDetail(this.currentRow);
      },
      handleRefreshDetail() {
        this.requestDetail(this.currentRow);
      },
      showSlider() {
        if (!this.isStopCollection) this.requestIssuedClusterList();
      },
      closeSlider() {
        this.detail.content = '';
        this.detail.loading = false;
        this.tableList?.splice(0, this.tableList?.length);
        this.tableAllList?.splice(0, this.tableAllList?.length);
        this.stopStatusPolling();
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
        return `<span style="color: #34d97b" class="success-status">${success}</span> ${this.$t('个成功')}，<span style="color: #ff5656">${failed}</span> ${this.$t('个失败')}`;
      },
      startStatusPolling() {
        this.timerNum += 1;
        this.stopStatusPolling();
        this.timer = setTimeout(() => {
          if (this.isLeavePage) {
            this.stopStatusPolling();
            return;
          }
          this.elapsedSeconds += 0.5;
          if (this.elapsedSeconds % 1 !== 0.5) {
            this.displaySeconds = this.elapsedSeconds.toFixed(0);
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
      async requestIssuedClusterList(isPolling = '') {
        if (!isPolling) {
          this.loading = true;
        }
        const params = {
          collector_config_id: this.curCollect.collector_config_id,
        };
        const { timerNum } = this;
        await this.$http
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
                  this.tableListAll = [...data];
                  this.tableList = [...data];
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
              this.tableListAll = [...data];
              this.tableList = [...data];
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
        if (!row || this.isContainer) return;
        this.detail.loading = true;
        this.currentActiveRow = row?.ip || '';
        this.currentRow = row;
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
  @import '@/scss/mixins/flex.scss';

  /* stylelint-disable no-descending-specificity */
  .step-issued-wrapper {
    position: relative;
    max-height: 100%;
    padding: 20px;
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

      .notice-time {
        position: absolute;
        right: 40px;
        color: #a6acb8;
      }

      .notice-icon {
        font-size: 14px;
        vertical-align: text-bottom;
      }

      &.notice-primary {
        background: #f0f8ff;

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
      width: 40%;
      height: calc(100vh - 204px);
      overflow: scroll;
      border: 1px solid #e5e7ec;
    }

    .cluster-menu {
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
    }

    .cluster-table {
      &.bk-table th :hover {
        background: #fff;
      }

      &::before {
        display: none;
      }

      :deep(.bk-table-row) {
        cursor: pointer;
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

    .nav-section {
      margin-bottom: 20px;
      @include flex-justify(space-between);

      .nav-btn-box {
        align-items: center;
        min-width: 327px;
        height: 36px;
        padding: 5px 4px;
        font-size: 14px;
        background: #f0f1f5;
        border-radius: 4px;

        @include flex-justify(space-between);

        .nav-btn {
          position: relative;
          display: flex;
          padding: 4px 15px;
          color: #63656e;
          border-radius: 4px;

          &:not(:last-child)::after {
            position: absolute;
            top: 3px;
            right: -8px;
            color: #dcdee5;
            content: '|';
          }

          &:not(:first-child) {
            margin-left: 12px;
          }

          &:hover {
            cursor: pointer;
            background: #fff;
          }

          &.active {
            color: #3a84ff;
            background: #fff;
          }
        }
      }
    }

    .ip-status-cicle {
      width: 10px;
      height: 10px;
      margin: 4px 5px 0 0;
      border: 1px solid $failColor;
      border-radius: 50%;
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

  .issued-btn-wrap {
    position: fixed;
    right: 45px;
    bottom: 35px;
    z-index: 10;
    width: 47px;
    height: 47px;
    padding: 12px;
    color: #666871;
    cursor: pointer;
    background-color: rgb(250, 251, 253);
    border: 1px solid #dde4eb;
    border-radius: 4px;

    .issued-btn-dot {
      position: absolute;
      top: -2px;
      right: -2px;
      width: 8px;
      height: 8px;
      background-color: #ea3939;
      border-radius: 50%;
    }

    .issued-icon {
      font-size: 25px;
    }

    &:hover {
      color: #699df4;
      box-shadow: 5px 5px 10px rgba(0, 0, 0, 0.3);
    }
  }

  .collect-link {
    color: #63656e;
    border-radius: 2px;

    .icon-position {
      font-size: 14px;
      color: #c4c6cc;
    }
  }

  :deep(.bk-sideslider-wrapper) {
    padding-bottom: 0;

    .header {
      display: flex;
      align-items: center;
      justify-content: space-between;
    }

    .header-refresh {
      margin-right: 8px;
    }

    .step-issued-content {
      display: flex;

      .detail-wrap {
        width: 60%;
        height: calc(100vh - 200px);
        padding: 20px;
        overflow: scroll;
        font-size: 12px;
        color: #c4c6cc;
        white-space: pre-wrap;
        background-color: #313238;

        .detail-header {
          display: flex;
          align-items: center;
          justify-content: space-between;

          .detail-title {
            font-size: 14px;
            color: #888c95;
          }
        }

        .detail-content {
          width: 100%;
          padding: 20px;
          background-color: #2a2b2f;
        }

        a {
          color: #3a84ff;
        }
      }
    }
  }

  :deep(.bk-table-body .selected-row) {
    /* stylelint-disable-next-line declaration-no-important */
    border: 1px #3a84ff solid !important;
  }
</style>
