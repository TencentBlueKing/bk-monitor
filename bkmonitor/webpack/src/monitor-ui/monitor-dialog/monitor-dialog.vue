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
  <transition
    name="monitor-dialog"
    @after-enter="afterEnter"
    @after-leave="afterLeave"
  >
    <div
      v-show="value"
      class="monitor-dialog-mask"
      :style="{ zIndex }"
      @click="handleMaskClick"
    >
      <div
        ref="monitor-dialog"
        class="monitor-dialog"
        :class="[{ 'full-screen': fullScreen }, headerTheme]"
        :style="{ width: width + 'px' }"
      >
        <i
          v-if="headerTheme !== 'header-bar'"
          class="bk-icon icon-close monitor-dialog-close"
          @click="handleClose"
        />
        <div
          v-if="needHeader"
          :class="['monitor-dialog-header', headerTheme]"
        >
          <slot name="header">
            {{ title }}
            <i
              v-if="headerTheme === 'header-bar'"
              class="bk-icon icon-close monitor-dialog-close"
              @click="handleClose"
            />
          </slot>
        </div>
        <div class="monitor-dialog-body">
          <slot />
        </div>
        <div
          v-if="needFooter"
          class="monitor-dialog-footer"
        >
          <slot name="footer">
            <bk-button
              v-show="showConfirmBtn"
              class="footer-btn"
              theme="primary"
              @click="handleClickConfirm"
            >
              {{ $t('确定') }}
            </bk-button>
            <bk-button
              theme="default"
              @click="handleClickCancel"
            >
              {{ $t('取消') }}
            </bk-button>
          </slot>
        </div>
      </div>
    </div>
  </transition>
</template>
<script lang="ts">
import { Component, Prop, Vue, Watch } from 'vue-property-decorator';

enum HeaderThemeType {
  headerBar = 'header-bar',
}
@Component
export default class MonitorDialog extends Vue {
  closed = false;
  // 是否显示
  @Prop({
    type: Boolean,
    default: false,
  })
  value: boolean;

  // 标题
  @Prop({
    type: String,
    default() {
      return '';
      // return this.$t('监控平台')
    },
  })
  title: string;

  // 宽度
  @Prop({
    type: [String, Number],
    default: 400,
  })
  width: number | string;

  // 是否插入到body下
  @Prop({
    type: Boolean,
    default: false,
  })
  appendToBody: boolean;

  // 是否点击mask关闭
  @Prop({
    type: Boolean,
    default: false,
  })
  maskClose: boolean;

  // 层级
  @Prop({
    type: [String, Number],
    default: 1000,
  })
  zIndex: number;

  // 是否需要footer
  @Prop({
    type: Boolean,
    default: true,
  })
  needFooter: boolean;

  // 关闭之前触发
  @Prop([Function])
  beforeClose: (args: any) => void;

  // 是否全屏
  @Prop([Boolean])
  fullScreen: boolean;

  // 是否需要展示header
  @Prop({
    type: Boolean,
    default: true,
  })
  needHeader: boolean;

  // header的主题
  @Prop({
    type: String,
    validator: theme => [HeaderThemeType.headerBar].includes(theme),
  })
  headerTheme: HeaderThemeType;

  // 是否需要展示确定按钮
  @Prop({
    type: Boolean,
    default: true,
  })
  showConfirmBtn: boolean;

  @Watch('value')
  onValueChange(val: boolean): void {
    if (val) {
      this.closed = false;
      this.appendToBody && document.body.appendChild(this.$el);
      this.$emit('on-open');
    } else {
      if (!this.closed) this.$emit('on-close');
    }
  }

  mounted() {
    this.value && this.appendToBody && document.body.appendChild(this.$el);
  }

  destroyed() {
    if (this.appendToBody && this.$el?.parentNode) {
      this.$el.parentNode.removeChild(this.$el);
    }
  }

  // 点击背景mask
  handleMaskClick(): void {
    if (!this.maskClose) return;
    this.handleClose();
  }

