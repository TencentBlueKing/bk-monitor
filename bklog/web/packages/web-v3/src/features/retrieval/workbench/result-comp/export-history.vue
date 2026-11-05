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
  <TDialog
    v-model:visible="isShowDialog"
    attach="body"
    dialog-class-name="export-history-dialog"
    top="120px"
    :header="false"
    width="80%"
    :close-on-overlay-click="false"
    :footer="false"
    destroy-on-close
    @close="closeDialog"
  >
    <div class="table-title">
      {{ $t('下载历史') }}
    </div>
    <div class="search-history">
      <TDateRangePicker
        :class="{ 'history-date-shortcut': shortcutSelectedIndex >= 0 && !historyDateFocused }"
        :range-input-props="historyDateInputProps"
        allow-input
        @focus="historyDateFocused = true"
        @blur="historyDateFocused = false"
        :value="dateRange"
        value-type="Date"
        enable-time-picker
        :clearable="false"
        :presets="nativeDatePresets"
        presets-placement="left"
        need-confirm
        :placeholder="[$t('开始时间'), $t('结束时间')]"
        @change="handleNativeDateChange"
        @confirm="handlePickSuccess"
      />
      <span :title="$t('查看所有的索引集的下载历史')" class="top-start">
        <t-button theme="primary" :disabled="tableLoading || isSearchAll" @click="handleSearchAll">
          {{ $t('查看所有') }}
        </t-button>
      </span>
    </div>
    <BklogLoading :loading="tableLoading" class="table-container">
      <TTable
        row-key="__taskKey"
        class="export-table"
        size="small"
        :data="historyTableRows"
        :columns="historyColumns"
        :pagination="nativePagination"
        @page-change="handleNativePageChange"
      >
        <template #indexSetId="{ row }">
          <span>
            {{ getIndexSetIDs(row) }}
          </span>
        </template>
        <template #request="{ row }">
          <TPopup placement="top">
            <template #content>
              <div>
                <!-- eslint-disable-next-line vue/no-v-html -->
                <div v-html="$xss(getSearchDictHtml(row.search_dict))"></div>
              </div>
            </template>
            <div class="parameter-search">
              <span>{{ getSearchDictStr(row.search_dict) }}</span>
            </div>
          </TPopup>
        </template>
        <template #status="{ row }">
          <TPopup v-if="isShowShape(row.export_status)" placement="top">
            <template #content>
              <div>
                <span v-if="!row.error_msg"> {{ $t('完成时间') }}: {{ getFormatDate(row.export_completed_at) }} </span>
                <span v-else>{{ $t('异常原因') }}: {{ row.error_msg }}</span>
              </div>
            </template>
            <span :class="['status', `status-${row.export_status + ''}`]">
              <i class="bk-icon icon-circle-shape"></i>
              {{ getStatusStr(row.export_status) }}
            </span>
          </TPopup>
          <span v-else :class="['status', `status-${row.export_status + ''}`]">
            <i v-if="isShowProgress(row.export_status)" class="bk-icon icon-refresh"></i>
            {{ getStatusStr(row.export_status) }}
            <span v-if="isShowProgress(row.export_status)" class="progress-text">
              {{ row.progressPercent || 0 }} % ({{ formatNumber(row.exported_count) }} /
              {{ formatNumber(row.export_total_count) }})
            </span>
          </span>
        </template>
        <template #filename="{ row }"
          ><TTooltip :content="row.export_pkg_name || '--'">
            <div class="title-overflow">
              <span>{{ row.export_pkg_name || '--' }}</span>
            </div>
          </TTooltip></template
        >
        <template #filesize="{ row }">
          <span>{{ row.export_pkg_size ? `${row.export_pkg_size}M` : '--' }}</span>
        </template>
        <template #creator="{ row }"
          ><TTooltip :content="row.export_created_by || '--'">
            <div class="title-overflow">
              <span>
                <bk-user-display-name :user-id="row.export_created_by || '--'"></bk-user-display-name>
              </span>
            </div> </TTooltip
        ></template>
        <template #createdAt="{ row }"
          ><TTooltip :content="getFormatDate(row.export_created_at)">
            <div class="title-overflow">
              <span>{{ getFormatDate(row.export_created_at) }}</span>
            </div>
          </TTooltip></template
        >
        <template #operations="{ row }">
          <span v-if="isShowDownload(row)" style="margin-right: 10px">
            <t-button variant="text" theme="primary" v-if="row.download_able" @click="downloadExport(row)">
              {{ $t('下载') }}
            </t-button>
            <span v-else :title="$t('下载链接过期')" class="top-start">
              <t-button variant="text" theme="primary" disabled>
                {{ $t('下载') }}
              </t-button>
            </span>
          </span>
          <span v-if="isShowRetry(row)" style="margin-right: 10px">
            <t-button
              variant="text"
              theme="primary"
              v-if="row.retry_able && row.export_status !== 'success'"
              @click="retryExport(row)"
            >
              {{ $t('重试') }}
            </t-button>
            <span v-else :title="row.export_status === 'success' ? undefined : $t('数据源过期')" class="top-start">
              <t-button variant="text" theme="primary" disabled>
                {{ $t('重试') }}
              </t-button>
            </span>
          </span>
          <t-button variant="text" theme="primary" @click="handleRetrieve(row)">
            {{ $t('检索') }}
          </t-button>
        </template>
      </TTable>
    </BklogLoading>
  </TDialog>
