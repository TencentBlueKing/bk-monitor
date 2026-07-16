<template>
  <div
    ref="refJsonFormatterCell"
    :class="[
      'bklog-json-formatter-root',
      {
        'is-wrap-line': !isOriginalMode && isWrap,
        'is-inline': !isOriginalMode && !isWrap,
        'is-original-wrap-line': isOriginalMode && isWrap,
        'is-json': formatJson,
        'is-hidden': !isRowIntersecting && isResolved,
        'show-all-word': showAllWords,
        'is-original-mode': isOriginalMode,
        'is-overflow-y': isShowOverflowY,
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
            v-html="getHighlightedFieldNameHtml(item.name)"
          ></span
        ></span>
        <span
          class="field-value"
          :data-with-intersection="true"
          :data-field-name="item.name"
          :data-search-field-name="item.name"
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
<script lang="ts">
  const ORIGINAL_VALUE_EXPAND_STATE_CACHE_LIMIT = 500;
  const originalValueExpandStateCache = new Map<string, Record<string, boolean>>();
</script>
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
  import { buildHighlightHtml, pageHighlightState } from '../views/retrieve-core/page-highlight';

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

    stateKey: {
      type: [String, Number],
      default: '',
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
    // KV 等场景传入 'auto'：不限制行高，也不展示「更多」
    if (props.limitRow === 'auto') {
      return 'auto';
    }

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
    if (limitRowNumber.value === 'auto') {
      return undefined;
    }

    if (isCurrentCellExpandText.value) {
      return {
        maxHeight: '50vh',
      };
    }

    if (typeof limitRowNumber.value === 'number') {
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

  const originalValueFieldsSignature = computed(() =>
    fieldList.value
      .map((item: any) => String(item.field_name) + ':' + String(item.field_type ?? ''))
      .join('\u0001'),
  );

  const clearOriginalValueRenderCache = () => {
    originalValuePreviewTextCache.clear();
    originalValuePreviewSegmentCache.clear();
    expandedOriginalValueTexts.value = {};
    expandedOriginalValueSegments.value = {};
  };

  const getOriginalValueExpandStateKey = () => {
    if (!isOriginalMode.value || props.stateKey === null || props.stateKey === undefined || props.stateKey === '') {
      return '';
    }

    return String(props.stateKey);
  };

  const persistOriginalValueExpandedFields = () => {
    const stateKey = getOriginalValueExpandStateKey();
    if (!stateKey) return;

    originalValueExpandStateCache.delete(stateKey);
    originalValueExpandStateCache.set(stateKey, { ...expandedOriginalValueFields.value });

    while (originalValueExpandStateCache.size > ORIGINAL_VALUE_EXPAND_STATE_CACHE_LIMIT) {
      const oldestKey = originalValueExpandStateCache.keys().next().value;
      originalValueExpandStateCache.delete(oldestKey);
    }
  };

  const restoreOriginalValueExpandedFields = () => {
    const stateKey = getOriginalValueExpandStateKey();
    expandedOriginalValueFields.value = stateKey
      ? { ...(originalValueExpandStateCache.get(stateKey) ?? {}) }
      : {};
  };

  const resetOriginalValueState = () => {
    expandedOriginalValueFields.value = {};
    persistOriginalValueExpandedFields();
    clearOriginalValueRenderCache();
  };

  const syncOriginalValueState = () => {
    restoreOriginalValueExpandedFields();
    clearOriginalValueRenderCache();
  };

  const pruneOriginalValueExpandedFields = () => {
    if (!isOriginalMode.value) return;

    const fieldNameSet = new Set(fieldList.value.map((item: any) => item.field_name));
    const nextExpandedFields: Record<string, boolean> = {};
    let hasPruned = false;

    for (const fieldName of Object.keys(expandedOriginalValueFields.value)) {
      if (fieldNameSet.has(fieldName)) {
        nextExpandedFields[fieldName] = expandedOriginalValueFields.value[fieldName];
      } else {
        hasPruned = true;
      }
    }

    if (hasPruned) {
      expandedOriginalValueFields.value = nextExpandedFields;
      persistOriginalValueExpandedFields();
    }
  };

  const showMoreTextAction = computed(() => {
    if (isOriginalMode.value) {
      return false;
    }

    if (typeof limitRowNumber.value === 'number' && !isLimitExpandText.value) {
      return true;
    }

    return false;
  });

  const showMoreAction = computed(() => showMoreTextAction.value && (hasScrollY.value || showAllText.value));

  const showAllWords = computed(() => {
    return !showMoreTextAction.value || showAllText.value;
  });

  const isShowOverflowY = computed(() => {
    return (showMoreAction.value && showAllText.value) || isLimitExpandText.value;
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

  /**
   * 从 renderMeta / __highlight / 字段值中取带 <mark> 的渲染文本。
   * 仅用于 Origin 截断内容生成，避免截断后丢失检索高亮。
   */
  const getFieldMarkedSourceText = (fieldName: string, field: any) => {
    // 1) renderMeta 预分词（与 Expand/表格同源，含检索高亮）
    const metaSegments = props.renderMeta?.fieldSegments?.[fieldName];
    if (Array.isArray(metaSegments) && metaSegments.length) {
      // 不能用 isMark 直接包裹整个 segment：whole-value 字段的 segment
      // 可能是几 KB 的纯文本，而 isMark 只表示“segment 内存在命中”。
      // 必须使用 resultRanges 恢复命中的局部范围，否则点击“更多”后会把
      // 命中点之后的整段内容误认为检索命中（尤其是 Origin 模式）。
      const markedFromSegments = metaSegments
        .map((segment) => {
          const text = String(segment?.text ?? '');
          const ranges = Array.isArray(segment?.resultRanges)
            ? segment.resultRanges
                .map(range => ({
                  start: Math.max(0, Math.min(text.length, Number(range?.start))),
                  end: Math.max(0, Math.min(text.length, Number(range?.end))),
                }))
                .filter(range => range.end > range.start)
                .sort((a, b) => a.start - b.start || a.end - b.end)
            : [];

          if (!ranges.length) {
            // 兼容旧缓存：旧数据没有 resultRanges 时才回退到 isMark。
            return segment?.isMark ? `<mark>${text}</mark>` : text;
          }

          let result = '';
          let cursor = 0;
          ranges.forEach((range) => {
            // 防止重叠 range 产生非法/嵌套 mark；重叠命中合并为一个连续范围。
            const start = Math.max(cursor, range.start);
            if (range.end <= start) return;
            result += text.slice(cursor, start);
            result += `<mark>${text.slice(start, range.end)}</mark>`;
            cursor = range.end;
          });
          return result + text.slice(cursor);
        })
        .join('');
      if (markedFromSegments) {
        return markedFromSegments;
      }
    }

    // 2) 大字段 32KB 截断文本（已保留 mark）
    const truncatedByField = props.renderMeta?.truncatedTextByField?.[fieldName];
    if (typeof truncatedByField === 'string' && truncatedByField) {
      return truncatedByField;
    }

    const row = props.jsonValue !== null && typeof props.jsonValue === 'object'
      ? props.jsonValue
      : null;

    // 3) __highlight 原始命中文本
    if (row) {
      const highlightValue = row.__highlight?.[fieldName];
      const marked = Array.isArray(highlightValue) ? highlightValue[0] : highlightValue;
      if (typeof marked === 'string' && /<\/?mark>/i.test(marked)) {
        return marked;
      }
    }

    // 4) 字段值本身可能已叠加 mark overlay
    const [, val] = getFieldValue(field);
    const renderText = getDateFieldValue(field, getCellRender(val), isFormatDateField.value);
    return renderText?.replace?.(/<\/mark>/igm, '</mark>') ?? String(renderText ?? '');
  };

  /** 截断判定仍基于字段展示原文长度，避免因 mark 源切换改变「是否展示更多」 */
  const getOriginalValuePlainText = (fieldName: string) => {
    const field = fieldList.value.find((item: any) => item.field_name === fieldName) ?? { field_name: fieldName };
    const [, val] = getFieldValue(field);
    const renderText = getDateFieldValue(field, getCellRender(val), isFormatDateField.value);
    return renderText?.replace?.(/<\/mark>/igm, '</mark>') ?? String(renderText ?? '');
  };

  const getOriginalValueRenderText = (fieldName: string) => {
    const field = fieldList.value.find((item: any) => item.field_name === fieldName) ?? { field_name: fieldName };
    return getFieldMarkedSourceText(fieldName, field);
  };

  const getOriginalValuePreviewInfo = (fieldName: string) => {
    if (!originalValuePreviewTextCache.has(fieldName)) {
      // 先按原文长度判定是否截断：绝大多数短字段到此结束，避免无谓重建 mark 文本
      const plainText = getOriginalValuePlainText(fieldName);
      const isTruncated = stripMark(plainText).length > ORIGINAL_VALUE_PREVIEW_TEXT_LENGTH;
      if (!isTruncated) {
        originalValuePreviewTextCache.set(fieldName, {
          text: plainText,
          isTruncated: false,
        });
        return originalValuePreviewTextCache.get(fieldName);
      }

      // 仅超长字段才拼接/截断带 mark 的源文本
      const markedText = getOriginalValueRenderText(fieldName);
      originalValuePreviewTextCache.set(fieldName, {
        text: truncateMarkedTextByChars(markedText, ORIGINAL_VALUE_PREVIEW_TEXT_LENGTH),
        isTruncated: true,
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

  const getAliasAwareSegments = (field: any, segments: Record<string, any[]> | undefined) => {
    if (!segments || !store.state.storage[BK_LOG_STORAGE.SHOW_FIELD_ALIAS]) {
      return segments;
    }

    const mappedSegments = { ...segments };
    let hasMappedAlias = false;

    // 接口 list 的别名值以 query_alias 为 key；formatter/JSON 树则按真实字段路径消费。
    // 这里覆盖当前列及 Object 子字段，确保 alias segments 优先于未高亮的真实字段 segments。
    for (const aliasFieldName of Object.keys(segments)) {
      const sourceFieldName = fieldNameHook.changeFieldName(aliasFieldName);
      if (sourceFieldName !== aliasFieldName && Array.isArray(segments[aliasFieldName])) {
        mappedSegments[sourceFieldName] = segments[aliasFieldName];
        hasMappedAlias = true;
      }
    }

    const aliasFieldName = field.query_alias || (field.is_virtual_alias_field ? field.field_name : '');
    if (aliasFieldName && Array.isArray(segments[aliasFieldName])) {
      mappedSegments[field.field_name] = segments[aliasFieldName];
      hasMappedAlias = true;
    }

    return hasMappedAlias ? mappedSegments : segments;
  };

  const getOriginalValueSegments = (field: any) => {
    const fieldName = field.field_name;
    const aliasAwareSegments = getAliasAwareSegments(field, props.renderMeta?.fieldSegments);
    if (!isOriginalMode.value) {
      return aliasAwareSegments;
    }

    if (expandedOriginalValueFields.value[fieldName]) {
      if (!expandedOriginalValueSegments.value[fieldName]) {
        const expandedText = getOriginalValueExpandedText(fieldName);
        expandedOriginalValueSegments.value = {
          ...expandedOriginalValueSegments.value,
          [fieldName]: splitRenderText(expandedText, field),
        };
      }

      return {
        ...aliasAwareSegments,
        [fieldName]: expandedOriginalValueSegments.value[fieldName],
      };
    }

    if (isOriginalValueTruncated(fieldName)) {
      if (!originalValuePreviewSegmentCache.has(fieldName)) {
        // 基于保留 mark 的截断文本重新分词，保证 isMark 与 Expand 一致
        originalValuePreviewSegmentCache.set(fieldName, splitRenderText(getOriginalValuePreviewText(fieldName), field));
      }

      return {
        ...aliasAwareSegments,
        [fieldName]: originalValuePreviewSegmentCache.get(fieldName),
      };
    }

    return aliasAwareSegments;
  };

  const getOriginalValueDisplayText = (fieldName: string, fallback: any) => {
    if (!isOriginalMode.value) {
      return fallback;
    }

    const renderText = expandedOriginalValueFields.value[fieldName]
      ? getOriginalValueExpandedText(fieldName)
      : getOriginalValuePreviewText(fieldName);

    // 模板初始展示去掉 mark 标签，避免出现原始 <mark> 文本闪烁；
    // 检索高亮由 precomputedSegments.isMark 在分词渲染阶段恢复。
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

  const resetAllWordSplitFlags = () => {
    const root = refJsonFormatterCell.value as HTMLElement | undefined;
    const elements = root?.querySelectorAll?.('.field-value[data-has-word-split]') ?? [];
    for (const element of Array.from(elements) as HTMLElement[]) {
      element.removeAttribute('data-has-word-split');
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
    persistOriginalValueExpandedFields();
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
      if (/^\s*(\{|\[)/.test(val)) {
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

  const getCellRender = (val: unknown, isJson = false) => {
    if (val !== null && typeof val === 'object') {
      if (isJson) {
        return Array.isArray(val) ? '[...]' : '{...}';
      }

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
    const isJsonValue = objValue !== null && typeof objValue === 'object' && objValue !== undefined;
    const parsedFromJsonString = typeof val === 'string' && isJsonValue;
    const strVal = getDateFieldValue(field, getCellRender(val, isJsonValue), formatDate);
    return {
      ref: ref(),
      isJson: isJsonValue,
      value: formatEmptyObject(getDateFieldValue(field, objValue, formatDate)),
      stringValue: strVal?.replace?.(/<\/?mark>/igm, '') ?? strVal,
      field,
      parsedFromJsonString,
    };
  };

  const getFieldName = field => fieldNameHook.getFieldName(field);

  /** 根字段 KEY 同样应用页面高亮，与 VALUE 划选高亮保持一致 */
  const getHighlightedFieldNameHtml = (fieldName: string) => {
    // 依赖 version，确保匹配模式/关键字变化后 KEY 同步重绘
    void pageHighlightState.version;
    return buildHighlightHtml({ text: String(getFieldName(fieldName) ?? '') });
  };

  const rootList = computed(() => {
    return fieldList.value.map((f: any) => {
      const shouldFormatDate = isFormatDateField.value && (!!f.__is_virtual_root__ || isOriginalMode.value);
      const isDateField = ['date', 'date_nanos'].includes(f.field_type);
      const formatter = getFieldFormatter(f, shouldFormatDate);
      /**
       * Origin 模式根级 1000 截断：
       * - 未开启 JSON 解析：保持原逻辑，整段 VALUE 超长则截断 + 更多
       * - 已开启 JSON 解析且可解析为对象/数组：禁止根级 slice，交由 JSON 树渲染；
       *   1000/更多仅作用于叶子不可解析字符串
       */
      const shouldUseOriginalValueText =
        isOriginalMode.value
        && isOriginalValueTruncated(f.field_name)
        && !(formatJson.value && formatter.isJson);
      /**
       * precomputedSegments 策略：
       * 时间格式化只应让 date/date_nanos 跳过预分词（展示值已重算）。
       * 若对 Object/文本等非时间字段也跳过，会落入 getSplitList 非 analyzed
       * 单段 isMark 回退，把子字段命中放大成整 Column <mark>。
       */
      const shouldSkipPrecomputedSegments = shouldFormatDate && isDateField;
      return {
        name: f.field_name,
        type: f.field_type,
        formatter: {
          ...formatter,
          isJson: shouldUseOriginalValueText ? false : formatter.isJson,
          value: shouldUseOriginalValueText ? getOriginalValueDisplayText(f.field_name, formatter.stringValue) : formatter.value,
          stringValue: shouldUseOriginalValueText
            ? getOriginalValueDisplayText(f.field_name, formatter.stringValue)
            : formatter.stringValue,
          precomputedSegments: shouldSkipPrecomputedSegments
            ? undefined
            : getOriginalValueSegments(f),
          // JSON 解析开启时：叶子长字符串启用 1000/更多（Origin & Table 均生效）
          enableLeafTruncate: formatJson.value,
          parsedFromJsonString: formatter.parsedFromJsonString,
          resolveFieldDisplayName: (fieldName: string) => fieldNameHook.getFieldName(fieldName),
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
    () => [props.limitRow, isLimitExpandText.value],
    () => {
      showAllText.value = false;
      hasScrollY.value = false;
      scheduleSetIsOverflowY();
    },
  );

  watch(
    () => [props.jsonValue, originalValueFieldsSignature.value, isOriginalMode.value],
    () => {
      if (isOriginalMode.value) return;

      showAllText.value = false;
      hasScrollY.value = false;
      scheduleSetIsOverflowY();
    },
  );

  watch(
    () => [props.jsonValue, isOriginalMode.value, props.stateKey],
    () => {
      if (getOriginalValueExpandStateKey()) {
        syncOriginalValueState();
      } else {
        resetOriginalValueState();
      }
      hasScrollY.value = false;
      scheduleSetIsOverflowY();
    },
    {
      immediate: true,
    },
  );

  watch(
    () => [originalValueFieldsSignature.value, formatJson.value],
    () => {
      pruneOriginalValueExpandedFields();
      clearOriginalValueRenderCache();
      hasScrollY.value = false;
      scheduleSetIsOverflowY();
    },
  );

  watch(
    () => isFormatDateField.value,
    () => {
      // 时间格式化开关变化后，必须清掉分词标记并强制重渲染；
      // 否则 DOM 仍保留旧的 data-has-word-split 文本，看起来像开关失效。
      pruneOriginalValueExpandedFields();
      clearOriginalValueRenderCache();
      resetAllWordSplitFlags();
      hasScrollY.value = false;
      if (isResolved.value) {
        debounceUpdate();
      }
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

    &.is-overflow-y {
      overflow-y: auto;

      .btn-more-action {
        position: relative;
      }
    }

    .bklog-scroll-box {
      max-height: none;
      overflow: visible;
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
      border-radius: 2px;
      padding: 1px 0px;
    }

    mark.result-highlight {
      background-color: #faeeb1;
    }

    mark.page-highlight {
      border-radius: 2px;
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
      .field-value[data-with-intersection] {
        display: inline !important;
        white-space: normal;
      }

      .field-value .segment-content,
      .field-value .bklog-scroll-cell,
      .field-value span,
      .field-value mark,
      .valid-text {
        white-space: normal;
      }

      .field-value,
      .field-value[data-with-intersection] {
        max-height: none !important;
        overflow: visible !important;
        word-break: break-all;
        overflow-wrap: anywhere;
      }

      &.is-original-wrap-line {
        display: block;

        > .bklog-root-field {
          display: block !important;
          margin-right: 0;
        }
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

    // JSON 解析后叶子节点「更多/收起」：Origin / Table 共用
    .btn-json-leaf-more {
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
          border-radius: 2px;

          mark.page-highlight {
            padding: 0;
            font-weight: 500;
            border-radius: 2px;
          }
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

    &:not(.is-original-mode).show-all-word {
      // 非 JSON 文本展开时，保留字段值容器滚动，避免超长普通文本撑开表格行。
      &:not(.is-json) {
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

      // JSON 格式化后的超大 value 只由最内层分词容器负责滚动加载。
      // KV 展开模式外层已有 .kv-list-wrapper 滚动，避免 field-value 再产生第三层滚动条。
      .bklog-scroll-box {
        max-height: 50vh;
        overflow: auto;
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
        &:hover,
        &.focus-text *,
        &:hover * {
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
        display: inline;
        word-break: break-all;
        vertical-align: baseline;

        .field-name,
        .field-value {
          display: inline;
          white-space: normal;
        }

        .field-name[data-is-virtual-root='true'] {
          display: none;
        }

        // Table 非换行模式复用 Origin 的 JSON 渲染内容，只将外层流式排布改成 inline；
        // 不能隐藏 .bklog-json-view-icon-text，否则收起态的 {...}/[...] 会丢失。
        .field-value > .bklog-json-view-node,
        .field-value > .bklog-json-view-node > .bklog-json-view-object,
        .field-value > .bklog-json-view-node > .bklog-json-view-object > .bklog-json-view-icon-expand,
        .field-value > .bklog-json-view-node > .bklog-json-view-object > .bklog-json-view-icon-text,
        .field-value > .bklog-json-view-node > .bklog-json-view-object > .bklog-json-view-copy {
          display: inline-block;
          white-space: normal;
          vertical-align: baseline;
        }

        .field-value > .bklog-json-view-node > .bklog-json-view-object > .bklog-json-view-icon-expand {
          vertical-align: middle;
        }

        .bklog-json-field-value,
        .segment-content,
        .bklog-scroll-cell {
          display: inline;
          white-space: normal;
        }

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
