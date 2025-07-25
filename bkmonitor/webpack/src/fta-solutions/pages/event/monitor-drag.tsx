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
import { Component, Emit, Prop, Watch } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import { Debounce } from 'monitor-common/utils/utils';

import './monitor-drag.scss';

interface IMonitorDragEvent {
  onTrigger: boolean;
  onMove: (left: number, swipeRight: boolean, cancelFn: () => void) => void;
}
interface IMonitorDragProps {
  isOnlyShowIndex?: boolean;
  isShow?: boolean;
  lineText?: string;
  maxWidth?: number;
  minWidth?: number;
  resetPosKey?: string;
  startPlacement?: string;
  theme?: ThemeType;
  toggleSet?: boolean;
  top?: number;
}
type ThemeType = 'line' | 'line-round' | 'normal' | 'simple-line-round';
@Component
export default class MonitorDrag extends tsc<IMonitorDragProps, IMonitorDragEvent> {
  @Prop({ type: Number, default: 200 }) minWidth: number;
  @Prop({ type: Number, default: 500 }) maxWidth: number;
  @Prop({ type: Boolean, default: false }) toggleSet: boolean;
  @Prop({ type: String, default: '' }) resetPosKey: string;
  @Prop({ type: String, default: 'right' }) startPlacement: string;
  /** 拖拽器的主题 */
  @Prop({ type: String, default: 'normal' }) theme: ThemeType;
  /** theme: line 时候生效 */
  @Prop({ type: String, default: window.i18n.tc('详情') }) lineText: string;
  /** 是否展开装填 */
  @Prop({ type: Boolean, default: false }) isShow: boolean;
  @Prop({ type: Boolean, default: false }) isInPanelView: boolean;
  @Prop({ type: Number, default: 0 }) top: number;
  @Prop({ type: Boolean, default: false }) isOnlyShowIndex: boolean;
  left = 0;
  defaultLeft = 0;
  show = true;
  isMoving = false;

  @Watch('toggleSet')
  handleToogleSetChange() {
    this.show = false;
    setTimeout(this.handleSetDefault, 320);
  }
  @Watch('resetPosKey')
  handleNeedResetPosChange() {
    this.show = false;
    setTimeout(this.handleSetDefault, 320);
  }
  mounted() {
    this.handleSetDefault();
    window.addEventListener('resize', this.handleClientResize);
  }
  activated() {
    this.handleSetDefault();
  }
  destroyed() {
    window.removeEventListener('resize', this.handleClientResize);
  }
  /** 监听视窗的resize变化 */
  @Debounce(100)
  handleClientResize() {
    this.handleSetDefault();
  }
  /**
   * @description: 初始化设置位置
   * @param {*}
   * @return {*}
   */
  handleSetDefault() {
    setTimeout(() => {
      const rect = this.$el.parentElement.getBoundingClientRect();
      this.left = this.startPlacement === 'left' ? rect.left - 3 : rect.width + rect.left - 3;
      this.$el.parentElement.style.position = 'relative';
      this.defaultLeft = this.left;
      this.show = true;
    }, 30);
  }
  /**
   * @description: mousdown触发
   * @param {object} e 事件参数
   * @return {*}
   */
  handleMouseDown(mouseDownEvent: MouseEvent) {
    const target = this.$el.parentElement;
    let mouseX = mouseDownEvent.clientX;
    // eslint-disable-next-line @typescript-eslint/no-this-alias
    const vm = this;
    if (this.isInPanelView && this.left) {
    }
    document.onselectstart = () => false;
    document.ondragstart = () => false;
    function handleMouseMove(event) {
      vm.isMoving = true;
      const swipeRight = event.clientX - mouseX >= 0;
      mouseX = event.clientX;
      document.body.style.cursor = 'col-resize';
      const rect = target.getBoundingClientRect();
      const isMax =
        vm.startPlacement === 'left'
          ? rect.width - event.clientX + rect.left < vm.minWidth
          : event.clientX - rect.left < vm.minWidth;
      if (isMax) {
        vm.$emit('move', 0, swipeRight, handleMouseUp);
        handleMouseUp();
        vm.left = vm.startPlacement === 'left' ? rect.left - 3 : rect.left + rect.width - 3;
        vm.$nextTick(() => (vm.left = vm.defaultLeft));
      } else {
        const left = Math.min(
          Math.max(
            vm.minWidth,
            vm.startPlacement === 'left' ? rect.width - event.clientX + rect.left : event.clientX - rect.left
          ),
          vm.maxWidth
        );
        vm.$emit('move', left, swipeRight, handleMouseUp);
        if (left >= vm.maxWidth) {
          handleMouseUp();
        }
        vm.left = vm.startPlacement === 'left' ? rect.left + rect.width - left - 3 : left + rect.left - 3;
      }
    }
    function handleMouseUp() {
      vm.isMoving = false;
      document.body.style.cursor = '';
      document.removeEventListener('mousemove', handleMouseMove);
      document.removeEventListener('mouseup', handleMouseUp);
      document.onselectstart = null;
      document.ondragstart = null;
    }
    document.addEventListener('mousemove', handleMouseMove);
    document.addEventListener('mouseup', handleMouseUp);
  }

  @Emit('trigger')
  handleTrigger() {
    return !this.isShow;
  }

  render() {
    return (
      <div
        style={{ left: this.theme !== 'normal' ? '' : `${this.left}px`, display: this.show ? 'flex' : 'none' }}
        class={['monitor-drag', this.theme, this.startPlacement]}
        onMousedown={this.handleMouseDown}
      >
        <div>
          {['line', 'line-round', 'simple-line-round'].includes(this.theme) && (
            <div class={['theme-line', this.startPlacement, { 'is-show': this.isShow }]}>
              <span class='line-wrap'>
                <span
                  style={{ top: `${this.top}px` }}
                  class={['line', { 'is-moving': this.isMoving }]}
                >
                  {this.theme === 'line-round' && (
                    <div class='line-round-wrap'>
                      {[1, 2, 3, 4, 5].map(i => (
                        <span
                          key={i}
                          class={`line-round ${i === 3 ? `line-square line-round-${i}` : `line-round-${i}`}`}
                        />
                      ))}
                    </div>
                  )}
                  {this.theme === 'simple-line-round' && (
                    <div class='simple-line-round-wrap'>
                      {[1, 2, 3, 4, 5].map(i => (
                        <span
                          key={i}
                          class='line-round'
                        />
                      ))}
                    </div>
                  )}
                </span>
              </span>
              {(this.lineText || this.isOnlyShowIndex) && (
                <span
                  class='line-trigger'
                  onClick={this.handleTrigger}
                >
                  {!this.isShow && <span class='trigger-text'>{this.lineText}</span>}
                  <i class='icon-monitor icon-arrow-left' />
                </span>
              )}
            </div>
          )}
        </div>
        {this.$slots?.default}
      </div>
    );
  }
}
