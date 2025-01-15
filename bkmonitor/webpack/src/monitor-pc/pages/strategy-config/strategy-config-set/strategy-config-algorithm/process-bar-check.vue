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
  <ul class="check-bar">
    <li
      v-for="index in list.length - 1"
      :key="index"
      class="bar-item"
      :class="{ 'is-checked': value > list[index - 1] }"
      :style="{ '--before': list[index - 1], '--after': list[index] }"
      @click="$emit('change', list[index])"
    >
      <span
        v-if="value === list[index]"
        class="is-active"
      />
    </li>
  </ul>
</template>
<script>
export default {
  model: {
    prop: 'value',
    event: 'change',
  },
  props: {
    value: {
      type: Number,
      default: 25,
    },
    list: {
      type: Array,
      default() {
        return [0, 25, 50, 75, 100];
      },
    },
  },
};
</script>
<style lang="scss" scoped>
.check-bar {
  margin-left: 10px;
  display: flex;
  align-items: center;
  height: 20px;
  .bar-item {
    height: 4px;
    flex: 0 0 134px;
    width: 135px;
    margin-right: 2px;
    background: #dcdee5;
    position: relative;
    cursor: pointer;
    &.is-checked {
      background-color: #3a84ff;
    }
    &:before {
      counter-reset: progress var(--before);
      content: counter(progress);
      position: absolute;
      color: #979ba5;
      left: 0;
      top: 4px;
      bottom: -22px;
      transform: translate(-50%, 0);
    }
    &:first-child {
      border-top-left-radius: 2px;
      border-bottom-left-radius: 2px;
    }
    &:last-child {
      border-top-right-radius: 2px;
      border-bottom-right-radius: 2px;
      &:after {
        counter-reset: progress var(--after);
        content: counter(progress);
        position: absolute;
        color: #979ba5;
        right: 0;
        top: 4px;
        bottom: -22px;
        transform: translate(50%, 0);
      }
    }
    .is-active {
      border: 2px solid #3a84ff;
      border-radius: 50%;
      width: 8px;
      height: 8px;
      background: white;
      position: absolute;
      right: 0;
      top: 0;
      transform: translate(50%, -25%);
      z-index: 9;
    }
  }
}
</style>
