<!--
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
-->
<script setup>
  import { ref, watch, computed, nextTick, onMounted, onBeforeUnmount } from 'vue';

  import { TABLE_FOUNT_FAMILY } from '@/common/util';
  import useIntersectionObserver from '@/hooks/use-intersection-observer';
  import UseJsonFormatter from '@/hooks/use-json-formatter';
  import useLocale from '@/hooks/use-locale';
  import useStore from '@/hooks/use-store';
  import useTruncateText from '@/hooks/use-truncate-text';
  import { debounce } from 'lodash';

  const emit = defineEmits(['menu-click']);

  const props = defineProps({
    field: { type: Object, required: true },
    data: { type: Object },
    content: { type: [String, Number, Boolean], required: true },
  });

  const refContent = ref();
  const refFieldValue = ref();
  const store = useStore();
  const { $t } = useLocale();
  const isWrap = computed(() => store.state.tableLineIsWrap);
  const isLimitExpandView = computed(() => store.state.isLimitExpandView);
  const showAll = ref(false);
  const maxWidth = ref(0);
  const isIntersecting = ref(false);
  const isSegmentTagInit = ref(false);

  const handleMenuClick = event => {
    emit('menu-click', event);
  };

  const instance = new UseJsonFormatter({
    target: refContent,
    fields: [props.field],
    jsonValue: props.content,
    onSegmentClick: handleMenuClick,
  });

  const textTruncateOption = computed(() => ({
    fontSize: 12,
    text: props.content,
    maxWidth: maxWidth.value,
    font: `12px ${TABLE_FOUNT_FAMILY}`,
    showAll: isLimitExpandView.value || showAll.value,
  }));

  const { truncatedText, showMore } = useTruncateText(textTruncateOption);
  const renderText = computed(() => {
    if (showAll.value || isLimitExpandView.value || true) {
      return props.content;
    }

    return truncatedText.value;
  });

  const btnText = computed(() => {
    if (showAll.value) {
      return $t('收起');
    }

    return $t('更多');
  });

  let resizeObserver = null;

  const debounceSetSegmentTag = debounce(() => {
    if (!isIntersecting.value || (isSegmentTagInit.value && instance.config.jsonValue === renderText.value)) {
      return;
    }

    instance.config.jsonValue = props.content;
    instance.destroy?.();

    const appendText =
      showMore.value && !isLimitExpandView.value
        ? {
            text: btnText.value,
            onClick: handleClickMore,
            attributes: {
              class: `btn-more-action ${!showAll.value ? 'show-all' : ''}`,
            },
          }
        : undefined;
    instance.initStringAsValue(props.content, appendText);
  });

  watch(
    () => [renderText.value],
    () => {
      debounceSetSegmentTag();
    },
    {
      immediate: true,
    },
  );

  const handleClickMore = e => {
    e.stopPropagation();
    e.preventDefault();
    e.stopImmediatePropagation();

    showAll.value = !showAll.value;
  };

  const getCellElement = () => {
    return refContent.value?.parentElement;
  };

  const debounceUpdateSegmentTag = debounce(() => {
    const cellElement = getCellElement();

    if (cellElement) {
      const elementMaxWidth = cellElement.offsetWidth * 3;
      maxWidth.value = elementMaxWidth;
    }
  });

  const createResizeObserve = () => {
    const cellElement = getCellElement();
    if (cellElement) {
      const elementMaxWidth = cellElement.offsetWidth * 3;
      maxWidth.value = elementMaxWidth;

      // 创建一个 ResizeObserver 实例
      resizeObserver = new ResizeObserver(() => {
        debounceUpdateSegmentTag();
      });

      resizeObserver?.observe(getCellElement());
    }
  };

  useIntersectionObserver(refContent, entry => {
    isIntersecting.value = entry.isIntersecting;
    if (entry.isIntersecting) {
      // 进入可视区域重新计算宽度
      debounceSetSegmentTag();
    } else {
      if (refFieldValue.value) {
        debounceSetSegmentTag.cancel();
        refFieldValue.value.innerText = props.content;
      }
    }
  });

  onMounted(() => {
    debounceUpdateSegmentTag();
    createResizeObserve();
  });

  onBeforeUnmount(() => {
    const target = getCellElement();
    if (target) {
      resizeObserver?.unobserve(target);
    }
    resizeObserver?.disconnect();
    resizeObserver = null;
  });
</script>
<template>
  <div
    ref="refContent"
    :class="[
      'bklog-text-segment',
      'bklog-root-field',
      { 'is-wrap-line': isWrap, 'is-inline': !isWrap, 'is-show-long': isLimitExpandView, 'is-expand-all': showAll },
    ]"
  >
    <span
      style="display: none"
      class="field-name"
      ><span
        class="black-mark"
        :data-field-name="field.field_name"
      >
        {{ field.field_name }}
      </span></span
    >
    <span
      ref="refFieldValue"
      class="field-value"
      :data-field-name="field.field_name"
      >{{ renderText }}</span
    >
  </div>
</template>
<style lang="scss">
  .bklog-text-segment {
    position: relative;
    max-height: 60px;
    overflow: hidden;
    font:
      12px Menlo,
      Monaco,
      Consolas,
      Courier,
      'PingFang SC',
      'Microsoft Yahei',
      monospace;
    font-size: 12px;
    text-align: left;
    word-break: break-all;
    white-space: pre-line;

    &.is-expand-all {
      max-height: max-content;
    }

    &.is-show-long {
      max-height: max-content;

      .btn-more-action {
        display: none;
      }
    }

    span {
      line-height: 20px;

      &.segment-content {
        span {
          font:
            12px Menlo,
            Monaco,
            Consolas,
            Courier,
            'PingFang SC',
            'Microsoft Yahei',
            monospace;
        }

        .btn-more-action {
          position: absolute;
          right: 0;
          bottom: 2px;
          padding-left: 18px;
          color: #3a84ff;
          cursor: pointer;
          background-color: #fff;

          &.show-all {
            &::before {
              position: absolute;
              top: 50%;
              left: 4px;
              content: '...';
              transform: translateY(-50%);
            }
          }
        }
      }
    }

    &.is-inline {
      display: flex;
    }
  }
</style>
