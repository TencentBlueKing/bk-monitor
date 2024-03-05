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
  <bk-dialog
    :title="title"
    :value="visible"
    @value-change="valueChange"
    header-position="left"
    width="480"
    :show-footer="false"
  >
    <slot />
    <div
      v-if="!$slots.default"
      class="param-body"
    >
      <div
        class="item"
        v-for="(item, index) in list"
        :key="index"
      >
        <div class="label">
          {{ item.label }} ：
        </div>
        <div
          class="value"
          v-if="Array.isArray(item.value)"
        >
          <bk-tag
            v-for="tag of item.value"
            :key="tag"
          >{{ tag }}</bk-tag>
        </div>
        <div
          class="value"
          v-else
        >{{ item.value || '--' }}</div>
      </div>
    </div>
  </bk-dialog>
</template>

<script>
export default {
  name: 'ViewParam',
  props: {
    title: {
      type: String,
      default: '标题'
    },
    visible: {
      type: Boolean,
      required: true
    },
    list: {
      type: Array,
      default: () => []
    }
  },
  methods: {
    valueChange(val) {
      this.$emit('update:visible', val);
    }
  }
};
</script>

<style lang="scss" scoped>
.param-body {
  .item {
    display: flex;
    margin-bottom: 20px;

    .label {
      flex: 0 0 170px;
      margin-right: 24px;
      font-size: 14px;
      color: #979ba5;
      text-align: right;
    }

    .value {
      flex: 1;
      word-break: break-all;
    }

    &:last-child {
      margin-bottom: 0;
    }
  }

  .bk-tag {
    max-width: 200px;

    :deep(span) {
      display: block;
      width: 100%;
      height: 100%;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }
  }
}
</style>
