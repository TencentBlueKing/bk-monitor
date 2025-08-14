<!-- eslint-disable vue/no-v-html -->
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
  <ul class="preview-template">
    <li
      v-for="(item, index) in renderList"
      :key="index"
      class="preview-template-item"
    >
      <h5 class="item-title">
        {{ item.name }}
      </h5>

      <!-- eslint-disable-next-line vue/no-v-html -->
      <div
        v-if="item.type === 'mail'"
        class="item-template"
        :class="{ 'no-br': item.type === 'mail' }"
        v-html="item.message"
      />
      <pre v-else>{{ item.message }}</pre>
    </li>
  </ul>
</template>
<script>
export default {
  name: 'PreviewTemplate',
  props: {
    // 需要渲览预览通知模板
    renderList: {
      type: Array,
      required: true,
    },
  },
};
</script>
<style lang="scss" scoped>
.preview-template {
  display: flex;
  flex-direction: column;
  height: 390px;
  margin-right: -22px;
  margin-bottom: 2px;
  overflow: auto;
  font-size: 14px;
  color: #63656e;

  &-item {
    padding-right: 22px;
    margin-top: 17px;

    .item-title {
      margin-top: 0;
      margin-bottom: 7px;
      font-size: 14px;
      font-weight: 500;
    }

    pre {
      font-size: 14px;
      line-height: 20px;
      color: #63656e;
    }

    .item-template {
      &.no-br {
        :deep(br) {
          display: none;
        }
      }

      :deep(div) {
        /* stylelint-disable-next-line declaration-no-important */
        background-color: white !important;
      }
    }
  }
}
</style>
