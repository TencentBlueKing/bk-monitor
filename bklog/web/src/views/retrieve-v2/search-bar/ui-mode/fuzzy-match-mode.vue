<script setup lang="ts">
/**
 * 模糊匹配组件（封闭匹配逻辑）
 * - value 接收/输出实际下发查询数组
 * - 组件内部维护匹配模式、标签输入、批量输入、标签编辑/删除
 * - relation 仅用于恢复旧版多个标签的 AND / OR 关系设置
 */
import { computed, nextTick, ref, watch } from 'vue';
import useLocale from '@/hooks/use-locale';
import BatchInput from '../../components/batch-input';

type Mode = 'exact' | 'prefix' | 'suffix' | 'contains' | 'custom';
type EngineType = 'es' | 'doris';

const props = defineProps({
  value: {
    type: [Array, String],
    default: () => [],
  },
  operator: {
    type: String,
    default: '',
  },
  type: {
    type: String,
    default: 'es',
  },
  relation: {
    type: String,
    default: 'OR',
  },
});

const emit = defineEmits(['input', 'relation-change', 'batch-show-change', 'wildcard-change']);
const { t } = useLocale();

const activeMode = ref<Mode>('exact');
const keywordList = ref<string[]>([]);
const inputValue = ref('');
const editIndex = ref<number | null>(null);
const editValue = ref('');
const refRoot = ref<HTMLElement | null>(null);
const refTagInput = ref<HTMLInputElement | null>(null);
let isEmitting = false;

const modeButtons: Array<{ id: Mode; label: string; sample: string }> = [
  { id: 'exact', label: '精确', sample: '' },
  { id: 'prefix', label: '前缀', sample: 'abc*' },
  { id: 'suffix', label: '后缀', sample: '*abc' },
  { id: 'contains', label: '包含', sample: '*abc*' },
  { id: 'custom', label: '自定义', sample: '' },
];

const engineType = computed<EngineType>(() => (String(props.type).toLowerCase() === 'doris' ? 'doris' : 'es'));
const currentRelation = computed({
  get() {
    return ['AND', 'OR'].includes(String(props.relation).toUpperCase()) ? String(props.relation).toUpperCase() : 'OR';
  },
  set(value: string) {
    emit('relation-change', value);
  },
});

const normalizeValues = (value: string | string[]) => {
  if (Array.isArray(value)) {
    return value.filter(item => item !== undefined && item !== null).map(item => String(item));
  }
  const text = String(value ?? '');
  return text ? [text] : [];
};

const isAsteriskEscaped = (text: string, index: number) => {
  let slashCount = 0;
  for (let i = index - 1; i >= 0 && text[i] === '\\'; i--) {
    slashCount++;
  }
  return slashCount % 2 === 1;
};

const startsWithUnescapedAsterisk = (text: string) => text.startsWith('*') && !isAsteriskEscaped(text, 0);
const endsWithUnescapedAsterisk = (text: string) => text.endsWith('*') && !isAsteriskEscaped(text, text.length - 1);
const hasUnescapedWildcard = (text: string) => {
  for (let i = 0; i < text.length; i++) {
    if ((text[i] === '*' || text[i] === '?') && !isAsteriskEscaped(text, i)) {
      return true;
    }
  }
  return false;
};

const escapeEdgeAsterisks = (text: string) => {
  if (!text) {
    return '';
  }

  const chars = text.split('');
  const escapeIndexSet = new Set<number>();
  for (let i = 0; i < chars.length && chars[i] === '*'; i++) {
    escapeIndexSet.add(i);
  }
  for (let i = chars.length - 1; i >= 0 && chars[i] === '*'; i--) {
    if (!isAsteriskEscaped(text, i)) {
      escapeIndexSet.add(i);
    }
  }

  return chars.map((char, index) => escapeIndexSet.has(index) ? '\\' + char : char).join('');
};

const normalizeKeyword = (value: string) => escapeEdgeAsterisks(String(value ?? '').trim());
const isExactOperator = (operator: string) => ['contains match phrase', 'not contains match phrase'].includes(operator);
const isWildcardOperator = (operator: string) => ['=~', '!=~', '&=~', '&!=~'].includes(operator);