</template>

<script>
import {
  MessagePlugin as TDesignMessage,
  Dialog as TDialog,
  Table as TTable,
  Popup as TPopup,
  DateRangePicker as TDateRangePicker,
  Tooltip as TTooltip,
} from 'tdesign-vue-next';
import BklogLoading from '@/shared/ui/loading';
import { ServicesInstance } from '@/platform/services';

import axios from 'axios';
import { formatDate, blobDownload } from '@/shared/lib/util';
import { mapGetters } from '@/app/state/map-helpers';
import { parseTableIdConditions } from '@/app/state/helper.ts';
import { resolveExportHistoryIndexSetId } from '@/features/retrieval/workbench/sub-bar/union-to-single';

import { axiosInstance } from '@/platform/http/index';
import {
  buildExportRetryRequest,
  EXPORT_SUBMITTED_MESSAGE,
  getExportDownloadFileName,
  submitExportWithSortConfirmation,
  getExportTaskKey,
} from './download/exportTask';
import { calculateProgressPercent, formatNumber } from '@/features/retrieval/workbench/result-comp/download/downloadProgress';
import {
  DOWNLOAD_DATA_DELAY,
  DOWNLOAD_POLLING_INTERVAL,
  DOWNLOAD_RECENT_DAYS,
  MILLISECONDS_PER_DAY,
} from '@/features/retrieval/workbench/result-comp/download/constants';

const HISTORY_PAGE_SIZE = 10;

