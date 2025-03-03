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
    <div
      v-if="!isUnionSearch"
      :class="{ 'operation-icon': true, 'disabled-icon': !queueStatus }"
      data-test-id="fieldForm_div_exportData"
      @mouseenter="handleShowAlarmPopover"
    >
      <span class="icon bklog-icon bklog-xiazai"></span>
    </div>

    <div v-show="false">
      <div
        ref="downloadTips"
        class="download-box"
      >
        <span @click="exportLog">{{ $t('下载日志') }}</span>
        <span @click="downloadTable">{{ $t('下载历史') }}</span>
      </div>
    </div>

    <export-history
      :index-set-list="indexSetList"
      :show-history-export="showHistoryExport"
      @handle-close-dialog="handleCloseDialog"
    />

    <!-- 导出弹窗提示 -->
    <bk-dialog
      ext-cls="async-export-dialog"
      v-model="isShowExportDialog"
      :mask-close="false"
      :ok-text="$t('下载')"
      :title="$t('日志下载')"
      :width="640"
      header-position="left"
      theme="primary"
      @after-leave="closeExportDialog"
      @confirm="handleClickSubmit"
    >
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
              :name="option.field_name"
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

  import exportHistory from './export-history';
  import { axiosInstance } from '@/api';

  export default {
    components: {
      exportHistory,
    },
    inheritAttrs: false,
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
      };
    },
    computed: {
      ...mapState({
        // totalCount: state => state.searchTotal,
        // queueStatus: state => state.retrieve.isTrendDataLoading
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
        return this.$route.params.indexId;
      },
    },
    beforeUnmount() {
      this.popoverInstance = null;
    },

    methods: {
      handleShowAlarmPopover(e) {
        if (this.popoverInstance || !this.queueStatus) return;
        this.popoverInstance?.hide();
        this.popoverInstance?.destroyed();
        this.popoverInstance = null;
        this.popoverInstance = this.$bkPopover(e.target, {
          content: this.$refs.downloadTips,
          trigger: 'mouseenter',
          placement: 'top',
          theme: 'light',
          offset: '0, -1',
          interactive: true,
          hideOnClick: false,
          extCls: 'download-box',
          arrow: true,
        });
        this.popoverInstance?.show();
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
        const downRequestUrl = `/search/index_set/${this.routerIndexSet}/quick_export/`;
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
            if (res.result) {
              this.$bkMessage({
                theme: 'success',
                message: this.$t('任务提交成功，下载完成将会收到邮件通知。可前往下载历史查看下载状态'),
                ellipsisLine: 2,
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
      openDownloadUrl() {
        const { timezone, ...rest } = this.retrieveParams;
        const params = Object.assign(rest, { begin: 0, bk_biz_id: this.bkBizId });
        let downRequestUrl = `/search/index_set/${this.routerIndexSet}/export/`;
        if (this.isUnionSearch) {
          // 判断是否是联合查询 如果是 则加参数
          downRequestUrl = '/search/index_set/union_search/export/';
          Object.assign(params, { index_set_ids: this.unionIndexList });
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
      downloadAsync() {
        const { timezone, ...rest } = this.retrieveParams;
        const params = Object.assign(rest, { begin: 0, bk_biz_id: this.bkBizId });
        const data = { ...params };
        data.size = this.totalCount;
        data.export_fields = this.submitSelectFiledList;
        data.is_desensitize = this.desensitizeRadioType === 'desensitize';

        this.exportLoading = true;
        this.$http
          .request('retrieve/exportAsync', {
            params: {
              index_set_id: this.routerIndexSet,
            },
            data,
          })
          .then(res => {
            if (res.result) {
              this.$bkMessage({
                theme: 'success',
                ellipsisLine: 2,
                message: this.$t('任务提交成功，下载完成将会收到邮件通知。可前往下载历史查看下载状态'),
              });
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
  @import '@/scss/mixins/flex.scss';

  .operation-icon {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 32px;
    height: 32px;
    margin-left: 10px;
    cursor: pointer;
    border: 1px solid #c4c6cc;
    border-radius: 2px;
    outline: none;
    transition: boder-color 0.2s;

    &:hover {
      border-color: #979ba5;
      transition: boder-color 0.2s;
    }

    &:active {
      border-color: #3a84ff;
      transition: boder-color 0.2s;
    }

    .bklog-icon {
      width: 16px;
      font-size: 16px;
      color: #979ba5;
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
  }

  .download-box {
    display: flex;
    flex-direction: column;
    justify-content: space-evenly;
    min-height: 60px;
    padding: 4px 0;
    font-size: 12px;

    span {
      padding: 2px 6px;
      cursor: pointer;

      &:hover {
        color: #3a84ff;
      }
    }
  }
</style>