const computeQuery = (mode: Mode, text: string) => {
  const value = normalizeKeyword(text);
  if (!value) {
    return '';
  }

  switch (mode) {
    case 'prefix':
      return `${value}*`;
    case 'suffix':
      return `*${value}`;
    case 'contains':
      return `*${value}*`;
    case 'custom':
    case 'exact':
    default:
      return value;
  }
};

const isSimpleText = (text: string) => !hasUnescapedWildcard(text);

const inferModeAndKeywords = (value: string | string[], operator = props.operator): { mode: Mode; keywords: string[] } => {
  const values = normalizeValues(value);
  if (isExactOperator(operator)) {
    return { mode: 'exact', keywords: values };
  }
  if (!values.length) {
    return { mode: 'exact', keywords: [] };
  }

  const containsKeywords = values.map(item => startsWithUnescapedAsterisk(item) && endsWithUnescapedAsterisk(item) && item.length >= 2 ? item.slice(1, -1) : null);
  if (containsKeywords.every(item => item !== null && isSimpleText(item))) {
    return { mode: 'contains', keywords: containsKeywords as string[] };
  }

  const suffixKeywords = values.map(item => startsWithUnescapedAsterisk(item) && !endsWithUnescapedAsterisk(item) ? item.slice(1) : null);
  if (suffixKeywords.every(item => item !== null && isSimpleText(item))) {
    return { mode: 'suffix', keywords: suffixKeywords as string[] };
  }

  const prefixKeywords = values.map(item => !startsWithUnescapedAsterisk(item) && endsWithUnescapedAsterisk(item) ? item.slice(0, -1) : null);
  if (prefixKeywords.every(item => item !== null && isSimpleText(item))) {
    return { mode: 'prefix', keywords: prefixKeywords as string[] };
  }

  if (values.some(item => hasUnescapedWildcard(item))) {
    return { mode: 'custom', keywords: values };
  }

  if (isWildcardOperator(operator)) {
    return { mode: 'custom', keywords: values };
  }

  return { mode: 'exact', keywords: values };
};

const syncFromValue = (value: string | string[], operator = props.operator) => {
  const result = inferModeAndKeywords(value, operator);
  activeMode.value = result.mode;
  keywordList.value = [...result.keywords];
};

watch(
  () => [props.value, props.operator],
  ([value, operator]) => {
    if (isEmitting) {
      return;
    }
    syncFromValue(value as string | string[], operator as string);
  },
  { immediate: true, deep: true },
);

const actualQueryList = computed(() => keywordList.value.map(item => computeQuery(activeMode.value, item)).filter(Boolean));
const actualQueryText = computed(() => actualQueryList.value.length ? actualQueryList.value.join(` ${currentRelation.value} `) : '');

const inputPlaceholder = computed(() => {
  if (activeMode.value === 'custom') {
    return t('可手写 * / ?，如 user_*_error');
  }

  if (activeMode.value === 'exact') {
    return t('请输入关键词，Enter 生成标签');
  }

  return t('只输入关键词即可，无需自己写 *，Enter 生成标签');
});

const engineDescription = computed(() => {
  if (engineType.value === 'doris') {
    return t('Doris 引擎下，可携带符号 / 空格，且无视分词。');
  }
  return t('ES 引擎下，关键词必须是一个完整的词，中间不能包含符号或空格。');
});

const modeDescription = computed(() => {
  switch (activeMode.value) {
    case 'prefix':
      return `${t('前缀匹配，命中所有以关键词开头的内容。')}${engineDescription.value}`;
    case 'suffix':
      return `${t('后缀匹配，命中所有以关键词结尾的内容。')}${engineDescription.value}`;
    case 'contains':
      return `${t('包含匹配，命中所有含有关键词的内容。')}${engineDescription.value}`;
    case 'custom':
      return t('自定义模式，按你输入的 * / ? 直接匹配。');
    case 'exact':
    default:
      return t('精确匹配，与关键词完全相等的内容才会命中。');
  }
});

