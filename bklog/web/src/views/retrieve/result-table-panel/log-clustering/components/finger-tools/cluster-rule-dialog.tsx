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

import { Component, Emit, Ref, Watch, Model } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import { xssFilter } from '@/common/util';

import xiaojingAI from '../../../../../../images/xiaojingAI.svg';

import type { Popover, Form } from 'bk-magic-vue';

import './cluster-rule-dialog.scss';
const { $i18n } = window.mainComponent;

interface IProps {
  value: string;
}

@Component
export default class ClusterPopover extends tsc<IProps> {
  @Model('change', { type: Boolean, default: false }) value: IProps['value'];
  @Ref('occupy') occupyRef: Popover;
  @Ref('occupyForm') occupyFormRef: Form;
  @Ref('sample') sampleRef: HTMLElement;

  popoverInstance: Popover = null;
  isShowRuleDialog = false;

  ruleList = [{ ruleStr: '', originStr: '', occupy: '', isChecked: false }];
  checkedRuleList: string[] = [];
  occupyData = {
    textInputStr: '',
  };
  occupyOriginStr = '';
  occupyRules = {
    specification: [
      {
        validator: this.checkName,
        message: $i18n.t('{n}不规范, 包含特殊符号.', { n: $i18n.t('占位符') }),
        trigger: 'blur',
      },
      {
        required: true,
        message: $i18n.t('必填项'),
        trigger: 'blur',
      },
    ],
  };

  @Watch('value')
  handleValueChange(val: boolean) {
    if (val) {
      this.isShowRuleDialog = true;
    }
  }

  @Emit('change')
  handleCancel(val?: boolean) {
    this.isShowRuleDialog = false;
    return val ?? !this.value;
  }

