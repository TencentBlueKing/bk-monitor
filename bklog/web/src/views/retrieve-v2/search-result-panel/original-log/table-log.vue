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
  <div class="bklog-result-list">
    <div
      ref="scrollContainer"
      class="result-table-container"
      data-test-id="retrieve_from_fieldForm"
      @scroll.passive="handleOriginScroll"
    >
      <KeepAlive>
        <template v-if="showOriginal">
          <OriginalList
            :handle-click-tools="handleClickTools"
            :is-page-over="isPageOver"
            :operator-config="indexSetOperatorConfig"
            :origin-table-list="originLogList"
            :retrieve-params="retrieveParams"
            :show-field-alias="showFieldAlias"
            :table-list="tableList"
            :table-loading="isContentLoading"
            :time-field="timeField"
            :total-fields="totalFields"
            :visible-fields="visibleFields"
          ></OriginalList>
        </template>
        <template v-else>
          <TableList
            :handle-click-tools="handleClickTools"
            :is-page-over="isPageOver"
            :operator-config="indexSetOperatorConfig"
            :origin-table-list="originLogList"
            :retrieve-params="retrieveParams"
            :show-field-alias="showFieldAlias"
            :table-list="tableList"
            :table-loading="isContentLoading"
            :time-field="timeField"
            :total-fields="totalFields"
            :visible-fields="visibleFields"
          ></TableList>
        </template>
      </KeepAlive>

      <!-- 表格底部内容 -->
      <p
        v-if="tableList.length === limitCount"
        class="more-desc"
      >
        {{ $t('仅展示检索结果的前2000条，如果要查看更多请优化查询条件') }}
        <a
          href="javascript: void(0);"
          @click="scrollToTop"
          >{{ $t('返回顶部') }}</a
        >
      </p>
    </div>

    <!-- 实时滚动日志/上下文弹窗 -->
    <bk-dialog
      v-model="logDialog.visible"
      :draggable="false"
      :esc-close="false"
      :ext-cls="logDialog.fullscreen ? 'log-dialog log-full-dialog' : 'log-dialog'"
      :fullscreen="logDialog.fullscreen"
      :header-position="logDialog.headerPosition"
      :mask-close="false"
      :show-footer="false"
      :width="logDialog.width"
      @after-leave="hideDialog"
    >
      <real-time-log
        v-if="logDialog.type === 'realTimeLog'"
        :log-params="logDialog.data"
        :target-fields="targetFields"
        :title="logDialog.title"
        @close-dialog="hideDialog"
        @toggle-screen-full="toggleScreenFull"
      />
      <context-log
        v-if="logDialog.type === 'contextLog'"
        :log-params="logDialog.data"
        :retrieve-params="retrieveParams"
        :target-fields="targetFields"
        :title="logDialog.title"
        @close-dialog="hideDialog"
        @toggle-screen-full="toggleScreenFull"
      />
    </bk-dialog>

    <retrieve-loader
      v-if="isPageOver || isContentLoading"
      class="bklog-skeleton-loading"
      :is-loading="false"
      :is-page-over="isPageOver || isContentLoading"
      :max-length="36"
      :static="true"
      :visible-fields="[]"
    >
    </retrieve-loader>
  </div>
</template>

