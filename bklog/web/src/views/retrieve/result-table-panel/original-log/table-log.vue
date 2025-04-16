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
    <div
      class="result-table-container"
      data-test-id="retrieve_from_fieldForm"
    >
      <keep-alive>
        <component
          :is="`${showOriginal ? 'OriginalList' : 'TableList'}`"
          v-bind="$attrs"
          v-on="$listeners"
          :handle-click-tools="handleClickTools"
          :retrieve-params="retrieveParams"
          :table-list="tableList"
        ></component>
      </keep-alive>

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
  </div>
</template>

<script>
  import tableRowDeepViewMixin from '@/mixins/table-row-deep-view-mixin';
  import { mapState } from 'vuex';

  import ContextLog from '../../result-comp/context-log';
  import RealTimeLog from '../../result-comp/real-time-log';
  import OriginalList from './original-list';
  import TableList from './table-list';

  export default {
    components: {
      RealTimeLog,
      ContextLog,
      OriginalList,
      TableList,
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
      }),
      ...mapState('globals', ['fieldTypeMap']),
    },
    inject: ['changeShowUnionSource'],
    methods: {
      // 滚动到顶部
      scrollToTop() {
        this.$easeScroll(0, 300, this.$parent.$parent.$parent.$refs.scrollContainer);
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
              index_set_id: this.$route.params.indexId,
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
            contextFields.push(config.timeField);
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
        else if (event === 'logSource') this.changeShowUnionSource();
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

  .result-table-container {
    position: relative;
    background: #fff;

    .is-hidden-table-header {
      & .bk-table-header-wrapper,
      .is-right {
        display: none;
      }
    }

    .king-table {
      margin-top: 12px;

      td {
        vertical-align: top;
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

      .icon-handle {
        font-size: 14px;
        color: #979ba5;
        cursor: pointer;

        &:hover {
          color: #3a84ff;
        }
      }

      .time-field {
        font-family: var(--table-fount-family);
        font-size: var(--table-fount-size);
        font-weight: 700;
        color: var(--table-fount-color);
        white-space: nowrap;
      }

      .original-str,
      .visiable-field {
        .str-content {
          position: relative;
          line-height: 20px;

          &.is-limit {
            max-height: 106px;
          }
        }

        &.is-wrap {
          .str-content {
            display: block;
            overflow: hidden;
          }
        }

        .origin-str {
          line-height: 20px;
          color: #313238;
        }

        .show-whole-btn {
          position: absolute;
          top: 82px;
          width: 100%;
          height: 24px;
          font-size: 12px;
          color: #3a84ff;
          cursor: pointer;
          background: #fff;
          transition: background-color 0.25s ease;
        }

        .hide-whole-btn {
          margin-top: -2px;
          line-height: 14px;
          color: #3a84ff;
          cursor: pointer;
        }
      }

      .original-time {
        padding-top: 12px;

        .cell {
          padding-left: 2px;
        }
      }

      .hover-row {
        .show-whole-btn {
          background-color: #f5f7fa;
        }
      }

      .original-str {
        .hide-whole-btn {
          margin-top: 4px;
        }

        .cell {
          padding: 10px 14px 0 2px;
        }

        &.is-wrap .cell {
          padding: 10px 14px 8px 2px;
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

        .cell {
          padding: 12px 14px 0 14px;
        }

        &.is-wrap .cell {
          padding: 12px 14px 8px;
        }

        .show-whole-btn {
          top: 82px;
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
        top: 19px;
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
