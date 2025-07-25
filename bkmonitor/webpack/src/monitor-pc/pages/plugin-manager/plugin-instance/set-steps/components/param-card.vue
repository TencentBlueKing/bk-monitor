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
  <div :class="{ 'param-card': true, disabled: disabled }">
    <div class="title">
      {{ title }}
    </div>
    <div class="content">
      <bk-input
        :disabled="disabled"
        :value="value"
        :placeholder="placeholder"
        @change="handleChange"
        @blur="handleBlur"
      />
    </div>
  </div>
</template>
<script lang="ts">
import { Component, Prop, Vue } from 'vue-property-decorator';

@Component({
  name: 'param-card',
  model: {
    prop: 'value',
    event: 'change',
  },
})
export default class ParamCard extends Vue {
  @Prop({ type: String, default: '' })
  title: string;

  @Prop({ type: String, default: '' })
  value: string;

  @Prop({
    type: String,
    default: () => this.$t('输入'),
  })
  placeholder: string;

  @Prop({ type: Boolean, default: false })
  disabled: boolean;

  handleChange(val: string) {
    this.$emit('change', val);
  }

  handleBlur() {
    this.$emit('blur');
  }
}
</script>
<style lang="scss" scoped>
.param-card {
  width: 465px;
  height: 58px;
  background: #fff;
  border: 1px solid #dcdee5;

  &:hover {
    box-shadow: 0 2px 4px 0 rgba(0, 0, 0, 0.06);
  }

  &.disabled {
    cursor: not-allowed;
    background: #fafbfd;

    :deep(.bk-form-input) {
      /* stylelint-disable-next-line declaration-no-important */
      color: #000 !important;
      border: 1px solid rgba(255, 255, 255, 0.5);

      /* stylelint-disable-next-line declaration-no-important */
      border-color: #fafbfd !important;
    }
  }

  .title {
    padding: 9px 15px 0 15px;
    margin-bottom: 1px;
    font-size: 12px;
    color: #63656e;
  }

  .content {
    padding: 0 6px;

    :deep(.bk-form-input) {
      height: 26px;
      padding-left: 8px;
      color: #000;
      border: 1px solid rgba(255, 255, 255, 0.5);

      &:hover {
        color: #c4c6cc;
        background: #f5f6fa;
      }

      &:focus {
        color: #63656e;
      }
    }
  }
}
</style>
