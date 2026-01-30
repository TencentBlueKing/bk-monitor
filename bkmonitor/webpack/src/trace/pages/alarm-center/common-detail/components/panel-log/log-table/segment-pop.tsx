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

import { defineComponent, onUnmounted, shallowRef } from 'vue';

import { useI18n } from 'vue-i18n';
import { useTippy } from 'vue-tippy';

import { EClickMenuType } from './typing';

import './segment-pop.scss';

export default defineComponent({
  name: 'SegmentPop',
  emits: {
    clickMenu: (_value: { type: EClickMenuType; value: string }) => true,
  },
  setup(_props, { emit }) {
    const { t } = useI18n();

    const curValue = shallowRef('');
    const instance = shallowRef(null);
    const tipInstance = shallowRef(null);
    const handleClickMenu = (_event: MouseEvent, type: EClickMenuType) => {
      emit('clickMenu', {
        type,
        value: curValue.value,
      });
      instance.value?.hide();
    };

    const handleMouseEnter = (event: MouseEvent) => {
      tipInstance.value = useTippy(() => event.target as HTMLElement, {
        content: t('新开标签页'),
        placement: 'top',
        trigger: 'mouseenter',
        theme: 'dark',
        zIndex: 9999,
      });
      tipInstance.value?.show();
    };

    const contextMenuComponent = {
      render: () => {
        return (
          <div class='log-cell-segment-pop-content-menu'>
            <div
              class='log-cell-segment-pop-content-menu-item'
              onClick={(_e: MouseEvent) => handleClickMenu(_e, EClickMenuType.Copy)}
            >
              <span class='menu-item-icon icon-monitor icon-mc-copy' />
              <span>{t('复制')}</span>
            </div>
            <div
              class='log-cell-segment-pop-content-menu-item'
              onClick={(_e: MouseEvent) => handleClickMenu(_e, EClickMenuType.Include)}
            >
              <span class='menu-item-icon icon-monitor icon-jia' />
              <span>{t('添加到本次检索')}</span>

              <span
                class='link-btn'
                onMouseenter={handleMouseEnter}
              >
                <span
                  class='icon-monitor icon-mc-goto'
                  onClick={(_e: MouseEvent) => {
                    _e.stopPropagation();
                    handleClickMenu(_e, EClickMenuType.IncludeLink);
                  }}
                />
              </span>
            </div>
            <div
              class='log-cell-segment-pop-content-menu-item'
              onClick={(_e: MouseEvent) => handleClickMenu(_e, EClickMenuType.Exclude)}
            >
              <span class='menu-item-icon icon-monitor icon-jian' />
              <span>{t('从本次检索中排除')}</span>
              <span
                class='link-btn'
                onMouseenter={handleMouseEnter}
              >
                <span
                  class='icon-monitor icon-mc-goto'
                  onClick={(_e: MouseEvent) => {
                    _e.stopPropagation();
                    handleClickMenu(_e, EClickMenuType.ExcludeLink);
                  }}
                />
              </span>
            </div>
            <div
              class='log-cell-segment-pop-content-menu-item'
              onClick={(_e: MouseEvent) => handleClickMenu(_e, EClickMenuType.Link)}
            >
              <span class='menu-item-icon icon-monitor icon-jia' />
              <span>{t('新建检索')}</span>
              <span
                class='link-btn'
                onMouseenter={handleMouseEnter}
              >
                <span
                  class='icon-monitor icon-mc-goto'
                  onClick={(_e: MouseEvent) => {
                    _e.stopPropagation();
                    handleClickMenu(_e, EClickMenuType.Link);
                  }}
                />
              </span>
            </div>
          </div>
        );
      },
    };

    const handleClick = (event: MouseEvent, opt) => {
      event.stopPropagation();
      curValue.value = opt.value;
      if (!instance.value) {
        instance.value = useTippy(() => document.activeElement.shadowRoot?.querySelector('#app') || document.body, {
          content: contextMenuComponent,
          placement: 'bottom',
          trigger: 'click',
          theme: 'light common-monitor padding-0',
          hideOnClick: true,
          interactive: true,
          arrow: true,
          zIndex: 9998,
          offset: [0, 12],
        });
      }
      instance.value.setProps({
        triggerTarget: event.target as HTMLElement,
        getReferenceClientRect: () => ({
          width: 0,
          height: 0,
          top: event.clientY,
          bottom: event.clientY,
          left: event.clientX,
          right: event.clientX,
        }),
      });
      instance.value.show();
    };

    onUnmounted(() => {
      instance.value?.destroy?.();
      tipInstance.value?.destroy?.();
    });

    return {
      handleClick,
    };
  },
  render() {
    return (
      <>
        {this.$slots.default?.({
          onClick: this.handleClick,
        })}
      </>
    );
  },
});
