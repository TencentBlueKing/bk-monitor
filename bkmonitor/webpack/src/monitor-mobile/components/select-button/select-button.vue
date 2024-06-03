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
  <span
    :class="['event-button', { 'event-button-active': active }]"
    @click="e => $emit('click', e)"
  >
    <i
      v-show="icon"
      :class="['icon-monitor', icon]"
    />
    <span class="text">{{ text }}</span>
  </span>
</template>
<script lang="ts">
import { Vue, Component, Prop } from 'vue-property-decorator';

@Component({
  name: 'event-type',
})
export default class EventType extends Vue {
  // 文字
  @Prop({ default: '' }) private text: string;

  // icon
  @Prop({ default: '' }) private icon: string;

  // 高亮
  @Prop({ default: false }) private active: boolean;
}
</script>
<style lang="scss" scoped>
@import '../../static/scss/variate.scss';
.event-button {
  display: flex;
  justify-content: center;
  align-items: center;
  height: 32px;
  border-radius: 4px;
  box-shadow: 0px 1px 0px 0px rgba(99, 101, 110, 0.05);
  box-sizing: border-box;
  border: 1px solid #fff;
  background-color: #fff;
  transition: all 0.2s ease-in-out;
  .text {
    color: $defaultFontColor;
    line-height: 20px;
    font-size: 14px;
    font-weight: 400;
  }
  .icon-monitor {
    display: flex;
    justify-content: center;
    align-items: center;
    width: 16px;
    height: 20px;
    margin-right: 7px;
    font-size: 16px;
  }
  .icon-danger {
    color: #ea3636;
  }
  .icon-mind-fill {
    color: #ff9c01;
  }
  .icon-tips {
    color: #ffd000;
  }
  .icon-user {
    color: #3a84ff;
  }
}
.event-button-active {
  border: 1px solid $primaryColor;
  background-color: #e1ecff;
  .text {
    color: $primaryColor;
  }
}
</style>
