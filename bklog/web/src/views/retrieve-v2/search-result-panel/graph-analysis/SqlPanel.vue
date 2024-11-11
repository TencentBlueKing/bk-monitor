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
import { ref, onMounted } from "vue";
import * as monaco from "monaco-editor";
import { bkResizeLayout } from "bk-magic-vue";
import useLocale from "@/hooks/use-locale";
const { $t } = useLocale();
const editorContainer = ref(null);
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
function resize() {
  if (editorInstance) {
    editorInstance.layout();
  }
}
onMounted(() => {
  // 在组件挂载后初始化 Monaco Editor
  if (editorContainer.value) {
    // editorContainer.value.style.height = "100%"; // 设置高度
    editorInstance = monaco.editor.create(editorContainer.value, {
      value: "123",
      language: "javascript", // 设置语言类型
      theme: "vs-dark", // 设置编辑器主题
    });
  }
});
</script>
<template>
  <div class="body-left">
    <bk-resize-layout
      class="full-height"
      placement="top"
      :initial-divide="274"
      @after-resize="resize"
      :min="274"
      :border="false"
    >
      <div
        ref="editorContainer"
        slot="aside"
        :immediate="true"
        class="editorContainer"
      ></div>
      <!-- <div ref="editorContainer" :style="{ height: `${topPanelHeight}px` }"></div> -->
      <div slot="main">main</div>
    </bk-resize-layout>
  </div>
</template>

<style lang="scss" scoped>
.body-left {
  .full-height {
    height: 100%;

    .editorContainer {
      height: 100%;

      .monaco-edito {
        height: 100%;
      }
    }
  }
}
</style>
