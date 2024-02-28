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
  <div>
    <!-- <div
      :class="{ 'operation-icon': true, 'disabled-icon': !queueStatus }"
      @click="exportLog"
      data-test-id="fieldForm_div_exportData"
      v-bk-tooltips="queueStatus ? $t('导出') : undefined">
      <span class="icon log-icon icon-xiazai"></span>
    </div> -->
    <div
      :class="{ 'operation-icon': true, 'disabled-icon': !queueStatus }"
      data-test-id="fieldForm_div_exportData"
      @mouseenter="handleShowAlarmPopover">
      <span class="icon log-icon icon-xiazai"></span>
    </div>

    <div v-show="false">
      <div class="download-box" ref="downloadTips">
        <span @click="exportLog">{{$t('下载日志')}}</span>
        <span @click="downloadTable">{{$t('下载历史')}}</span>
      </div>
    </div>

    <export-history
      :index-set-list="indexSetList"
      :show-history-export="showHistoryExport"
      @handleCloseDialog="handleCloseDialog" />

    <!-- 导出弹窗提示 -->
    <bk-dialog
      v-model="isShowExportDialog"
      theme="primary"
      header-position="left"
      ext-cls="async-export-dialog"
      :width="getDialogWidth"
      :title="getDialogTitle"
      :mask-close="false"
      :ok-text="$t('下载')"
      :show-footer="!isShowAsyncDownload"
      @confirm="handleClickSubmit"
      @after-leave="closeExportDialog">
      <div class="export-container" v-bkloading="{ isLoading: exportLoading }">
        <template v-if="isShowAsyncDownload">
          <span class="bk-icon bk-dialog-warning icon-exclamation"></span>
          <div class="header">{{ getExportTitle }}</div>
        </template>
        <div class="filed-select-box">
          <span class="middle-title">{{$t('下载范围')}}</span>
          <bk-radio-group class="filed-radio-box" v-model="selectFiledType">
            <bk-radio v-for="[key, val] in Object.entries(radioMap)" :key="key" :value="key">{{val}}</bk-radio>
          </bk-radio-group>
          <bk-select
            v-if="selectFiledType === 'specify'"
            v-model="selectFiledList"
            searchable
            display-tag
            multiple
            :placeholder="$t('未选择则默认为全部字段')">
            <bk-option
              v-for="option in totalFields"
              :key="option.field_name"
              :id="option.field_name"
              :name="option.field_name">
            </bk-option>
          </bk-select>
          <!-- <div v-if="asyncExportUsable && isShowAsyncDownload" class="style-line"></div> -->
        </div>
        <!-- v-if="isShowMaskingTemplate" -->
        <div v-if="false" class="desensitize-select-box">
          <span class="middle-title">{{$t('日志类型')}}</span>
          <bk-radio-group class="desensitize-radio-box" v-model="desensitizeRadioType">
            <bk-radio v-for="[key, val] in Object.entries(logTypeMap)" :key="key" :value="key">{{val}}</bk-radio>
          </bk-radio-group>
        </div>
        <div v-if="asyncExportUsable && isShowAsyncDownload" class="style-line"></div>
        <template v-if="!asyncExportUsable">
          <span>{{$t('当前因{n}导致无法进行异步下载， 可直接下载前1万条数据', { n: asyncExportUsableReason })}}</span>
          <div class="cannot-async-btn">
            <bk-button theme="primary" @click="openDownloadUrl">{{ $t('直接下载') }}</bk-button>
            <bk-button style="margin-left: 10px;" @click="() => isShowExportDialog = false">{{ $t('取消') }}</bk-button>
          </div>
        </template>
        <template v-if="asyncExportUsable && isShowAsyncDownload">
          <div class="export-type immediate-export">
            <span class="bk-icon icon-info-circle"></span>
            <span class="export-text">{{ $t('直接下载仅下载前1万条数据') }}</span>
            <bk-button theme="primary" @click="openDownloadUrl">{{ $t('直接下载') }}</bk-button>
          </div>
          <div class="export-type async-export">
            <span class="bk-icon icon-info-circle"></span>
            <span class="export-text">{{ getAsyncText }}</span>
            <bk-button @click="downloadAsync">{{ $t('异步下载') }}</bk-button>
          </div>
        </template>
      </div>
    </bk-dialog>
  </div>
