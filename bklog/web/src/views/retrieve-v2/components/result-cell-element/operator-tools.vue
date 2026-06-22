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
  <div :class="{ 'handle-content': true, 'fix-content': showAllHandle, 'origin-content': logType === 'origin' }">
    <template v-if="!isUnionSearch">
      <span
        class="handle-card"
        v-bk-tooltips="{ allowHtml: true, content: '#realTimeLog-html', delay: 500 }"
      >
        <span
          :class="`icon bklog-icon bklog-shishirizhi ${!isActiveLog && 'is-disable'}`"
          @click.stop="handleCheckClick('realTimeLog', isActiveLog)"
          @mouseup.stop
        >
        </span>
      </span>
      <span
        class="handle-card"
        v-bk-tooltips="{ allowHtml: true, content: '#contextLog-html', delay: 500 }"
      >
        <span
          :class="`icon bklog-icon bklog-shangxiawen ${!isActiveLog && 'is-disable'}`"
          @click.stop="handleCheckClick('contextLog', isActiveLog)"
          @mouseup.stop
        >
        </span>
      </span>
      <span
        class="handle-card"
        v-bk-tooltips="{ allowHtml: false, content: $t('全量'), delay: 500 }"
      >
        <span
          class="full-row-action"
          @click.stop="handleCheckClick('fullRow', true)"
          @mouseup.stop
        >{{ $t('全') }}</span>
      </span>
      <span
        v-if="isActiveWebConsole && !isMonitorApm"
        class="handle-card"
        v-bk-tooltips="{ allowHtml: true, content: '#webConsole-html', delay: 500 }"
      >
        <span
          :class="`icon bklog-icon bklog-consola ${!isCanClickWebConsole && 'is-disable'}`"
          @click.stop="handleCheckClick('webConsole', isCanClickWebConsole)"
          @mouseup.stop
        ></span>
      </span>
      <div v-show="false">
        <div id="realTimeLog-html">
          <span>
            <span
              v-if="!isActiveLog"
              class="bk-icon icon-exclamation-circle-shape"
            ></span>
            <span>{{ toolMessage.realTimeLog }}</span>
          </span>
        </div>
      </div>
      <div v-show="false">
        <div id="webConsole-html">
          <span>
            <span
              v-if="!isCanClickWebConsole"
              class="bk-icon icon-exclamation-circle-shape"
            ></span>
            <span>{{ toolMessage.webConsole }}</span>
          </span>
        </div>
      </div>
      <div v-show="false">
        <div id="contextLog-html">
          <span>
            <span
              v-if="!isActiveLog"
              class="bk-icon icon-exclamation-circle-shape"
            ></span>
            <span>{{ toolMessage.contextLog }}</span>
          </span>
        </div>
      </div>
    </template>
    <template v-else>
      <span
        class="handle-card"
        v-bk-tooltips="{ allowHtml: true, content: $t('上下文'), delay: 500 }"
      >
        <span
          :class="`icon bklog-icon bklog-shangxiawen ${!isActiveLog && 'is-disable'}` "
          @click.stop="handleCheckClick('contextLog', isActiveLog)"
          @mouseup.stop
        >
        </span>
      </span>
    </template>
    <template v-if="isAiAssistanceActive">
      <span
        class="handle-card ai-assistant bklog-row-ai"
        v-bk-tooltips="{ allowHtml: false, content: $t('AI助手'), delay: 500 }"
        @click.stop="e => handleCheckClick('ai', true, e)"
        @mouseup.stop
      >
        <span class="bklog-icon bklog-ai-mofabang"></span>
        <img :src="aiImageUrl" />
      </span>
    </template>
    <template v-if="showTraceInput">
      <span
        class="handle-card"
      >
        <span
          class="icon bklog-icon bklog-tracing"
          v-bk-tooltips="{ allowHtml: false, content: $t('关联Trace检索'), delay: 500 }"
          @click.stop="handleCheckClick('trace_id', true)"
          @mouseup.stop
        >
        </span>
      </span>
    </template>
  </div>
</template>

