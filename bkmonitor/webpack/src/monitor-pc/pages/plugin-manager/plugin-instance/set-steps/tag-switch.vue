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
    class="tag-switch-wrapper"
    :style="{ paddingBottom: (showValidate && message) ? '18px' : 0 }"
  >
    <bk-tag v-show="isTag">
      <span @click="switchStatus(false)">{{ `${tagLabel}:${value}` }}</span>
    </bk-tag>
    <verify-input
      class="param-item"
      :show-validate="showValidate"
      :validator="{ content: message }"
      :position="position"
    >
      <bk-input
        v-show="!isTag"
        ref="inputRef"
        :value="value"
        @input="handleInput"
        @blur="switchStatus(true)"
        @keydown.enter.native="switchStatus(true)"
      />
    </verify-input>

  </div>
</template>


<script>


import VerifyInput from '../../../../components/verify-input/verify-input.vue';

export default {
  name: 'TagSwitch',
  components: {
    VerifyInput
  },
  props: {
    tagLabel: {
      type: String,
      default: ''
    },
    value: {
      type: String,
      required: true
    },
    showValidate: {
      type: Boolean,
      default: false
    },
    message: {
      type: String,
      default: ''
    },
    position: {
      type: String,
      default: 'bottom'
    }
  },
  data() {
    return {
      isTag: true
    };
  },
  methods: {
    switchStatus(val) {
      if (val && this.showValidate) return;
      this.isTag = val;
      if (this.isTag === false) {
        this.$nextTick(() => {
          this.$refs.inputRef.focus();
        });
      }
    },
    handleInput(val) {
      this.$emit('input', val);
    }
  }
};
</script>
<style lang="scss" scoped>
/* stylelint-disable declaration-no-important */
.tag-switch-wrapper {
  margin-right: 5px;

  :deep(.bk-form-input) {
    width: 120px !important;
    margin-left: 6px;
  }
}

.bk-tag {
  margin: 0;
}
</style>
