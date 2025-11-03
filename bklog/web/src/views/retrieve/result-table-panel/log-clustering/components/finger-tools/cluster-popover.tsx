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

import { Component, Ref } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import ClusterRuleDialog from './cluster-rule-dialog';

import type { Popover } from 'bk-magic-vue';

import './cluster-popover.scss';
const { $i18n } = window.mainComponent;

@Component
export default class ClusterPopover extends tsc<object> {
  @Ref('eventTippy') eventTippyRef: Popover;

  popoverInstance = null;
  isShowFeedbackDialog = false;
  isShowRuleDialog = false;
  intersectionObserver = null;
  feedRulesData = {
    textInputStr: '',
  };
  feedRules = {
    labelRules: [
      {
        validator: this.checkName,
        message: this.$t('{n}不规范, 包含特殊符号.', { n: this.$t('问题反馈') }),
        trigger: 'blur',
      },
      {
        max: 100,
        message: this.$t('不能多于{n}个字符', { n: 100 }),
        trigger: 'blur',
      },
    ],
  };

  confirmFeedback() {}

  handleClickFeedback() {
    this.destroyPopover();
    this.isShowFeedbackDialog = true;
  }
  handleClickRuleBtn() {
    this.destroyPopover();
    this.isShowRuleDialog = true;
  }
  checkName() {
    if (this.feedRulesData.textInputStr.trim() === '') {
      return true;
    }

    return /^[\u4e00-\u9fa5_a-zA-Z0-9`~!\s@#$%^&*()_\-+=<>?:"{}|,./;'\\[\]·~！@#￥%……&*（）——\-+={}|《》？：“”【】、；‘'，。、]+$/im.test(
      this.feedRulesData.textInputStr.trim(),
    );
  }

  handleClickPattern(e: Event) {
    this.destroyPopover();
    this.popoverInstance = this.$bkPopover(e.target, {
      content: this.eventTippyRef,
      arrow: true,
      trigger: 'click',
      theme: 'light',
      placement: 'bottom',
      interactive: true,
      allowHTML: true,
      onShow: () => this.handlePopoverShow(),
      onHidden: () => this.handlePopoverHide(),
    });
    this.popoverInstance.show(500);
  }

  destroyPopover() {
    this.popoverInstance?.hide();
    this.popoverInstance?.destroy();
    this.popoverInstance = null;
  }

  handleClick(option: string, isLink = false) {
    this.destroyPopover();
    this.$emit('event-click', option, isLink);
  }

  unregisterOberver() {
    if (this.intersectionObserver) {
      this.intersectionObserver.unobserve(this.eventTippyRef);
      this.intersectionObserver.disconnect();
      this.intersectionObserver = null;
    }
  }
  // 注册Intersection监听
  registerObserver() {
    if (this.intersectionObserver) {
      this.unregisterOberver();
    }
    this.intersectionObserver = new IntersectionObserver(entries => {
      for (const entry of entries) {
        if (this.intersectionObserver && entry.intersectionRatio <= 0) {
          this.destroyPopover();
        }
      }
    });
    this.intersectionObserver.observe(this.eventTippyRef);
  }
  handlePopoverShow() {
    setTimeout(this.registerObserver, 20);
  }
  handlePopoverHide() {
    this.unregisterOberver();
  }

  render() {
    const feedbackDialog = () => (
      <bk-dialog
        width='480'
        v-model={this.isShowFeedbackDialog}
        confirm-fn={this.confirmFeedback}
        header-position='left'
        title={$i18n.t('问题反馈')}
      >
        <bk-form
          ref='labelRef'
          form-type='vertical'
          {...{
            props: {
              model: this.feedRulesData,
              rules: this.feedRules,
            },
          }}
        >
          <bk-form-item
            label={$i18n.t('请输入反馈问题')}
            property='labelRules'
            required
          >
            <bk-input
              v-model={this.feedRulesData.textInputStr}
              maxlength={100}
              placeholder={$i18n.t('请输入')}
              rows={5}
              type='textarea'
            />
          </bk-form-item>
        </bk-form>
      </bk-dialog>
    );
    const popoverSlot = () => (
      <div style={{ display: 'none' }}>
        <div
          ref='eventTippy'
          class='cluster-event-tippy'
        >
          <div class='event-icons'>
            <div class='event-box'>
              <span
                class='event-btn'
                onClick={() => this.handleClick('copy')}
              >
                <i class='icon bklog-icon bklog-copy' />
                <span>{$i18n.t('复制')}</span>
              </span>
            </div>
            <div class='event-box'>
              <span
                class='event-btn'
                onClick={() => this.handleClick('show original')}
              >
                <i class='icon bk-icon icon-eye' />
                <span>{$i18n.t('查询命中pattern的日志')}</span>
              </span>
              <div
                class='new-link'
                v-bk-tooltips={this.$t('新开标签页')}
                onClick={e => {
                  e.stopPropagation();
                  this.handleClick('show original', true);
                }}
              >
                <i class='bklog-icon bklog-jump' />
              </div>
            </div>
            {/* <div class='event-box'>
              <span
                class='event-btn'
                onClick={() => this.handleClickRuleBtn('copy')}
              >
                <i class='icon bk-icon icon-plus-circle'></i>
                <span>{$i18n.t('添加正则')}</span>
              </span>
            </div>
            <div class='event-box top-line'>
              <span
                class='event-btn'
                onClick={() => this.handleClickFeedback()}
              >
                <i class='icon log-icon icon-icon-help-document-fill'></i>
                <span>{$i18n.t('问题反馈')}</span>
              </span>
            </div> */}
          </div>
        </div>
      </div>
    );
    return (
      <div
        class='pattern-line'
        onClick={this.handleClickPattern}
      >
        {this.$slots.default}
        {popoverSlot()}
        {feedbackDialog()}
        <ClusterRuleDialog v-model={this.isShowRuleDialog} />
      </div>
    );
  }
}