<script>
  import { mapGetters } from 'vuex';
  export default {
    props: {
      index: {
        type: Number,
        default: 0,
      },
      rowData: {
        type: Object,
        required: true,
      },
      operatorConfig: {
        type: Object,
        required: true,
      },
      logType: {
        type: String,
        default: 'table',
      },
      handleClick: Function,
    },
    emits: ['handleAi'],
    data() {
      return {
        showAllHandle: false, // hove操作区域显示全部icon
        isMonitorApm: window.__IS_MONITOR_APM__,
      };
    },
    computed: {
      ...mapGetters({
        unionIndexList: 'unionIndexList',
        isUnionSearch: 'isUnionSearch',
      }),
      aiImageUrl() {
        return require('@/images/rowAiNew.svg');
      },
      isActiveLog() {
        return this.operatorConfig?.contextAndRealtime?.is_active ?? false;
      },
      isActiveWebConsole() {
        return this.operatorConfig?.bcsWebConsole?.is_active ?? false;
      },
      isAiAssistanceActive() {
        return this.$store.getters.isAiAssistantActive;
      },
      /** 判断webConsole是否能点击 */
      isCanClickWebConsole() {
        if (!this.isActiveWebConsole) return false;
        const { cluster, container_id: containerID, __ext } = this.rowData;
        let queryData = {};
        if (cluster && containerID) {
          queryData = {
            cluster,
            container_id: containerID,
          };
        } else {
          if (!__ext) return false;
          if (!__ext.container_id) return false;
          queryData = { container_id: __ext.container_id };
          if (__ext.io_tencent_bcs_cluster) {
            Object.assign(queryData, {
              cluster: __ext.io_tencent_bcs_cluster,
            });
          } else if (__ext.bk_bcs_cluster_id) {
            Object.assign(queryData, {
              cluster: __ext.bk_bcs_cluster_id,
            });
          }
        }
        if (!queryData.cluster || !queryData.container_id) return false;
        return true;
      },
      toolMessage() {
        return (
          this.operatorConfig?.toolMessage ?? {
            realTimeLog: '',
            webConsole: '',
            contextLog: '',
          }
        );
      },
      isShowSourceField() {
        return this.operatorConfig?.isShowSourceField;
      },
      showTraceInput() {
        return this.$store.state.indexSetFieldConfig?.apm_relation?.is_active ?? false;
      }
    },
    methods: {
      normalizeTraceSearchText(value) {
        return String(value).replace(/<[^>]*>/g, '');
      },
      getTraceIdFromText(value) {
        const text = this.normalizeTraceSearchText(value);
        const traceIdPattern = /\btrace_?id\b\s*[=:]\s*([a-f0-9]{32})(?![a-z0-9])/i;
        const traceIdMatch = text.match(traceIdPattern);
        if (traceIdMatch) {
          return traceIdMatch[1];
        }

        const strictTraceIdPattern = /(^|[^a-z0-9])([a-f0-9]{32})(?![a-z0-9])/i;
        const strictTraceIdMatch = text.match(strictTraceIdPattern);
        return strictTraceIdMatch?.[2] ?? null;
      },
      getTraceIdFromRowData() {
        const traceId = this.rowData.trace_id ?? this.rowData.traceid;
        if (traceId) {
          const matchedTraceId = this.getTraceIdFromText(traceId);
          if (matchedTraceId) {
            return matchedTraceId;
          }
        }

        const rowValues = Object.values(this.rowData);
        for (const value of rowValues) {
          if (typeof value !== 'string') {
            continue;
          }

          const traceIdFromText = this.getTraceIdFromText(value);
          if (traceIdFromText) {
            return traceIdFromText;
          }
        }

        for (const value of rowValues) {
          if (!value || typeof value !== 'object') {
            continue;
          }

          const traceIdFromText = this.getTraceIdFromText(JSON.stringify(value));
          if (traceIdFromText) {
            return traceIdFromText;
          }
        }

        return null;
      },
      handleCheckClick(clickType, isActive = false, event) {
        if (!isActive) return;

        if (clickType === 'trace_id') {
          const apmRelation = this.$store.state.indexSetFieldConfig?.apm_relation;
          const traceId = this.getTraceIdFromRowData();
          if (apmRelation?.is_active && traceId) {
            const { app_name: appName, bk_biz_id: bkBizId } = apmRelation.extra;
            const path = `/?bizId=${bkBizId}#/trace/home?app_name=${appName}&search_type=accurate&trace_id=${traceId}`;
            if (path) {
              const url = `${window.MONITOR_URL ?? ''}${path}`;
              window.open(url, '_blank');
            }
          } else {
            this.$bkMessage({
              theme: 'warning',
              message: this.$t('当前选中日志暂无trace字段，请检查日志内容'),
            });
          }

          return;
        }
        return this.handleClick(clickType, event);
      },
    },
  };
</script>

<style lang="scss" scoped>
  .handle-content {
    position: relative;
    display: inline-flex;
    gap: 2px;
    align-items: center;
    justify-content: flex-start;
    width: max-content;
    overflow: visible;

    .handle-card {
      display: flex;
      align-items: center;
      justify-content: center;
      width: 20px;
      min-width: 20px;
      height: 20px;
      margin-left: 0;
      font-size: 16px;
      line-height: 20px;
      color: #8b92a5;

      .bklog-icon,
      .icon {
        font-size: 16px;
        line-height: 20px;
        cursor: pointer;
      }

      .full-row-action {
        display: inline-flex;
        align-items: center;
        justify-content: center;
        width: 18px;
        height: 18px;
        font-size: 12px;
        font-weight: 600;
        line-height: 18px;
        color: #63656e;
        cursor: pointer;
        border: 1px solid #c4c6cc;
        border-radius: 2px;
      }

      &.ai-assistant {
        position: relative;

        img {
          position: absolute;
          top: 0;
          left: 0;
          width: 20px;
          height: 20px;
          cursor: pointer;
          background-color: #fff;
          opacity: 0;
        }
      }
    }
  }

  .fix-content {
    width: max-content;
    background-color: #f5f7fa;
  }

  .icon-exclamation-circle-shape {
    color: #d7473f;
  }

  .icon-more {
    transform: translateY(2px) translateX(4px);
  }

  .is-disable {
    /* stylelint-disable-next-line declaration-no-important */
    color: #eceef2 !important;

    /* stylelint-disable-next-line declaration-no-important */
    cursor: no-drop !important;
  }

  .clean-str {
    color: #3a84ff;
    cursor: pointer;
  }

  .union-icon {
    margin-right: 8px;
  }

  .bklog-handle {
    font-size: 14px;
    color: #979ba5;
    cursor: pointer;

    &:hover {
      color: #3a84ff;
    }
  }
</style>
