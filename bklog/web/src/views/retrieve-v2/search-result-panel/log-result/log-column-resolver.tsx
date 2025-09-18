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
import { defineComponent, ref, type CreateElement, watch, computed } from 'vue';

import { formatDate, formatDateNanos, xssFilter } from '@/common/util';

export default defineComponent({
  props: {
    isIntersection: {
      type: Boolean,
      default: false,
    },
    content: {
      type: [Object, String, Number, Boolean],
      default: () => ({}),
    },
    maxHeight: {
      type: [String, Number],
      default: '100%',
    },
    fieldType: {
      type: String,
      default: '',
    },
    formatDate: {
      type: Boolean,
      default: true,
    },
  },
  setup(props, { slots }) {
    const isResolved = ref(props.isIntersection);
    const formatContent = () => {
      if (props.formatDate) {
        if (props.fieldType === 'date') {
          return formatDate(Number(props.content));
        }

        // 处理纳秒精度的UTC时间格式
        if (props.fieldType === 'date_nanos') {
          return formatDateNanos(props.content);
        }
      }
      return props.content || '--';
    };

    watch(
      () => [props.isIntersection],
      ([isIntersection]) => {
        if (isIntersection) {
          isResolved.value = true;
        }
      },
    );

    const renderPlaceholder = computed(() => {
      if (typeof props.content === 'object') {
        return JSON.stringify(props.content, null, 2);
      }

      return formatContent();
    });

    return (h: CreateElement) => {
      if (isResolved.value) {
        return slots.default?.();
      }

      return h(
        'div',
        {
          class: 'bklog-v3-column-placeholder',
          style: {
            '--max-height': props.maxHeight,
          },
          domProps: {
            innerHTML: xssFilter(renderPlaceholder.value) || '--',
          },
        },
        [],
      );
    };
  },
});
