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
  <div
    v-loading="{ loading: basicLoading, indicator: renderFieldListSkeleton }"
    class="collection-status-container"
  >
    <!-- 容器日志状态页 -->
    <container-status
      v-if="isContainer"
      :is-loading.sync="basicLoading"
    />
    <template v-else>
      <div
        v-if="dataFir"
        class="collect"
      >
        <div class="nav-section">
          <div class="button-group bk-button-group" data-bklog-button-group="connected">
            <button
              type="button"
              v-for="(val, x) in dataButton"
              :key="x"
              :aria-pressed="clickSec.selected === val.key"
              @click="handleChangeGroup(val)"
              >{{ val.content }}({{ val.dataList.totalLenght }})</button
            >
          </div>
          <div class="status-toolbar-actions">
            <span>{{ $t('每15分钟按照CMDB最新拓扑自动部署或取消采集') }}</span>
            <!-- <span class="bk-icon icon-question-circle" v-log-tooltip="$t('每15分钟按照CMDB最新拓扑自动部署或取消采集')"></span> -->
            <t-button
              class="mr10"
              :disabled="!collectProject"
              :size="size"
              :title="$t('重试')"

              theme="default"
              @click="retryClick(dataFal, dataFir.contents.length)"
              ><template #icon><span :class="`bk-icon icon-${'right-turn-line'}`"></span></template>{{ $t('失败批量重试') }}
            </t-button>
            <!-- <bk-button
            :theme="'primary'"
            :title="$t('数据采样')"
            class="mr10"
            :size="size"
            :disabled="!collectProject"
            @click="jsonFormatClick">
            {{$t('数据采样')}}
          </bk-button> -->
          </div>
        </div>
        <div
          v-for="(value, i) in renderTableList"
          :key="i"
          class="collection-status-group"
        >
          <div class="table-detail">
            <button type="button" :aria-expanded="!collapsedGroups.has(i)" @click="closeTable(i)">
              <i
                aria-hidden="true"
                :style="{ color: collapseColor }"
                class="bk-icon title-icon"
                :class="collapsedGroups.has(i) ? 'icon-right-shape' : 'icon-down-shape'"
              ></i>
              <span class="group-title">{{ value.node_path }}</span>
              <span class="group-summary">
                <span class="SUCCESS">{{ dataSec[i] ? dataSec[i].length : '' }}</span><span>{{ $t('个成功') }},</span>
                <span class="FAILED">{{ dataFal[i] ? dataFal[i].length : '' }}</span><span>{{ $t('个失败') }}</span>
              </span>
            </button>
          </div>
          <div v-show="!collapsedGroups.has(i)" class="table-calc">
            <bk-table
              :class="{ 'status-table-with-rows': clickSec.data[i]?.length }"
              :loading="reloadTable"
              :data="clickSec.data[i]"
              :empty-text="$t('暂无内容')"
              size="small"
            >
              <bk-table-column
                native-cell-slot
                :label="$t('目标')"
              >
                <template #default="props">
                  <span>{{ getShowIp(props.row) }}</span>
                </template>
              </bk-table-column>
              <bk-table-column
                native-cell-slot
                :label="$t('状态')"
              >
                <template #default="props">
                  <span class="collection-status-cell" @click="reset(props.row)">
                    <span class="collection-status-icon" aria-hidden="true">
                      <span v-if="props.row.status === 'SUCCESS'" class="collection-status-dot is-success" />
                      <span v-else-if="props.row.status === 'FAILED'" class="collection-status-dot is-failed" />
                      <span v-else class="collection-status-spinner" />
                    </span>
                    <span
                      v-if="props.row.status === 'SUCCESS'"
                      class="SUCCESS"
                    >
                      {{ $t('成功') }}
                    </span>
                    <span
                      v-else-if="props.row.status === 'FAILED'"
                      class="FAILED"
                    >
                      {{ $t('失败') }}
                    </span>
                    <span
                      v-else
                      class="PENDING"
                      >{{ $t('执行中') }}</span
                    >
                  </span>
                </template>
              </bk-table-column>
              <bk-table-column
                :label="$t('更新时间')"
                prop="create_time"
              ></bk-table-column>
              <bk-table-column
                :label="$t('插件版本')"
                prop="plugin_version"
              ></bk-table-column>
              <bk-table-column
                native-cell-slot
                width="280"
                :label="$t('详情')"
              >
                <template #default="props">
                  <div class="text-style">
                    <span @click.stop="viewDetail(props.row)">{{ $t('部署详情') }}</span>
                    <span
                      v-if="enableCheckCollector && collectorData.environment === 'linux'"
                      @click.stop="viewReport(props.row)"
                    >
                      {{ $t('一键检测') }}
                    </span>
                  </div>
                </template>
              </bk-table-column>
              <bk-table-column
                native-cell-slot
                width="120"
                label=""
              >
                <template #default="props">
                  <t-button :variant="(true) ? 'text' : ('base')"
                    v-if="props.row.status === 'FAILED'"
                    theme="primary"

                    @click="retryClick(props.row, 'odd')"
                  >
                    {{ $t('重试') }}
                  </t-button>
                </template>
              </bk-table-column>
              <template #empty>
                <div class="bklog-table-empty-region">
                  <empty-status
                    v-if="!(basicLoading || reloadTable)"
                    :show-text="false"
                    empty-type="empty"
                  >
                    <span>{{ $t('暂无内容') }}</span>
                  </empty-status>
                </div>
              </template>
            </bk-table>
          </div>
        </div>
        <div v-if="!basicLoading && !reloadTable && !renderTableList.length" class="bklog-table-empty-region">
          <empty-status :empty-type="statusFailed ? '500' : 'empty'" @operation="getCollectList()" />
        </div>
        <template v-if="renderTableList.length">
          <div
            v-show="!isPageOver && !reloadTable"
            v-loading="{ loading: true, indicator: renderListRefreshSkeleton }"
            style="height: 40px"
          ></div>
        </template>
        <bk-sideslider
          :ext-cls="'issued-detail'"
          :is-show.sync="detail.isShow"
          :quick-close="true"
          :width="800"
          transfer
          @animation-end="closeSlider"
        >
          <template #header>
            <div>{{ detail.title }}</div>
          </template>
          <!-- eslint-disable-next-line vue/no-v-html -->
          <template #content>
            <div
              v-loading="{ loading: detail.loading, indicator: renderCodeSampleSkeleton }"
              class="p20 detail-content"
              v-html="$xss(detail.content)"
            ></div>
          </template>
        </bk-sideslider>
      </div>
    </template>
    <collection-report-view
      v-model="reportDetailShow"
      :check-record-id="checkRecordId"
      @close-report="() => (reportDetailShow = false)"
    />
  </div>
