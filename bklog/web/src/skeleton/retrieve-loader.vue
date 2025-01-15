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
    v-if="columnField.length"
    class="skeleton-table"
    :data="renderList"
    :show-header="false"
  >
    <bk-table-column width="30"></bk-table-column>
    <template>
      <bk-table-column
        v-for="(field, index) in columnField"
        :key="index"
        :min-width="!isLoading || isOriginalField ? field.minWidth : 0"
        :width="!isLoading || isOriginalField ? field.width : 'auto'"
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
      visibleFields: {
        type: Array,
        required: true,
      },
      // 用于初次loading
      isLoading: {
        type: Boolean,
        default: false,
      },
      // 是否原始日志
      isOriginalField: {
        type: Boolean,
        default: false,
      },
      isPageOver: {
        type: Boolean,
        required: false,
      },
      isNewSearch: {
        type: Boolean,
        default: false,
      },
      static: {
        type: Boolean,
        default: false,
      },
      maxLength: {
        type: Number
      }
    },
    data() {
      return {
        throttle: false, // 滚动节流
        loaderLen: 12, // 骨架行数
      };
    },
    computed: {
      renderList() {
        return new Array(this.maxLength ?? this.loaderLen).fill('');
      },
      columnField() {
        const visibleTable = !this.visibleFields.length
          ? Array(3).fill({ width: '', minWidth: 0 })
          : this.visibleFields;
        return this.isOriginalField
          ? [
              { width: 160, minWidth: 0, field_name: 'time' },
              { width: '', minWidth: 0, field_name: 'log' },
            ]
          : visibleTable;
      },
      loaderClassName() {
        return this.isNewSearch ? '.result-table-container' : '.result-scroll-container';
      },
    },
    mounted() {
      if (!this.static) {
        if (this.isLoading) this.loaderLen = 12;
        const ele = document.querySelector(this.loaderClassName);
        if (ele) ele.addEventListener('scroll', this.handleScroll);
      }
    },
    beforeDestroy() {
      if (!this.static) {
        const ele = document.querySelector(this.loaderClassName);
        if (ele) ele.removeEventListener('scroll', this.handleScroll);
      }
    },
    methods: {
      getRandom() {
        // 骨架占位随机长度
        return Math.floor(Math.random() * (20 - 100) + 100);
      },
      handleScroll() {
        if (this.throttle || this.isLoading) {
          return;
        }

        const el = document.querySelector(this.loaderClassName);
        if (el.scrollHeight - el.offsetHeight - el.scrollTop < 100) {
          this.throttle = true;
          setTimeout(() => {
            this.loaderLen = this.loaderLen + 24;
            el.scrollTop = el.scrollTop - 100;
            this.throttle = false;
          }, 100);
        }
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
