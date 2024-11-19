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
import useLocale from "@/hooks/use-locale";
const { $t } = useLocale();

function handlePageLimitChange() {
  console.log("handlePageLimitChange", arguments);
}

const data = ref([]);
const size = ref("small");
const pagination = ref({
  current: 1,
  count: 500,
  limit: 20,
});
function handleRowMouseEnter() {}
function handleRowMouseLeave() {}
function handlePageChange(page) {
  this.pagination.current = page;
}
</script>
<template>
  <div class="graph-context graph-table">
    <bk-table
      style="margin-top: 15px"
      :data="data"
      :size="size"
      :pagination="pagination"
      @row-mouse-enter="handleRowMouseEnter"
      @row-mouse-leave="handleRowMouseLeave"
      @page-change="handlePageChange"
      @page-limit-change="handlePageLimitChange"
    >
      <bk-table-column type="selection" width="60"></bk-table-column>
      <bk-table-column type="index" label="序列" width="60"></bk-table-column>
      <bk-table-column label="名称/内网IP" prop="ip"></bk-table-column>
      <bk-table-column label="来源" prop="source"></bk-table-column>
      <bk-table-column label="状态" prop="status"></bk-table-column>
      <bk-table-column label="创建时间" prop="create_time"></bk-table-column>
      <bk-table-column label="操作" width="150">
        <template slot-scope="props">
          <bk-button
            style="margin-right: 12px"
            theme="primary"
            text
            :disabled="props.row.status === '创建中'"
            @click="reset(props.row)"
            >重置</bk-button
          >
          <bk-button
            style="margin-right: 12px"
            theme="primary"
            text
            @click="remove(props.row)"
            >移除</bk-button
          >
          <bk-popover
            class="dot-menu"
            placement="bottom-start"
            theme="dot-menu light"
            :trigger="props.$index % 2 === 0 ? 'click' : 'mouseenter'"
            :arrow="false"
            offset="15"
            :distance="0"
          >
            <span class="dot-menu-trigger"></span>
            <ul class="dot-menu-list" slot="content">
              <li class="dot-menu-item">导入</li>
              <li class="dot-menu-item">导出</li>
            </ul>
          </bk-popover>
        </template>
      </bk-table-column>
    </bk-table>
  </div>
</template>

<style lang="scss" scoped>
.graph-context {
  width: 100%;
  height: calc(100% - 22px);
}
</style>
