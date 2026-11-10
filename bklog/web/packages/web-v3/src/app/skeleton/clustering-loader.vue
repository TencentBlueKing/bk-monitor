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
  <div
    v-if="widthList.length"
    class="skeleton-table"
    aria-hidden="true"
  >
    <div
      v-for="(_, rowIndex) in renderList"
      :key="rowIndex"
      class="skeleton-table__row"
    >
      <div class="skeleton-table__cell skeleton-table__cell--gutter"></div>
      <div
        v-for="(field, columnIndex) in widthList"
        :key="columnIndex"
        class="skeleton-table__cell"
        :style="getCellStyle(field)"
      >
        <div
          :style="`width:${getRandom()}%`"
          class="cell-bar"
        ></div>
      </div>
      <div
        v-if="!isLoading"
        class="skeleton-table__cell skeleton-table__cell--operation"
      ></div>
    </div>
  </div>
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
      getCellStyle(field) {
        if (!field) {
          return {
            flex: '1 1 auto',
            minWidth: 0,
          };
        }
        const width = typeof field === 'number' || /^\d+$/.test(field) ? `${field}px` : field;
        return {
          flex: `0 0 ${width}`,
          width,
        };
      },
      getRandom() {
        // 骨架占位随机长度
        return Math.floor(Math.random() * (20 - 100) + 100);
      },
    },
  };
</script>

<style lang="scss">
  .skeleton-table {
    width: 100%;

    &__row {
      display: flex;
      width: 100%;
      height: 43px;
      background-color: #fff;
      border-bottom: 1px solid #dcdee5;
      box-sizing: border-box;
    }

    &__cell {
      display: flex;
      align-items: center;
      padding: 8px 15px;
      box-sizing: border-box;

      &--gutter {
        flex: 0 0 30px;
        width: 30px;
        padding: 0;
      }

      &--operation {
        flex: 0 0 84px;
        width: 84px;
        padding: 0;
      }
    }

    .cell-bar {
      position: relative;
      height: 12px;
      background-color: #e9e9e9;
    }

  }
</style>
