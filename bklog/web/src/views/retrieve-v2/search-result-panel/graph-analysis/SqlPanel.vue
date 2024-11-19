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
<script setup>
import { ref, onMounted, defineExpose, nextTick } from "vue";
import * as monaco from "monaco-editor";
import useLocale from "@/hooks/use-locale";
import PreviewSql from "./common/PreviewSql.vue"
import $http from '../../../../api';
const { $t } = useLocale();
const editorContainer = ref(null);
const showDialog = ref(false);
const emit = defineEmits(['search-completed']);
let editorInstance = null;
window.MonacoEnvironment = {
  // 根据提供的worker类别标签（label）返回一个新的Worker实例, Worker负责处理与该标签相关的任务
  // 当label是’json’时，将初始化并返回一个专门处理JSON文件的Worker。如果label不是’json’，则返回一个通用的编辑器Worker
  getWorker: (workerId, label) => {
    console.log(workerId, label);

    if (label === "yaml") {
      return process.env.NODE_ENV === "production"
        ? `${window.BK_STATIC_URL}/yaml.worker.js`
        : "./yaml.worker.js";
    }
    if (label === "json") {
      return process.env.NODE_ENV === "production"
        ? `${window.BK_STATIC_URL}/json.worker.js`
        : "./json.worker.js";
    }
    return process.env.NODE_ENV === "production"
      ? `${window.BK_STATIC_URL}/editor.worker.js`
      : "./editor.worker.js";
  },
};
// resize后重新计算高度
async function resize() {
  if (editorInstance) {
    await nextTick();
    editorInstance.layout();
  }
}
function emitQuery() {}
function emitStop() {}
async function sqlSearch() {
  if (!editorInstance) {
    console.error("Editor instance is not available.");
    return;
  }

  // 获取编辑器内容
  const sqlQuery = editorInstance.getValue();
  console.log("SQL Query:", sqlQuery);

  // 这里将编辑器内容作为 SQL 查询的一部分发送
  const res = await $http.request("graphAnalysis/searchSQL", {
    params: {
      index_set_id: 627298,
    },
    data: {
      query_mode: "sql",
      sql: sqlQuery, // 使用获取到的内容
    },
  });
  emit('search-completed', res);
  // 处理响应
  console.log(res);
}
onMounted(() => {
  // 在组件挂载后初始化 Monaco Editor
  if (editorContainer.value) {
    // editorContainer.value.style.height = "100%"; // 设置高度
    editorInstance = monaco.editor.create(editorContainer.value, {
      value: "sELECT thedate, dtEventTimeStamp, iterationIndex, log, time FROM 100968_proz_rd_ds2_test.doris WHERE thedate>='20241111' AND thedate<='20241111' limit 2",
      language: "javascript", // 设置语言类型
      theme: "vs-dark", // 设置编辑器主题
    });
  }
});
defineExpose({
  resize,
});
</script>
<template>
  <div class="sql-editor">
    <div ref="editorContainer" :immediate="true" class="editorContainer"></div>
    <div class="sql-editor-tools">
      <bk-button
        @click="emitQuery"
        class="sql-editor-query-button font-small mr-small"
        theme="primary"
        size="small"
        v-bk-tooltips="{
          content: $t('请先在左侧选择需要查询的数据源'),
        }"
      >
        <!-- <template v-if="props.isQuerying">
          <img :src="loading" class="sql-editor-query-button-spinner font-small" />
        </template>
        <template v-else> -->
        <i class="bklog-icon bklog-bofang"></i>
        <!-- </template> -->
        <span class="ml-min" @click="sqlSearch">{{ $t("查询") }}</span>
      </bk-button>
      <bk-button
        @click="emitStop"
        class="sql-editor-view-button text-center pl-min pr-min mr-small cursor-pointer"
        size="small"
      >
        <span class="icon bklog-icon bklog-stop" />
        <span>{{ $t("中止") }}</span>
      </bk-button>
      <bk-button
        class="sql-editor-view-button text-center pl-min pr-min cursor-pointer"
        size="small"
        @click="showDialog = true"
      >
        {{ $t("预览查询 SQL") }}
      </bk-button>
      <PreviewSql
         :isShow="showDialog"
        @update:isShow="newValue => showDialog = newValue"
      />
    </div>
  </div>
</template>

<style lang="scss" scoped>
.sql-editor {
  display: flex;
  flex-direction: column;
  height: 100%;
  background-color: #1e1e1e;

  .editorContainer {
    height: 100%;

    .monaco-edito {
      height: 100%;
    }
  }

  .sql-editor-tools {
    margin: 16px;

    .sql-editor-view-button {
      height: 28px;
      line-height: 26px;
      color: #c4c6cc;
      background-color: #313238;
      border: 1px solid #63656e;
      border-radius: 2px;
      transition: border-color 0.3s ease-in-out;

      &:hover {
        border-color: #979ba5;
      }
    }
  }
}
</style>