export default {
  components: { TDialog, TTable, TPopup, TDateRangePicker, TTooltip, BklogLoading },
  emits: ['refresh-current-tasks', 'refreshCurrentTasks', 'handle-close-dialog', 'handleCloseDialog', 'sync-tracked-tasks', 'syncTrackedTasks'],

  props: {
    showHistoryExport: {
      type: Boolean,
      default: false,
    },
    indexSetList: {
      type: Array,
      required: true,
    },
    trackedTasks: {
      type: Object,
      default: () => ({}),
    },
  },
  data() {
    return {
      exportList: [],
      isShowDialog: false,
      tableLoading: false,
      isSearchAll: false, // 是否查看所有索引集下载历史
      dateRange: [], // 日期范围
      historyDateFocused: false,
      historyPollingTimer: null,
      historyCancelExecutor: null,
      pagination: {
        current: 1,
        count: 0,
        limit: HISTORY_PAGE_SIZE,
      },
      shortcutSelectedIndex: 3, // 当前选中的快捷键索引（默认为"最近3月"）
      dateShortcuts: [
        {
          text: this.$t('近{n}天', { n: 7 }),
          value() {
            const end = new Date();
            const start = new Date();
            start.setTime(start.getTime() - 3600 * 1000 * 24 * 7);
            return [start, end];
          },
        },
        {
          text: this.$t('本月'),
          value() {
            const end = new Date();
            const start = new Date();
            start.setDate(1);
            start.setHours(0, 0, 0, 0);
            return [start, end];
          },
        },
        {
          text: this.$t('上月'),
          value() {
            const end = new Date();
            const start = new Date();
            // 上月第一天
            start.setDate(1);
            start.setMonth(start.getMonth() - 1);
            start.setHours(0, 0, 0, 0);
            // 上月最后一天
            end.setDate(0);
            end.setHours(23, 59, 59, 999);
            return [start, end];
          },
        },
        {
          text: this.$t('最近{n}月', { n: 3 }),
          value() {
            const end = new Date();
            const start = new Date();
            start.setTime(start.getTime() - MILLISECONDS_PER_DAY * DOWNLOAD_RECENT_DAYS);
            return [start, end];
          },
        },
      ],
      exportStatusList: {
        download_log: this.$t('拉取中'),
        export_package: this.$t('打包中'),
        export_upload: this.$t('上传中'),
        success: this.$t('完成'),
        failed: this.$t('异常'),
        download_expired: this.$t('下载链接过期'),
        data_expired: this.$t('数据源过期'),
        null: this.$t('未启动'),
      },
      position: {
        top: 120,
      },
      enTableWidth: {
        export_status: '250',
        operate: '220',
      },
      cnTableWidth: {
        export_status: '230',
        operate: '150',
      },
    };
  },
  computed: {
    historyDateInputProps() {
      const label = !this.historyDateFocused && this.dateShortcuts[this.shortcutSelectedIndex]?.text;
      return label ? { inputProps: [{ value: label }, { value: '' }] } : {};
    },
    historyColumns() {
      return [
        { colKey: 'id', title: 'ID', width: 80 },
        ...(this.isSearchAll ? [{ colKey: 'indexSetId', title: this.$t('索引集ID'), width: 100 }] : []),
        { colKey: 'request', title: this.$t('检索请求参数'), width: 180 },
        {
          colKey: 'status',
          title: this.$t('导出状态'),
          width: Number(this.getTableWidth.export_status),
          align: 'center',
        },
        { colKey: 'filename', title: this.$t('文件名'), align: 'center' },
        { colKey: 'filesize', title: this.$t('文件大小'), align: 'center' },
        { colKey: 'creator', title: this.$t('操作者'), align: 'center' },
        { colKey: 'createdAt', title: this.$t('操作时间'), width: 240, align: 'center' },
        { colKey: 'operations', title: this.$t('操作'), width: Number(this.getTableWidth.operate), align: 'center' },
      ];
    },
    historyTableRows() {
      return this.exportList.map((row) => {
        const source = this.trackedTasks[this.getExportTaskKey(row)] || row;
        return { ...source, __taskKey: this.getExportTaskKey(source) };
      });
    },
    nativePagination() {
      return {
        current: this.pagination.current,
        pageSize: this.pagination.limit,
        total: this.pagination.count,
        pageSizeOptions: [10, 20, 50, 100],
      };
    },
    nativeDatePresets() {
      return Object.fromEntries(
        this.dateShortcuts.map((shortcut, index) => [
          shortcut.text,
          () => {
            this.handleShortcutChange({ index });
            return shortcut.value();
          },
        ]),
      );
    },
    bkBizId() {
      return this.$store.state.bkBizId;
    },
    getTableWidth() {
      return this.$store.getters.isEnLanguage ? this.enTableWidth : this.cnTableWidth;
    },
    ...mapGetters({
      unionIndexList: 'unionIndexList',
      isUnionSearch: 'isUnionSearch',
      retrieveParams: 'retrieveParams',
    }),
    isScene() {
      return this.$store.getters.isSceneMode;
    },
    routerIndexSet() {
      return resolveExportHistoryIndexSetId({
        isMonitorComponent: window.__IS_MONITOR_COMPONENT__,
        queryIndexId: this.$route.query.indexId,
        storeIndexId: this.$store.state.indexId,
      });
    },
  },
  watch: {
    showHistoryExport(val) {
      this.isShowDialog = val;
      if (val) {
        this.resetHistoryState();
        this.fetchHistoryList();
        this.startHistoryPolling();
      } else {
        this.resetHistoryState(false);
      }
    },
  },
  beforeDestroy() {
    this.resetHistoryState(false);
  },
  methods: {
    handleNativeDateChange(value, context) {
      this.dateRange = value;
      if (['confirm', 'enter'].includes(context?.trigger)) this.shortcutSelectedIndex = -1;
      if (['preset', 'enter'].includes(context?.trigger)) this.handlePickSuccess();
    },
    handleNativePageChange({ current, pageSize }) {
      if (pageSize !== this.pagination.limit) this.handleLimitChange(pageSize);
      else if (current !== this.pagination.current) this.handlePageChange(current);
    },
    formatNumber,
    getExportTaskKey,
    downloadExport($row) {
      if ($row.engine === 'sharded') {
        if (!$row.download_able) return;
        return this.downloadShardedExport($row);
      }
      // 异步导出使用downloadURL下载
      if ($row.download_url) {
        window.open($row.download_url);
        return;
      }
      return this.openDownloadUrl($row);
    },
    retryExport($row) {
      // 异常任务直接异步下载
      if ($row.engine !== 'sharded' && $row.export_type === 'sync') {
        return this.openDownloadUrl($row);
      }
      return this.downloadAsync($row);
    },
    async downloadShardedExport(row) {
      try {
        const res = await ServicesInstance.retrieve.getExportDownloadLink({
          params: { job_id: row.id },
          query: {
            space_uid: this.$store.getters.spaceUid,
            artifact_id: 'full',
          },
        });
        if (res.result && res.data?.url) {
          window.open(res.data.url);
        }
      } catch (error) {
        if (!axios.isCancel(error)) {
          console.error(error);
        }
      }
    },
    /**
     * @desc: 同步下载
     * @param { Object } params
     */
    openDownloadUrl(params) {
      const request = buildExportRetryRequest({ ...params, export_type: 'sync' });
      return axiosInstance
        .post(request.url, request.config.data, {
          responseType: 'blob',
        })
        .then((res) => {
          blobDownload(res.data, getExportDownloadFileName(params, this.indexSetList));
          return true;
        })
        .catch((error) => {
          console.error(error);
          return false;
        })
        .finally(() => {
          this.refreshAfterDownload();
        });
    },
    /**
     * @desc: 异步下载
     * @param { Object } task 原始导出任务
     */
    downloadAsync(task) {
      const request = buildExportRetryRequest(task);
      return submitExportWithSortConfirmation(this, request.service, request.config)
        .then((res) => {
          if (res?.result) {
            TDesignMessage('success', { content: res.data?.prompt || this.$t(EXPORT_SUBMITTED_MESSAGE) });
            return true;
          }
          return false;
        })
        .catch((error) => {
          console.error(error);
          return false;
        })
        .finally(() => {
          setTimeout(() => {
            this.refreshAfterDownload();
          }, 1000);
        });
    },
    refreshAfterDownload() {
      this.setDefaultDateRange();
      this.fetchHistoryList(true);
      this.$emit('refresh-current-tasks');
    },
    handleSearchAll() {
      if (this.tableLoading || this.isSearchAll) {
        return;
      }
      this.isSearchAll = true;
      this.fetchHistoryList(true);
    },
    /**
     * @desc: 设置默认日期范围（最近3月）
     */
    setDefaultDateRange() {
      const end = new Date();
      const start = new Date();
      start.setTime(start.getTime() - MILLISECONDS_PER_DAY * DOWNLOAD_RECENT_DAYS);
      this.dateRange = [start, end];
      this.shortcutSelectedIndex = 3;
    },
    /**
     * @desc: 日期选择器快捷键变更
     */
    handleShortcutChange(shortcut) {
      this.shortcutSelectedIndex = shortcut.index;
    },
    /**
     * @desc: 日期选择器确认
     */
    handlePickSuccess() {
      this.fetchHistoryList(true);
    },
    getSearchDictStr(searchObj) {
      return JSON.stringify(searchObj);
    },
    getSearchDictHtml(searchObj) {
      const objStr = JSON.stringify(searchObj, null, 4);
      return objStr.replace(/\n/g, '<br>').replace(/\s/g, ' ');
    },
    isShowDownload(row) {
      return ['success', 'download_expired', 'data_expired'].includes(row.export_status);
    },
    isShowRetry(row) {
      return ['failed', 'download_expired', 'data_expired', 'success'].includes(row.export_status);
    },
    isShowShape(status) {
      return ['success', 'failed'].includes(status);
    },
    isShowProgress(status) {
      return ['download_log'].includes(status);
    },
    getStatusStr(status) {
      return this.exportStatusList[status];
    },
    getFormatDate(time) {
      return formatDate(new Date(time).getTime(), true);
    },
    handleRetrieve($row) {
      const { spaceUid } = this.$store.state;
      const { log_index_set_id: indexSetID, search_dict: dict } = $row;
      // 检索数据回填
      const queryParamsStr = {};
      for (const key in dict) {
        switch (key) {
          case 'keyword':
          case 'start_time':
          case 'end_time':
          case 'time_range':
            if (dict[key] !== '') {
              // 不在这里编码，下面 reduce 中会统一编码，避免双重编码
              queryParamsStr[key] = dict[key];
            }
            break;
          case 'ip_chooser':
          case 'addition':
            queryParamsStr[key] = JSON.stringify(dict[key]);
            break;
          default:
            break;
        }
      }

      // 拼接 URL 参数
      const params = Object.keys(queryParamsStr)
        .reduce((output, key) => {
          output.push(`${key}=${encodeURIComponent(queryParamsStr[key])}`);
          return output;
        }, [])
        .join('&');

      // 场景化检索下，search_dict 会附加 table_id_conditions 和 scene_filter_values
      // 单独解析并拼接场景化参数
      let sceneParams = '';
      if (dict.table_id_conditions || dict.scene_filter_values) {
        const { scene_active: sceneActive, scene_filter_values } = parseTableIdConditions(
          dict.table_id_conditions,
          dict.scene_filter_values,
        );
        const sceneParts = [];
        sceneParts.push('retrieve_type=scene');
        if (sceneActive) {
          sceneParts.push(`scene_active=${encodeURIComponent(sceneActive)}`);
        }
        for (const [fieldKey, fieldValue] of Object.entries(scene_filter_values)) {
          const rawValue = fieldValue?.value ?? fieldValue;
          const op = fieldValue?.op;
          if (rawValue !== undefined && rawValue !== null && rawValue !== '') {
            if (Array.isArray(rawValue)) {
              // 数组值展开为多个同 key 参数（与 Vue Router 行为一致）
              rawValue.forEach((v) => sceneParts.push(`${fieldKey}=${encodeURIComponent(v)}`));
            } else {
              sceneParts.push(`${fieldKey}=${encodeURIComponent(rawValue)}`);
            }
            // 操作符参数
            if (op) {
              sceneParts.push(`${fieldKey}[op]=${encodeURIComponent(op)}`);
            }
          }
        }
        sceneParams = sceneParts.join('&');
      }

      const allParams = [params, sceneParams].filter(Boolean).join('&');
      const siteUrl = window.__IS_MONITOR_COMPONENT__ ? window.site_url : window.SITE_URL;
      const jumpUrl = `${siteUrl}#/retrieve/${indexSetID}?spaceUid=${spaceUid}&bizId=${dict.bk_biz_id}&${allParams}`;
      window.open(jumpUrl, '_blank', 'noopener,noreferrer');
    },
    resetHistoryState(resetDateRange = true) {
      this.cancelHistoryRequest();
      this.stopHistoryPolling();
      this.exportList = [];
      this.tableLoading = false;
      this.isSearchAll = false;
      this.pagination = {
        current: 1,
        count: 0,
        limit: HISTORY_PAGE_SIZE,
      };
      this.dateRange = [];
      if (resetDateRange) {
        this.setDefaultDateRange();
      }
    },
    cancelHistoryRequest() {
      if (this.historyCancelExecutor) {
        this.historyCancelExecutor();
        this.historyCancelExecutor = null;
      }
    },
    startHistoryPolling() {
      this.stopHistoryPolling();
      this.historyPollingTimer = setInterval(() => {
        if (this.isShowDialog) {
          this.fetchHistoryList(false, true);
        }
      }, DOWNLOAD_POLLING_INTERVAL);
    },
    stopHistoryPolling() {
      if (this.historyPollingTimer) {
        clearInterval(this.historyPollingTimer);
        this.historyPollingTimer = null;
      }
    },
    createProgressRow(row) {
      return {
        ...row,
        progressPercent: calculateProgressPercent(row.exported_count || 0, row.export_total_count || 0),
      };
    },
    setExportListData(data) {
      const currentRowMap = new Map(this.exportList.map((row) => [getExportTaskKey(row), row]));
      this.exportList = data.map((item) => {
        const currentRow = currentRowMap.get(getExportTaskKey(item));
        const progressRow = this.createProgressRow(item);
        if (!currentRow) {
          return progressRow;
        }
        Object.assign(currentRow, progressRow);
        return currentRow;
      });
    },
    async fetchHistoryList(isReset = false, isPolling = false) {
      if (!this.isShowDialog) {
        return;
      }
      if (isReset) {
        this.pagination.current = 1;
      }
      this.cancelHistoryRequest();
      if (!isPolling) {
        this.tableLoading = true;
      }

      if (this.isUnionSearch && !this.unionIndexList.length) {
        this.exportList = [];
        this.pagination.count = 0;
        this.tableLoading = false;
        return;
      }

      let cancelExecutor;
      const cancelToken = new axios.CancelToken((executor) => {
        cancelExecutor = executor;
      });
      this.historyCancelExecutor = cancelExecutor;
      const { limit, current } = this.pagination;
      const params = {
        bk_biz_id: this.bkBizId,
        page: current,
        pagesize: limit,
        show_all: this.isSearchAll,
        start_time: this.dateRange[0]?.getTime() || null,
        end_time: this.dateRange[1] ? this.dateRange[1].getTime() + DOWNLOAD_DATA_DELAY : null,
      };
      let queryUrl;
      let requestConfig;

      if (this.isScene) {
        queryUrl = ServicesInstance.retrieve.getSceneExportHistory;
        params.space_uid = this.retrieveParams?.space_uid;
        params.table_id_conditions = this.retrieveParams?.table_id_conditions;
        params.scene_filter_values = this.retrieveParams?.scene_filter_values;
        requestConfig = { data: params };
      } else if (this.isUnionSearch) {
        queryUrl = ServicesInstance.unionSearch.unionExportHistory;
        params.index_set_id = this.routerIndexSet;
        params.index_set_ids = this.unionIndexList;
        requestConfig = { params };
      } else {
        queryUrl = ServicesInstance.retrieve.getExportHistoryList;
        params.index_set_id = this.routerIndexSet;
        requestConfig = { params };
      }

      try {
        const res = await queryUrl(requestConfig, { cancelToken });
        if (this.historyCancelExecutor !== cancelExecutor) {
          return;
        }
        if (res.result) {
          this.pagination.count = res.data.total || 0;
          this.setExportListData(res.data.list);
          const trackedTasks = res.data.list.filter((item) => this.trackedTasks[getExportTaskKey(item)]);
          if (trackedTasks.length) {
            this.$emit('sync-tracked-tasks', trackedTasks);
          }
        }
      } catch (error) {
        if (axios.isCancel(error)) {
          return;
        }
      } finally {
        if (this.historyCancelExecutor === cancelExecutor) {
          this.historyCancelExecutor = null;
          this.tableLoading = false;
        }
      }
    },
    handlePageChange(page) {
      this.pagination.current = page;
      this.fetchHistoryList();
    },
    handleLimitChange(size) {
      if (this.pagination.limit !== size) {
        this.pagination.current = 1;
        this.pagination.limit = size;
        this.fetchHistoryList();
      }
    },
    /**
     * @desc: 关闭table弹窗清空数据
     */
    closeDialog() {
      this.resetHistoryState(false);
      this.$emit('handle-close-dialog');
    },
    getIndexSetIDs(row) {
      return row.log_index_set_ids?.length ? row.log_index_set_ids.join(',') : row.log_index_set_id;
    },
  },
};
</script>

