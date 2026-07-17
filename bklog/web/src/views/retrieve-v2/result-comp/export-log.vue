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
  <div>
    <!-- <div
        :class="{ 'operation-icon': true, 'disabled-icon': !queueStatus }"
        @click="exportLog"
        data-test-id="fieldForm_div_exportData"
        v-bk-tooltips="queueStatus ? $t('导出') : undefined">
        <span class="icon bklog-icon bklog-xiazai"></span>
      </div> -->
    <BklogPopover
      ref="downloadProgressPopover"
      :key="displayTasks.length >= 1 ? 'popover-active' : 'popover-inactive'"
      :trigger="displayTasks.length >= 1 ? 'hover' : 'manual'"
      :options="{ placement: 'bottom', arrow: true }"
      content-class="download-progress-popover"
    >
      <bk-badge
        :visible="failedTaskCount > 0"
        :val="failedTaskCount"
        theme="danger"
        position="top-right"
      >
        <div
          :class="{ 'operation-icon': true, 'disabled-icon': !queueStatus }"
          data-test-id="fieldForm_div_exportData"
          @click="exportLog"
        >
          <span
            class="icon bklog-icon bklog-download"
            style="font-size: 16px"
          ></span>
          <div
            v-if="totalProgressPercent > 0"
            class="progress-mask"
            :style="{ '--progress': totalProgressPercent + '%' }"
          >
          </div>
        </div>
      </bk-badge>
      <template #content>
        <div
          class="download-progress-content"
          @click="handleShowHistoryExport"
        >
          <TaskItem
            v-for="task in displayTasks"
            :key="task.id"
            :item="task"
            @retry-export="handleRetryExport"
          />
        </div>
      </template>
    </BklogPopover>

    <!-- 原downloadTips选项弹窗已移除，点击下载按钮直接打开下载日志弹窗
    <div v-show="false">
      <div
        ref="downloadTips"
        class="download-box"
      >
        <span @click="exportLog">{{ $t('下载日志') }}</span>
        <span @click="downloadTable">{{ $t('下载历史') }}</span>
      </div>
    </div>
    -->

    <export-history
      :index-set-list="indexSetList"
      :show-history-export="showHistoryExport"
      :export-list="exportListData"
      :table-loading="exportTableLoading"
      :date-range="exportDateRange"
      :pagination="exportPagination"
      @handle-close-dialog="handleCloseDialog"
      @date-range-change="handleDateRangeChange"
      @pagination-change="handlePaginationChange"
      @loading-change="handleLoadingChange"
      @start-polling="startStatusPolling"
      @get-table-list="getTableList"
    />

    <!-- 导出弹窗提示 -->
    <bk-dialog
      ext-cls="async-export-dialog"
      v-model="isShowExportDialog"
      :mask-close="false"
      :ok-text="$t('下载')"
      :width="640"
      header-position="left"
      theme="primary"
      @after-leave="closeExportDialog"
      @confirm="handleClickSubmit"
    >
      <template #header>
        <div class="dialog-header-custom">
          <span>{{ $t('下载日志') }}</span>
          <span
            class="view-history-btn"
            @click="handleViewDownloadHistory"
          >{{ $t('查看下载历史') }}</span>
          <div
            v-if="totalProgressPercent > 0"
            class="circular-progress"
            :style="{ '--progress': totalProgressPercent + '%' }"
          >
          </div>
          <div
            v-if="failedTaskCount > 0"
            class="failed-task-tip"
          >
            <span class="failed-task-count">{{ failedTaskCount }}</span>
            <span class="failed-task-text">{{ $t('存在下载失败') }}</span>
          </div>
        </div>
      </template>
      <div
        class="export-container"
        v-bkloading="{ isLoading: exportLoading }"
      >
        <div class="log-num-container">
          <div class="num-box">
            <span class="log-num">{{ $t('{n}条', { n: totalCount }) }}</span>
            <span class="log-unit">{{ $t('当前数据量级') }}</span>
          </div>
          <div class="num-box">
            <span class="log-num">{{ sizDownload }}min</span>
            <span class="log-unit">{{ $t('预计下载时长') }}</span>
          </div>
        </div>
        <div class="filed-select-box">
          <span class="middle-title">{{ $t('下载模式') }}</span>
          <bk-radio-group
            class="filed-radio-box"
            v-model="downloadType"
          >
            <bk-radio
              v-for="[key, val] in Object.entries(downloadTypeRadioMap)"
              :key="key"
              :value="key"
            >
              {{ val }}
            </bk-radio>
          </bk-radio-group>
          <span
            v-if="!!typeTipsMap[downloadType]"
            class="mode-hint"
          >
            <bk-alert
              type="info"
              :title="typeTipsMap[downloadType]"
            ></bk-alert>
          </span>
        </div>
        <div
          class="filed-select-box"
          v-if="downloadType !== 'quick'"
        >
          <span class="middle-title">{{ $t('下载范围') }}</span>
          <bk-radio-group
            class="filed-radio-box"
            v-model="selectFiledType"
          >
            <bk-radio
              v-for="[key, val] in Object.entries(radioMap)"
              :key="key"
              :value="key"
            >
              {{ val }}
            </bk-radio>
          </bk-radio-group>
          <bk-select
            v-if="selectFiledType === 'specify'"
            v-model="selectFiledList"
            :placeholder="$t('未选择则默认为全部字段')"
            display-tag
            multiple
            searchable
          >
            <bk-option
              v-for="option in totalFields"
              :id="option.field_name"
              :key="option.field_name"
              :name="getFieldName(option)"
            >
            </bk-option>
          </bk-select>
        </div>
        <!-- <div class="filed-select-box">
          <span class="middle-title">{{ $t('文件类型') }}</span>
          <bk-select
            style="margin-top: 10px"
            v-model="documentType"
            :clearable="false"
            :placeholder="$t('请选择文件类型')"
          >
            <bk-option
              v-for="option in documentTypeList"
              :id="option.id"
              :key="option.id"
              :name="option.name"
            >
            </bk-option>
          </bk-select>
        </div> -->
        <!-- v-if="isShowMaskingTemplate" -->
        <div
          v-if="false"
          class="desensitize-select-box"
        >
          <span class="middle-title">{{ $t('日志类型') }}</span>
          <bk-radio-group
            class="desensitize-radio-box"
            v-model="desensitizeRadioType"
          >
            <bk-radio
              v-for="[key, val] in Object.entries(logTypeMap)"
              :key="key"
              :value="key"
            >
              {{ val }}
            </bk-radio>
          </bk-radio-group>
        </div>
      </div>
    </bk-dialog>
  </div>