  // 点击关闭按钮
  handleClose(): void {
    this.$emit('on-cancel');
    if (typeof this.beforeClose === 'function') {
      this.beforeClose(this.hideDialog);
    } else {
      this.hideDialog();
    }
  }

  // 点击确定
  handleClickConfirm(): void {
    this.$emit('on-confirm');
  }

  // 点击取消
  handleClickCancel(): void {
    this.handleClose();
    this.$emit('on-cancel');
  }

  // 关闭弹窗
  hideDialog(cancel?: boolean): void {
    if (cancel !== false) {
      this.$emit('update:value', false);
      this.$emit('change', false);
      this.$emit('on-close');
      this.closed = true;
    }
  }

  // 打开动画执行完毕
  afterEnter(): void {
    this.$emit('on-opened');
  }

  // 关闭动画执行完毕
  afterLeave(): void {
    this.$emit('on-closed');
  }
}
</script>
<style lang="scss" scoped>
.monitor-dialog-mask {
  position: fixed;
  top: 0;
  right: 0;
  bottom: 0;
  left: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  background-color: rgba(0, 0, 0, 0.6);
  transition: opacity 0.3s;

  .monitor-dialog {
    position: relative;
    box-sizing: border-box;
    display: flex;
    flex-direction: column;
    min-height: 200px;
    padding: 20px 24px 0 24px;
    color: #63656e;
    background-color: rgb(255, 255, 255);
    background-clip: padding-box;
    border-width: 0px;
    border-radius: 2px;
    box-shadow: rgba(0, 0, 0, 0.15) 0px 4px 12px;
    transition: opacity 0.3s;

    &.header-bar {
      padding-top: 38px;
    }

    &.full-screen {
      position: fixed;
      top: 0;
      right: 0;
      bottom: 0;
      left: 0;
      z-index: 2001;

      /* stylelint-disable-next-line declaration-no-important */
      width: 0 !important;
      min-width: 100%;

      /* stylelint-disable-next-line declaration-no-important */
      height: 0 !important;
      min-height: 100%;
    }

    &-header {
      font-size: 20px;

      &.header-bar {
        position: absolute;
        top: 0;
        right: 0;
        left: 0;
        height: 52px;
        font-size: 16px;
        line-height: 52px;
        text-align: center;
        background: #fff;
        box-shadow:
          0 1px 0 0 #dcdee5,
          0 3px 4px 0 rgba(64, 112, 203, 0.06);

        .monitor-dialog-close {
          top: 14px;
          right: 28px;
          font-size: 24px;
        }
      }
    }

    &-body {
      flex: 1;
    }

    &-footer {
      display: flex;
      align-items: center;
      justify-content: flex-end;
      height: 50px;
      padding-right: 24px;
      margin: 0 -24px;
      background-color: #fafbfd;
      border-top: 1px solid #dcdee5;

      .footer-btn {
        margin-right: 10px;
        margin-left: auto;
      }
    }

    /* stylelint-disable-next-line no-descending-specificity */
    &-close {
      position: absolute;
      top: 10px;
      right: 10px;
      z-index: 2000;
      display: flex;
      align-items: center;
      justify-content: center;
      width: 24px;
      height: 24px;
      font-size: 16px;
      font-weight: bold;

      /* stylelint-disable-next-line no-descending-specificity */
      &:hover {
        cursor: pointer;
        background-color: #f0f1f5;
        border-radius: 50%;
      }
    }
  }
}

.monitor-dialog-enter-active {
  animation: monitor-dialog-in 0.3s;
}

.monitor-dialog-leave-active {
  animation: monitor-dialog-out 0.3s;
}

@keyframes monitor-dialog-in {
  0% {
    opacity: 0;
    transform: translate3d(0, -20px, 0);
  }

  100% {
    opacity: 1;
    transform: translate3d(0, 0, 0);
  }
}

@keyframes monitor-dialog-out {
  0% {
    opacity: 1;
    transform: translate3d(0, 0, 0);
  }

  100% {
    opacity: 0;
    transform: translate3d(0, -20px, 0);
  }
}
</style>