const tooltipContent = computed(() => [
  t('匹配模式说明'),
  t('精确匹配：完整等于关键词。'),
  t('前缀 / 后缀 / 包含：在关键词前后自动添加通配，匹配以关键词开头 / 结尾 / 含有关键词的内容。'),
  t('自定义：允许手写 *（任意字符串）、?（任意单字符），适合高级用法。'),
  t('ES 受分词限制：关键词必须是一个完整的词，中间不能含符号或空格。如 *err-404* 无效。'),
  t('Doris 无视分词，可带符号查询。如 *err-404 timeout* 可正常命中。'),
].join('\n'));

const emitValue = () => {
  isEmitting = true;
  emit('wildcard-change', activeMode.value !== 'exact');
  emit('input', [...actualQueryList.value]);
  nextTick(() => {
    isEmitting = false;
  });
};

const handleModeClick = (mode: Mode) => {
  activeMode.value = mode;
  emitValue();
};

const appendKeyword = (value: string) => {
  const text = normalizeKeyword(value);
  if (!text) {
    return;
  }
  if (!keywordList.value.includes(text)) {
    keywordList.value.push(text);
  }
};

const handleInputEnter = (event: KeyboardEvent) => {
  if ((event as any).isComposing) {
    return;
  }
  event.preventDefault();
  appendKeyword(inputValue.value);
  inputValue.value = '';
  emitValue();
};

const handleInputBlur = () => {
  if (!inputValue.value.trim()) {
    return;
  }
  appendKeyword(inputValue.value);
  inputValue.value = '';
  emitValue();
};

const handleDeleteTag = (index: number) => {
  keywordList.value.splice(index, 1);
  emitValue();
};

const handleEditTagDBClick = (index: number) => {
  editIndex.value = index;
  editValue.value = keywordList.value[index] ?? '';
  nextTick(() => {
    const editInput = refRoot.value?.querySelector<HTMLInputElement>(`[data-fuzzy-edit-index="${index}"]`);
    editInput?.focus();
    editInput?.select();
  });
};

const commitEditTag = () => {
  if (editIndex.value === null) {
    return;
  }
  const text = normalizeKeyword(editValue.value);
  if (text) {
    keywordList.value.splice(editIndex.value, 1, text);
  } else {
    keywordList.value.splice(editIndex.value, 1);
  }
  editIndex.value = null;
  editValue.value = '';
  emitValue();
};

const handleEditEnter = (event: KeyboardEvent) => {
  if ((event as any).isComposing) {
    return;
  }
  event.preventDefault();
  commitEditTag();
};

const handleInputDelete = (event: KeyboardEvent) => {
  if (inputValue.value || !keywordList.value.length) {
    return;
  }
  event.preventDefault();
  keywordList.value.splice(-1, 1);
  emitValue();
};

const handleClear = () => {
  keywordList.value = [];
  inputValue.value = '';
  editIndex.value = null;
  editValue.value = '';
  emitValue();
};

const handleBatchInputChange = (selectData: string[]) => {
  const values = Array.isArray(selectData)
    ? selectData.filter(item => item !== undefined && item !== null).map(item => String(item).trim()).filter(Boolean)
    : [];
  if (!values.length) {
    return;
  }
  values.forEach(appendKeyword);
  emitValue();
};

const handleBatchShowChange = (value: boolean) => {
  emit('batch-show-change', value);
};

const focusInput = (event?: MouseEvent) => {
  const target = event?.target as HTMLElement | null;
  if (target?.closest('.fuzzy-match-tag, .fuzzy-match-tag-edit, .fuzzy-match-tag-del')) {
    return;
  }
  refTagInput.value?.focus();
};

defineExpose({
  computeQuery,
  inferModeAndKeywords,
  escapeEdgeAsterisks,
});
</script>

