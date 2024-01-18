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
import { Component, Emit, Prop } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';
import { debounce } from 'throttle-debounce';

import './notice-guide.scss';

export interface IStepItem {
  target: string;
  title: string;
  content: string;
}
export interface INoticeCuideProps {
  stepList: IStepItem[];
  defaultStep?: number;
}
interface INoticeCuideEvent {
  onDone: void;
}
@Component
export default class NoticeGuide extends tsc<INoticeCuideProps, INoticeCuideEvent> {
  @Prop({ default: () => [] }) stepList: IStepItem[];
  @Prop({ default: 0 }) defaultStep: number;

  step = 0;
  tipStyles = {};
  placement = '';
  handleReize: any = null;
  showWrap = false;

  get currentStep() {
    return this.stepList[this.step] || null;
  }
  created() {
    this.step = this.defaultStep;
    this.handleReize = debounce(100, false, () => {
      this.step < this.stepList.length && this.activeStep();
    });
  }
  mounted() {
    this.init();
    window.addEventListener('resize', this.handleReize);
  }
  beforeDestroy() {
    this.clearActive();
    (this.$refs.wraper as Element)?.parentNode.removeChild(this.$refs.wraper as Element);
    window.removeEventListener('resize', this.handleReize);
  }
  /**
   * 指引初始化
   */
  init() {
    if (this.step < this.stepList.length) {
      document.body.appendChild(this.$refs.wraper as Element);
      window.requestIdleCallback(this.activeStep);
    }
  }
  /**
   * 步骤切换时激活目标步骤
   */
  activeStep() {
    this.$nextTick(() => {
      // const windowWidth = window.innerWidth;
      // const windowHieght = window.innerHeight;
      const currentStep = this.stepList[this.step];
      const $stepTarget = document.querySelector(currentStep.target);
      const moreDropdown = document.querySelector('.header-more-dropdown');

      this.clearActive();
      moreDropdown?.contains($stepTarget)
        ? moreDropdown.classList.add('guide-highlight')
        : $stepTarget.classList.add('guide-highlight');
      this.showWrap = true;
      setTimeout(() => {
        const {
          width
          // height
        } = (this.$refs.tip as Element).getBoundingClientRect();

        // 如果指引菜单在下拉菜单中，指引直接指向下拉菜单
        if (moreDropdown?.contains($stepTarget)) {
          const {
            bottom: moreDropdownBottom,
            left: moreDropdownLeft,
            width: moreListWidth
          } = moreDropdown.getBoundingClientRect();

          this.tipStyles = Object.freeze({
            top: `${moreDropdownBottom + 10}px`,
            left: `${moreDropdownLeft + (moreListWidth - width) / 2}px`
          });
          this.placement = 'bottom';
          return;
        }

        const {
          // top: targetTop,
          // right: targetRight,
          bottom: targeBottom,
          left: targetLeft,
          width: targetWidth
        } = $stepTarget.getBoundingClientRect();
        // let placement = 'left';

        // if (width > height && targeBottom < 0.3 * windowHieght) {
        //   placement = targeBottom > 0.5 * windowHieght ? 'top' : 'bottom';
        // } else {
        //   placement = targetLeft > 0.5 * windowWidth ? 'left' : 'right';
        // }

        // let styles = {};

        // if (placement === 'bottom') {
        //   styles = {
        //     top: `${targeBottom + 10}px`,
        //     left: `${targetLeft + (targetWidth - width) / 2}px`
        //   };
        // }
        // else if (placement === 'top') {
        //   styles = {
        //     top: `${windowHieght - targetTop - height - 10}px`,
        //     left: `${targetLeft + (targetWidth - width) / 2}px`
        //   };
        // } else if (placement === 'left') {
        //   styles = {
        //     top: `${targetTop}px`,
        //     right: `${windowWidth - targetLeft + 10}px`
        //   };
        // } else if (placement === 'right') {
        //   styles = {
        //     top: `${targetTop}px`,
        //     left: `${targetRight + 10}px`
        //   };
        // }
        this.tipStyles = Object.freeze({
          top: `${targeBottom + 10}px`,
          left: `${targetLeft + (targetWidth - width) / 2}px`
        });
        this.placement = 'bottom';
      });
    });
  }
  /**
   * 清空所有步骤的激活状态
   */
  clearActive() {
    document.body.querySelectorAll('.guide-highlight').forEach(el => {
      el.classList.remove('guide-highlight');
    });
  }
  /**
   * 完成指引
   */
  @Emit('done')
  doneGudie() {
    this.step = this.stepList.length;
    setTimeout(() => {
      (this.$refs.wraper as Element)?.parentNode.removeChild(this.$refs.wraper as Element);
    });
  }
  /**
   * 切换步骤
   */
  handleNext() {
    this.step += 1;
    this.clearActive();
    this.activeStep();
  }
  /**
   * 结束指引确认操作
   */
  handleFinish() {
    this.clearActive();
    this.doneGudie();
  }
  /**
   * 完成指引
   */
  handleStepChange() {
    this.step === this.stepList.length - 1 ? this.handleFinish() : this.handleNext();
  }
  render() {
    return (
      <transition name='guide-fade'>
        {this.step < this.stepList.length && (
          <div
            ref='wraper'
            class='novice-guide'
            style={{ display: this.showWrap ? 'flex' : 'none' }}
          >
            <div
              ref='tip'
              class={`step-box ${this.placement}`}
              style={this.tipStyles}
            >
              <div class='step-title'>{this.currentStep.title}</div>
              <div class='step-close-icon'>
                <i
                  class='icon-monitor icon-mc-close'
                  onClick={this.handleFinish}
                ></i>
              </div>
              <div class='step-content'>{this.currentStep.content}</div>
              <div class='step-action'>
                {
                  <div class='step-nums'>
                    {this.$t('第{step}步，共{total}步', { step: this.step, total: this.stepList.length })}
                  </div>
                }
                {
                  <div
                    class='action-btn'
                    onClick={this.handleStepChange}
                  >
                    {this.step === this.stepList.length - 1 ? this.$t('button-完成') : this.$t('下一步')}
                  </div>
                }
                <bk-button
                  text={true}
                  title='primary'
                  ext-cls='ukown-btn'
                  onClick={this.handleFinish}
                  v-show={this.step !== 3}
                >
                  {this.$t('知道了!')}
                </bk-button>
              </div>
              <div class='target-arrow'></div>
            </div>
          </div>
        )}
      </transition>
    );
  }
}
