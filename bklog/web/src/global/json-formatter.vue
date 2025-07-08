<template>
  <div
    ref="refJsonFormatterCell"
    :class="['bklog-json-formatter-root', { 'is-wrap-line': isWrap, 'is-inline': !isWrap, 'is-json': formatJson }]"
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
          v-html="item.formatter.stringValue"
        ></span>
      </span>
    </template>
    <template v-if="showMoreTextAction && hasScrollY">
      <span
        class="btn-more-action"
        @click="handleClickMore"
      >
        {{ btnText }}
      </span>
    </template>
  </div>
</template>
<script setup lang="ts">
  import { computed, ref, watch, onBeforeUnmount, onMounted } from 'vue';

  // @ts-ignore
  import { formatDate, formatDateNanos, parseTableRowData } from '@/common/util';
  import useFieldNameHook from '@/hooks/use-field-name';

  import useJsonRoot from '../hooks/use-json-root';
  import useStore from '../hooks/use-store';
  import RetrieveHelper from '../views/retrieve-helper';
  import { BK_LOG_STORAGE } from '../store/store.type';
  import { debounce } from 'lodash';
  import JSONBig from 'json-bigint';
  import useLocale from '@/hooks/use-locale';

  const emit = defineEmits(['menu-click']);
  const store = useStore();
  const { $t } = useLocale();

  const props = defineProps({
    jsonValue: {
      type: [Object, String],
      default: () => ({}),
    },
    fields: {
      type: [Array, Object],
      default: () => [],
    },
    formatJson: {
      type: Boolean,
      default: true,
    },
    isIntersection: {
      type: Boolean,
      default: false,
    },
    limitRow: {
      type: [Number, String, null],
      default: 3,
    },
  });

  const bigJson = JSONBig({ useNativeBigInt: true });
  const formatCounter = ref(0);
  const refJsonFormatterCell = ref();
  const isResolved = ref(props.isIntersection);
  const showAllText = ref(false);
  const hasScrollY = ref(false);

  const isFormatDateField = computed(() => store.state.isFormatDate);
  const isWrap = computed(() => store.state.storage[BK_LOG_STORAGE.TABLE_LINE_IS_WRAP]);
  const isLimitExpandText = computed(() => store.state.storage[BK_LOG_STORAGE.IS_LIMIT_EXPAND_VIEW]);
  const isCurrentCellExpandText = computed(() => {
    if (isLimitExpandText.value) {
      return true;
    }

    return showAllText.value;
  });

  const rootElementStyle = computed(() => {
    if (props.formatJson) {
      return {
        maxHeight: undefined,
      };
    }

    if (isCurrentCellExpandText.value) {
      return {
        maxHeight: '50vh',
      };
    }

    if (typeof props.limitRow === 'number') {
      return {
        maxHeight: `${20 * props.limitRow}px`,
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
    if (typeof props.limitRow === 'number' && !props.formatJson && !isLimitExpandText.value) {
      return true;
    }

    return false;
  });

  const btnText = computed(() => {
    if (showAllText.value) {
      return ` ...${$t('收起')}`;
    }

    return ` ...${$t('更多')}`;
  });

  const handleClickMore = e => {
    e.stopPropagation();
    e.preventDefault();
    showAllText.value = !showAllText.value;
  };

  const onSegmentClick = args => {
    emit('menu-click', args);
  };
  const { updateRootFieldOperator, setExpand, setEditor, destroy } = useJsonRoot({
    fields: fieldList.value,
    onSegmentClick,
  });

  const convertToObject = val => {
    if (typeof val === 'string' && props.formatJson) {
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

  const getDateFieldValue = (field, content) => {
    if (isFormatDateField.value) {
      const formatFn = {
        date: formatDate,
        date_nanos: formatDateNanos,
      };

      if (formatFn[field.field_type]) {
        if (/^<mark>(\d+)<\/mark>$/i.test(content)) {
          return content.replace(/^<mark>(\d+)<\/mark>$/i, (_, p1) => {
            return `<mark>${formatFn[field.field_type](Number(p1))}</mark>`;
          });
        }

        return formatFn[field.field_type](Number(content)) || content || '--';
      }
    }

    return content;
  };

  const getFieldValue = field => {
    if (props.formatJson) {
      if (typeof props.jsonValue === 'string') {
        return [convertToObject(props.jsonValue), props.jsonValue];
      }

      const fieldValue = parseTableRowData(props.jsonValue, field.field_name);
      return [convertToObject(fieldValue), fieldValue];
    }

    if (typeof props.jsonValue === 'object') {
      const fieldValue = parseTableRowData(props.jsonValue, field.field_name);
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

  const getFieldFormatter = field => {
    const [objValue, val] = getFieldValue(field);

    return {
      ref: ref(),
      isJson: typeof objValue === 'object' && objValue !== undefined,
      value: getDateFieldValue(field, objValue),
      stringValue: getDateFieldValue(field, getCellRender(val)),
      field,
    };
  };

  const getFieldName = field => {
    const { getFieldName } = useFieldNameHook({ store });
    return getFieldName(field);
  };

  const rootList = computed(() => {
    formatCounter.value++;
    return fieldList.value.map((f: any) => ({
      name: f.field_name,
      type: f.field_type,
      formatter: getFieldFormatter(f),
      __is_virtual_root__: !!f.__is_virtual_root__,
    }));
  });

  const depth = computed(() => store.state.storage[BK_LOG_STORAGE.TABLE_JSON_FORMAT_DEPTH]);
  const debounceUpdate = debounce(() => {
    updateRootFieldOperator(rootList.value, depth.value);
    setEditor(depth.value);
    isResolved.value = true;
    setTimeout(() => {
      RetrieveHelper.highlightElement(refJsonFormatterCell.value);
      setIsOverflowY();
    });
  }, 120);

  const setIsOverflowY = () => {
    if (refJsonFormatterCell.value) {
      const { offsetHeight, scrollHeight } = refJsonFormatterCell.value;
      hasScrollY.value = scrollHeight > offsetHeight;
      return;
    }

    hasScrollY.value = false;
  };

  watch(
    () => [props.isIntersection],
    () => {
      if (props.isIntersection && !isResolved.value) {
        debounceUpdate();
      }
    },
  );

  watch(
    () => [formatCounter.value],
    () => {
      if (isResolved.value) {
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
    font-family: var(--table-fount-family);
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
      border-radius: 2px;
    }

    .btn-more-action {
      position: absolute;
      right: 6px;
      bottom: 0px;
      color: #3a84ff;
      cursor: pointer;
      background-color: #fff;
    }

    .bklog-root-field {
      margin-right: 4px;
      line-height: 20px;

      .bklog-json-view-row {
        word-break: break-all;
      }

      [data-with-intersection] {
        font-family: var(--bklog-v3-row-ctx-font);
        font-size: var(--table-fount-size);
        color: var(--table-fount-color);
        white-space: pre-wrap;
      }

      &:not(:first-child) {
        margin-top: 1px;
      }

      .field-name {
        min-width: max-content;

        .black-mark {
          width: max-content;
          padding: 2px 2px;
          font-family: var(--bklog-v3-row-tag-font);
          font-weight: 500;
          color: #16171a;
          background-color: #ebeef5;
          border-radius: 2px;
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
          overflow: auto;
          transform: translateZ(0); /* 强制开启GPU加速 */
          will-change: transform;
        }
      }
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