<template>
  <div
    ref="refRoot"
    class="fuzzy-match-mode"
  >
    <div class="fuzzy-match-header">
      <span class="fuzzy-match-actions">
        <span class="fuzzy-match-label">{{ t('检索内容') }}</span>
        <BatchInput
          @value-change="handleBatchInputChange"
          @show-change="handleBatchShowChange"
        />
        <bk-button
          text
          :disabled="keywordList.length === 0 && !inputValue.length"
          class="fuzzy-match-clear-btn"
          @click="handleClear"
        >
          {{ t('清空') }}
        </bk-button>
      </span>
      <span class="fuzzy-match-title-wrap">
        <span class="fuzzy-match-title">{{ t('匹配模式') }}</span>
        <span
          v-bk-tooltips="{ content: tooltipContent, placement: 'top', allowHTML: false }"
          class="fuzzy-match-help"
        >?</span>
      </span>
    </div>

    <div
      class="fuzzy-match-buttons"
      role="group"
      :aria-label="t('匹配模式')"
    >
      <button
        v-for="button in modeButtons"
        :key="button.id"
        type="button"
        :class="['fuzzy-match-button', { active: activeMode === button.id }]"
        @click.stop="handleModeClick(button.id)"
      >
        <span class="mode-label">{{ t(button.label) }}</span>
        <span
          v-if="button.sample"
          class="mode-sample"
        >{{ button.sample }}</span>
      </button>
    </div>

    <div
      class="fuzzy-match-tag-input"
      @click="focusInput"
    >
      <span
        v-for="(item, index) in keywordList"
        :key="`${item}-${index}`"
        class="fuzzy-match-tag"
      >
        <template v-if="editIndex === index">
          <input
            v-model="editValue"
            class="fuzzy-match-tag-edit"
            :data-fuzzy-edit-index="index"
            @blur="commitEditTag"
            @click.stop
            @dblclick.stop
            @mousedown.stop
            @keydown.enter="handleEditEnter"
          >
        </template>
        <template v-else>
          <span
            class="fuzzy-match-tag-text"
            :title="item"
            @dblclick.stop="handleEditTagDBClick(index)"
          >{{ item }}</span>
          <span
            class="fuzzy-match-tag-del bk-icon icon-close"
            @click.stop="handleDeleteTag(index)"
          />
        </template>
      </span>
      <input
        ref="refTagInput"
        v-model="inputValue"
        class="fuzzy-match-input"
        :placeholder="keywordList.length ? '' : inputPlaceholder"
        @blur="handleInputBlur"
        @keydown.enter="handleInputEnter"
        @keydown.delete="handleInputDelete"
      >
    </div>

    <div
      v-show="keywordList.length > 1"
      class="fuzzy-match-relation"
    >
      <span class="fuzzy-match-relation-label">{{ t('组间关系') }}</span>
      <bk-radio-group v-model="currentRelation">
        <bk-radio
          style="margin-right: 12px"
          value="AND"
        >
          AND
        </bk-radio>
        <bk-radio value="OR">
          OR
        </bk-radio>
      </bk-radio-group>
    </div>

    <div class="fuzzy-match-preview-card">
      <div class="fuzzy-match-preview">
        <span class="preview-label">{{ t('实际下发查询') }}：</span>
        <span class="preview-value">{{ actualQueryText || t('(空)') }}</span>
      </div>
      <div
        v-if="activeMode === 'custom'"
        class="fuzzy-match-custom-tip"
      >
        {{ t('自定义模式下可手写 *（任意字符串）、?（任意单字符）') }}
      </div>
      <div class="fuzzy-match-desc">
        {{ modeDescription }}
      </div>
    </div>
  </div>
</template>

<style scoped lang="scss">
.fuzzy-match-mode {
  width: 100%;
}

.fuzzy-match-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 12px;
  font-size: 12px;
  line-height: 20px;
  color: #4d4f56;
}

.fuzzy-match-actions,
.fuzzy-match-title-wrap {
  display: inline-flex;
  align-items: center;
}

.fuzzy-match-label,
.fuzzy-match-title {
  font-weight: 600;
}

.fuzzy-match-clear-btn {
  margin-left: 2px;
  font-size: 12px;
}

.fuzzy-match-help {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 18px;
  height: 18px;
  margin-left: 8px;
  font-size: 13px;
  font-weight: 700;
  line-height: 18px;
  color: #979ba5;
  cursor: pointer;
  background: #f0f1f5;
  border-radius: 50%;

  &:hover {
    color: #3a84ff;
    background: #e1ecff;
  }
}

