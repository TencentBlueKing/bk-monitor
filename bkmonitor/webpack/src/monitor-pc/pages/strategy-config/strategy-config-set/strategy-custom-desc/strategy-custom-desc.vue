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
    class="custom-desc"
    :class="{ hidden: !value }"
  >
    <div
      v-for="(desc, index) in descList"
      :key="index"
    >
      {{ index + 1 }}. {{ desc }}
    </div>
    <span
      class="custom-desc-btn"
      @click="$emit('change', false)"
      >{{ $t('收起') }}</span
    >
  </div>
</template>
<script lang="ts">
import { Component, Model, Prop, Vue } from 'vue-property-decorator';

@Component({
  name: 'StrategyCustomDesc',
})
export default class StrategyCustomDesc extends Vue {
  @Prop()
  descList: string[];

  @Model('change', { type: Boolean })
  readonly value!: boolean;
}
</script>
<style lang="scss" scoped>
.custom-desc {
  position: relative;
  width: 800px;
  padding: 10px 35px 10px 10px;
  margin: -10px 0 20px 36px;
  overflow: hidden;
  line-height: 24px;
  background-color: #f0f8ff;
  border: 1px solid #a3c5fd;
  border-radius: 2px;
  transition: height ease-in-out 0.3s;

  &.hidden {
    display: none;
    height: 0;
  }

  &-btn {
    position: absolute;
    top: 10px;
    right: 10px;
    line-height: 20px;
    color: #3a84ff;
    cursor: pointer;
  }
}
</style>