<script>
  import tableRowDeepViewMixin from '@/mixins/table-row-deep-view-mixin';
  import RetrieveLoader from '@/skeleton/retrieve-loader';
  import { mapState } from 'vuex';

  import { bigNumberToString } from '../../../../common/util';
  // #if MONITOR_APP !== 'trace'
  import ContextLog from '../../result-comp/context-log';
  import RealTimeLog from '../../result-comp/real-time-log';
  // #else
  // #code const ContextLog = () => null;
  // #code const RealTimeLog = () => null;
  // #endif
  import OriginalList from './original-list';
  import TableList from './table-list';

  export default {
    components: {
      RealTimeLog,
      ContextLog,
      OriginalList,
      TableList,
      RetrieveLoader,
    },
    mixins: [tableRowDeepViewMixin],
    inheritAttrs: false,
    props: {
      retrieveParams: {
        type: Object,
        required: true,
      },
      tableList: {
        type: Array,
        required: true,
      },
      showOriginal: {
        type: Boolean,
        default: false,
      },
    },
    data() {
      return {
        limitCount: 2000,
        webConsoleLoading: false,
        targetFields: [],
        isPageOver: false,
        newScrollHeight: 0,
        finishPolling: false,
        logDialog: {
          title: '',
          type: '',
          width: '100%',
          visible: false,
          headerPosition: 'left',
          fullscreen: true,
          data: {},
        },
      };
    },
    computed: {
      ...mapState({
        bkBizId: state => state.bkBizId,
        indexFieldInfo: 'indexFieldInfo',
        indexSetQueryResult: 'indexSetQueryResult',
        visibleFields: 'visibleFields',
        indexSetOperatorConfig: 'indexSetOperatorConfig',
        showFieldAlias: 'showFieldAlias',
        indexItem: 'indexItem',
      }),
      ...mapState('globals', ['fieldTypeMap']),
      timeField() {
        return this.indexFieldInfo.time_field;
      },
      totalFields() {
        return this.indexFieldInfo.fields ?? [];
      },
      originLogList() {
        return this.indexSetQueryResult.origin_log_list ?? [];
      },
      isContentLoading() {
        return this.indexSetQueryResult.is_loading;
      },
      isSearchFinish() {
        return this.tableList.length === bigNumberToString(this.indexSetQueryResult.total);
      },
      isSearchError() {
        return this.indexSetQueryResult?.is_error || bigNumberToString(this.indexSetQueryResult.total) === 0;
      },
    },
    watch: {
      'indexItem.begin'(v) {
        if (v === 0) this.finishPolling = false;
      },
    },
    methods: {
      // 滚动到顶部
      scrollToTop() {
        this.$easeScroll(0, 300, this.$refs.scrollContainer);
      },
      handleOriginScroll() {
        const el = this.$refs.scrollContainer;
        if (this.isPageOver || !el.scrollTop || this.isSearchFinish || this.isSearchError) return;
        clearTimeout(this.timer);

        this.timer = setTimeout(() => {
          // this.showScrollTop = el.scrollTop > 550;
          if (el.scrollHeight - el.offsetHeight - el.scrollTop < 20) {
            if (this.totalFields.length === this.limitCount || this.finishPolling) return;
            this.isPageOver = true;
            this.newScrollHeight = el.scrollTop;
            this.$store.dispatch('requestIndexSetQuery', { isPagination: true }).then(res => {
              this.finishPolling = res.data.total < this.indexItem.begin;
              requestAnimationFrame(() => {
                this.isPageOver = false;
                this.$refs.scrollContainer.scrollTop = this.newScrollHeight;
              });
            });
          }
        }, 200);
      },
      // 打开实时日志或上下文弹窗
      openLogDialog(row, type) {
        this.logDialog.data = row;
        this.logDialog.type = type;
        this.logDialog.title = type === 'realTimeLog' ? this.$t('实时滚动日志') : this.$t('上下文');
        this.logDialog.visible = true;
        this.logDialog.fullscreen = true;
      },
      openWebConsole(row) {
        // (('cluster', 'container_id'),
        // ('__ext.io_tencent_bcs_cluster', '__ext.container_id'),
        // ('__ext.bk_bcs_cluster_id', '__ext.container_id')) 不能同时为空
        const { cluster, container_id: containerID, __ext } = row;
        let queryData = {};
        if (cluster && containerID) {
          queryData = {
            cluster_id: encodeURIComponent(cluster),
            container_id: containerID,
          };
        } else {
          if (!__ext) return;
          if (!__ext.container_id) return;
          queryData = { container_id: __ext.container_id };
          if (__ext.io_tencent_bcs_cluster) {
            Object.assign(queryData, {
              cluster_id: encodeURIComponent(__ext.io_tencent_bcs_cluster),
            });
          } else if (__ext.bk_bcs_cluster_id) {
            Object.assign(queryData, {
              cluster_id: encodeURIComponent(__ext.bk_bcs_cluster_id),
            });
          }
        }
        if (!queryData.cluster_id || !queryData.container_id) return;
        this.webConsoleLoading = true;
        this.$http
          .request('retrieve/getWebConsoleUrl', {
            params: {
              index_set_id: window.__IS_MONITOR_COMPONENT__ ? this.$route.query.indexId : this.$route.params.indexId,
            },
            query: queryData,
          })
          .then(res => {
            window.open(res.data);
          })
          .catch(e => {
            console.warn(e);
          })
          .finally(() => {
            this.webConsoleLoading = false;
          });
      },
      handleClickTools(event, row, config) {
        if (['realTimeLog', 'contextLog'].includes(event)) {
          const contextFields = config.contextAndRealtime.extra?.context_fields;
          const dialogNewParams = {};
          Object.assign(dialogNewParams, { dtEventTimeStamp: row.dtEventTimeStamp });
          const { targetFields, sortFields } = config.indexSetValue;
          const fieldParamsKey = [...new Set([...targetFields, ...sortFields])];
          this.targetFields = targetFields ?? [];
          // 非日志采集的情况下判断是否设置过字段设置 设置了的话传已设置过的参数
          if (config.indexSetValue.scenarioID !== 'log' && fieldParamsKey.length) {
            fieldParamsKey.forEach(field => {
              dialogNewParams[field] = this.tableRowDeepView(row, field, '', this.$store.state.isFormatDate, '');
            });
          } else if (Array.isArray(contextFields) && contextFields.length) {
            // 传参配置指定字段
            contextFields.push(this.timeField);
            contextFields.forEach(field => {
              if (field === 'bk_host_id') {
                if (row[field]) dialogNewParams[field] = row[field];
              } else {
                dialogNewParams[field] = this.tableRowDeepView(row, field, '', this.$store.state.isFormatDate, '');
              }
            });
          } else {
            Object.assign(dialogNewParams, row);
          }
          this.openLogDialog(dialogNewParams, event);
        } else if (event === 'webConsole') this.openWebConsole(row);
        else if (event === 'logSource') this.$store.dispatch('changeShowUnionSource');
      },
      // 关闭实时日志或上下文弹窗后的回调
      hideDialog() {
        this.logDialog.type = '';
        this.logDialog.title = '';
        this.logDialog.visible = false;
        this.targetFields = [];
      },
      // 实时日志或上下文弹窗开启或关闭全屏
      toggleScreenFull(isScreenFull) {
        this.logDialog.width = isScreenFull ? '100%' : 1078;
        this.logDialog.fullscreen = isScreenFull;
      },
    },
  };