</template>

<script>
  import { blobDownload } from '@/common/util';
  import { mapGetters, mapState } from 'vuex';
  import useFieldNameHook from '@/hooks/use-field-name';
  import exportHistory from './export-history';
  import { axiosInstance } from '@/api';
  import { BK_LOG_STORAGE } from '@/store/store.type';
  import { getEffectiveSearchTotal } from '@/storage/utils/normalize-search-total';
  import BklogPopover from '@/components/bklog-popover';
  import TaskItem from './TaskItem';
  import {
    calculateProgress,
    adjustGrowthAfterPoll,
    calculateProgressPercent,
  } from '@/views/retrieve-v2/result-comp/download/downloadProgress';

  // 需要轮询的状态列表
  const POLLING_STATUS = ['download_log', 'export_package', 'export_upload', null];

  export default {
    components: {
      exportHistory,
      BklogPopover,
      TaskItem,
    },
    inheritAttrs: false,
    props: {
      retrieveParams: {
        type: Object,
        required: true,
      },
      // totalCount: {
      //   type: Number,
      //   default: 0,
      // },
      // visibleFields: {
      //   type: Array,
      //   require: true,
      // },
      // queueStatus: {
      //   type: Boolean,
      //   default: true,
      // },
      // totalFields: {
      //   type: Array,
      //   require: true,
      // },
      datePickerValue: {
        type: Array,
        require: true,
      },
      indexSetList: {
        type: Array,
        required: true,
      },
    },
    data() {
      return {
        isShowExportDialog: false,
        exportLoading: false,
        showHistoryExport: false,
        selectFiledList: [], // 手动选择字段列表
        selectFiledType: 'all', // 字段下载类型
        desensitizeRadioType: 'desensitize', // 原文还是脱敏下载日志类型
        popoverInstance: null,
        exportFirstComparedSize: 10000, // 显示异步下载的临界值
        exportSecondComparedSize: 2000000, // 可异步下载最大值
        radioMap: {
          all: this.$t('全部字段'),
          show: this.$t('当前显示字段'),
          specify: this.$t('指定字段'),
        },
        downloadType: 'all',
        downloadTypeRadioMap: {
          all: this.$t('全文下载'),
          quick: this.$t('快速下载(提速100%+)'),
          sampling: this.$t('取样下载(前1万条)'),
        },
        typeTipsMap: {
          quick: this.$t(
            '该模式下，仅下载您上报的无序日志原文，您可以通过日志时间进行本地排序；日志无法包含平台补充字段：如集群名、模块名等信息。该模式的日志导出上限为500万条',
          ),
          all: this.$t('该模式下，下载的日志有序，可包含平台补充字段，但下载时间较长。该模式的日志导出上限为200万条'),
          sampling: '',
        },
        timeCalculateMap: {
          all: 200000,
          quick: 400000,
          sampling: 0,
        },
        logTypeMap: {
          desensitize: this.$t('脱敏'),
          // origin: this.$t('原始'),
        },
        documentType: 'log',
        documentTypeList: [
          // {
          //   id: 'csv',
          //   name: 'csv',
          // },
          {
            id: 'log',
            name: 'log',
          },
        ],
        modeHintMap: {},
        // queueStatus: true
        // 导出历史相关数据
        exportListData: [], // 导出列表数据
        exportTableLoading: false, // 表格加载状态
        exportPollingTimer: null, // 轮询定时器
        exportDateRange: [], // 查询时间范围（默认最近3月）
        exportPagination: {
          current: 1,
          count: 0,
          limit: 10,
        },
        isComponentUnmounted: false, // 组件是否已卸载
        progressUpdateTimer: null, // 进度更新定时器
        baseGrowth: 20000, // 基础增长量：10秒增长20000条
        popoverHoverTimer: null, // Popover 悬浮延迟隐藏定时器
        pendingTaskStatus: {}, // 进行中任务状态记录 { [taskId]: status }
        failedTaskIds: [],
        failedTaskTimer: null, // 失败任务定时器
      };
    },
    computed: {
      ...mapState({
        totalCount: state => {
          const effectiveTotal = getEffectiveSearchTotal(state);
          if (effectiveTotal > 0) {
            return effectiveTotal;
          }

          return state.retrieve.trendDataCount;
        },
        queueStatus: state => state.retrieve.isTotalCountLoaded,
        totalFields: (_state, getters) => getters.filteredFieldList,
        visibleFields: state => state.visibleFields ?? [],
        showFieldAlias: state => state.storage[BK_LOG_STORAGE.SHOW_FIELD_ALIAS],
        retrieveType: state => state.indexItem?.retrieve_type,
        isLoading: state => state.indexSetQueryResult?.is_loading,
      }),
      ...mapGetters({
        bkBizId: 'bkBizId',
        spaceUid: 'spaceUid',
        isShowMaskingTemplate: 'isShowMaskingTemplate',
        unionIndexList: 'unionIndexList',
        isUnionSearch: 'isUnionSearch',
      }),
      sizDownload() {
        if (this.downloadType === 'sampling') return '< 1';
        return Math.ceil(this.totalCount / this.timeCalculateMap[this.downloadType]);
      },
      submitSelectFiledList() {
        // 下载时提交的字段
        if (this.selectFiledType === 'specify') return this.selectFiledList;
        if (this.selectFiledType === 'show') return this.visibleFields.map(item => item.field_name);
        return [];
      },
      routerIndexSet() {
        return window.__IS_MONITOR_COMPONENT__ ? this.$route.query.indexId : this.$store.state.indexId;
      },
      isScene() {
        return this.$store.getters.isSceneMode;
      },
      /** 当前显示的单个下载中任务（最先下载的任务），优先取 download_log 类型 */
      activeDownloadingTask() {
        const tasks = this.displayTasks;
        // 优先查找 download_log 类型的任务
        const downloadLogTask = tasks.find(row => row.export_type === 'download_log');
        if (downloadLogTask) return downloadLogTask;
        // 否则返回第一个任务
        return tasks[0] || null;
      },
      /** 当前下载中任务的进度百分比 */
      totalProgressPercent() {
        const task = this.activeDownloadingTask;
        if (!task) return 0;
        const total = task.export_total_count || 0;
        if (total <= 0) return 0;
        return calculateProgressPercent(task.exported_count || 0, total);
      },
      /** 需要显示的任务列表（下载中/未启动任务 + 失败任务） */
      displayTasks() {
        const currentUser = this.$store.state.userMeta?.username || '';
        return this.exportListData
          .filter(row => {
            // 只显示当前用户的任务
            if (row.export_created_by !== currentUser) return false;
            const status = row.export_status;
            if (status === 'failed') {
              return this.failedTaskIds.includes(row.id);
            }
            return POLLING_STATUS.includes(status);
          })
          .reverse();
      },
      /** 失败任务数量 */
      failedTaskCount() {
        return this.failedTaskIds.length;
      },
    },
    watch: {
      totalCount(val) {
        if (val < 10000) {
          this.downloadType = 'sampling';
        } else if (val < 2000000) {
          this.downloadType = 'all';
        } else {
          this.downloadType = 'quick';
        }
      },
      routerIndexSet: {
        immediate: true,
        handler(newVal) {
          if (newVal) {
            this.resetComponentState();
          }
        }
      },
      // 联合查询索引集组变化时重置状态
      unionIndexList: {
        handler(newVal) {
          if (this.isUnionSearch && newVal?.length) {
            this.resetComponentState();
          }
        },
        immediate: true,
      },
      retrieveType(newVal, oldVal) {
        if (oldVal === 'scene' && newVal !== 'scene') {
          this.resetComponentState();
        }
      },
      isLoading(newVal, oldVal) {
        if (this.isScene && oldVal === true && newVal === false) {
          this.resetComponentState();
        }
      },
      displayTasks() {
        // 当 displayTasks 为空时，手动关闭 popover
        if (this.displayTasks.length === 0 && this.$refs.downloadProgressPopover) {
          this.$refs.downloadProgressPopover.hide();
        }
      },
      showHistoryExport(val) {
        // 当下载历史弹窗打开时，拉取最新数据
        if (val) {
          this.initDateRange();
          this.getTableList(true);
        }
      },
    },
    mounted() {
      // 初始化时间范围为最近3月
      this.initDateRange();
    },
    beforeDestroy() {
      // 设置组件卸载标志位
      this.isComponentUnmounted = true;
      // 清除轮询定时器
      this.stopStatusPolling();
      // 清除进度更新定时器
      this.stopProgressUpdate();
      // 清除 Popover 悬浮定时器
      clearTimeout(this.popoverHoverTimer);
      // 清除失败任务定时器
      this.clearFailedTaskTimer();
    },
    methods: {
      // 原handleShowAlarmPopover方法已移除，点击下载按钮直接打开下载日志弹窗
      // handleShowAlarmPopover(e) {
      //   if (this.popoverInstance || !this.queueStatus) return;
      //   this.popoverInstance?.hide();
      //   this.popoverInstance?.destroyed();
      //   this.popoverInstance = null;
      //   this.popoverInstance = this.$bkPopover(e.target, {
      //     content: this.$refs.downloadTips,
      //     trigger: 'mouseenter',
      //     placement: 'top',
      //     theme: 'light',
      //     offset: '0, -1',
      //     interactive: true,
      //     hideOnClick: false,
      //     extCls: 'download-box',
      //     arrow: true,
      //   });
      //   this.popoverInstance?.show();
      // },
      /**
       * 重置组件状态：清空进行中任务记录、失败任务定时器和记录，重新初始化数据
       */
      resetComponentState() {
        // 清空进行中任务状态记录
        this.pendingTaskStatus = {};
        // 清空失败任务定时器和记录
        this.clearFailedTaskTimer();
        this.failedTaskIds = [];
        // 重新初始化数据
        this.initDateRange();
        this.getTableList();
      },
      exportLog() {
        if (!this.queueStatus) return;
        // 导出数据为空
        if (!this.totalCount) {
          const infoDialog = this.$bkInfo({
            type: 'error',
            title: this.$t('导出失败'),
            subTitle: this.$t('检索结果条数为0'),
            showFooter: false,
          });
          setTimeout(() => infoDialog.close(), 3000);
          return;
        }
        this.isShowExportDialog = true;
      },
      handleViewDownloadHistory() {
        // 关闭当前下载日志弹窗
        this.isShowExportDialog = false;
        // 打开下载历史弹窗
        this.showHistoryExport = true;
      },
      handleClickSubmit() {
        if (this.downloadType === 'quick') {
          this.quickDownload();
        } else if (this.downloadType === 'all') {
          this.downloadAsync();
        } else {
          this.openDownloadUrl();
        }
        this.isShowExportDialog = false;
      },
      quickDownload() {
        const { timezone, ...rest } = this.retrieveParams;
        const params = Object.assign(rest, { begin: 0, bk_biz_id: this.bkBizId });
        let downRequestUrl;
        if (this.isScene) {
          downRequestUrl = '/search/scene/export/quick/';
        } else if (this.isUnionSearch) {
          downRequestUrl = `/search/index_set/union_async_export/`;
        } else {
          downRequestUrl = `/search/index_set/${this.routerIndexSet}/quick_export/`;
        }
        const data = {
          ...params,
          size: this.totalCount,
          time_range: 'customized',
          export_fields: this.submitSelectFiledList,
          is_desensitize: this.desensitizeRadioType === 'desensitize',
          file_type: this.documentType,
        };
        if (this.isUnionSearch) {
          Object.assign(data, {
            is_quick_export: true,
            union_configs: this.unionIndexList.map(item => {
              return {
                begin: 0,
                index_set_id: item,
              };
            }),
          });
        }
        axiosInstance
          .post(downRequestUrl, data, {
            originalResponse: true,
          })
          .then(res => {
            if (res.result) {
              this.$bkMessage({
                theme: 'success',
                ellipsisLine: 2,
                message: this.$t('任务提交成功，下载完成将会收到邮件通知。可前往下载历史查看下载状态'),
              });
              // 更新时间范围拉取最新数据
              this.initDateRange(true);
              this.getTableList(true);
            } else {
              this.$bkMessage({
                theme: 'error',
                ellipsisLine: 2,
                message: res.message,
              });
            }
          })
          .catch(err => {
            console.log(err);
          })
          .finally(() => {
            this.isShowExportDialog = false;
            this.selectFiledList = [];
          });
      },
      async openDownloadUrl() {
        const { timezone, ...rest } = this.retrieveParams;
        const params = Object.assign(rest, { begin: 0, bk_biz_id: this.bkBizId });
        let downRequestUrl;
        if (this.isScene) {
          downRequestUrl = '/search/scene/export/sample/';
        } else if (this.isUnionSearch) {
          // 判断是否是联合查询 如果是 则加参数
          downRequestUrl = '/search/index_set/union_search/export/';
          Object.assign(params, { index_set_ids: this.unionIndexList });
        } else {
          downRequestUrl = `/search/index_set/${this.routerIndexSet}/export/`;
        }
        const data = {
          ...params,
          size: this.totalCount,
          time_range: 'customized',
          export_fields: this.submitSelectFiledList,
          is_desensitize: this.desensitizeRadioType === 'desensitize',
          file_type: this.documentType,
        };
        axiosInstance
          .post(downRequestUrl, data)
          .then(res => {
            if (typeof res !== 'string') {
              this.$bkMessage({
                theme: 'error',
                message: this.$t('导出失败'),
              });
              return;
            }
            const lightName = this.indexSetList.find(item => item.index_set_id === this.routerIndexSet)?.lightenName;
            const downloadName = lightName
              ? `bk_log_search_${lightName.substring(2, lightName.length - 1)}.${this.documentType}`
              : `bk_log_search.${this.documentType}`;
            blobDownload(res, downloadName);
          })
          .finally(() => {
            this.isShowExportDialog = false;
            this.selectFiledList = [];
          });
      },
      async downloadAsync() {
        const { timezone, ...rest } = this.retrieveParams;
        const params = Object.assign(rest, { begin: 0, bk_biz_id: this.bkBizId });
        const data = { ...params };
        let downRequestUrl;
        if (this.isScene) {
          downRequestUrl = 'retrieve/getSceneAsyncExport';
        } else if (this.isUnionSearch) {
          downRequestUrl = 'retrieve/unionExportAsync';
        } else {
          downRequestUrl = 'retrieve/exportAsync';
        }
        data.size = this.totalCount;
        data.export_fields = this.submitSelectFiledList;
        data.is_desensitize = this.desensitizeRadioType === 'desensitize';
        if (this.isUnionSearch) {
          Object.assign(data, {
            is_quick_export: false,
            union_configs: this.unionIndexList.map(item => {
              return {
                begin: 0,
                index_set_id: item,
              };
            }),
          });
        }
        this.exportLoading = true;
        const requestConfig = this.isScene || this.isUnionSearch
          ? { data }
          : {
              params: { index_set_id: this.routerIndexSet },
              data,
            };
        this.$http
          .request(downRequestUrl, requestConfig)
          .then(res => {
            if (res.result) {
              this.$bkMessage({
                theme: 'success',
                ellipsisLine: 2,
                message: this.$t('任务提交成功，下载完成将会收到邮件通知。可前往下载历史查看下载状态'),
              });
              // 更新时间范围拉取最新数据
              this.initDateRange(true);
              this.getTableList(true);
            }
          })
          .catch(err => {
            console.log(err);
          })
          .finally(() => {
            this.exportLoading = false;
            this.isShowExportDialog = false;
            this.selectFiledList = [];
          });
      },
      closeExportDialog() {
        this.selectFiledType = 'all';
        this.selectFiledList = [];
        // 清空失败任务定时器和记录
        this.clearFailedTaskTimer();
        this.failedTaskIds = [];
      },
      // 原downloadTable方法已修改，不再需要隐藏popover
      downloadTable() {
        this.showHistoryExport = true;
        // this.popoverInstance.hide(0);
      },
      handleCloseDialog() {
        this.showHistoryExport = false;
      },
      getFieldName(field) {
        const { getQueryAlias } = useFieldNameHook({ store: this.$store });
        return getQueryAlias(field);
      },
      // ========== 导出历史相关方法 ==========
      /**
       * @desc: 初始化时间范围（最近3月）
       */
      /**
       * @desc: 初始化时间范围（最近3月）
       * @param { boolean } extendEndTime - 是否延长查询截止时间
       */
      initDateRange(extendEndTime = false) {
        const end = new Date();
        if (extendEndTime) {
          end.setTime(end.getTime() + 3000);
        }
        const start = new Date();
        start.setTime(start.getTime() - 3600 * 1000 * 24 * 90);
        this.exportDateRange = [start, end];
      },
      /**
       * @desc: 处理子组件时间范围变更事件
       */
      handleDateRangeChange(newDateRange) {
        this.exportDateRange = newDateRange;
        this.getTableList(true);
      },
      /**
       * @desc: 处理子组件分页变更事件
       */
      handlePaginationChange({ page, limit }) {
        if (page) {
          this.exportPagination.current = page;
        }
        if (limit) {
          this.exportPagination.limit = limit;
          this.exportPagination.current = 1;
        }
        this.getTableList();
      },
      /**
       * @desc: 处理子组件 loading 变更事件
       */
      handleLoadingChange(isLoading) {
        this.exportTableLoading = isLoading;
      },
      /**
       * @desc: 显示下载历史弹窗
       */
      handleShowHistoryExport() {
        // 打开下载历史弹窗
        this.showHistoryExport = true;
        // 清空失败任务定时器和记录
        this.clearFailedTaskTimer();
        this.failedTaskIds = [];
      },
      /**
       * @desc: 处理重试导出
       * @param { Object } task 任务对象
       */
      async handleRetryExport(task) {
        // 从失败任务列表中移除
        this.failedTaskIds = this.failedTaskIds.filter(id => id !== task.id);
        // 异常任务直接异步下载
        if (task.export_type === 'sync') {
          await this.openDownloadUrl(task);
        } else {
          await this.downloadAsync(task.search_dict);
        }
        this.getTableList(true);
      },
      /**
       * @desc: 轮询
       */
      startStatusPolling() {
        this.stopStatusPolling();
        this.exportPollingTimer = setInterval(() => {
          this.getTableList(false, true);
        }, 10000);
      },
      stopStatusPolling() {
        if (this.exportPollingTimer) {
          clearInterval(this.exportPollingTimer);
          this.exportPollingTimer = null;
        }
      },
      /**
       * @desc: 检查是否需要继续轮询
       * @returns { Boolean } 是否需要继续轮询
       */
      shouldContinuePolling() {
        return this.exportListData.some(item => POLLING_STATUS.includes(item.export_status));
      },
      /**
       * @desc: 初始化拉取中任务的增长修正量
       * 为每个拉取中的任务设置 currentGrowth 和 progressPercent
       */
      initGrowthAdjustMap() {
        this.exportListData.forEach(row => {
          if (row.export_status === 'download_log') {
            // 初始增长量等于基础增长量
            row.currentGrowth = this.baseGrowth;
            // 初始化进度百分比
            row.progressPercent = calculateProgressPercent(
              row.exported_count || 0,
              row.export_total_count || 0,
            );
          }
        });
      },
      /**
       * @desc: 启动1秒进度更新定时器
       */
      startProgressUpdate() {
        this.stopProgressUpdate();
        this.progressUpdateTimer = setInterval(() => {
          this.updateAllTaskProgress();
        }, 1000);
      },
      /**
       * @desc: 停止1秒进度更新定时器
       */
      stopProgressUpdate() {
        if (this.progressUpdateTimer) {
          clearInterval(this.progressUpdateTimer);
          this.progressUpdateTimer = null;
        }
      },
      /**
       * @desc: 清除失败任务定时器
       */
      clearFailedTaskTimer() {
        if (this.failedTaskTimer) {
          clearTimeout(this.failedTaskTimer);
          this.failedTaskTimer = null;
        }
      },
      /**
       * @desc: 每秒更新当前下载中任务的进度
       */
      updateAllTaskProgress() {
        let hasActiveTask = false;

        this.exportListData.forEach(row => {
          if (POLLING_STATUS.includes(row.export_status)) {
            hasActiveTask = true;
            row.export_status === 'download_log' && calculateProgress(row);
          }
        });

        if (!hasActiveTask) {
          this.stopProgressUpdate();
        }
      },
      /**
       * @desc: 处理任务状态记录与变化检测
       * @param { Array } data 任务列表数据
       */
      handleTaskStatus(data) {
        const currentUser = this.$store.state.userMeta?.username || '';
        data.forEach(item => {
          // 只处理当前用户的任务
          if (item.export_created_by !== currentUser) return;

          const oldStatus = this.pendingTaskStatus[item.id];
          const currentStatus = item.export_status;

          // 成功或失败状态：检查是否有记录，有记录则提示
          if (currentStatus === 'success' || currentStatus === 'failed') {
            if (oldStatus !== undefined) {
              // 下载成功时显示文件名，失败时显示错误信息
              const message = currentStatus === 'success'
                ? `${item.export_pkg_name || ''}${this.$t('下载成功')}`
                : (item.eerror_msg || this.$t('下载任务异常，请查看下载历史'));
              this.$bkMessage({
                theme: currentStatus === 'success' ? 'success' : 'error',
                message,
                closeIcon: true,
              });
              // 从记录中移除
              delete this.pendingTaskStatus[item.id];

              // 处理失败任务记录
              if (currentStatus === 'failed') {
                // 进行中任务失败时，记录到 failedTaskIds
                if (!this.failedTaskIds.includes(item.id)) {
                  this.failedTaskIds.push(item.id);
                }
                // 清除之前的定时器，重新设置20分钟定时器
                this.clearFailedTaskTimer();
                this.failedTaskTimer = setTimeout(() => {
                  this.failedTaskIds = [];
                }, 20 * 60 * 1000);
              }
            }
          } else if (POLLING_STATUS.includes(currentStatus)) {
            // 进行中状态：检查是否已有记录，没有则进行记录
            if (oldStatus === undefined) {
              this.pendingTaskStatus[item.id] = currentStatus;
            }
          }
        });
      },
      /**
       * @desc: 设置导出列表数据
       * @param { Array } data 数据
       * @param { Boolean } isPolling 该次请求是否是轮询
       */
      setExportListData(data, isPolling) {
        if (isPolling) {
          data.forEach(item => {
            this.exportListData.forEach(row => {
              if (row.id === item.id) {
                // 如果是拉取中的任务，修正增长量
                if (row.export_status === 'download_log' && item.export_status === 'download_log') {
                  adjustGrowthAfterPoll(row, item.exported_count || 0, this.baseGrowth);
                } else {
                  Object.assign(row, { ...item });
                }
              }
            });
          });
        } else {
          this.exportListData = data;
          if (this.shouldContinuePolling()) {
            // 初始化进行中任务的增长修正量
            this.initGrowthAdjustMap();
            this.startStatusPolling();
            this.startProgressUpdate();
          }
        }
      },
      /**
       * @desc: 获取table列表数据
       * @param { Boolean } isReset 是否从1页开始查询
       * @param { Boolean } isPolling 该次请求是否是轮询
       */
      getTableList(isReset = false, isPolling = false) {
        isReset && (this.exportPagination.current = 1);
        !isPolling && (this.exportTableLoading = true);
        const { limit, current } = this.exportPagination;
        let queryUrl;
        let requestConfig;

        // 将日期范围转换为时间戳（毫秒）
        const startTime = this.exportDateRange[0] ? this.exportDateRange[0].getTime() : null;
        const endTime = this.exportDateRange[1] ? this.exportDateRange[1].getTime() : null;

        const params = {
          bk_biz_id: this.bkBizId,
          page: current,
          pagesize: limit,
          show_all: false,
          start_time: startTime,
          end_time: endTime,
        };

        if (this.isUnionSearch && !this.unionIndexList.length) {
          this.exportListData = [];
          this.exportPagination.count = 0;
          this.stopStatusPolling();
          this.stopProgressUpdate();
          this.exportTableLoading = false;
          return;
        }

        if (this.isScene) {
          queryUrl = 'retrieve/getSceneExportHistory';
          params.space_uid = this.retrieveParams?.space_uid;
          params.table_id_conditions = this.retrieveParams?.table_id_conditions;
          params.scene_filter_values = this.retrieveParams?.scene_filter_values;
          requestConfig = { data: params };
        } else if (this.isUnionSearch) {
          queryUrl = 'unionSearch/unionExportHistory';
          params.index_set_id = window.__IS_MONITOR_COMPONENT__
            ? this.$route.query.indexId : this.$store.state.indexId;
          params.index_set_ids = this.unionIndexList;
        } else {
          queryUrl = 'retrieve/getExportHistoryList';
          params.index_set_id = window.__IS_MONITOR_COMPONENT__
            ? this.$route.query.indexId : this.$store.state.indexId;
        }

        if (!this.isScene) {
          requestConfig = { params };
        }

        this.$http
          .request(queryUrl, requestConfig)
          .then(res => {
            if (this.isComponentUnmounted) {
              // 组件已卸载，清除定时器并直接返回
              this.stopStatusPolling();
              this.stopProgressUpdate();
              return;
            }
            if (res.result) {
              this.exportPagination.count = res.data.total || 0;
              // 处理任务状态记录与变化检测
              this.handleTaskStatus(res.data.list);
              this.setExportListData(res.data.list, isPolling);
            }
            if (!this.shouldContinuePolling()) {
              this.stopStatusPolling();
              this.stopProgressUpdate();
            }
          })
          .finally(() => {
            this.exportTableLoading = false;
          });
      },
    },
  };
