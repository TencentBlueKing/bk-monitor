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
        v-bk-tooltips="{ allowHtml: true, content: '#realTimeLog-html' }"
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
        v-bk-tooltips="{ allowHtml: true, content: '#contextLog-html' }"
      >
        <span
          :class="`icon bklog-icon bklog-shangxiawen ${!isActiveLog && 'is-disable'}`"
          @click.stop="handleCheckClick('contextLog', isActiveLog)"
          @mouseup.stop
        >
        </span>
      </span>
      <span
        v-if="isActiveWebConsole && !isMonitorApm"
        class="handle-card"
        v-bk-tooltips="{ allowHtml: true, content: '#webConsole-html' }"
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
        v-bk-tooltips="{ allowHtml: true, content: $t('上下文') }"
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
        v-bk-tooltips="{ allowHtml: false, content: $t('AI助手') }"
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
          v-bk-tooltips="{ allowHtml: false, content: $t('关联Trace检索') }"
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
      getTraceIdFromRowData() {
        const traceId = this.rowData.trace_id;
        if (traceId) {
          return traceId;
        }

        for (let v of Object.values(this.rowData)) {
          if (typeof v === 'string') {
            const traceIdPattern = /[a-f0-9]{32}/;
            const match = v.match(traceIdPattern);
            if (match) {
              return match[0];
            }
          }

          if (typeof v === 'object') {
            const jsonValue = JSON.stringify(v);
            const traceIdPattern = /[a-f0-9]{32}/;
            const match = jsonValue.match(traceIdPattern);
            if (match) {
              return match[0];
            }
          }
        }

        return null;
      },
      handleCheckClick(clickType, isActive = false, event) {
        if (!isActive) return;

        if (clickType === 'trace_id') {
          const apmRelation = this.$store.state.indexSetFieldConfig?.apm_relation;
          const traceId = this.getTraceIdFromRowData() ;
          if (apmRelation?.is_active && traceId) {
            const { app_name: appName, bk_biz_id: bkBizId } = apmRelation.extra;
            const path = `/?bizId=${bkBizId}#/trace/home?app_name=${appName}&search_type=accurate&trace_id=${traceId}`;
            if (path) {
              const url = `${window.MONITOR_URL}${path}`;
              window.open(url, '_blank');
            }
          } else {
            this.$bkMessage({
              theme: 'warning',
              message: this.$t('未找到相关的应用，请确认是否有Trace数据的接入。'),
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
    position: absolute;
    right: 0;
    display: flex;
    align-items: flex-start;
    justify-content: center;
    width: 84px;
    overflow: hidden;

    .handle-card {
      display: flex;
      align-items: center;
      justify-content: center;
      width: 18px;
      height: 20px;
      margin-left: 10px;
      font-size: 18px;
      color: #8b92a5;

      .bklog-icon {
        cursor: pointer;
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
    width: auto;
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
