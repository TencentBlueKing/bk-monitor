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
  <div class="alarm-footer">
    <van-button
      class="alarm-footer-btn"
      :disabled="disabled"
      :loading="loading"
      :type="type"
      @click="handleAlarmCheck"
    >
      <slot />
    </van-button>
  </div>
</template>
<script lang="ts">
import { Component, Emit, Prop, Vue } from 'vue-property-decorator';

import { Button } from 'vant';
@Component({
  name: 'footer-button',
  components: {
    [Button.name]: Button,
  },
})
export default class AlarmFooterBtn extends Vue {
  @Prop({ default: 'info' }) type: string;

  @Prop({ default: false }) disabled: boolean;

  @Prop({ default: false }) loading: boolean;

  @Emit('click')
  handleAlarmCheck(e: Event) {
    return e;
  }
}
</script>
<style lang="scss" scoped>
.alarm-footer {
  // height: 72px;
  position: fixed;
  right: 16px;
  bottom: 15px;
  left: 16px;
  background: linear-gradient(rgba(255, 255, 255, 0) 0, #fff 100%);

  :deep(button[disabled]) {
    background-color: #c4c6cc;
    box-shadow: 0px 3px 6px 0px rgba(152, 154, 157, 0.3);
    opacity: 1;
  }

  &-btn {
    display: flex;
    align-items: center;
    justify-content: center;
    width: calc(100vw - 32px);
    border: 0;
    border-radius: 4px;
    box-shadow: 0px 2px 6px 0px rgba(96, 89, 79, 0.3);
  }
}
</style>