<style lang="scss" scoped>
@import '@/shared/styles/mixins/flex.scss';
@import '@/shared/styles/conf';

.table-title {
  font-size: 16px;
  font-weight: 700;
}

.search-history {
  display: flex;
  align-items: center;
  justify-content: space-between;
  width: 100%;
  margin: 10px 0 20px 0;
}

.export-table {
  height: calc(100vh - 380px);
  overflow-y: auto;

  .t-table__content {
    min-height: calc(100vh - 520px);

    .t-table__empty {
      min-height: calc(100vh - 440px);

      @include flex-center;
    }
  }
}

.parameter-search {
  max-width: 170px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  cursor: pointer;
}

.file-name {
  width: 140px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  cursor: pointer;
}

.status {
  cursor: pointer;

  &.status-null i {
    display: inline-block;
    animation: button-icon-loading 1s linear infinite;
  }

  &.status-success i {
    color: $iconSuccessColor;
  }

  &.status-failed i {
    color: $iconFailColor;
  }
}

.progress-text {
  font-size: 12px;
  font-weight: 700;
  color: #3a84ff;
  white-space: nowrap;
}
</style>

<style lang="scss">
.export-history-dialog.t-dialog {
  padding: 24px;
  .t-dialog__header {
    height: 0;
    min-height: 0;
  }
  .t-dialog__body {
    padding: 12px 0 0;
  }
  .history-date-shortcut {
    .t-range-input__inner-right,
    .t-range-input__inner-separator {
      display: none;
    }
  }
  .search-history .t-date-range-picker {
    width: 342px;
  }
  .t-dialog__close {
    top: 12px;
    right: 12px;
  }
  .export-table {
    .t-table__header th {
      height: 43px;
      padding: 0 12px;
      background: #f0f1f5;
    }
    .t-table__body td {
      height: 42px;
      padding: 0 12px;
    }
    .t-table__content > table {
      height: auto;
    }
    .t-button--variant-text {
      height: 24px;
      padding: 0;
      font-size: 12px;
    }
    .t-pagination__total {
      flex: initial;
      margin-right: 8px;
    }
    .t-pagination__select {
      margin-right: auto;
    }
  }
}
</style>
