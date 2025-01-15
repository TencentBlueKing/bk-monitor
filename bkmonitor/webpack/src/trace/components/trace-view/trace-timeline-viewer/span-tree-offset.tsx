/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台社区版 (BlueKing PaaS Community Edition) available.
 *
 * Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
 *
 * 蓝鲸智云PaaS平台社区版 (BlueKing PaaS Community Edition) is licensed under the MIT License.
 *
 * License for 蓝鲸智云PaaS平台社区版 (BlueKing PaaS Community Edition):
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

import { type PropType, defineComponent, ref } from 'vue';

import _get from 'lodash/get';

import AngleDownIcon from '../icons/angle-down.svg';
import AngleRightIcon from '../icons/angle-right.svg';
import spanAncestorIds from '../utils/span-ancestor-ids';

import type { Span } from '../typings';

import './span-tree-offset.scss';

const SpanTreeOffsetProps = {
  // addHoverIndentGuideId: Function as PropType<(spanID: string) => void>,
  // removeHoverIndentGuideId: Function as PropType<(spanID: string) => void>,
  childrenVisible: {
    type: Boolean,
    required: false,
    default: false,
  },
  // hoverIndentGuideIds: {
  //   // type: Array as PropType<string[]>,
  //   default: new Set()
  // },
  onClick: {
    type: Function,
    required: false,
  },
  span: {
    type: Object as PropType<Span>,
  },
  showChildrenIcon: {
    type: Boolean,
    required: false,
    default: false,
  },
};

export default defineComponent({
  name: 'SpanTreeOffset',
  props: SpanTreeOffsetProps,
  setup(props) {
    const ancestorIds = ref<string[]>(spanAncestorIds(props.span));

    ancestorIds.value.push('root');

    ancestorIds.value.reverse();

    /**
     * If the mouse leaves to anywhere except another span with the same ancestor id, this span's ancestor id is
     * removed from the set of hoverIndentGuideIds.
     *
     * @param {Object} event - React Synthetic event tied to mouseleave. Includes the related target which is
     *     the element the user is now hovering.
     * @param {string} ancestorId - The span id that the user was hovering over.
     */
    const handleMouseLeave = (event: MouseEvent, ancestorId: string) => {
      if (
        !(event.relatedTarget instanceof HTMLSpanElement) ||
        _get(event, 'relatedTarget.dataset.ancestorId') !== ancestorId
      ) {
        // props.removeHoverIndentGuideId(ancestorId);
      }
    };

    /**
     * If the mouse entered this span from anywhere except another span with the same ancestor id, this span's
     * ancestorId is added to the set of hoverIndentGuideIds.
     *
     * @param {Object} event - React Synthetic event tied to mouseenter. Includes the related target which is
     *     the last element the user was hovering.
     * @param {string} ancestorId - The span id that the user is now hovering over.
     */
    const handleMouseEnter = (event: MouseEvent, ancestorId: string) => {
      if (
        !(event.relatedTarget instanceof HTMLSpanElement) ||
        _get(event, 'relatedTarget.dataset.ancestorId') !== ancestorId
      ) {
        // props.addHoverIndentGuideId(ancestorId);
      }
    };

    return {
      ancestorIds,
      handleMouseLeave,
      handleMouseEnter,
    };
  },

  render() {
    const {
      childrenVisible,
      onClick,
      showChildrenIcon,
      span,
      // hoverIndentGuideIds
    } = this.$props;
    const { hasChildren, spanID } = span as Span;
    const wrapperProps =
      hasChildren || showChildrenIcon ? { onClick, role: 'switch', 'aria-checked': childrenVisible } : null;

    const icon =
      (hasChildren && (childrenVisible ? AngleDownIcon : AngleRightIcon)) || (showChildrenIcon && AngleRightIcon);

    return (
      <span
        class={`span-tree-offset ${hasChildren ? 'is-parent' : ''}`}
        {...wrapperProps}
      >
        {this.ancestorIds.map(ancestorId => (
          <span
            key={ancestorId}
            class={[
              'span-tree-offset-indent-guide',
              // {
              //   'is-active': hoverIndentGuideIds.has(ancestorId)
              // }
            ]}
            data-ancestor-id={ancestorId}
            onMouseenter={event => this.handleMouseEnter(event, ancestorId)}
            onMouseleave={event => this.handleMouseLeave(event, ancestorId)}
          />
        ))}
        {icon && (
          <span
            class='span-tree-offset-icon-wrapper'
            onMouseenter={event => this.handleMouseEnter(event, spanID)}
            onMouseleave={event => this.handleMouseLeave(event, spanID)}
          >
            <img
              alt={icon}
              src={icon}
            />
          </span>
        )}
      </span>
    );
  },
});
