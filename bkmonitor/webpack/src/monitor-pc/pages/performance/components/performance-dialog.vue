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
  <transition name="ease">
    <div
      v-show="value"
      class="dialog"
    >
      <div class="dialog-header">
        <slot name="header">
          <span class="dialog-header-title">
            {{ title }}
          </span>
          <span class="dialog-header-close">
            <i
              class="icon-monitor icon-mc-close"
              @click="handleClose"
            />
          </span>
        </slot>
      </div>
      <div class="dialog-content">
        <slot />
      </div>
      <div class="dialog-footer">
        <slot name="footer">
          <bk-button
            :disabled="loading"
            :loading="loading"
            theme="primary"
            class="confirm-btn mr8"
            @click="handleConfirm"
          >
            {{ okText }}
          </bk-button>
          <bk-button
            :disabled="loading"
            :loading="loading"
            class="mr8"
            @click="handleCancel"
            >{{ cancelText }}</bk-button
          >
          <bk-button
            v-show="showUndo"
            :disabled="loading"
            :loading="loading"
            @click="handleUndo"
            >{{ $t('还原默认') }}</bk-button
          >
        </slot>
      </div>
    </div>
  </transition>
</template>
<script lang="ts">
import { Component, Emit, Model, Prop, Vue } from 'vue-property-decorator';

@Component({ name: 'performance-dialog' })
export default class Dialog extends Vue {
  @Model('change', { type: Boolean }) readonly value: boolean;
  @Prop({ default: '', type: String }) readonly title: string;
  @Prop({ default: '', type: String }) readonly okText: string;
  @Prop({ default: '', type: String }) readonly cancelText: string;
  @Prop({ default: false, type: Boolean }) readonly loading: boolean;
  @Prop({ default: true, type: Boolean }) private readonly showUndo: boolean;

  @Emit('close')
  @Emit('change')
  handleClose() {
    return !this.value;
  }

  @Emit('confirm')
  handleConfirm() {}

  @Emit('cancel')
  handleCancel() {}

  @Emit('undo')
  handleUndo() {}
}
</script>
<style lang="scss" scoped>
.dialog {
  position: absolute;
  top: 0;
  right: 24px;
  bottom: 0;
  z-index: 200;
  width: 360px;
  background: #fff;
  border-radius: 2px;
  box-shadow: 0px 3px 6px 0px rgba(0, 0, 0, 0.1);

  &-header {
    display: flex;
    justify-content: space-between;
    height: 56px;
    padding: 10px 6px 0 24px;
    border-bottom: 1px solid #f0f1f5;

    &-title {
      font-size: 20px;
      line-height: 28px;
    }

    &-close {
      margin-top: -4px;

      i {
        font-size: 32px;
        cursor: pointer;
      }
    }
  }

  &-content {
    max-height: calc(100% - 115px);
    overflow: auto;
  }

  &-footer {
    padding: 16px 0 0 20px;

    .mr8 {
      margin-right: 8px;
    }

    .confirm-btn {
      min-width: 86px;
      margin-right: 8px;
    }
  }
}
</style>
