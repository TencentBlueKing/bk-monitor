<template>
  <div
    ref="refJsonFormatterCell"
    :class="[
      'bklog-json-formatter-root',
      {
        'is-wrap-line': !isOriginalMode && isWrap,
        'is-inline': !isOriginalMode && !isWrap,
        'is-json': formatJson,
        'is-hidden': !isRowIntersecting && isResolved,
        'show-all-word': showAllWords,
        'is-original-mode': isOriginalMode,
      },
    ]"
    :style="rootElementStyle"
  >
    <template v-for="item in rootList">
      <span
        class="bklog-root-field"
        :key="item.name"
      >
        <span
          class="field-name"
          :data-is-virtual-root="item.__is_virtual_root__"
          ><span
            class="black-mark"
            :data-field-name="item.name"
            >{{ getFieldName(item.name) }}</span
          ></span
        >
        <span
          class="field-value"
          :data-with-intersection="true"
          :data-field-name="item.name"
          :ref="item.formatter.ref"
          >{{ item.formatter.stringValue }}</span
        >
        <button
          v-if="isOriginalMode && item.originalValueMeta?.isTruncated"
          class="btn-original-value-action"
          type="button"
          :aria-expanded="isOriginalValueExpanded(item.name)"
          @click="handleOriginalValueActionClick($event, item.name)"
          @mousedown="stopOriginalValueActionEvent"
          @mouseup="stopOriginalValueActionEvent"
        >
          {{ getOriginalValueActionText(item.name) }}
        </button>
      </span>
    </template>
    <template v-if="showMoreAction">
      <span
        class="btn-more-action"
        @mouseup="handleMouseUp"
        @mousedown="handleMouseDown"
      >
        {{ btnText }}
      </span>
    </template>
  </div>
