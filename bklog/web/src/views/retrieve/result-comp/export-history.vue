<!--
  - Tencent is pleased to support the open source community by making BK-LOG 蓝鲸日志平台 available.
  - Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
  - BK-LOG 蓝鲸日志平台 is licensed under the MIT License.
  -
  - License for BK-LOG 蓝鲸日志平台:
  - -------------------------------------------------------------------
  -
  - Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated
  - documentation files (the "Software"), to deal in the Software without restriction, including without limitation
  - the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software,
  - and to permit persons to whom the Software is furnished to do so, subject to the following conditions:
  - The above copyright notice and this permission notice shall be included in all copies or substantial
  - portions of the Software.
  -
  - THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT
  - LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN
  - NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY,
  - WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE
  - SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE
  -->

<template>
  <bk-dialog
    v-model="isShowDialog"
    theme="primary"
    width="80%"
    render-directive="if"
    :position="position"
    :show-footer="false"
    :mask-close="false"
    :draggable="false"
    :scrollable="true"
    @cancel="closeDialog"
  >
    <div class="table-title">
      {{ $t('下载历史') }}
    </div>
    <div class="search-history">
      <span
        v-bk-tooltips="$t('查看所有的索引集的下载历史')"
        class="top-start"
      >
        <bk-button
          theme="primary"
          @click="handleSearchAll"
        >
          {{ $t('查看所有') }}</bk-button
        >
      </span>
    </div>
    <div
      v-bkloading="{ isLoading: tableLoading }"
      class="table-container"
    >
      <bk-table
        class="export-table"
        :data="exportList"
        :pagination="pagination"
        :outer-border="false"
        @page-change="handlePageChange"
        @page-limit-change="handleLimitChange"
      >
        <!-- ID -->
        <bk-table-column
          label="ID"
          prop="id"
          width="80"
        ></bk-table-column>
        <!-- index_set_id -->
        <template v-if="isShowSetLabel">
          <bk-table-column
            :label="$t('索引集ID')"
            width="100"
          >
            <template slot-scope="{ row }">
              <span>
                {{ getIndexSetIDs(row) }}
              </span>
            </template>
          </bk-table-column>
        </template>
        <!-- 检测请求参数 -->
        <bk-table-column
          :label="$t('检索请求参数')"
          width="180"
        >
          <template slot-scope="{ row }">
            <bk-popover
              placement="top"
              theme="light"
            >
              <div slot="content">
                <!-- eslint-disable-next-line vue/no-v-html -->
                <div v-html="getSearchDictHtml(row.search_dict)"></div>
              </div>
              <div class="parameter-search">
                <span>{{ getSearchDictStr(row.search_dict) }}</span>
              </div>
            </bk-popover>
          </template>
        </bk-table-column>
        <!-- 下载类型 -->
        <bk-table-column
          :label="$t('下载类型')"
          align="center"
          header-align="center"
        >
          <template slot-scope="{ row }">
            <div
              v-bk-overflow-tips
              class="title-overflow"
            >
              <span>{{ row.export_type === 'async' ? $t('异步') : $t('同步') }}</span>
            </div>
          </template>
        </bk-table-column>
        <!-- 导出状态 -->
        <bk-table-column
          :label="$t('导出状态')"
          :width="getTableWidth.export_status"
          align="center"
          header-align="center"
        >
          <template slot-scope="{ row }">
            <bk-popover
              v-if="isShowShape(row.export_status)"
              placement="top"
              theme="light"
            >
              <div slot="content">
                <span v-if="!row.error_msg"> {{ $t('完成时间') }}: {{ getFormatDate(row.export_completed_at) }} </span>
                <span v-else>{{ $t('异常原因') }}: {{ row.error_msg }}</span>
              </div>
              <span :class="['status', `status-${row.export_status + ''}`]">
                <i class="bk-icon icon-circle-shape"></i>
                {{ getStatusStr(row.export_status) }}
              </span>
            </bk-popover>
            <span
              v-else
              :class="['status', `status-${row.export_status + ''}`]"
            >
              <i
                v-if="row.export_status === null"
                class="bk-icon icon-refresh"
              ></i>
              {{ getStatusStr(row.export_status) }}
            </span>
          </template>
        </bk-table-column>
        <!-- 文件名 -->
        <bk-table-column
          :label="$t('文件名')"
          align="center"
          header-align="center"
        >
          <template slot-scope="{ row }">
            <div
              v-bk-overflow-tips
              class="title-overflow"
            >
              <span>{{ row.export_pkg_name || '--' }}</span>
            </div>
          </template>
        </bk-table-column>
        <!-- 文件大小 -->
        <bk-table-column
          :label="$t('文件大小')"
          align="center"
          header-align="center"
        >
          <template slot-scope="{ row }">
            <span>{{ row.export_pkg_size ? `${row.export_pkg_size}M` : '--' }}</span>
          </template>
        </bk-table-column>
        <!-- 操作者 -->
        <bk-table-column
          :label="$t('操作者')"
          align="center"
          header-align="center"
        >
          <template slot-scope="{ row }">
            <div
              v-bk-overflow-tips
              class="title-overflow"
            >
              <span>{{ row.export_created_by || '--' }}</span>
            </div>
          </template>
        </bk-table-column>
        <!-- 操作时间 -->
        <bk-table-column
          :label="$t('操作时间')"
          width="150"
          align="center"
          header-align="center"
        >
          <template slot-scope="{ row }">
            <div
              v-bk-overflow-tips
              class="title-overflow"
            >
              <span>{{ getFormatDate(row.export_created_at) }}</span>
            </div>
          </template>
        </bk-table-column>
        <!-- 操作 -->
        <bk-table-column
          :label="$t('操作')"
          :width="getTableWidth.operate"
          align="center"
          header-align="center"
        >
          <template slot-scope="{ row }">
            <span
              v-if="isShowDownload(row)"
              style="margin-right: 10px"
            >
              <bk-button
                v-if="row.download_able"
                text
                @click="downloadExport(row)"
              >
                {{ $t('下载') }}
              </bk-button>
              <span
                v-else
                v-bk-tooltips="$t('下载链接过期')"
                class="top-start"
              >
                <bk-button
                  text
                  disabled
                >
                  {{ $t('下载') }}
                </bk-button>
              </span>
            </span>
            <span
              v-if="isShowRetry(row)"
              style="margin-right: 10px"
            >
              <bk-button
                v-if="row.retry_able && row.export_status !== 'success'"
                text
                @click="retryExport(row)"
              >
                {{ $t('重试') }}
              </bk-button>
              <span
                v-else
                v-bk-tooltips="{
                  content: $t('数据源过期'),
                  disabled: row.export_status === 'success'
                }"
                class="top-start"
              >
                <bk-button
                  text
                  disabled
                >
                  {{ $t('重试') }}
                </bk-button>
              </span>
            </span>
            <bk-button
              text
              @click="handleRetrieve(row)"
            >
              {{ $t('检索') }}
            </bk-button>
          </template>
        </bk-table-column>
      </bk-table>
    </div>
  </bk-dialog>