.fuzzy-match-buttons {
  display: flex;
  width: 100%;
  margin-bottom: 12px;
  overflow: hidden;
  background: #ffffff;
  border: 1px solid #dcdee5;
  border-radius: 4px;
}

.fuzzy-match-button {
  display: inline-flex;
  flex: 1 1 0;
  align-items: center;
  justify-content: center;
  min-width: 0;
  height: 34px;
  padding: 0 6px;
  margin: 0;
  font-size: 12px;
  line-height: 32px;
  color: #63656e;
  cursor: pointer;
  background: #ffffff;
  border: 0;
  border-right: 1px solid #dcdee5;
  outline: none;
  transition: color .15s, background .15s;

  &:last-child {
    border-right: 0;
  }

  &:hover {
    color: #3a84ff;
    background: #f5f7fa;
  }

  &.active {
    color: #3a84ff;
    background: #e1ecff;

    .mode-label {
      font-weight: 700;
    }

    .mode-sample {
      color: #3a84ff;
    }
  }
}

.mode-label,
.mode-sample {
  white-space: nowrap;
}

.mode-sample {
  margin-left: 4px;
  color: #c4c6cc;
}

.fuzzy-match-tag-input {
  display: flex;
  flex-wrap: wrap;
  align-content: flex-start;
  gap: 6px;
  width: 100%;
  min-height: 72px;
  max-height: 160px;
  padding: 6px;
  margin-bottom: 12px;
  overflow: auto;
  cursor: text;
  background: #fff;
  border: 1px solid #c4c6cc;
  border-radius: 2px;

  &:focus-within {
    border-color: #3a84ff;
  }
}

.fuzzy-match-tag {
  display: inline-flex;
  align-items: center;
  max-width: 100%;
  height: 24px;
  padding: 0 6px;
  line-height: 22px;
  color: #63656e;
  background: #f0f1f5;
  border: 1px solid #dcdee5;
  border-radius: 2px;
}

.fuzzy-match-tag-text {
  max-width: 260px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  cursor: pointer;
}

.fuzzy-match-tag-del {
  margin-left: 4px;
  font-size: 14px;
  color: #979ba5;
  cursor: pointer;

  &:hover {
    color: #ea3636;
  }
}

.fuzzy-match-tag-edit,
.fuzzy-match-input {
  min-width: 120px;
  height: 22px;
  padding: 0;
  font-size: 12px;
  color: #313238;
  background: transparent;
  border: 0;
  outline: 0;
}

.fuzzy-match-input {
  flex: 1;
}

.fuzzy-match-relation {
  display: flex;
  flex-wrap: nowrap;
  align-items: center;
  margin-bottom: 12px;
  font-size: 12px;
  color: #63656e;
  white-space: nowrap;

  :deep(.bk-radio-group) {
    display: inline-flex;
    flex-wrap: nowrap;
    align-items: center;
  }

  :deep(.bk-form-radio) {
    display: inline-flex;
    flex-shrink: 0;
    align-items: center;
  }
}

.fuzzy-match-relation-label {
  flex: 0 0 auto;
  margin-right: 16px;
  font-weight: 600;
  color: #4d4f56;
  white-space: nowrap;
}

.fuzzy-match-preview-card {
  padding: 12px 16px;
  background: #fafbfd;
  border: 1px dashed #dcdee5;
  border-radius: 4px;
}

.fuzzy-match-preview {
  display: flex;
  max-width: 100%;
  font-size: 12px;
  line-height: 22px;
  color: #979ba5;
}

.preview-label {
  flex-shrink: 0;
  font-weight: 600;
}

.preview-value {
  max-width: 100%;
  overflow: hidden;
  font-family: Menlo, Monaco, Consolas, Courier, monospace;
  color: #3a84ff;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.fuzzy-match-custom-tip,
.fuzzy-match-desc {
  margin-top: 8px;
  font-size: 12px;
  line-height: 20px;
  color: #979ba5;
}
</style>
