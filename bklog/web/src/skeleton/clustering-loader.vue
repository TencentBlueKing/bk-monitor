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
  <bk-table
    v-if="widthList.length"
    class="skeleton-table"
    :data="renderList"
    :outer-border="false"
    :show-header="false"
  >
    <bk-table-column width="30"></bk-table-column>
    <template>
      <bk-table-column
        v-for="(field, index) in widthList"
        :key="index"
        :min-width="field ? field : 0"
        :width="field ? field : 'auto'"
      >
        <!-- eslint-disable-next-line vue/no-unused-vars -->
        <template #default="props">
          <div
            :style="`width:${getRandom()}%`"
            class="cell-bar"
          ></div>
        </template>
      </bk-table-column>
    </template>
    <bk-table-column
      v-if="!isLoading"
      width="84"
    ></bk-table-column>
  </bk-table>
</template>

<script>
export default {
  props: {
    // 用于初次loading
    isLoading: {
      type: Boolean,
      default: false,
    },
    widthList: {
      type: Array,
      require: true,
    },
    loaderLen: {
      // 骨架行数
      type: Number,
      default: 24,
    },
  },
  data() {
    return {};
  },
  computed: {
    renderList() {
      return new Array(this.loaderLen).fill('');
    },
  },
  methods: {
    getRandom() {
      // 骨架占位随机长度
      return Math.floor(Math.random() * (20 - 100) + 100);
    },
  },
};
</script>

<style lang="scss">
  .skeleton-table {
    &:before {
      z-index: -1;
    }

    .cell {
      width: 100%;
      padding-top: 14px;
    }

    .cell-bar {
      position: relative;
      height: 12px;
      background-color: #e9e9e9;
    }

    :deep(.bk-table-empty-text) {
      width: 100%;
      padding: 0;
    }
  }
</style>
