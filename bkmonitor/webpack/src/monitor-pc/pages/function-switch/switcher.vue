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
  <span :class="['switcher-wrapper', { 'switch-acitve': value }]">
    <input
      type="checkbox"
      :checked="value"
      @change="handleChange"
    />
  </span>
</template>

<script lang="ts">
import { Component, Prop, Vue } from 'vue-property-decorator';

@Component({
  name: 'switcher',
})
export default class Switcher extends Vue {
  // checkbox的状态
  @Prop({ default: false, required: true }) readonly value: boolean;

  handleChange(evt) {
    this.$emit('input', evt.target.checked);
    this.$emit('change', evt);
  }
}
</script>

<style lang="scss" scoped>
@import '../../theme/index.scss';

.switcher-wrapper {
  position: relative;
  display: inline-block;
  width: 24px;
  height: 10px;

  &::before {
    position: absolute;
    top: 50%;
    left: 0;
    width: 100%;
    height: 4px;
    content: '';
    background-color: $slightFontColor;
    border-radius: 2px;
    transition: all 0.4s ease;
    transform: translate3D(0, -50%, 0);
    will-change: background-color;
  }

  &::after {
    position: absolute;
    top: 0;
    left: 3px;
    width: 10px;
    height: 10px;
    content: '';
    background-color: $defaultFontColor;
    border-radius: 50%;
    transition: all 0.4s ease;
    will-change: background-color, left;
  }

  input[type='checkbox'] {
    position: absolute;
    top: 0;
    left: 0;
    z-index: 1;
    width: 100%;
    height: 100%;
    cursor: pointer;
    opacity: 0;
  }
}

.switch-acitve {
  &::before {
    background-color: #a3c5fd;
  }

  &::after {
    left: 11px;
    background-color: $primaryFontColor;
  }
}
</style>