</template>

<script>
import { mapGetters } from 'vuex';
import exportHistory from './export-history';
import { axiosInstance } from '@/api';
import { blobDownload } from '@/common/util';

export default {
  components: {
    exportHistory,
  },
  props: {
    retrieveParams: {
      type: Object,
      required: true,
    },
    totalCount: {
      type: Number,
      default: 0,
    },
    visibleFields: {
      type: Array,
      require: true,
    },
    queueStatus: {
      type: Boolean,
      default: true,
    },
    asyncExportUsable: {
      type: Boolean,
      default: true,
    },
    asyncExportUsableReason: {
      type: String,
      default: '',
    },
    totalFields: {
      type: Array,
      require: true,
    },
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
      logTypeMap: {
        desensitize: this.$t('脱敏'),
        // origin: this.$t('原始'),
      },
    };
  },
  computed: {
    ...mapGetters({
      bkBizId: 'bkBizId',
      spaceUid: 'spaceUid',
      isShowMaskingTemplate: 'isShowMaskingTemplate',
    }),
    getAsyncText() { // 异步下载按钮前的文案
      return this.totalCount > this.exportSecondComparedSize
        ? this.$t('建议缩小查询范围，异步下载只能下载前200w条，注意查看邮件')
        : this.$t('异步下载可打包下载所有数据，请注意查收下载通知邮件');
    },
    getExportTitle() { // 超过下载临界值，当前数据超过多少条文案
      return this.$t('当前数据超过{n}万条', { n: this.totalCount > this.exportSecondComparedSize ? 200 : 1 });
    },
    getDialogTitle() { // 异步下载临界值，dialog标题
      return this.totalCount < this.exportFirstComparedSize ? this.$t('日志下载') : '';
    },
    isShowAsyncDownload() { // 是否展示异步下载
      return this.totalCount > this.exportFirstComparedSize;
    },
    submitSelectFiledList() { // 下载时提交的字段
      if (this.selectFiledType === 'specify') return this.selectFiledList;
      if (this.selectFiledType === 'show') return this.visibleFields.map(item => item.field_name);
      return [];
    },
    getDialogWidth() {
      return this.$store.getters.isEnLanguage ? '470' : '440';
    },
    routerIndexSet() {
      return this.$route.params.indexId;
    },
  },
  beforeDestroy() {
    this.popoverInstance = null;
  },
  methods: {
    handleShowAlarmPopover(e) {
      if (this.popoverInstance || !this.queueStatus) return;

      this.popoverInstance = this.$bkPopover(e.target, {
        content: this.$refs.downloadTips,
        trigger: 'mouseenter',
        placement: 'top',
        theme: 'light',
        offset: '0, -1',
        interactive: true,
        hideOnClick: false,
        arrow: true,
      });
      this.popoverInstance && this.popoverInstance.show();
    },
    exportLog() {
      if (!this.queueStatus) return;
      this.popoverInstance.hide(0);
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
    handleClickSubmit() {
      this.openDownloadUrl();
      this.isShowExportDialog = false;
    },
    openDownloadUrl() {
      const { timezone, ...rest } = this.retrieveParams;
      const params = Object.assign(rest, { begin: 0, bk_biz_id: this.bkBizId });
      const data = {
        ...params,
        size: this.totalCount,
        time_range: 'customized',
        export_fields: this.submitSelectFiledList,
        is_desensitize: this.desensitizeRadioType === 'desensitize',
      };
      axiosInstance.post(`/search/index_set/${this.routerIndexSet}/export/`, data)
        .then((res) => {
          if (Object.prototype.hasOwnProperty.call(res, 'result') && !res.result) {
            this.$bkMessage({
              theme: 'error',
              message: this.$t('导出失败'),
            });
            return;
          };
          const lightName = this.indexSetList.find(item => item.index_set_id === this.routerIndexSet)?.lightenName;
          const downloadName = lightName ? `bk_log_search_${lightName.substring(2, lightName.length - 1)}.txt` : 'bk_log_search.txt';
          blobDownload(res, downloadName);
        })
        .catch(() => {})
        .finally(() => {
          this.isShowExportDialog = false;
          this.selectFiledList = [];
        });
    },
    downloadAsync() {
      const { timezone, ...rest } = this.retrieveParams;
      const params = Object.assign(rest, { begin: 0, bk_biz_id: this.bkBizId });
      const data = { ...params };
      data.size = this.totalCount;
      data.export_fields = this.submitSelectFiledList;
      data.is_desensitize = this.desensitizeRadioType === 'desensitize';

      this.exportLoading = true;
      this.$http.request('retrieve/exportAsync', {
        params: {
          index_set_id: this.routerIndexSet,
        },
        data,
      }).then((res) => {
        if (res.result) {
          this.$bkMessage({
            theme: 'success',
            message: res.data.prompt,
          });
        }
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
    },
    downloadTable() {
      this.showHistoryExport = true;
      this.popoverInstance.hide(0);
    },
    handleCloseDialog() {
      this.showHistoryExport = false;
    },
  },
};
</script>

<style lang="scss" scoped>
  .operation-icon {
    display: flex;
    justify-content: center;
    align-items: center;
    width: 32px;
    height: 32px;
    margin-left: 10px;
    cursor: pointer;
    border: 1px solid #c4c6cc;
    transition: boder-color .2s;
    border-radius: 2px;
    outline: none;

    &:hover {
      border-color: #979ba5;
      transition: boder-color .2s;
    }

    &:active {
      border-color: #3a84ff;
      transition: boder-color .2s;
    }

    .log-icon {
      width: 16px;
      font-size: 16px;
      color: #979ba5;
    }
  }

  .cannot-async-btn {
    display: flex;
    justify-content: center;
    align-items: center;
    margin-top: 10px;
  }

  .disabled-icon {
    background-color: #fff;
    border-color: #dcdee5;
    cursor: not-allowed;

    &:hover,
    .log-icon {
      border-color: #dcdee5;
      color: #c4c6cc;
    }
  }

  :deep(.bk-dialog-header-inner) {
    /* stylelint-disable-next-line declaration-no-important */
    color: #000 !important;
  }

  .filed-select-box {
    text-align: left;
    margin-bottom: 10px;
    font-size: 12px;

    .filed-radio-box {
      margin: 8px 0 10px 0;

      .bk-form-radio {
        margin-right: 24px;
      }
    }
  }

  .style-line {
    width: 100%;
    height: 1px;
    margin: 25px 0 35px 0;
    border-top: 1px solid #c4c6cc;
  }

  .desensitize-select-box {
    text-align: left;
    margin: 18px 0 10px 0;
    font-size: 12px;

    .desensitize-radio-box {
      margin-top: 8px;

      .bk-form-radio {
        margin-right: 24px;
      }
    }
  }

  .middle-title {
    &::after {
      content: '*';
      display: inline-block;
      transform: translateX(2px) translateY(2px);
      color: #ea3636;
    }
  }

  :deep(.bk-radio-text) {
    /* stylelint-disable-next-line declaration-no-important */
    font-size: 12px !important;
  }

  .async-export-dialog {
    .header {
      text-align: center;

      /* stylelint-disable-next-line declaration-no-important */
      padding: 18px 0px 16px !important;
    }

    .export-container {
      text-align: center;
    }

    .bk-dialog-warning {
      display: block;
      margin: 0 auto;
      width: 58px;
      height: 58px;
      line-height: 58px;
      font-size: 30px;
      color: #ff9c01;
      border-radius: 50%;
      background-color: #ffe8c3;
    }

    .header {
      padding: 18px 24px 32px;
      display: inline-block;
      width: 100%;
      font-size: 24px;
      color: #313238;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
      line-height: 1.5;
      margin: 0;
    }

    .export-type {
      margin-bottom: 24px;
      padding: 0 22px;
      display: flex;
      align-items: start;

      .export-text {
        margin-left: 8px;
        max-width: 184px;
        text-align: left;
        font-size: 12px;
        color: #63656e;
        line-height: 18px;
      }

      .bk-button {
        margin-left: auto;
        min-width: auto;
      }

      .bk-icon {
        margin-top: 2px;
      }
    }
  }

  .download-box {
    display: flex;
    font-size: 12px;
    flex-direction: column;
    justify-content: space-evenly;
    min-height: 60px;

    span {
      cursor: pointer;

      &:hover {
        color: #3a84ff;
      }
    }
  }
</style>
