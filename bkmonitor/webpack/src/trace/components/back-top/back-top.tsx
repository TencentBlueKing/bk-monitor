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
import {
  type PropType,
  computed,
  defineComponent,
  getCurrentInstance,
  onBeforeUnmount,
  onMounted,
  shallowRef,
} from 'vue';

import './back-top.scss';

export default defineComponent({
  name: 'BackTop',
  props: {
    parentElement: {
      type: Object as PropType<HTMLElement>,
      default: () => null,
    },
    scrollTop: {
      type: Number,
      default: 200,
    },
  },
  setup(props) {
    const vmInstance = getCurrentInstance();

    /** 显隐状态 */
    const isShow = shallowRef(false);
    /** 当前滚动高度 */
    const currentScrollTop = shallowRef(0);

    const parentEl = computed(() => {
      return props.parentElement || vmInstance?.vnode?.el?.parentElement;
    });

    onMounted(() => {
      parentEl.value?.addEventListener?.('scroll', handleParentScroll);
    });

    onBeforeUnmount(() => {
      parentEl.value?.removeEventListener?.('scroll', handleParentScroll);
    });

    /**
     * @description: 监听滚动情况
     * @param {Event} evt
     * @return {*}
     */
    function handleParentScroll(evt: Event) {
      const target = evt.target as HTMLElement;
      const { scrollTop } = target;
      currentScrollTop.value = scrollTop;
      isShow.value = props.scrollTop <= scrollTop;
    }

    /**
     * @description: 点击回到顶部
     */
    function handleBackTop(enableAnimate = true) {
      return new Promise(resolve => {
        if (!enableAnimate) {
          parentEl?.value?.scrollTo?.({ top: 0, left: 0, behavior: 'instant' });
          resolve(true);
          return;
        }
        animate(currentScrollTop.value, scroll => {
          parentEl?.value?.scrollTo?.(0, scroll);
          if (scroll <= 0) resolve(true);
        });
      });
    }

    /**
     * @description: 回到顶部滚动动画
     * @param {number} scrollTop 当前滚动量
     * @param {Function} callback 回调函数
     * @return {*}
     */
    function animate(scrollTop: number, callback: (num: number) => void) {
      const MAX_STEP = 1000; // 最大步长
      const STEP_IN = 10; // 步长递增量
      let step = 20; // 运动步长
      let targetTop = scrollTop;
      const timer = setInterval(() => {
        targetTop = targetTop - step;
        if (targetTop <= 0) clearInterval(timer);
        step = step > MAX_STEP ? MAX_STEP : step + STEP_IN;
        callback(targetTop);
      }, 16);
    }

    return {
      isShow,
      handleBackTop,
    };
  },
  render() {
    return (
      <span
        class={['back-top-btn', { 'is-show': this.isShow }]}
        onClick={() => this.handleBackTop()}
      >
        {this.$slots.default() ?? 'UP'}
      </span>
    );
  },
});