</template>

<script>
import { renderFieldListSkeleton, renderListRefreshSkeleton } from '@/shared/ui/loading/list-skeleton';
import { renderCodeSampleSkeleton } from '@/shared/ui/loading/list-skeleton';

import { useApplicationStore } from '@/app/state/domains/application-store';
import { useGlobalsStore } from '@/app/state/domains/globals-store';

import { MessagePlugin as TDesignMessage } from 'tdesign-vue-next';
import { ServicesInstance } from '@/platform/services';

  import { projectManages } from '@/shared/lib/util';
  import EmptyStatus from '@/shared/ui/empty-status/index';

  import CollectionReportView from '../../../components/collection-report-view/index';
  import containerStatus from './components/container-status.vue';

  export default {
    components: {
      containerStatus,
      CollectionReportView,
      EmptyStatus,
    },
    props: {
      collectorData: {
        type: Object,
        required: true,
      },
    },
    data() {
      return {
        basicLoading: false,
        currentPage: 0,
        isPageOver: false, // 前端分页加载是否结束
        dataListPaged: [], // 将列表数据按 pageSize 分页
        count: 0, // 数据总条数
        pageSize: 30, // 每页展示多少数据
        totalPage: 1,
        size: 'small',
        collapsedGroups: new Set(),
        statusFailed: false,
        renderTableList: [],
        detail: {
          isShow: false,
          title: this.$t('详情'),
          loading: true,
          content: '',
          log: '',
        },
        dataButton: [
          {
            key: 'all',
            content: this.$t('全部'),
            dataList: {},
          },
          {
            key: 'sec',
            content: this.$t('正常'),
            dataList: {},
          },
          {
            key: 'fal',
            content: this.$t('失败'),
            dataList: {},
          },
          {
            key: 'pen',
            content: this.$t('执行中'),
            dataList: {},
          },
        ],
        collapseColor: {
          type: String,
          default: '#63656E',
        },
        showSetting: true,
        reloadTable: false,
        instance: null,
        clickSec: {
          selected: 'all',
          data: '',
        },
        dataFir: null,
        dataSec: {},
        dataFal: {},
        dataPen: {},
        dataAll: {},
        // 是否支持一键检测
        enableCheckCollector: JSON.parse(window.ENABLE_CHECK_COLLECTOR),
        // 一键检测弹窗配置
        reportDetailShow: false,
        // 一键检测采集项标识
        checkRecordId: '',
      };
    },
    computed: {
      collectProject() {
        return projectManages(useApplicationStore().topMenu, 'collection-item');
      },
      isContainer() {
        return this.collectorData.environment === 'container';
      },
      hostIdentifierPriority() {
        return useGlobalsStore().globalsData?.host_identifier_priority ?? ['ip', 'host_name', 'ipv6'];
      },
    },
    created() {
      // 容器日志展示容器日志的内容
      if (this.isContainer) return;
      this.getCollectList();
    },
    beforeDestroy() {
      // 标记组件已销毁，防止异步回调中再创建定时器
      this.isDestroyed = true;
      // 清除定时器
      if (this.timer) {
        clearInterval(this.timer);
        this.timer = null;
      }
    },
    mounted() {
      // 容器日志展示容器日志的内容
      if (this.isContainer) return;
      this.adadScrollEvent();
    },
    methods: {
      renderFieldListSkeleton,
      renderListRefreshSkeleton,
      renderCodeSampleSkeleton,
      closeTable(index) {
        if (!this.collapsedGroups.delete(index)) this.collapsedGroups.add(index);
      },
      adadScrollEvent() {
        this.scrollontentEl = document.querySelector('.allocation');
        if (!this.scrollontentEl) return;

        this.scrollontentEl.addEventListener('scroll', this.handleScroll, { passive: true });
      },
      // 获取采集状态
      getCollectList(isLoading = true) {
        if (isLoading) {
          this.reloadTable = true;
          this.basicLoading = true;
        }
        this.dataAll = { totalLenght: 0 };
        this.dataSec = { totalLenght: 0 };
        this.dataFal = { totalLenght: 0 };
        this.dataPen = { totalLenght: 0 };

        // 组件已销毁则不再查询状态
        if (this.isDestroyed) return;

        return ServicesInstance.source.collectList({
            params: {
              collector_config_id: this.$route.params.collectorId,
            },
            manualSchema: true,
          })
          .then(res => {
            this.statusFailed = false;
            this.dataFir = res.data;
            if (!this.dataFir.contents.length) {
              clearInterval(this.timer);
              this.timer = null;
              this.renderTableList = [];
              this.collapsedGroups.clear();
              this.initPageConf([]);
              this.loadPage();
            }
            if (this.dataFir.contents.length !== 0) {
              // 过滤child为空的节点
              this.dataFir.contents = this.dataFir.contents.filter(data => data.child.length);

              for (let x = 0; x < this.dataFir.contents.length; x++) {
                let allSet = [];
                const secSet = [];
                const failSet = [];
                const penSet = [];
                allSet = this.dataFir.contents[x].child;
                for (let i = 0; i < allSet.length; i++) {
                  if (allSet[i].status === 'SUCCESS') {
                    secSet.push(allSet[i]);
                  } else if (allSet[i].status === 'FAILED') {
                    failSet.push(allSet[i]);
                  } else {
                    penSet.push(allSet[i]);
                  }
                }
                this.dataAll[x] = allSet;
                this.dataSec[x] = secSet;
                this.dataFal[x] = failSet;
                this.dataPen[x] = penSet;
                this.dataAll.totalLenght += allSet.length;
                this.dataSec.totalLenght += secSet.length;
                this.dataFal.totalLenght += failSet.length;
                this.dataPen.totalLenght += penSet.length;
              }
              this.dataButton.forEach(item => {
                item.dataList =
                  item.key === 'pen'
                    ? this.dataPen
                    : item.key === 'sec'
                      ? this.dataSec
                      : item.key === 'fal'
                        ? this.dataFal
                        : this.dataAll;
              });
              const sel = this.clickSec.selected;
              this.clickSec.data =
                sel === 'pen'
                  ? this.dataPen
                  : sel === 'sec'
                    ? this.dataSec
                    : sel === 'fal'
                      ? this.dataFal
                      : this.dataAll;

              if (!this.timer) {
                this.dataListPaged = [];
                this.dataListShadow = [];
                this.collapsedGroups.clear();
                this.renderTableList = [];
                this.initPageConf(this.dataFir.contents);
                this.loadPage();
              }

              // 组件已销毁则不再创建定时器
              if (this.isDestroyed) return;

              //  如果存在执行中添加定时器
              if (this.dataPen.totalLenght === 0) {
                clearInterval(this.timer);
                this.timer = null;
              } else {
                if (this.timer) {
                  return 1;
                }
                this.timer = setInterval(() => {
                  this.getCollectList(false);
                }, 10000);
              }
            }
          })
          .catch(e => {
            console.warn(e);
            this.statusFailed = true;
          })
          .finally(() => {
            this.reloadTable = false;
            this.basicLoading = false;
          });
      },
      // 采集状态过滤
      handleChangeGroup(val) {
        this.clickSec.selected = val.key;
        this.clickSec.data = val.dataList;
        this.dataListPaged = [];
        this.dataListShadow = [];
        this.collapsedGroups.clear();
        this.renderTableList = [];
        this.initPageConf(this.dataFir.contents || []);
        this.loadPage();
      },
      // 初始化前端分页
      initPageConf(list) {
        this.currentPage = 0;
        this.isPageOver = false;

        this.count = list.length;
        this.totalPage = Math.ceil(this.count / this.pageSize) || 1;
        this.dataListShadow = list;
        this.dataListPaged = [];
        for (let i = 0; i < this.count; i += this.pageSize) {
          this.dataListPaged.push(this.dataListShadow.slice(i, i + this.pageSize));
        }
      },
      loadPage() {
        this.currentPage += 1;
        this.isPageOver = this.currentPage === this.totalPage;

        if (this.dataListPaged[this.currentPage - 1]) {
          this.renderTableList.splice(this.renderTableList.length, 0, ...this.dataListPaged[this.currentPage - 1]);
          top &&
            this.$nextTick(() => {
              // this.scrollontentEl.scrollTop = top
            });
        }
      },
      handleScroll() {
        if (this.throttle) {
          return;
        }

        this.throttle = true;
        setTimeout(() => {
          this.throttle = false;

          const el = this.scrollontentEl;

          if (this.isPageOver) {
            return;
          }
          if (el.scrollHeight - el.offsetHeight - el.scrollTop < 60) {
            this.loadPage(el.scrollTop);
          }
        }, 200);
      },
      // 重试
      retryClick(val, key) {
        this.reloadTable = true;
        const retryList = [];
        if (key === 'odd') {
          retryList.push(val.instance_id);
        } else {
          if (val.totalLenght === 0) {
            // 判断是否存在失败项
            this.reloadTable = false;
            return 1;
          }
          for (let y = 0; y < key; y++) {
            for (let i = 0; i < val[y].length; i++) {
              retryList.push(val[y][i].instance_id);
            }
          }
        }
        ServicesInstance.source.retryList({
            params: {
              collector_config_id: this.$route.params.collectorId,
            },
            data: {
              instance_id_list: retryList,
            },
          })
          .then(() => {
            this.getCollectList();
          })
          .catch(e => {
            console.warn(e);
            this.reloadTable = false;
          });
      },
      viewDetail(row) {
        this.detail.isShow = true;
        this.detail.loading = true;
        this.requestDetail(row);
      },
      requestDetail(row) {
        ServicesInstance.collect.executDetails({
            params: {
              collector_id: this.$route.params.collectorId,
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
            TDesignMessage("error", { content: err.message || err });
          })
          .finally(() => {
            this.detail.loading = false;
          });
      },
      closeSlider() {
        this.detail.content = '';
        this.detail.loading = false;
      },
      jsonFormatClick() {
        // this.$router.push({
        //   name: 'jsonFormat',
        //   params: {
        //     collectorId: this.config_id,
        //   },
        //   query: {
        //     spaceUid: this.$store.state.spaceUid,
        //   },
        // });
      },
      viewReport(row) {
        const { cloud_id: cloudId, host_id: hostId, ip } = row;
        ServicesInstance.collect.runCheck({
            data: {
              collector_config_id: this.$route.params.collectorId,
              hosts: [
                {
                  bk_cloud_id: cloudId,
                  bk_host_id: hostId,
                  ip,
                },
              ],
            },
          })
          .then(res => {
            if (res.data?.check_record_id) {
              this.reportDetailShow = true;
              this.checkRecordId = res.data.check_record_id;
            }
          });
      },
      getShowIp(row) {
        return row[this.hostIdentifierPriority.find(pItem => Boolean(row[pItem]))] ?? row.ip;
      },
    },
  };
</script>

<style lang="scss" scoped>
@use '../../../../../shared/styles/mixins/clearfix' as *;
@use '@/shared/ui/loading/status-spinner' as *;
  /* stylelint-disable no-descending-specificity */
  .collection-status-container {
    .table-calc {
      overflow-x: auto;
    }

    .status-table-with-rows {
      min-width: 1040px;
    }

    .nav-section {
      display: flex;
      flex-wrap: wrap;
      align-items: center;
      justify-content: space-between;
      gap: var(--bklog-space-8);
      margin-block-end: var(--bklog-space-12);

      .status-toolbar-actions {
        display: flex;
        flex-wrap: wrap;
        align-items: center;
        gap: var(--bklog-space-8);

        > span {
          font-size: var(--bklog-font-body);
          color: var(--td-text-color-secondary);
        }
      }

      .icon-question-circle {
        margin-right: 10px;
        font-size: var(--bklog-font-action);
        color: var(--td-text-color-secondary);
      }

      :deep(.t-button) {
        padding: 0 10px;
        font-size: var(--bklog-font-body, 12px);

        .icon-right-turn-line {
          margin-right: 4px;
          font-size: 18px;
        }
      }
    }

    .collection-status-group {
      overflow: hidden;
    }

    .collection-status-group + .collection-status-group {
      margin-block-start: var(--bklog-space-12);
    }

    .table-detail {
      width: 100%;

      > button {
        width: 100%;
        text-align: start;
        font-family: inherit;
        box-sizing: border-box;
        display: flex;
        gap: var(--bklog-space-4);
        align-items: center;
        height: var(--bklog-table-header-medium);
        padding-inline: var(--bklog-space-24);
        font-size: var(--bklog-font-body);
        line-height: var(--bklog-line-height-body);
        color: var(--bklog-standard-control-text, var(--td-text-color-primary));
        cursor: pointer;
        user-select: none;
        background-color: var(--bklog-surface-subtle, var(--td-bg-color-secondarycontainer));
        border: var(--bklog-border-width) solid var(--bklog-standard-control-border-disabled, var(--td-component-stroke));
        border-bottom: 0;
        border-radius: var(--bklog-standard-control-radius) var(--bklog-standard-control-radius) 0 0;
        &:focus-visible {
          outline: var(--bklog-border-width) solid var(--bklog-brand-primary, var(--td-brand-color));
          outline-offset: calc(-2 * var(--bklog-border-width));
        }
      }

      .group-title {
        font-weight: var(--bklog-table-header-font-weight);
      }

      .group-summary {
        margin-inline-start: var(--bklog-space-16);
        color: var(--bklog-standard-control-border-hover, var(--td-text-color-secondary));
      }
    }

    .collection-status-cell {
      display: inline-flex;
      gap: var(--bklog-space-4);
      align-items: center;

      .collection-status-icon {
        @include collection-status-icon-slot();
      }

      .collection-status-dot {
        @include collection-status-dot();

        &.is-success {
          @include collection-status-dot-color(var(--bklog-status-success, var(--td-success-color)), var(--bklog-status-success-ring, var(--td-success-color-light)));
        }

        &.is-failed {
          @include collection-status-dot-color(var(--bklog-status-error, var(--td-error-color)), var(--bklog-status-error-ring, var(--td-error-color-light)));
        }
      }

      .collection-status-spinner {
        width: 14px;
        height: 14px;

        @include status-spinner();
        @include status-spinner-segments();
      }
    }

    .text-style {
      display: flex;
      gap: var(--bklog-space-12);

      span {
        color: var(--bklog-brand-primary);
        cursor: pointer;

        &:hover {
          color: var(--bklog-brand-hover);
        }
      }
    }

    .SUCCESS {
      color: var(--bklog-status-success, var(--td-success-color));
    }

    .FAILED {
      color: var(--bklog-status-error, var(--td-error-color));
    }

    .PENDING {
      color: var(--bklog-brand-primary);
    }

    .button-group {
      max-width: 100%;
      overflow-x: auto;

      > button {
        flex: none;
        white-space: nowrap;
        box-sizing: border-box;
        display: inline-flex;
        align-items: center;
        justify-content: center;
        height: var(--bklog-control-size-medium);
        padding-inline: var(--bklog-space-12);
        font-size: var(--bklog-font-body);
        line-height: var(--bklog-line-height-body);
        color: var(--bklog-standard-control-text, var(--td-text-color-primary));
        font-family: inherit;
        cursor: pointer;
        background-color: var(--bklog-surface, var(--td-bg-color-container));
        border: var(--bklog-border-width) solid var(--bklog-standard-control-border, var(--td-border-level-2-color));

        &:hover {
          border-color: var(--bklog-brand-primary, var(--td-brand-color));
        }

        &:focus-visible {
          outline: var(--bklog-border-width) solid currentColor;
          outline-offset: calc(-2 * var(--bklog-border-width));
        }

        &[aria-pressed="true"] {
          color: var(--bklog-brand-primary, var(--td-brand-color));
          background-color: var(--bklog-brand-tint, var(--td-brand-color-light));
          border-color: var(--bklog-brand-primary, var(--td-brand-color));

          &:hover {
            border-color: var(--bklog-brand-active, var(--td-brand-color-active));
          }
        }
      }
    }

    .content-style {
      display: flex;

      > div {
        margin-left: 24px;
        font-size: 14px;

        p {
          display: inline-block;
          height: 20px;
          padding: 0 5px;
          margin-right: 2px;
          line-height: 20px;
          color: var(--td-text-color-secondary);
          text-align: center;
          background-color: var(--bklog-surface-subtle, var(--td-bg-color-secondarycontainer));
          border-radius: var(--bklog-standard-control-radius);
        }
      }
    }

    .title-icon {
      font-size: var(--bklog-font-action);

      &:hover {
        cursor: pointer;
      }
    }
  }

  .detail-content {
    min-height: calc(100vh - 60px);
    color: var(--td-text-color-primary);
    overflow-wrap: anywhere;
    white-space: pre-wrap;
    background-color: var(--td-bg-color-container);

    :deep(a) {
      color: var(--td-text-color-link);
    }
  }
</style>
