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
import { defineComponent } from 'vue';

import { useI18n } from 'vue-i18n';

import './timeline-view-hidden.scss';

/** 折叠中间 View 时的一张隐藏卡片，点击展开全部 View */
export default defineComponent({
  name: 'TimelineViewHidden',
  props: {
    /** 被隐藏的 View 数量 */
    count: {
      type: Number,
      default: 0,
    },
  },
  emits: {
    expand: () => true,
  },
  setup(props, { emit }) {
    const { t } = useI18n();

    return () => (
      <div
        class='timeline-view-hidden'
        onClick={() => emit('expand')}
      >
        <i18n-t
          keypath='已折叠中间 {0} 个 View，{1}'
          tag='span'
        >
          <span class='hidden-count'>{props.count}</span>
          <span class='hidden-action'>{t('点击展开')}</span>
        </i18n-t>
      </div>
    );
  },
});
