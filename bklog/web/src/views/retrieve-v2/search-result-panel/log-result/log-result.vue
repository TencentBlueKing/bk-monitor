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
  <div class="bklog-result-box">
    <LogRows
      :content-type="contentType"
      :handle-click-tools="handleClickTools"
    ></LogRows>
    <RealTimeLog
      :is-show="isShowRealTimeLog"
      :log-params="logDialog.data"
      :retrieve-params="retrieveParams"
      :target-fields="targetFields"
      :indexSetId="logDialog.indexSetId"
      :row-index="currentIndex"
      @close-dialog="hideDialog"
    />
    <ContextLog
      :is-show="isShowContextLog"
      :log-params="logDialog.data"
      :retrieve-params="retrieveParams"
      :target-fields="targetFields"
      :indexSetId="logDialog.indexSetId"
      :row-index="currentIndex"
      @close-dialog="hideDialog"
    />
    <AiAssitant ref="refAiAssitant" :is-external="isExternal" @close="handleAiClose"></AiAssitant>
  </div>
</template>

<script>
import { parseTableRowData } from "@/common/util";
import RetrieveLoader from "@/skeleton/retrieve-loader";

import ContextLog from "@/views/retrieve-v3/search-result/original-log/context-log/index.tsx";
import RealTimeLog from "@/views/retrieve-v3/search-result/original-log/real-time-log";
import LogRows from "./log-rows.tsx";
// #if MONITOR_APP !== 'apm' && MONITOR_APP !== 'trace'
import AiAssitant from "@/global/ai-assitant.tsx";
// #else
// #code const AiAssitant = () => null;
// #endif
export default {
  components: {
    RetrieveLoader,
    ContextLog,
    RealTimeLog,
    AiAssitant,
    LogRows,
  },
  props: {
    contentType: {
      type: String,
      default: "table",
    },
    retrieveParams: {
      type: Object,
      default: () => ({}),
    },
  },
  data() {
    return {
      targetFields: [],
      isShowRealTimeLog: false,
      isShowContextLog: false,
      logDialog: {
        type: "",
        data: {},
        indexSetId: 0,
      },
      currentIndex: 0,
    };
  },
  computed: {
    isExternal() {
      return this.$store.state.isExternal;
    },
  },
  methods: {
    handleAiClose() {
      this.$el.querySelector(".ai-active")?.classList.remove("ai-active");
    },
    // 打开实时日志或上下文弹窗
    openLogDialog(row, type, indexSetId) {
      this.logDialog.data = row;
      this.logDialog.type = type;
      this.logDialog.indexSetId = indexSetId;
      if (type === "realTimeLog") {
        this.isShowRealTimeLog = true;
      } else {
        this.isShowContextLog = true;
      }
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
      this.$http
        .request("retrieve/getWebConsoleUrl", {
          params: {
            index_set_id: this.$route.params.indexId,
          },
          query: queryData,
        })
        .then((res) => {
          window.open(res.data);
        })
        .catch((e) => {
          console.warn(e);
        });
    },
    handleClickTools(event, row, config, index) {
      if (event === 'ai') {
          this.$refs.refAiAssitant.open(true, {
            space_uid: this.$store.getters.spaceUid,
            index_set_id: this.$store.getters.indexId,
            log: row,
            index,
          });
          return;
        }

        if (event === 'add-to-ai') {
          this.$refs.refAiAssitant.setCiteText(row);
          return;
        }
      if (["realTimeLog", "contextLog"].includes(event)) {
        this.currentIndex = index - 1;
        const contextFields = config.contextAndRealtime.extra?.context_fields;
        const timeField = this.$store.state.indexFieldInfo.time_field;
        const dialogNewParams = {};
        const { targetFields = [], sortFields = [] } = config.indexSetValue;

        // const fieldParamsKey = [...new Set([...targetFields, ...sortFields])];
        this.targetFields = targetFields ?? [];

        Object.assign(dialogNewParams, {
          dtEventTimeStamp: row.dtEventTimeStamp,
        });
        // 非日志采集的情况下判断是否设置过字段设置 设置了的话传已设置过的参数
        // if (config.indexSetValue.scenarioID !== 'log' && fieldParamsKey.length) {
        //   fieldParamsKey.forEach(field => {
        //     dialogNewParams[field] = parseTableRowData(row, field, '', this.$store.state.isFormatDate, '');
        //   });
        // } else
        if (Array.isArray(contextFields) && contextFields.length) {
          // 传参配置指定字段
          contextFields.push(timeField);
          contextFields.forEach((field) => {
            if (field === "bk_host_id") {
              if (row[field]) dialogNewParams[field] = row[field];
            } else {
              dialogNewParams[field] = parseTableRowData(
                row,
                field,
                "",
                this.$store.state.isFormatDate,
                ""
              );
            }
          });
        } else {
          Object.assign(dialogNewParams, row);
        }
        this.openLogDialog(dialogNewParams, event, row.__index_set_id__);
      } else if (event === "webConsole") this.openWebConsole(row);
      else if (event === "logSource")
        this.$store.dispatch("changeShowUnionSource");
    },
    // 关闭实时日志或上下文弹窗后的回调
    hideDialog() {
      this.logDialog.type = "";
      this.targetFields = [];
      this.isShowContextLog = false;
      this.isShowRealTimeLog = false;
    },
  },
};
</script>
<style lang="scss">
.bklog-result-box {
  position: relative;

  .bklog-skeleton-loading {
    position: absolute;
    top: 0;
    z-index: 10;
  }
}
</style>