</script>

<style lang="scss" scoped>
  @import '@/scss/mixins/flex.scss';

  .operation-icon {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 32px;
    height: 32px;
    margin-left: 10px;
    cursor: pointer;
    background-color: #f0f1f5;
    border-radius: 2px;
    outline: none;
    transition: boder-color 0.2s;
    position: relative;

    &:hover {
      border-color: #4d4f56;
      transition: boder-color 0.2s;
    }

    &:active {
      border-color: #3a84ff;
      transition: boder-color 0.2s;
    }

    .bklog-icon {
      width: 16px;
      font-size: 16px;
      color: #4d4f56;
    }

    .progress-mask {
      position: absolute;
      top: 0;
      left: 0;
      right: 0;
      bottom: 0;
      background: conic-gradient(from 0deg, rgba(0, 0, 0, 0) var(--progress, 0%), rgba(0, 0, 0, 0.3) 0);
      transition: background 0.25s ease;
    }
  }

  .cannot-async-btn {
    display: flex;
    align-items: center;
    justify-content: center;
    margin-top: 10px;
  }

  .disabled-icon {
    cursor: not-allowed;
    background-color: #fff;
    border-color: #dcdee5;

    &:hover,
    .bklog-icon {
      color: #c4c6cc;
      border-color: #dcdee5;
    }
  }

  :deep(.bk-dialog-header-inner) {
    /* stylelint-disable-next-line declaration-no-important */
    color: #000 !important;
  }

  .filed-select-box {
    margin-bottom: 10px;
    font-size: 12px;
    text-align: left;

    .bk-select {
      width: 284px;
    }

    .filed-radio-box {
      margin: 8px 0 10px 0;

      .bk-form-radio {
        margin-right: 20px;
      }
    }
  }

  .desensitize-select-box {
    margin: 18px 0 10px 0;
    font-size: 12px;
    text-align: left;

    .desensitize-radio-box {
      margin-top: 8px;

      .bk-form-radio {
        margin-right: 24px;
      }
    }
  }

  .middle-title {
    font-size: 14px;
    font-weight: 700;

    &::after {
      display: inline-block;
      color: #ea3636;
      content: '*';
      transform: translateX(2px) translateY(2px);
    }
  }

  %num-box-extend {
    width: 48%;
    background: #f5f7fa;
    border-radius: 2px;

    @include flex-center();
  }

  .log-num-container {
    margin: 8px 0;
    font-size: 12px;

    @include flex-justify(space-between);

    .num-box {
      flex-direction: column;
      height: 80px;

      @extend %num-box-extend;

      .log-num,
      log-unit {
        color: #313238;
      }

      .log-num {
        margin-right: 2px;
        font-size: 24px;
        font-weight: 700;
      }
    }

    .log-str {
      margin-top: 4px;
    }
  }

  .mode-hint {
    margin-top: 20px;

    :deep(.icon-info) {
      color: #63656e;
    }

    :deep(.bk-alert-info) {
      border: none;
    }

    :deep(.bk-alert-wraper) {
      background: #f0f1f5;
    }
  }

  :deep(.bk-radio-text) {
    /* stylelint-disable-next-line declaration-no-important */
    font-size: 12px !important;
  }

  .async-export-dialog {
    .header {
      /* stylelint-disable-next-line declaration-no-important */
      padding: 18px 0px 16px !important;
      text-align: center;
    }

    .export-container {
      text-align: center;
    }

    .bk-dialog-warning {
      display: block;
      width: 58px;
      height: 58px;
      margin: 0 auto;
      font-size: 30px;
      line-height: 58px;
      color: #ff9c01;
      background-color: #ffe8c3;
      border-radius: 50%;
    }

    /* stylelint-disable-next-line no-duplicate-selectors */
    .header {
      display: inline-block;
      width: 100%;
      padding: 18px 24px 32px;
      margin: 0;
      overflow: hidden;
      font-size: 24px;
      line-height: 1.5;
      color: #313238;
      text-overflow: ellipsis;
      white-space: nowrap;
    }

    .export-type {
      display: flex;
      align-items: flex-start;
      padding: 0 22px;
      margin-bottom: 24px;

      .export-text {
        max-width: 184px;
        margin-left: 8px;
        font-size: 12px;
        line-height: 18px;
        color: #63656e;
        text-align: left;
      }

      .bk-button {
        min-width: auto;
        margin-left: auto;
      }

      .bk-icon {
        margin-top: 2px;
      }
    }

    .dialog-header-custom {
      display: flex;
      align-items: center;
      width: 100%;

      .view-history-btn {
        margin-left: 16px;
        padding-left: 12px;
        font-size: 14px;
        color: #3a84ff;
        cursor: pointer;
        z-index: 10;
        border-left: 1px solid #dcdee5;

        &:hover {
          color: #699df4;
        }
      }

      .failed-task-tip {
        display: flex;
        align-items: center;
        margin-left: 8px;
        font-size: 14px;

        .failed-task-count {
          width: 20px;
          height: 20px;
          text-align: center;
          line-height: 20px;
          font-size: 12px;
          background-color: #EA3636;
          border-radius: 50%;
          color: #fff;
          margin-right: 4px;
        }

        .failed-task-text {
          font-weight: 400;
          color: #EA3636;
        }
      }

      .circular-progress {
        width: 16px;
        height: 16px;
        margin-left: 8px;
        border-radius: 50%;
        background: conic-gradient(from 0deg, rgba(233, 237, 245, 1) var(--progress, 0%), rgba(0, 0, 0, 0.3) 0);
      }
    }
  }

  // 原download-box样式已移除，不再需要
  // .download-box {
  //   display: flex;
  //   flex-direction: column;
  //   justify-content: space-evenly;
  //   min-height: 60px;
  //   padding: 4px 0;
  //   font-size: 12px;

  //   span {
  //     padding: 2px 6px;
  //     cursor: pointer;

  //     &:hover {
  //       color: #3a84ff;
  //     }
  //   }
  // }

  // 下载进度弹窗样式
  .download-progress-popover {
    max-width: 320px;
    padding: 0;
    border-radius: 2px;
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.15);
  }

  .download-progress-content {
    padding: 16px 0;
    display: flex;
    flex-direction: column;
    gap: 24px;
    cursor: pointer;
  }
</style>