</script>

<style lang="scss">
  /* stylelint-disable no-descending-specificity */
  .tippy-tooltip.light-theme.bk-table-setting-popover-content-theme {
    padding: 0;
  }

  .bklog-result-list {
    position: relative;
    height: calc(100% - 42px);

    .bklog-skeleton-loading {
      /* stylelint-disable-next-line declaration-no-important */
      position: absolute !important;
      top: 0;
      z-index: 10;
    }

    .result-table-container {
      position: relative;
      height: 100%;
      background: #fff;

      .is-hidden-table-header {
        & .bk-table-header-wrapper,
        .is-right {
          display: none;
        }
      }

      .bklog-origin-list,
      .bklog-table-list {
        td {
          font-family: var(--table-fount-family);
          font-size: var(--table-fount-size);
          color: var(--table-fount-color);
          vertical-align: top;

          &.bk-table-column-expand {
            .bk-table-expand-icon {
              .bk-icon {
                top: 18px;
              }
            }
          }

          &.bklog-result-list-col-index {
            .cell {
              padding: 0;

              div {
                padding: 8px 0;
                line-height: 20px;
              }
            }
          }
        }

        .bk-table-body-wrapper {
          min-height: calc(100vh - 550px);
          color: #313238;

          .bk-table-empty-block {
            display: flex;
            align-items: center;
            justify-content: center;
            min-height: calc(100vh - 600px);
          }
        }

        .cell {
          .operation-button:not(:last-child) {
            padding-right: 8px;
          }
        }

        td mark {
          color: #313238;
          background: #f3e186;
        }

        :deep(.result-table-loading) {
          width: calc(100% - 2px);
          height: calc(100% - 2px);
        }

        .handle-card {
          display: inline-block;
          width: 14px;
          height: 14px;
          margin-left: 10px;

          &:first-child {
            margin-left: 0;
          }
        }

        .time-field {
          padding: 8px 0;
          line-height: 20px;
          white-space: nowrap;
        }

        .hover-row {
          .show-whole-btn {
            background-color: #f5f7fa;
          }
        }

        td.bk-table-expanded-cell {
          padding: 0;
        }

        .bk-table-column-expand .bk-icon {
          top: 21px;
        }

        .bk-table-empty-text {
          width: 100%;
          padding: 0;
        }

        .visiable-field {
          .str-content {
            &.is-limit {
              max-height: 106px;
            }
          }

          .show-whole-btn {
            top: 84px;
          }
        }

        .row-hover {
          background: #fff;
        }

        th .cell {
          /* stylelint-disable-next-line declaration-no-important */
          padding: 0 15px !important;
        }

        &.original-table .bk-table-column-expand .bk-icon {
          top: 21px;
        }

        &.is-hidden-index-column {
          .bklog-result-list-col-index {
            .cell {
              opacity: 0;
            }
          }
        }

        &.is-show-index-column {
          .bklog-result-list-col-index {
            .cell {
              opacity: 1;
              transition: opacity 1s;
            }
          }
        }
      }

      .render-header {
        display: inline;

        .field-type-icon {
          display: inline-flex;
          align-items: center;
          justify-content: center;
          min-width: 16px;
          height: 16px;
          margin: 0 5px 0 0;
          font-size: 12px;
          color: #63656e;
          background: #dcdee5;
          border-radius: 2px;
        }

        .bklog-ext {
          min-width: 22px;
          height: 22px;
          transform: translateX(-3px) scale(0.7);
        }

        .toggle-display {
          position: absolute;
          top: 16px;
          right: 12px;
          display: none;
          color: #c4c6cc;
          cursor: pointer;

          &:hover {
            color: #ea3636;
          }

          &.is-hidden {
            visibility: hidden;
          }
        }

        .timer-formatter {
          transform: translateY(-1px);
        }

        .lack-index-filed {
          padding-bottom: 2px;
          border-bottom: 1px dashed #63656e;
        }
      }

      th .cell:hover {
        .toggle-display {
          display: inline-block;
        }
      }
    }
  }

  // 日志全屏状态下的样式
  .log-full-dialog {
    :deep(.bk-dialog-content) {
      /* stylelint-disable-next-line declaration-no-important */
      margin-bottom: 0 !important;
    }
  }

  .more-desc {
    font-size: 12px;
    color: #979ba5;
    text-align: center;

    a {
      color: #3a84ff;
    }
  }
</style>
