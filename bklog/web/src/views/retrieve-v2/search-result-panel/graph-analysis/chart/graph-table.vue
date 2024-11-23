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
import { ref, defineProps, defineExpose, computed } from "vue";
import useLocale from "@/hooks/use-locale";
const { $t } = useLocale();
const props = defineProps({
  hidden: {
    type: Array,
    default: [],
  },
});

const tableData = ref([]);
const rawColumns = ref([]);

function setOption(data) {
  console.log(data);
  tableData.value = data.data.list;
  rawColumns.value = data.data.select_fields_order;
}
const column = computed(() => {
  return rawColumns.value.filter((item) => !props.hidden.includes(item));
});
function handleRowMouseEnter() {}
function handleRowMouseLeave() {}
defineExpose({
  setOption,
});
</script>
<template>
  <div class="graph-context graph-table">
    <bk-table
      style="margin-top: 15px"
      :data="tableData"
      @row-mouse-enter="handleRowMouseEnter"
      @row-mouse-leave="handleRowMouseLeave"
      height="220px"
    >
      <bk-table-column
        v-for="(item, index) in column"
        :label="item"
        :prop="item"
        :key="index"
      ></bk-table-column>
      <!-- <bk-table-column type="index" label="序列" width="60"></bk-table-column>
      <bk-table-column label="名称/内网IP" prop="ip"></bk-table-column>
      <bk-table-column label="来源" prop="source"></bk-table-column>
      <bk-table-column label="状态" prop="status"></bk-table-column>
      <bk-table-column label="创建时间" prop="create_time"></bk-table-column> -->
    </bk-table>
  </div>
</template>

<style lang="scss" scoped>
.graph-context {
  width: 100%;
  height: calc(100% - 22px);
}
</style>