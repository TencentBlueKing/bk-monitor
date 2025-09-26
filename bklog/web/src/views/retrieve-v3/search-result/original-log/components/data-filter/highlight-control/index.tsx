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

import { defineComponent, ref, watch } from 'vue';

import { contextHighlightColor } from '@/common/util';

import './index.scss';

export default defineComponent({
  name: 'HighlightControl',
  props: {
    showType: {
      type: String,
      default: 'log',
    },
    lightList: {
      type: Array,
      default: () => [],
    },
  },
  setup(props, { expose }) {
    const jumpInputRef = ref<HTMLElement>();
    const catchViewIndex = ref(1);
    const lightSize = ref(0);
    const focus = ref(false);
    const isUpDisabled = ref(false);
    const isDownDisabled = ref(false);

    const lightToDarkColorMap = contextHighlightColor.reduce<Record<string, string>>(
      (colorMap, item) =>
        Object.assign(colorMap, {
          [item.light]: item.dark,
        }),
      {},
    );
    const darkToLightColorMap = contextHighlightColor.reduce<Record<string, string>>(
      (colorMap, item) =>
        Object.assign(colorMap, {
          [item.dark]: item.light,
        }),
      {},
    );

    let currentViewIndex = 1;
    let highlightHtmlList: any = [];

    const clearLightCatch = () => {
      lightSize.value = 0;
      currentViewIndex = 1;
      catchViewIndex.value = 1;
      highlightHtmlList = [];
    };

    const initLightItemList = (direction = '') => {
      highlightHtmlList = document.querySelectorAll('[data-index="light"]');
      lightSize.value = highlightHtmlList.length;
      if (lightSize.value) {
        const markDom = document.querySelector('.dialog-log-markdown');
        const markTop = markDom!.getBoundingClientRect().top;
        let isFindShow = false;
        for (let index = 0; index < highlightHtmlList.length; index++) {
          const iItemTop = highlightHtmlList[index].getBoundingClientRect().top;
          if (iItemTop > markTop) {
            currentViewIndex = Number(index) + 1;
            catchViewIndex.value = currentViewIndex;
            // 这个必须，不然偶现数值不匹配
            setInputIndexShow(currentViewIndex);
            const background = highlightHtmlList[index].style.background;
            highlightHtmlList[index].style.background = lightToDarkColorMap[background] || background;
            highlightHtmlList[index].style.fontWeight = '700';
            isFindShow = true;
            break;
          }
        }
        if (!isFindShow && direction !== 'top' && direction !== 'down') {
          catchViewIndex.value = highlightHtmlList.length;
          handelChangeLight(highlightHtmlList.length);
        }
      }
      checkUpDownDisabled();
    };

    watch(
      () => props.lightList,
      () => {
        if (props.lightList.length) {
          setTimeout(() => {
            initLightItemList();
          });
        } else {
          clearLightCatch();
        }
      },
      {
        immediate: true,
        deep: true,
      },
    );

    watch(
      () => props.showType,
      () => {
        if (lightSize.value) {
          const background = highlightHtmlList[currentViewIndex - 1].style.background;
          highlightHtmlList[currentViewIndex - 1].style.background = lightToDarkColorMap[background] || background;
        }
      },
    );

    const checkUpDownDisabled = () => {
      isUpDisabled.value = currentViewIndex === 1;
      isDownDisabled.value = currentViewIndex === lightSize.value;
    };

    const handelChangeLight = (page: number) => {
      catchViewIndex.value = currentViewIndex;
      currentViewIndex = page > highlightHtmlList.length ? 1 : page;
      const viewIndex = currentViewIndex - 1;
      const catchIndex = catchViewIndex.value - 1;
      highlightHtmlList[viewIndex].scrollIntoView({
        behavior: 'instant',
        block: 'center',
        inline: 'center',
      });
      highlightHtmlList[catchIndex].style.background =
        darkToLightColorMap[highlightHtmlList[catchIndex].style.background];
      highlightHtmlList[catchIndex].style.fontWeight = '500';
      highlightHtmlList[viewIndex].style.background =
        lightToDarkColorMap[highlightHtmlList[viewIndex].style.background];
      highlightHtmlList[viewIndex].style.fontWeight = '700';
      setInputIndexShow(currentViewIndex);
      checkUpDownDisabled();
    };

    const handleInputChange = event => {
      const $target = event.target;
      const value = parseInt($target.textContent, 10);
      // 无效值不抛出事件
      if (!value || value < 1 || value > lightSize.value || value === currentViewIndex) return;
      currentViewIndex = value;
    };

    const initHightlightList = () => {
      highlightHtmlList.forEach(item => {
        item.style.background = darkToLightColorMap[item.style.background] || item.style.background;
      });
    };

    const handleBlur = () => {
      initHightlightList();
      focus.value = false;
      if (typeof catchViewIndex.value !== 'string') {
        catchViewIndex.value = currentViewIndex;
      }
      handelChangeLight(currentViewIndex);
    };

    const handleKeyDown = e => {
      if (['Enter', 'NumpadEnter'].includes(e.code)) {
        initHightlightList();
        focus.value = true;
        handelChangeLight(currentViewIndex);
        e.preventDefault();
      }
    };

    const setInputIndexShow = (v: number) => {
      if (jumpInputRef.value) {
        jumpInputRef.value.textContent = String(v);
      }
    };

    expose({
      initLightItemList,
    });

    return () => (
      <div class='highlight-control-main'>
        <div class={['jump-input-wrapper', { focus: focus.value }]}>
          <span
            ref={jumpInputRef}
            class='jump-input'
            contenteditable
            onBlur={handleBlur}
            onFocus={() => (focus.value = true)}
            onInput={handleInputChange}
            onKeydown={handleKeyDown}
          >
            {catchViewIndex.value}
          </span>
          <span class={['page-total', { focus: focus.value }]}>/ {lightSize.value}</span>
        </div>
        <div class='jump-btns-main'>
          <div
            class={{ 'jump-btn': true, 'is-disabled': isUpDisabled.value }}
            onClick={() => {
              if (currentViewIndex === 1) return;
              handelChangeLight(currentViewIndex - 1);
            }}
          >
            <i class='bk-icon icon-arrows-up'></i>
          </div>
          <div
            style='margin-right: 6px'
            class={{
              'jump-btn': true,
              'is-disabled': isDownDisabled.value,
            }}
            onClick={() => {
              if (currentViewIndex === lightSize.value) return;
              handelChangeLight(currentViewIndex + 1);
            }}
          >
            <i class='bk-icon icon-arrows-down'></i>
          </div>
        </div>
      </div>
    );
  },
});
