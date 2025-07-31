/*
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
 */
import { Component, Prop, Watch } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import './monitor-dialog.scss';

interface IMonitorDialogEvent {
  onCancel: void;
  onChange: boolean;
  onConfirm: void;
}
interface IMonitorDialogProps {
  appendToBody?: boolean;
  fullScreen?: boolean;
  maskClose?: boolean;
  needCloseIcon?: boolean;
  needFooter?: boolean;
  needHeader?: boolean;
  showConfirmBtn?: boolean;
  title?: string;
  value: boolean;
  width?: number | string;
  zIndex?: number;
  beforeClose?: (args: any) => void;
}
@Component
export default class MonitorDialog extends tsc<IMonitorDialogProps, IMonitorDialogEvent> {
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

  // 是否需要展示确定按钮
  @Prop({
    type: Boolean,
    default: true,
  })
  showConfirmBtn: boolean;

  // 是否需要展示关闭按钮
  @Prop({
    type: Boolean,
    default: true,
  })
  needCloseIcon: boolean;

  @Watch('value')
  onValueChange(val: boolean): void {
    if (val) {
      this.closed = false;
      this.appendToBody && document.body.appendChild(this.$el);
      this.$emit('open');
    } else {
      if (!this.closed) this.$emit('close');
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
    this.$emit('cancel');
    if (typeof this.beforeClose === 'function') {
      this.beforeClose(this.hideDialog);
    } else {
      this.hideDialog();
    }
  }

  // 点击确定
  handleClickConfirm(): void {
    this.$emit('confirm');
  }

  // 点击取消
  handleClickCancel(): void {
    this.handleClose();
    this.$emit('cancel');
  }

  // 关闭弹窗
  hideDialog(cancel?: boolean): void {
    if (cancel !== false) {
      this.$emit('update:value', false);
      this.$emit('change', false);
      this.$emit('close');
      this.closed = true;
    }
  }

  // 打开动画执行完毕
  afterEnter(): void {
    this.$emit('opened');
  }

  // 关闭动画执行完毕
  afterLeave(): void {
    this.$emit('closed');
  }
  renderContent() {
    return (
      <div
        ref='monitor-dialog'
        style={{
          width: `${this.width}px`,
        }}
        class={{
          'full-screen': this.fullScreen,
          'monitor-dialog': true,
        }}
        onClick={(e: Event) => {
          e.stopPropagation();
          // e.preventDefault();
        }}
      >
        {this.needCloseIcon && (
          <i
            class='bk-icon icon-close monitor-dialog-close'
            onClick={this.handleClose}
          />
        )}
        {this.needHeader && <div class='monitor-dialog-header'>{this.$slots.header || this.title}</div>}
        <div class='monitor-dialog-body'>{this.$slots.default}</div>
        {this.needFooter && (
          <div class='monitor-dialog-footer'>
            {this.$slots.footer || [
              <bk-button
                style={{ display: this.showConfirmBtn ? 'flex' : 'none' }}
                class='footer-btn'
                theme='primary'
                onClick={this.handleClickConfirm}
              >
                {window.i18n.t('确定')}
              </bk-button>,
              <bk-button
                theme='default'
                onClick={this.handleClickCancel}
              >
                {window.i18n.t('取消')}
              </bk-button>,
            ]}
          </div>
        )}
      </div>
    );
  }
  render() {
    return (
      <transition
        name='monitor-dialog'
        on-after-enter={this.afterEnter}
        on-after-leave={this.afterLeave}
      >
        <div
          style={{ zIndex: this.zIndex, display: this.value ? 'flex' : 'none' }}
          class='monitor-dialog-mask'
          onClick={this.handleMaskClick}
        >
          {this.renderContent()}
        </div>
      </transition>
    );
  }
}
