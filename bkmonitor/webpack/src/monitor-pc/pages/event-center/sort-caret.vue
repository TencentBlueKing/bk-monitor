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
  <span :class="['sort-wrapper', active]">
    <i class="sort-caret ascending" />
    <i class="sort-caret descending" />
  </span>
</template>
<script lang="ts">
import { Component, Prop, Vue } from 'vue-property-decorator';

@Component({ name: 'sort-caret' })
export default class SortCaret extends Vue {
  @Prop({ required: true }) active: 'asc' | 'desc' | 'normal';
  private list: [
    {
      id: 'asc';
      name: 'asc';
      next: 'desc';
    },
    {
      id: 'desc';
      name: 'desc';
      next: 'normal';
    },
    {
      id: 'normal';
      name: 'normal';
      next: 'asc';
    },
  ];
}
</script>
<style lang="scss" scoped>
.sort-wrapper {
  position: relative;
  display: flex;
  align-items: center;
  justify-content: center;
  width: 20px;
  height: 20px;
  cursor: pointer;

  .sort-caret {
    position: absolute;
    width: 0;
    height: 0;
    border: 5px solid transparent;

    &.ascending {
      top: -1px;
      border-bottom-color: #c0c4cc;
    }

    &.descending {
      bottom: -1px;
      border-top-color: #c0c4cc;
    }
  }

  &.asc .sort-caret.ascending {
    border-bottom-color: #63656e;
  }

  &.desc .sort-caret.descending {
    border-top-color: #63656e;
  }
}
</style>
