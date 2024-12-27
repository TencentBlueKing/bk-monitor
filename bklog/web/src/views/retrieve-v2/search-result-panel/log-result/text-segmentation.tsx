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
import { ref, computed, inject, watch, defineComponent, Ref, h } from 'vue';

import useLocale from '@/hooks/use-locale';
import useResizeObserve from '@/hooks/use-resize-observe';
import useStore from '@/hooks/use-store';
import UseTextSegmentation from '@/hooks/use-text-segmentation';
import { debounce } from 'lodash';

import './text-segmentation.scss';
export default defineComponent({
  props: {
    field: { type: Object, required: true },
    data: { type: Object },
    content: { type: [String, Number, Boolean], required: true },
  },
  emits: ['menu-click'],
  setup(props, { emit }) {
    const refContent = ref();
    const refFieldValue = ref();
    const store = useStore();
    const { $t } = useLocale();
    const isWrap = computed(() => store.state.tableLineIsWrap);
    const isLimitExpandView = computed(() => store.state.isLimitExpandView);
    const showAll = ref(false);
    const hasEllipsis = ref(false);

    const isVisible: Ref<boolean> = inject('isRowVisible', ref(false));

    const handleMenuClick = event => {
      emit('menu-click', event);
    };

    const textSegmentInstance = new UseTextSegmentation({
      onSegmentClick: handleMenuClick,
      options: {
        content: props.content,
        field: props.field,
        data: props.data,
      },
    });

    const textContent = computed(() => `${props.content}`.replace(/<mark>/g, '').replace(/<\/mark>/g, ''));
    const renderText: Ref<{ child?: boolean | number | string; className?: string; tag?: string }[]> = ref([
      {
        child: textContent.value,
        tag: 'span',
        className: 'others-text',
      },
    ]);

    const btnText = computed(() => {
      if (showAll.value) {
        return ` ...${$t('收起')}`;
      }

      return ` ...${$t('更多')}`;
    });

    const debounceUpdateHasEllpsis = debounce(() => {
      hasEllipsis.value = (refContent.value?.offsetHeight ?? 0) < (refContent.value?.scrollHeight ?? 0);
    });

    const debounceSetSegmentTag = () => {
      renderText.value = textSegmentInstance?.getChildNodes();
    };

    const handleClickMore = e => {
      e.stopPropagation();
      e.preventDefault();
      e.stopImmediatePropagation();

      showAll.value = !showAll.value;
    };

    const getCellElement = () => {
      return refContent.value?.parentElement;
    };

    let timer = null;
    let isMounted = false;
    const debounceUpdateSegmentTag = () => {
      timer && clearTimeout(timer);
      timer = setTimeout(() => {
        debounceSetSegmentTag();
        isMounted = true;
      }, 100);
    };

    watch(
      () => [props.content, props.field, props.data],
      () => {
        textSegmentInstance?.update({
          options: {
            content: props.content,
            field: props.field,
            data: props.data,
          },
        });

        debounceUpdateSegmentTag();
      },
    );

    watch(
      () => [isVisible.value],
      () => {
        if (isMounted) {
          return;
        }

        if (isVisible.value) {
          debounceUpdateHasEllpsis();
          debounceUpdateSegmentTag();
          return;
        }

        timer && clearTimeout(timer);
      },
      { immediate: true },
    );

    useResizeObserve(getCellElement, debounceUpdateHasEllpsis);

    const handleSegmentClick = e => {
      textSegmentInstance?.getCellClickHandler(e);
    };

    const getBodyRender = () => {
      if (isVisible.value) {
        return renderText.value.map(({ child, className, tag }) =>
          h(
            tag,
            {
              class: className,
            },
            [child],
          ),
        );
      }

      return <span>{textContent.value}</span>;
    };

    const renderBody = () => {
      return (
        <div
          ref={refContent}
          class={[
            'bklog-text-segment',
            'bklog-root-field',
            {
              'is-wrap-line': isWrap.value,
              'is-inline': !isWrap.value,
              'is-show-long': isLimitExpandView.value,
              'is-expand-all': showAll.value,
            },
          ]}
          onClick={handleSegmentClick}
        >
          <span
            style='display: none'
            class='field-name'
          >
            <span
              class='black-mark'
              data-field-name={props.field.field_name}
            >
              {props.field.field_name}
            </span>
          </span>
          <span
            ref={refFieldValue}
            class='field-value'
            data-field-name={props.field.field_name}
          >
            <span class='segment-content'>{getBodyRender()}</span>
          </span>
          <span
            class={['btn-more-action', { 'is-show': hasEllipsis.value || showAll.value }]}
            onClick={handleClickMore}
          >
            {btnText.value}
          </span>
        </div>
      );
    };

    return { renderBody };
  },
  render() {
    return this.renderBody();
  },
});
