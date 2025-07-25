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
    class="step-verify-input"
    :class="{ 'is-empty': showValidate && validator.content }"
    @click="handleFocus"
  >
    <slot />
    <span
      v-show="showValidate && validator.content && position === 'right'"
      v-bk-tooltips.top-end="validator"
      class="bk-icon icon-exclamation-circle-shape tooltips-icon"
    />
    <span
      v-show="showValidate && position === 'bottom'"
      :style="{ top: errorTextTopMargin ? `${errorTextTopMargin}px` : null }"
      class="bottom-text"
      >{{ validator.content }}</span
    >
  </div>
</template>

<script>
export default {
  name: 'StepVerifyInput',
  props: {
    position: {
      type: String,
      default: 'bottom',
    },
    validator: {
      type: Object,
      default() {
        return {
          content: this.$t('必填项'),
        };
      },
    },
    showValidate: {
      type: Boolean,
      default: false,
    },
    errorTextTopMargin: {
      type: Number,
      default: 0,
    },
  },
  methods: {
    handleFocus() {
      // this.$emit('update:showValidate', false)
    },
  },
};
</script>

<style scoped lang="scss">
.step-verify-input {
  position: relative;
  display: flex;
  align-items: center;

  .tooltips-icon {
    position: absolute;
    top: 10px;
    right: 20px;
    display: inline-block;
    font-size: 16px;
  }

  .bottom-text {
    position: absolute;
    top: 100%;
    left: 0;
    width: 600px;
    padding-top: 6px;
    font-size: 12px;
    line-height: 1;
    color: #f56c6c;
  }

  :deep(.bk-select) {
    width: 100%;
  }
}

.is-empty {
  :deep(input) {
    border-color: #ff5656;
  }

  .tooltips-icon {
    color: #ea3636;
    cursor: pointer;
  }

  :deep(.bk-select) {
    border-color: #ff5656;
  }
}
</style>
