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
  <div :class="['handle-content', { 'fix-content': showAllHandle, 'origin-content': logType === 'origin' }]">
    <template v-if="!isUnionSearch">
      <button
        :class="['handle-item', { 'is-disable': !isActiveLog }]"
        type="button"
        v-bk-tooltips="{ allowHtml: true, content: '#realTimeLog-html', delay: 500 }"
        @click.stop="handleCheckClick('realTimeLog', isActiveLog)"
        @mouseup.stop
      >
        <span class="icon bklog-icon bklog-shishirizhi" />
        <span class="handle-label">{{ $t('实时') }}</span>
      </button>
      <span class="handle-divider" />
      <button
        :class="['handle-item', { 'is-disable': !isActiveLog }]"
        type="button"
        v-bk-tooltips="{ allowHtml: true, content: '#contextLog-html', delay: 500 }"
        @click.stop="handleCheckClick('contextLog', isActiveLog)"
        @mouseup.stop
      >
        <span class="icon bklog-icon bklog-shangxiawen" />
        <span class="handle-label">{{ $t('上下文') }}</span>
      </button>
      <template v-if="showTraceInput">
        <span class="handle-divider" />
        <button
          class="handle-item"
          type="button"
          v-bk-tooltips="{ allowHtml: false, content: $t('关联Trace检索'), delay: 500 }"
          @click.stop="handleCheckClick('trace_id', true)"
          @mouseup.stop
        >
          <span class="icon bklog-icon bklog-tracing" />
          <span class="handle-label">Trace</span>
        </button>
      </template>
      <template v-if="showFullRow">
        <span class="handle-divider" />
        <button
          class="handle-item"
          type="button"
          v-bk-tooltips="{ allowHtml: false, content: $t('全量'), delay: 500 }"
          @click.stop="handleCheckClick('fullRow', true)"
          @mouseup.stop
        >
          <span class="icon bklog-icon bklog-match-all"></span>
          <span class="handle-label">{{ $t('全量') }}</span>
        </button>
      </template>
      <template v-if="isAiAssistanceActive">
        <span class="handle-divider" />
        <button
          class="handle-item ai-assistant bklog-row-ai"
          type="button"
          v-bk-tooltips="{ allowHtml: false, content: $t('AI助手'), delay: 500 }"
          @click.stop="e => handleCheckClick('ai', true, e)"
          @mouseup.stop
        >
          <span class="bklog-icon bklog-ai-mofabang" />
          <img :src="aiImageUrl" />
          <span class="handle-label ai-label">AI</span>
        </button>
      </template>
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
      <button
        :class="['handle-item', { 'is-disable': !isActiveLog }]"
        type="button"
        v-bk-tooltips="{ allowHtml: true, content: $t('上下文'), delay: 500 }"
        @click.stop="handleCheckClick('contextLog', isActiveLog)"
        @mouseup.stop
      >
        <span class="icon bklog-icon bklog-shangxiawen" />
        <span class="handle-label">{{ $t('上下文') }}</span>
      </button>
      <template v-if="showFullRow">
        <span class="handle-divider" />
        <button
          class="handle-item"
          type="button"
          v-bk-tooltips="{ allowHtml: false, content: $t('全量'), delay: 500 }"
          @click.stop="handleCheckClick('fullRow', true)"
          @mouseup.stop
        >
          <span class="icon bklog-icon bklog-lc-star-shape" />
          <span class="handle-label">{{ $t('全量') }}</span>
        </button>
      </template>
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
      showFullRow: {
        type: Boolean,
        default: false,
      },
      handleClick: Function,
    },
    emits: ['handleAi'],
    data() {
      return {
        showAllHandle: false,
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
      isAiAssistanceActive() {
        return this.$store.getters.isAiAssistantActive;
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
              window.open(url, '_blank', 'noopener,noreferrer');
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
    gap: 0;
    align-items: center;
    justify-content: flex-start;
    width: max-content;
    overflow: visible;
    background: #fff;
    border: 1px solid #c4cee3;
    border-radius: 4px;
    box-shadow: 0 2px 6px 0 #0000001f;

    .handle-item {
      display: inline-flex;
      gap: 4px;
      align-items: center;
      height: 28px;
      padding: 0 10px;
      font-size: 12px;
      line-height: 20px;
      color: #4d4f56;
      cursor: pointer;
      background: transparent;
      border: 0;
      border-radius: 2px;

      .bklog-icon,
      .icon {
        font-size: 14px;
        line-height: 14px;
      }

      .handle-label {
        white-space: nowrap;
      }

      &:hover,
      &:focus-visible {
        color: #3a84ff;
        background: #edf4ff;
        outline: none;
      }

      &.ai-assistant {
        position: relative;

        img {
          position: absolute;
          top: 50%;
          left: 10px;
          width: 14px;
          height: 14px;
          cursor: pointer;
          background-color: #fff;
          opacity: 0;
          transform: translateY(-50%);
        }

        .ai-label {
          font-weight: 600;
          background: linear-gradient(118deg, #235dfa 0%, #e28bed 100%);
          -webkit-background-clip: text;
          background-clip: text;
          -webkit-text-fill-color: transparent;
          color: transparent;
        }
      }
    }

    .handle-divider {
      flex: 0 0 1px;
      width: 1px;
      height: 16px;
      background: #dcdee5;
    }
  }

  .fix-content {
    width: max-content;
    background-color: #f5f7fa;
  }

  .icon-exclamation-circle-shape {
    color: #d7473f;
  }

  .is-disable {
    /* stylelint-disable-next-line declaration-no-important */
    color: #c4c6cc !important;

    /* stylelint-disable-next-line declaration-no-important */
    cursor: no-drop !important;

    &:hover,
    &:focus-visible {
      color: #c4c6cc !important;
      background: transparent !important;
    }
  }
</style>