</template>
<script setup lang="ts">
  import { computed, inject, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue';

  // @ts-ignore
  import { getRowFieldValue } from '@/common/util';
  import useFieldNameHook from '@/hooks/use-field-name';

  import useLocale from '@/hooks/use-locale';
  import useRetrieveEvent from '@/hooks/use-retrieve-event';
  import JSONBig from 'json-bigint';
  import { debounce, isEmpty } from 'lodash-es';
  import {
    ORIGINAL_VALUE_EXPANDED_TEXT_LENGTH,
    ORIGINAL_VALUE_PREVIEW_TEXT_LENGTH,
    splitRenderText,
    stripMark,
    truncateMarkedTextByChars,
  } from '../storage/utils/retrieve-render-meta';
  import useJsonRoot from '../hooks/use-json-root';
  import useStore from '../hooks/use-store';
  import { BK_LOG_STORAGE } from '../store/store.type';
  import RetrieveHelper, { RetrieveEvent } from '../views/retrieve-helper';
  import { pageHighlightState } from '../views/retrieve-core/page-highlight';

  const emit = defineEmits(['menu-click']);
  const store = useStore();
  const { $t } = useLocale();

  const props = defineProps({
    jsonValue: {
      type: [Object, String, Number, Boolean],
      default: () => ({}),
    },
    fields: {
      type: [Array, Object],
      default: () => [],
    },
    renderMeta: {
      type: Object,
      default: null,
    },

    originalMode: {
      type: Boolean,
      default: false,
    },

    limitRow: {
      type: [Number, String, null],
      default: 3,
    },
  });

  const bigJson = JSONBig({ useNativeBigInt: true });
  const fieldNameHook = useFieldNameHook({ store });
  const refJsonFormatterCell = ref();
  const showAllText = ref(false);
  const expandedOriginalValueFields = ref<Record<string, boolean>>({});
  const originalValuePreviewTextCache = new Map<string, { text: string; isTruncated: boolean }>();
  const originalValuePreviewSegmentCache = new Map<string, any[]>();
  const expandedOriginalValueTexts = ref<Record<string, string>>({});
  const expandedOriginalValueSegments = ref<Record<string, any[]>>({});
  const hasScrollY = ref(false);
  const isRowIntersecting = inject('isRowIntersecting', ref(false));
  const isResolved = ref(isRowIntersecting.value);

  const isFormatDateField = computed(() => store.state.isFormatDate);
  const isWrap = computed(() => store.state.storage[BK_LOG_STORAGE.TABLE_LINE_IS_WRAP]);
  const isLimitExpandText = computed(() => store.state.storage[BK_LOG_STORAGE.IS_LIMIT_EXPAND_VIEW]);
  const formatJson = computed(() => store.state.storage[BK_LOG_STORAGE.TABLE_JSON_FORMAT]);
  const isOriginalMode = computed(() => props.originalMode);
  const limitRowNumber = computed(() => {
    if (props.limitRow === null || props.limitRow === undefined || props.limitRow === '') {
      return null;
    }

    const limitRow = Number(props.limitRow);
    return Number.isFinite(limitRow) && limitRow > 0 ? limitRow : null;
  });

  const isCurrentCellExpandText = computed(() => {
    if (isLimitExpandText.value) {
      return true;
    }

    return showAllText.value;
  });

  const rootElementStyle = computed(() => {
    if (isCurrentCellExpandText.value) {
      return {
        maxHeight: '50vh',
      };
    }

    if (limitRowNumber.value !== null) {
      return {
        maxHeight: `${20 * limitRowNumber.value}px`,
      };
    }

    return {
      maxHeight: undefined,
    };
  });

  const fieldList = computed(() => {
    if (Array.isArray(props.fields)) {
      return props.fields;
    }

    return [Object.assign({}, props.fields, { __is_virtual_root__: true })];
  });

  const showMoreTextAction = computed(() => {
    if (isOriginalMode.value) {
      return false;
    }

    if (limitRowNumber.value !== null && !isLimitExpandText.value) {
      return true;
    }

    return false;
  });

  const showMoreAction = computed(() => showMoreTextAction.value && (hasScrollY.value || showAllText.value));

  const showAllWords = computed(() => {
    return !showMoreTextAction.value || showAllText.value;
  });

  const btnText = computed(() => {
    if (showAllText.value) {
      return ` ...${$t('收起')}`;
    }

    return ` ...${$t('更多')}`;
  });

  const stopOriginalValueActionEvent = (e: MouseEvent) => {
    e.stopPropagation();
    e.preventDefault();
    e.stopImmediatePropagation();
  };

  const isOriginalValueExpanded = (fieldName: string) => !!expandedOriginalValueFields.value[fieldName];

  const getOriginalValueActionText = (fieldName: string) => {
    return isOriginalValueExpanded(fieldName) ? $t('收起') : $t('更多');
  };

  const getOriginalValueRenderText = (fieldName: string) => {
    const field = fieldList.value.find((item: any) => item.field_name === fieldName) ?? { field_name: fieldName };
    const [, val] = getFieldValue(field);
    const renderText = getDateFieldValue(field, getCellRender(val), false);
    return renderText?.replace?.(/<\/mark>/igm, '</mark>') ?? String(renderText ?? '');
  };

  const getOriginalValuePreviewInfo = (fieldName: string) => {
    if (!originalValuePreviewTextCache.has(fieldName)) {
      const renderText = getOriginalValueRenderText(fieldName);
      originalValuePreviewTextCache.set(fieldName, {
        text: truncateMarkedTextByChars(renderText, ORIGINAL_VALUE_PREVIEW_TEXT_LENGTH),
        isTruncated: stripMark(renderText).length > ORIGINAL_VALUE_PREVIEW_TEXT_LENGTH,
      });
    }

    return originalValuePreviewTextCache.get(fieldName);
  };

  const getOriginalValuePreviewText = (fieldName: string) => getOriginalValuePreviewInfo(fieldName)?.text;

  const isOriginalValueTruncated = (fieldName: string) => !!getOriginalValuePreviewInfo(fieldName)?.isTruncated;

  const getOriginalValueExpandedText = (fieldName: string) => {
    if (!expandedOriginalValueTexts.value[fieldName]) {
      expandedOriginalValueTexts.value = {
        ...expandedOriginalValueTexts.value,
        [fieldName]: truncateMarkedTextByChars(
          getOriginalValueRenderText(fieldName),
          ORIGINAL_VALUE_EXPANDED_TEXT_LENGTH,
        ),
      };
    }

    return expandedOriginalValueTexts.value[fieldName];
  };

  const getOriginalValueSegments = (fieldName: string) => {
    if (!isOriginalMode.value) {
      return props.renderMeta?.fieldSegments;
    }

    if (expandedOriginalValueFields.value[fieldName]) {
      if (!expandedOriginalValueSegments.value[fieldName]) {
        const expandedText = getOriginalValueExpandedText(fieldName);
        expandedOriginalValueSegments.value = {
          ...expandedOriginalValueSegments.value,
          [fieldName]: splitRenderText(expandedText),
        };
      }

      return {
        ...props.renderMeta?.fieldSegments,
        [fieldName]: expandedOriginalValueSegments.value[fieldName],
      };
    }

    if (isOriginalValueTruncated(fieldName)) {
      if (!originalValuePreviewSegmentCache.has(fieldName)) {
        originalValuePreviewSegmentCache.set(fieldName, splitRenderText(getOriginalValuePreviewText(fieldName)));
      }

      return {
        ...props.renderMeta?.fieldSegments,
        [fieldName]: originalValuePreviewSegmentCache.get(fieldName),
      };
    }

    return props.renderMeta?.fieldSegments;
  };

  const getOriginalValueDisplayText = (fieldName: string, fallback: any) => {
    if (!isOriginalMode.value) {
      return fallback;
    }

    const renderText = expandedOriginalValueFields.value[fieldName]
      ? getOriginalValueExpandedText(fieldName)
      : getOriginalValuePreviewText(fieldName);

    return renderText?.replace?.(/<\/?mark>/igm, '') ?? fallback;
  };

  const resetOriginalValueRenderedFlag = (fieldName: string) => {
    const root = refJsonFormatterCell.value as HTMLElement | undefined;
    const elements = root?.querySelectorAll?.('.field-value[data-field-name]') ?? [];
    for (const element of Array.from(elements) as HTMLElement[]) {
      if (element.getAttribute('data-field-name') === fieldName) {
        element.removeAttribute('data-has-word-split');
      }
    }
  };

  const resetOriginalValueRenderedFlags = () => {
    if (!isOriginalMode.value) return;

    const root = refJsonFormatterCell.value as HTMLElement | undefined;
    const elements = root?.querySelectorAll?.('.field-value[data-field-name][data-has-word-split]') ?? [];
    for (const element of Array.from(elements) as HTMLElement[]) {
      const fieldName = element.getAttribute('data-field-name');
      if (fieldName && isOriginalValueTruncated(fieldName)) {
        element.removeAttribute('data-has-word-split');
      }
    }
  };

  const handleOriginalValueActionClick = (e: MouseEvent, fieldName: string) => {
    stopOriginalValueActionEvent(e);
    RetrieveHelper.jsonFormatter.setIsExpandNodeClick(true);
    expandedOriginalValueFields.value = {
      ...expandedOriginalValueFields.value,
      [fieldName]: !expandedOriginalValueFields.value[fieldName],
    };
    nextTick(() => {
      resetOriginalValueRenderedFlag(fieldName);
      debounceUpdate();
      scheduleSetIsOverflowY();
      RetrieveHelper.fire(RetrieveEvent.RESULT_ROW_BOX_RESIZE);
    });
  };

  let mousedownItem = null;
  const handleMouseDown = e => {
    e.stopPropagation();
    e.preventDefault();
    e.stopImmediatePropagation();
    mousedownItem = e.target;
  };

  const handleMouseUp = e => {
    e.stopPropagation();
    e.preventDefault();
    e.stopImmediatePropagation();
    if (mousedownItem === e.target) {
      RetrieveHelper.jsonFormatter.setIsExpandNodeClick(true);
      showAllText.value = !showAllText.value;
      scheduleSetIsOverflowY();
    }

    mousedownItem = null;
  };

  const onSegmentClick = args => {
    emit('menu-click', args);
  };
  const scheduleSetIsOverflowY = () => {
    nextTick(() => {
      requestAnimationFrame(() => {
        setIsOverflowY();
      });
    });
  };
  const { updateRootFieldOperator, setExpand, setEditor, destroy } = useJsonRoot({
    fields: fieldList.value,
    onSegmentClick,
    onSegmentRenderUpdate: scheduleSetIsOverflowY,
  });

  const convertToObject = val => {
    if (typeof val === 'string' && formatJson.value) {
      if (/^(\{|\[)/.test(val)) {
        try {
          return bigJson.parse(val);
        } catch (e) {
          if (/<mark>(-?\d+\.?\d*)<\/mark>/.test(val)) {
            console.warn(`${e.name}: ${e.message}; `, e);

            return convertToObject(val.replace(/<mark>(-?\d+\.?\d*)<\/mark>/gim, '$1'));
          }
          return val;
        }
      }
    }

    return val;
  };

  const getDateFieldValue = (field, content, formatDate) => {
    if (formatDate && ['date_nanos', 'date'].includes(field.field_type)) {
      const timezone = store.state.indexItem.timezone;
      return RetrieveHelper.formatTimeZoneValue(content, field.field_type, timezone);
    }

    return content !== null && content !== undefined && content !== '' ? content : '--';
  };

  const getFieldValue = field => {
    if (formatJson.value) {
      if (typeof props.jsonValue === 'string') {
        return [convertToObject(props.jsonValue), props.jsonValue];
      }

      if (typeof props.jsonValue === 'object') {
        const fieldValue = getRowFieldValue(props.jsonValue, field);
        return [convertToObject(fieldValue), fieldValue];
      }

      return [props.jsonValue, props.jsonValue];
    }

    if (typeof props.jsonValue === 'object') {
      const fieldValue = getRowFieldValue(props.jsonValue, field);
      return [fieldValue, fieldValue];
    }

    return [props.jsonValue, props.jsonValue];
  };

  const getCellRender = (val: unknown) => {
    if (typeof val === 'object') {
      try {
        return JSON.stringify(val, null, 2);
      } catch (e) {
        console.warn(`JSON.stringify error: ${e.name}: ${e.message}; `, e);
        return String(val);
      }
    }

    return val;
  };

  const formatEmptyObject = (val: unknown) => {
    if (typeof val === 'object') {
      return isEmpty(val) ? '--' : val;
    }

    return val;
  };

  const getFieldFormatter = (field, formatDate) => {
    const [objValue, val] = getFieldValue(field);
    const strVal = getDateFieldValue(field, getCellRender(val), formatDate);
    return {
      ref: ref(),
      isJson: typeof objValue === 'object' && objValue !== undefined,
      value: formatEmptyObject(getDateFieldValue(field, objValue, formatDate)),
      stringValue: strVal?.replace?.(/<\/?mark>/igm, '') ?? strVal,
      field,
    };
  };

  const getFieldName = field => fieldNameHook.getFieldName(field);

  const rootList = computed(() => {
    return fieldList.value.map((f: any) => {
      const shouldFormatDate = isFormatDateField.value && !!f.__is_virtual_root__;
      const formatter = getFieldFormatter(f, shouldFormatDate);
      const originalValueDisplayText = getOriginalValueDisplayText(f.field_name, formatter.stringValue);
      const shouldUseOriginalValueText = isOriginalMode.value && isOriginalValueTruncated(f.field_name);
      return {
        name: f.field_name,
        type: f.field_type,
        formatter: {
          ...formatter,
          isJson: shouldUseOriginalValueText ? false : formatter.isJson,
          value: shouldUseOriginalValueText ? originalValueDisplayText : formatter.value,
          stringValue: shouldUseOriginalValueText ? originalValueDisplayText : formatter.stringValue,
          precomputedSegments: shouldFormatDate ? undefined : getOriginalValueSegments(f.field_name),
        },
        originalValueMeta: {
          isTruncated: shouldUseOriginalValueText,
        },
        __is_virtual_root__: !!f.__is_virtual_root__,
      };
    });
  });

  const depth = computed(() => store.state.storage[BK_LOG_STORAGE.TABLE_JSON_FORMAT_DEPTH]);

  const debounceUpdate = debounce(() => {
    updateRootFieldOperator(rootList.value as any, depth.value);
    setEditor(depth.value);
    isResolved.value = true;
    setTimeout(() => {
      RetrieveHelper.highlightElement(refJsonFormatterCell.value);
      setIsOverflowY();
    });
  });

  const setIsOverflowY = () => {
    if (refJsonFormatterCell.value) {
      const { offsetHeight, scrollHeight } = refJsonFormatterCell.value;
      hasScrollY.value = offsetHeight > 0 && scrollHeight > offsetHeight;
      return;
    }

    hasScrollY.value = false;
  };

  watch(
    // renderMeta 会在日志行异步渲染/高亮回填时更新；它只影响内容重绘，不应重置用户手动展开状态。
    () => [props.limitRow, props.jsonValue, props.fields, isLimitExpandText.value, isOriginalMode.value],
    () => {
      showAllText.value = false;
      expandedOriginalValueFields.value = {};
      originalValuePreviewTextCache.clear();
      originalValuePreviewSegmentCache.clear();
      expandedOriginalValueTexts.value = {};
      expandedOriginalValueSegments.value = {};
      hasScrollY.value = false;
      scheduleSetIsOverflowY();
    },
  );

  watch(
    () => [isRowIntersecting.value],
    () => {
      if (isRowIntersecting.value && !isResolved.value) {
        debounceUpdate();
      }
    },
  );

  watch(
    () => [props.jsonValue, props.fields, props.renderMeta, formatJson.value, pageHighlightState.version, expandedOriginalValueFields.value],
    () => {
      if (isResolved.value) {
        resetOriginalValueRenderedFlags();
        debounceUpdate();
      }
    },
    {
      immediate: true,
    },
  );

  watch(
    () => [depth.value],
    () => {
      setExpand(depth.value);
    },
  );

  const { addEvent } = useRetrieveEvent();
  addEvent(RetrieveEvent.RESULT_ROW_BOX_RESIZE, setIsOverflowY);

  onMounted(() => {
    setIsOverflowY();
  });

  onBeforeUnmount(() => {
    destroy();
  });
</script>
<style lang="scss">
  @import '../global/json-view/index.scss';

  .bklog-json-formatter-root {
    position: relative;
    width: 100%;
    overflow: hidden;
    font-family: var(--bklog-v3-row-ctx-font);
    font-size: var(--table-fount-size);
    line-height: 20px;
    color: var(--table-fount-color);
    text-align: left;

    .bklog-scroll-box {
      max-height: 50vh;
      overflow: auto;
      transform: translateZ(0); /* 强制开启GPU加速 */
      will-change: transform;
    }

    .bklog-scroll-cell {
      word-break: break-all;

      span {
        content-visibility: auto;
        contain-intrinsic-size: 0 60px; /* 预估初始高度 */
      }
    }

    mark {
      border-radius: 4px;
      padding: 1px 2px;
    }

    mark.result-highlight {
      background-color: #faeeb1;
    }

    mark.page-highlight {
      border-radius: 4px;
    }

    mark.result-highlight.page-highlight {
      box-shadow: inset 0 -2px 0 rgb(255 128 0 / 70%);
    }

    .btn-more-action {
      position: absolute;
      right: 4px;
      bottom: 0px;
      color: #3a84ff;
      cursor: pointer;
      background-color: #fff;
    }

    &.is-original-mode {
      overflow: visible;
      max-height: none !important;
      white-space: normal;

      > .bklog-root-field {
        display: inline !important;
        max-width: none;
        margin-right: 8px;
        white-space: normal;
        word-break: break-all;
        vertical-align: baseline;
      }

      .field-name,
      .field-value,
      .field-value[data-with-intersection],
      .field-value .segment-content,
      .field-value .bklog-scroll-cell,
      .field-value span,
      .field-value mark,
      .valid-text {
        display: inline !important;
        white-space: normal;
      }

      .field-value,
      .field-value[data-with-intersection] {
        max-height: none !important;
        overflow: visible !important;
        word-break: break-all;
        overflow-wrap: anywhere;
      }

      .btn-more-action {
        display: none;
      }

      .btn-original-value-action {
        display: inline !important;
        padding: 0;
        margin: 0 4px 0 2px;
        font: inherit;
        line-height: inherit;
        color: #3a84ff;
        vertical-align: baseline;
        cursor: pointer;
        background: transparent;
        border: 0;
        appearance: none;
      }
    }

    .bklog-root-field {
      display: inline-block; // 修复内联元素基线对齐导致的 1px 差异
      margin-right: 4px;
      line-height: 20px;
      vertical-align: top; // 确保顶部对齐，避免基线对齐问题

      .bklog-json-view-row {
        word-break: break-all;
      }

      [data-with-intersection] {
        font-family: var(--bklog-v3-row-ctx-font);
        font-size: var(--table-fount-size);
        color: var(--table-fount-color);
        white-space: pre-wrap;
      }

      // &:not(:first-child) {
      //   margin-top: 1px;
      // }

      .field-name {
        min-width: max-content;

        .black-mark {
          width: max-content;
          padding: 1px 2px;
          font-family: var(--bklog-v3-row-tag-font);
          font-weight: 500;
          color: #16171a;
          background-color: #ebeef5;
          border-radius: 4px;
        }

        &::after {
          content: ':';
        }

        &[data-is-virtual-root='true'] {
          display: none;
        }
      }

      mark {
        background-color: rgb(250, 238, 177);

        &.valid-text {
          white-space: pre-wrap;
        }
      }

      .valid-text {
        :hover {
          color: #3a84ff;
          cursor: pointer;
        }
      }
    }

    &:not(.is-json) {
      .bklog-root-field {
        .field-value {
          max-height: 50vh;
          overflow: hidden;
        }
      }
    }

    &.show-all-word {
      .bklog-root-field {
        .field-value {
          max-height: 50vh;
          overflow: auto;

          &::-webkit-scrollbar {
            width: 6px;
            background: #fff;
          }

          &::-webkit-scrollbar-thumb {
            background: #dcdee5;
            border-radius: 2px;
          }
        }
      }
    }

    &.is-hidden {
      visibility: hidden;
    }

    .segment-content {
      font-family: var(--bklog-v3-row-ctx-font);
      font-size: var(--table-fount-size);
      line-height: 20px;
      white-space: pre-wrap;

      span {
        width: max-content;
        min-width: 4px;
        font-family: var(--bklog-v3-row-ctx-font);
        font-size: var(--table-fount-size);
        color: var(--table-fount-color);
        white-space: pre-wrap;
      }

      .menu-list {
        position: absolute;
        display: none;
      }

      .valid-text {
        cursor: pointer;

        &.focus-text,
        &:hover {
          color: #3a84ff;
        }
      }

      .null-item {
        display: inline-block;
        min-width: 6px;
      }
    }

    &.is-inline {
      .bklog-root-field {
        display: inline-flex;
        word-break: break-all;
        vertical-align: top; // 确保顶部对齐，避免基线对齐问题

        .segment-content {
          word-break: break-all;
        }
      }
    }

    &.is-json {
      // display: inline-flex;
      width: 100%;
    }

    &.is-wrap-line {
      display: flex;
      flex-direction: column;

      .bklog-root-field {
        display: flex;

        .field-value {
          word-break: break-all;
        }
      }
    }
  }
</style>
<style lang="scss">
  .bklog-text-segment {
    .segment-content {
      font-family: var(--bklog-v3-row-ctx-font);
      font-size: var(--table-fount-size);
      line-height: 20px;
      white-space: pre-wrap;

      mark {
        &.valid-text {
          white-space: pre-wrap;
        }
      }

      .valid-text {
        white-space: pre-wrap;
        cursor: pointer;

        &.focus-text,
        &:hover {
          color: #3a84ff;
        }
      }
    }
  }
</style>
