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
import { computed, defineComponent, ref } from 'vue';

import { getTargetElement } from '@/hooks/hooks-helper';
import useLocale from '@/hooks/use-locale';
import useRetrieveEvent from '@/hooks/use-retrieve-event';
import RetrieveHelper, { RetrieveEvent } from '@/views/retrieve-helper';


import './index.scss';

export default defineComponent({
  emits: ['scroll-top'],
  setup(_, { emit }) {
    const { $t } = useLocale();
    const offsetTop = ref(0);
    const GLOBAL_SCROLL_SELECTOR = RetrieveHelper.getScrollSelector();

    const { addEvent } = useRetrieveEvent();

    addEvent(RetrieveEvent.GLOBAL_SCROLL, event => {
      if (event.target) {
        offsetTop.value = (event.target as HTMLElement).scrollTop;
      }
    });

    const showBox = computed(() => offsetTop.value > 1000);
    const scrollTop = () => {
      getTargetElement(GLOBAL_SCROLL_SELECTOR)?.scrollTo(0, 0);
      emit('scroll-top');
    };

    const renderBody = () => (
      <span
        class={['bklog-v3-btn-scroll-top', { 'show-box': showBox.value }]}
        v-bk-tooltips={$t('返回顶部')}
        onClick={() => scrollTop()}
      >
        <i class='bklog-icon bklog-backtotop' />
      </span>
    );
    return {
      renderBody,
    };
  },
  render() {
    return this.renderBody();
  },
});
