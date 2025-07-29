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
import { Component, Emit, Model, Prop, Watch } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import './ai-level-select.scss';

interface IEvents {
  onChange: number | number[];
}

interface IProps {
  disabled?: boolean;
  value?: number | number[];
}

@Component
export default class AiLevelSelect extends tsc<IProps, IEvents> {
  /** 勾选的告警级别 */
  @Model('change', { required: true, type: [Number, Array] }) value: number | number[];
  /** 是否禁用 */
  @Prop({ type: Boolean, default: false }) disabled: boolean;
  /** 已选择告警级别方式 auto：智能生成 manual: 手动指定 */
  levelType: 'auto' | 'manual' = 'manual';
  localValue: number | number[] = 1;

  /** 告警级别方式 */
  levelTypeList = [
    { id: 'auto', name: this.$t('智能生成'), disabled: true },
    { id: 'manual', name: this.$t('手动指定'), disabled: false },
  ];

  /** 告警级别类型 */
  levelList = [
    { id: 1, name: this.$t('致命'), icon: 'icon-danger' },
    { id: 2, name: this.$t('预警'), icon: 'icon-mind-fill' },
    { id: 3, name: this.$t('提醒'), icon: 'icon-tips' },
  ];

  /** popover实例 */
  popoverInstance = null;

  @Watch('value', { immediate: true })
  watchValueChange(val) {
    this.localValue = val;
    this.levelType = Array.isArray(val) ? 'auto' : 'manual';
  }

  @Emit('change')
  valueChange() {
    return this.localValue;
  }

  /**
   * 告警方式切换事件
   * @param type 切换的告警方式
   */
  levelTypeChange(type: 'auto' | 'manual') {
    if (type === 'auto') this.localValue = [1, 2, 3];
    else {
      this.localValue = 1;
      this.popoverInstance?.destroy();
      this.popoverInstance = null;
    }
    this.valueChange();
  }

  /**
   * 展示告警级别弹出窗
   * @param el 挂载的DOM
   */
  showLevelPopover(el) {
    if (this.disabled) return;
    el.stopPropagation();
    if (!this.popoverInstance) {
      this.popoverInstance = this.$bkPopover(el.target, {
        content: this.$refs.aiLevelPopoverRef,
        trigger: 'manual',
        interactive: true,
        theme: 'light al-level-popover',
        arrow: true,
        placement: 'top',
        hideOnClick: false,
      });
    }
    this.popoverInstance?.show();
  }

  /**
   * 告警级别选择事件
   * @param val 改变后的值
   * @param oldVal 改变前的值
   */
  aiLevelChange(val: number[], oldVal: number[]) {
    if (val.length === 0) {
      this.localValue = oldVal;
    }
    this.valueChange();
  }

  /**
   * 页面点击事件，用于判断是否需要关闭popover
   * @param el 点击触发的DOM
   */
  handleDocumentClick(el) {
    if (this.popoverInstance && !this.popoverInstance.popper.contains(el.target)) {
      this.popoverInstance.hide();
    }
  }

  created() {
    document.addEventListener('click', this.handleDocumentClick);
  }

  destroyed() {
    this.popoverInstance?.destroy();
    this.popoverInstance = null;
    document.removeEventListener('click', this.handleDocumentClick);
  }

  render() {
    return (
      <div class='al-level'>
        <bk-select
          class='level-type-select simplicity-select'
          v-model={this.levelType}
          behavior='simplicity'
          clearable={false}
          disabled={this.disabled}
          onChange={this.levelTypeChange}
        >
          {this.levelTypeList.map(item => (
            <bk-option
              id={item.id}
              key={item.id}
              disabled={item.disabled}
              name={item.name}
            />
          ))}
        </bk-select>
        {this.levelType === 'auto' ? (
          <i
            class={['icon-monitor', 'icon-setting', this.disabled ? 'disabled' : '']}
            onClick={this.showLevelPopover}
          />
        ) : (
          <bk-select
            class='level-select'
            v-model={this.localValue}
            behavior='simplicity'
            clearable={false}
            disabled={this.disabled}
            ext-popover-cls='level-select-popover'
            prefix-icon={`icon-monitor ${this.levelList[(this.localValue as number) - 1].icon}`}
            onChange={this.valueChange}
          >
            {this.levelList.map(item => (
              <bk-option
                id={item.id}
                key={item.id}
                name={item.name}
              >
                <i class={`icon-monitor ${item.icon}`} />
                <span class='name'>{item.name}</span>
              </bk-option>
            ))}
          </bk-select>
        )}

        {this.levelType === 'auto' && (
          <div style={{ display: 'none' }}>
            <div
              ref='aiLevelPopoverRef'
              class='al-level-popover-content'
            >
              <span class='title'>
                {this.$t('输出级别')}
                <span class='msg'>({this.$t('至少选择一个')})</span>
              </span>
              <bk-checkbox-group
                v-model={this.localValue}
                onChange={this.aiLevelChange}
              >
                {this.levelList.map(level => (
                  <bk-checkbox
                    key={level.id}
                    value={level.id}
                  >
                    <i class={`icon-monitor ${level.icon}`} />
                    {level.name}
                  </bk-checkbox>
                ))}
              </bk-checkbox-group>
            </div>
          </div>
        )}
      </div>
    );
  }
}