</template>

<script>
import { formatDate, blobDownload } from '@/common/util';
import { axiosInstance } from '@/api';
import { mapGetters } from 'vuex';

export default {
  props: {
    showHistoryExport: {
      type: Boolean,
      default: false
    },
    indexSetList: {
      type: Array,
      required: true
    }
  },
  data() {
    return {
      exportList: [],
      isShowDialog: false,
      tableLoading: false,
      isSearchAll: false, // 是否查看所有索引集下载历史
      isShowSetLabel: false, // 是否展示索引集ID
      timer: false,
      exportStatusList: {
        download_log: this.$t('拉取中'),
        export_package: this.$t('打包中'),
        export_upload: this.$t('上传中'),
        success: this.$t('完成'),
        failed: this.$t('异常'),
        download_expired: this.$t('下载链接过期'),
        data_expired: this.$t('数据源过期'),
        null: this.$t('下载中')
      },
      pagination: {
        current: 1,
        count: 0,
        limit: 10
      },
      position: {
        top: 120
      },
      enTableWidth: {
        export_status: '190',
        operate: '220'
      },
      cnTableWidth: {
        export_status: '170',
        operate: '150'
      }
    };
  },
  computed: {
    bkBizId() {
      return this.$store.state.bkBizId;
    },
    getTableWidth() {
      return this.$store.getters.isEnLanguage ? this.enTableWidth : this.cnTableWidth;
    },
    ...mapGetters({
      unionIndexList: 'unionIndexList',
      isUnionSearch: 'isUnionSearch'
    })
  },
  watch: {
    showHistoryExport(val) {
      this.isShowDialog = val;
      if (val) {
        this.getTableList();
        this.startStatusPolling();
      }
    }
  },
  methods: {
    downloadExport($row) {
      // 异步导出使用downloadURL下载
      if ($row.download_url) {
        window.open($row.download_url);
        return;
      }
      this.openDownloadUrl($row.search_dict);
      this.startStatusPolling();
    },
    retryExport($row) {
      // 异常任务直接异步下载
      if ($row.export_type === 'sync') {
        this.openDownloadUrl($row.search_dict);
      } else {
        this.downloadAsync($row.search_dict);
      }
      this.startStatusPolling();
    },
    /**
     * @desc: 同步下载
     * @param { Object } params
     */
    openDownloadUrl(params) {
      const data = { ...params };
      const stringParamsIndexSetID = String(params.log_index_set_id);
      axiosInstance
        .post(`/search/index_set/${stringParamsIndexSetID}/export/`, data)
        .then(res => {
          if (Object.prototype.hasOwnProperty.call(res, 'result') && !res.result) {
            this.$bkMessage({
              theme: 'error',
              message: this.$t('导出失败')
            });
            return;
          }
          const lightName = this.indexSetList.find(item => item.index_set_id === stringParamsIndexSetID)?.lightenName;
          const downloadName = lightName
            ? `bk_log_search_${lightName.substring(2, lightName.length - 1)}.txt`
            : 'bk_log_search.txt';
          blobDownload(res, downloadName);
        })
        .catch(() => {})
        .finally(() => {
          this.getTableList(true);
        });
    },
    /**
     * @desc: 异步下载
     * @param { Object } data
     */
    downloadAsync(data) {
      this.tableLoading = true;
      this.$http
        .request('retrieve/exportAsync', {
          params: {
            index_set_id: this.$route.params.indexId
          },
          data
        })
        .then(res => {
          if (res.result) {
            this.$bkMessage({
              theme: 'success',
              message: res.data.prompt
            });
          }
        })
        .finally(() => {
          setTimeout(() => {
            this.getTableList(true);
          }, 1000);
        });
    },
    handleSearchAll() {
      if (this.tableLoading) {
        return;
      }
      this.isSearchAll = true;
      this.getTableList();
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
    getStatusStr(status) {
      return this.exportStatusList[status];
    },
    getFormatDate(time) {
      return formatDate(new Date(time).getTime());
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
              queryParamsStr[key] = encodeURIComponent(dict[key]);
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
      const params = encodeURIComponent(JSON.stringify(queryParamsStr));
      const jumpUrl = `${window.SITE_URL}#/retrieve/${indexSetID}?spaceUid=${spaceUid}&bizId=${dict.bk_biz_id}&routeParams=${params}`;
      window.open(jumpUrl, '_blank');
    },
    /**
     * @desc: 轮询
     */
    startStatusPolling() {
      this.stopStatusPolling();
      this.timer = setInterval(() => {
        this.getTableList(false, true);
      }, 10000);
    },
    stopStatusPolling() {
      clearTimeout(this.timer);
    },
    /**
     * @desc: 导出状态轮询
     * @param { Array } data 数据
     * @param { Boolean } isPolling 该次请求是否是轮询
     */
    setExportListData(data, isPolling) {
      if (isPolling) {
        data.forEach(item => {
          this.exportList.forEach(row => {
            if (row.id === item.id) {
              Object.assign(row, { ...item });
            }
          });
        });
      } else {
        this.exportList = data;
        this.startStatusPolling();
      }
    },
    /**
     * @desc: 获取table列表数据
     * @param { Boolean } isReset 是否从1页开始查询
     * @param { Boolean } isPolling 该次请求是否是轮询
     */
    getTableList(isReset = false, isPolling = false) {
      isReset && (this.pagination.current = 1);
      !isPolling && (this.tableLoading = true);
      const { limit, current } = this.pagination;
      const queryUrl = this.isUnionSearch ? 'unionSearch/unionExportHistory' : 'retrieve/getExportHistoryList';
      const params = {
        index_set_id: this.$route.params.indexId,
        bk_biz_id: this.bkBizId,
        page: current,
        pagesize: limit,
        show_all: this.isSearchAll
      };
      if (this.isUnionSearch) {
        Object.assign(params, { index_set_ids: this.unionIndexList });
      }
      this.$http
        .request(queryUrl, {
          params
        })
        .then(res => {
          if (res.result) {
            this.pagination.count = res.data.total;
            this.setExportListData(res.data.list, isPolling);
          }
          // 查询所有索引集时才显示索引集IDLabel
          if (this.isSearchAll) {
            this.isShowSetLabel = true;
          }
        })
        .finally(() => {
          this.tableLoading = false;
        });
    },
    handlePageChange(page) {
      this.pagination.current = page;
      this.getTableList();
    },
    handleLimitChange(size) {
      if (this.pagination.limit !== size) {
        this.pagination.current = 1;
        this.pagination.limit = size;
        this.getTableList();
      }
    },
    /**
     * @desc: 关闭table弹窗清空数据
     */
    closeDialog() {
      this.isSearchAll = false;
      this.isShowSetLabel = false;
      this.exportList = [];
      this.pagination = {
        current: 1,
        count: 0,
        limit: 10
      };
      this.stopStatusPolling();
      this.$emit('handleCloseDialog');
    },
    getIndexSetIDs(row) {
      return row.log_index_set_ids?.length ? row.log_index_set_ids.join(',') : row.log_index_set_id;
    }
  }
};
</script>

<style lang="scss" scoped>
@import '@/scss/mixins/flex.scss';
@import '@/scss/conf';

.table-title {
  font-size: 16px;
  font-weight: 700;
}

.search-history {
  width: 100%;
  margin: 10px 0 20px 0;
  text-align: right;
}

.export-table {
  height: calc(100vh - 380px);
  overflow-y: auto;

  .bk-table-body-wrapper {
    min-height: calc(100vh - 520px);

    .bk-table-empty-block {
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
</style>
