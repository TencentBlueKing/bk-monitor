/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 *
 * Copyright (C) 2017-2025 Tencent.  All rights reserved.
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

import { type PropType, computed, defineComponent } from 'vue';

import { useI18n } from 'vue-i18n';

import './slider-header.scss';

export interface ISliderHeaderButton {
  /** 是否禁用 */
  disabled?: boolean;
  /** 图标类名（icon-monitor 图标） */
  icon?: string;
  /** 按钮标识，点击时作为事件参数抛出 */
  id: string;
  /** 是否显示，默认 true */
  isShow?: boolean;
  /** 按钮文案 */
  title: string;
}

/**
 * 侧栏（sideslider）头部公共组件：左侧标题区 + 右侧操作按钮区。
 * 不依赖任何 store，所有按钮点击仅向上抛事件，组件内部不做业务处理。
 *
 * 标题：props.title 或 title 插槽；
 * 操作按钮：默认 上一个 / 下一个 / 新开页 / 全屏，可通过 props.buttons 替换，或通过 buttons 插槽完全覆盖。
 */
export default defineComponent({
  name: 'SliderHeader',
  props: {
    /** 标题文本，超长省略并提示；也可通过 title 插槽自定义标题区 */
    title: {
      type: String,
      default: '',
    },
    /** 是否全屏状态，控制默认"全屏"按钮的图标与文案 */
    isFullscreen: {
      type: Boolean,
      default: false,
    },
    /** 操作按钮配置，传入后替换默认按钮集合；按钮点击统一通过事件抛出 */
    buttons: {
      type: Array as PropType<string[]>,
      default: () => [],
    },
  },
  emits: {
    /** 点击"上一个" */
    previous: () => true,
    /** 点击"下一个" */
    next: () => true,
    /** 点击"全屏 / 退出全屏"，参数为切换后的目标状态 */
    fullscreen: (val: boolean) => typeof val === 'boolean',
    /** 点击"新开页" */
    blank: () => true,
    /** 点击任意按钮（含自定义按钮）时触发 */
    buttonClick: (_id: string, _button: ISliderHeaderButton) => true,
  },
  setup(props, { emit, slots }) {
    const { t } = useI18n();

    /** 默认按钮集合：上一个 / 下一个 / 新开页 / 全屏 */
    const defaultButtons = computed<ISliderHeaderButton[]>(() => [
      { id: 'previous', title: t('上一个'), icon: 'icon-last-one' },
      { id: 'next', title: t('下一个'), icon: 'icon-next-one' },
      { id: 'blank', title: t('新开页'), icon: 'icon-a-NewPagexinkaiye' },
      {
        id: 'fullscreen',
        title: props.isFullscreen ? t('退出全屏') : t('全屏'),
        icon: props.isFullscreen ? 'icon-mc-unfull-screen' : 'icon-fullscreen',
      },
    ]);

    const buttonList = computed(() => defaultButtons.value.filter(button => props.buttons.includes(button.id)));

    const handleButtonClick = (button: ISliderHeaderButton) => {
      if (button.disabled) return;
      emit('buttonClick', button.id, button);
      switch (button.id) {
        case 'previous':
          emit('previous');
          break;
        case 'next':
          emit('next');
          break;
        case 'blank':
          emit('blank');
          break;
        case 'fullscreen':
          emit('fullscreen', !props.isFullscreen);
          break;
      }
    };

    return () => (
      <div class='slider-header'>
        <div class='slider-header-main'>
          {slots.title ? (
            slots.title()
          ) : (
            <div
              class='slider-header-title'
              v-overflow-tips
            >
              {props.title}
            </div>
          )}
        </div>
        <div class='slider-header-btn-group'>
          {slots.buttons
            ? slots.buttons()
            : buttonList.value
                .filter(button => button.isShow !== false)
                .map(button => (
                  <div
                    key={button.id}
                    class={{ 'btn-group-item': true, 'is-disabled': !!button.disabled }}
                    onClick={() => handleButtonClick(button)}
                  >
                    {button.icon ? <span class={`icon-monitor btn-item-icon ${button.icon}`} /> : null}
                    <span class='btn-text'>{button.title}</span>
                  </div>
                ))}
        </div>
      </div>
    );
  },
});