  checkName() {
    if (this.occupyData.textInputStr.trim() === '') {
      return true;
    }

    return /^[\u4e00-\u9fa5_a-zA-Z0-9`~!\s@#$%^&*()_\-+=<>?:"{}|,./;'\\[\]·~！@#￥%……&*（）——\-+={}|《》？：“”【】、；‘'，。、]+$/im.test(
      this.occupyData.textInputStr.trim(),
    );
  }

  confirmRuleSubmit() {
    this.handleCancel();
  }

  handleClickFeedback() {
    this.isShowRuleDialog = true;
    this.destroyPopover();
  }

  destroyPopover() {
    this.occupyOriginStr = '';
    this.occupyData.textInputStr = '';
    this.popoverInstance?.hide();
    this.popoverInstance?.destroy();
    this.popoverInstance = null;
  }

  handleClick(option: string, isLink = false) {
    this.$emit('event-click', option, isLink);
  }

  handleMouseUpSample() {
    const selection = window.getSelection();
    const selectedText = selection.toString();
    if (selectedText) {
      const range = selection.getRangeAt(0);

      if (this.isAlreadyHighlighted(range)) {
        selection.removeAllRanges();
        return;
      }
      const wrapper = document.createElement('span');
      wrapper.classList.add('wrapper');
      wrapper.appendChild(range.extractContents());
      range.insertNode(wrapper);
      selection.removeAllRanges();
      this.$nextTick(() => {
        wrapper.addEventListener('popoverShowEvent', e => this.occupyTargetEvent(e, wrapper));
        wrapper.dispatchEvent(new Event('popoverShowEvent'));
      });
    }
  }

  isAlreadyHighlighted(range) {
    const fragment = range.cloneContents();
    const spans = fragment.querySelectorAll('span.wrapper');
    return spans.length > 0;
  }

  occupyTargetEvent(e: Event, wrapper: HTMLSpanElement) {
    this.destroyPopover();
    this.popoverInstance = this.$bkPopover(e.target, {
      content: this.occupyRef,
      arrow: true,
      trigger: 'manual',
      theme: 'light',
      placement: 'bottom-start',
      hideOnClick: false,
      interactive: true,
      allowHTML: true,
      boundary: 'window',
      onHidden: () => this.removeWrapper(wrapper),
    });
    this.occupyOriginStr = wrapper.innerText;
    this.popoverInstance.show();
  }

  removeWrapper(wrapper) {
    const parent = wrapper.parentNode;
    while (wrapper.firstChild) {
      parent?.insertBefore(wrapper.firstChild, wrapper);
    }
    parent.removeChild(wrapper);
  }

  // biome-ignore lint/complexity/noExcessiveCognitiveComplexity: reason
  findMatches(regexArray) {
    const text = this.sampleRef.innerText;
    const matches: Record<string, any>[] = [];

    // 对所有正则表达式进行匹配
    for (const regexStr of regexArray) {
      let regex: RegExp;
      try {
        regex = new RegExp(regexStr, 'g');
      } catch (e) {
        console.error(`Invalid regular expression: ${regexStr}`, e);
        return;
      }

      let match: any;
      while ((match = regex.exec(text)) !== null) {
        matches.push({
          start: match.index,
          end: match.index + match[0].length,
          text: match[0],
          regex: regexStr,
        });
      }
    }

    // 按起始位置和长度排序，以便于检测冲突
    matches.sort((a, b) => a.start - b.start || b.end - b.start - (a.end - a.start));

    const finalMatches: Record<string, any>[] = [];
    const conflicts: Record<string, any>[] = [];

    for (const match of matches) {
      let conflict = false;
      const conflictRegexes: string[] = [];

      for (const existingMatch of finalMatches) {
        if (match.start < existingMatch.end && match.end > existingMatch.start) {
          conflict = true;
          if (!conflictRegexes.includes(existingMatch.regex)) {
            conflictRegexes.push(existingMatch.regex);
          }
          existingMatch.conflictRegexes = existingMatch.conflictRegexes || [];
          if (!existingMatch.conflictRegexes.includes(match.regex)) {
            existingMatch.conflictRegexes.push(match.regex);
          }
          if (!conflicts.includes(existingMatch)) {
            conflicts.push(existingMatch);
          }
        }
      }

      if (conflict) {
        match.conflictRegexes = conflictRegexes;
        conflicts.push(match);
      } else {
        finalMatches.push(match);
      }
    }

    // 按起始位置排序
    finalMatches.sort((a, b) => a.start - b.start);
    conflicts.sort((a, b) => a.start - b.start);

    return { matches: finalMatches, conflicts };
  }

  async addLightTags(matches, conflicts) {
    const text = this.sampleRef.innerText;
    // 合并 matches 和 conflicts，并按起始位置排序
    const allMatches = [...matches, ...conflicts];
    // 按匹配的起始位置排序
    allMatches.sort((a, b) => a.start - b.start);

    let result = '';
    let lastIndex = 0;

    for (const match of allMatches) {
      const start = match.start;
      const end = match.end;
      const conflict = conflicts.find(newConflict => newConflict.start === start && newConflict.end === end);
      const className = `${conflict ? 'conflict' : ''} ${this.checkedRuleList.includes(match.regex) ? 'hit' : ''}`;
      const showTitleRegexes = conflict?.conflictRegexes
        .concat(match.regex)
        .map(item => item.replace(/'/g, '&apos;').replace(/"/g, '&quot;')); // 把单引号双引号换成转义字符
      const conflictRegexesStr = conflict
        ? `${showTitleRegexes.join(` ${$i18n.t('与')} `)} ${$i18n.t('存在冲突匹配结果')}`
        : '';

      if (start < lastIndex) {
        // 如果当前匹配项和上一个匹配项有重叠，跳过当前匹配项
        return;
      }

      if (start > lastIndex) {
        // 添加普通文本
        result += text.slice(lastIndex, start);
      }

      // 添加包裹匹配文本的 span 元素
      result += `<span class="${className}" data-index="${conflictRegexesStr}">${text.slice(start, end)}</span>`;

      lastIndex = end;
    }

    // 添加剩余的普通文本
    if (lastIndex < text.length) {
      result += text.slice(lastIndex);
    }

    this.sampleRef.innerHTML = xssFilter(result);
    await this.$nextTick();
    const spanList = document.querySelectorAll('span.conflict');
    for (const el of spanList) {
      el.addEventListener('mouseenter', e => {
        const instance = this.$bkPopover(e.target, {
          content: el.getAttribute('data-index'),
          arrow: true,
          boundary: 'window',
          placement: 'top',
          onHidden: () => {
            instance?.hide();
            instance?.destroy(true);
          },
        }) as Popover;
        instance?.show();
      });
    }
  }

  handleChangeRuleHighlight() {
    const ruleStrList: string[] = [];
    this.checkedRuleList = [];
    const filterRuleList = this.ruleList.filter(item => !!item.ruleStr);
    for (const item of filterRuleList) {
      ruleStrList.push(item.ruleStr);
      if (item.isChecked) {
        this.checkedRuleList.push(item.ruleStr);
      }
    }
    const { matches, conflicts } = this.findMatches(ruleStrList);
    this.addLightTags(matches, conflicts);
  }

  handleSubmitOccupy() {
    this.occupyFormRef.validate().then(() => {
      this.ruleList.push({
        ruleStr: '',
        originStr: this.occupyOriginStr,
        occupy: this.occupyData.textInputStr,
        isChecked: false,
      });
      this.destroyPopover();
    });
  }
  handleCancelOccupy() {
    this.occupyData.textInputStr = '';
    this.popoverInstance.hide();
  }
  handleDeleteRuleItem(index: number) {
    this.ruleList.splice(index, 1);
    this.handleChangeRuleHighlight();
  }
  render() {
    const popoverSlot = () => (
      <div style={{ display: 'none' }}>
        <div
          ref='occupy'
          class='occupy-popover'
        >
          <bk-form
            ref='occupyForm'
            form-type='vertical'
            {...{
              props: {
                model: this.occupyData,
                rules: this.occupyRules,
              },
            }}
          >
            <bk-form-item
              label={$i18n.t('占位符')}
              property='specification'
              required
            >
              <bk-input
                v-model={this.occupyData.textInputStr}
                placeholder={$i18n.t('请输入')}
                onEnter={this.handleSubmitOccupy}
              />
            </bk-form-item>
            <div class='btn-box'>
              <bk-button
                size='small'
                theme='primary'
                onClick={this.handleSubmitOccupy}
              >
                {$i18n.t('确认提取')}
              </bk-button>
              <bk-button
                size='small'
                onClick={this.handleCancelOccupy}
              >
                {$i18n.t('取消')}
              </bk-button>
            </div>
          </bk-form>
        </div>
      </div>
    );
    return (
      <div>
        <bk-dialog
          width='960'
          ext-cls='cluster-rule-dialog'
          v-model={this.isShowRuleDialog}
          confirm-fn={this.confirmRuleSubmit}
          header-position='left'
          title={$i18n.t('添加正则')}
        >
          <div class='sample-box'>
            <span class='title'>{$i18n.t('日志样例')}</span>
            <div
              ref='sample'
              class='sample-content'
              onMouseup={this.handleMouseUpSample}
            />
            <div class='tips'>
              <i class='log-icon icon-info-fill' />
              <span>{$i18n.t('左键框选字段，可提取并生成正则表达式')}</span>
            </div>
          </div>
          <div class='rule-box'>
            {!!this.ruleList.length && (
              <div class='rule-item title'>
                <span class='left'>{$i18n.t('正则表达式')}</span>
                <span>{$i18n.t('占位符')}</span>
              </div>
            )}
            {this.ruleList.map((item, index) => (
              <div
                key={`${index}-${item}`}
                class='rule-item'
              >
                <div class='left'>
                  <div class='input-content'>
                    <bk-checkbox
                      v-model={item.isChecked}
                      onChange={this.handleChangeRuleHighlight}
                    />
                    <bk-input
                      v-model={item.ruleStr}
                      onBlur={this.handleChangeRuleHighlight}
                      onEnter={this.handleChangeRuleHighlight}
                    />
                  </div>
                  <div class='btn-content'>
                    <i class='icon bk-icon icon-right-turn-line' />
                    {/** biome-ignore lint/nursery/useImageSize: reason */}
                    {/** biome-ignore lint/performance/noImgElement: reason */}
                    <img
                      class='xiaojing-AI'
                      alt='小鲸AI'
                      src={xiaojingAI}
                    />
                  </div>
                </div>
                <div class='right'>
                  <bk-input v-model={item.occupy} />
                  <i
                    class='bk-icon icon-minus-circle-shape icon'
                    onClick={() => this.handleDeleteRuleItem(index)}
                  />
                </div>
              </div>
            ))}
          </div>
        </bk-dialog>
        {popoverSlot()}
      </div>
    );
  }
}
