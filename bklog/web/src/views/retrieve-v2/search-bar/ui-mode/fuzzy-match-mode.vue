<script setup lang="ts">
/**
 * 模糊匹配组件（封闭式）
 * props:
 *   - value: 当前实际下发查询
 *   - type: 'es' | 'doris'
 * emits:
 *   - input: 向父组件返回实际下发查询
 *
 * 用户输入 1234 时：
 *   精确  => 1234
 *   前缀  => 1234*
 *   后缀  => *1234
 *   包含  => *1234*
 *   自定义 => 用户原文（如 user_*_error）
 */
import { computed, nextTick, ref, watch } from 'vue';
import useLocale from '@/hooks/use-locale';
import BatchInput from '../../components/batch-input';

type Mode = 'exact' | 'prefix' | 'suffix' | 'contains' | 'custom';
type EngineType = 'es' | 'doris';

const props = defineProps({
  value: {
    type: String,
    default: '',
  },
  type: {
    type: String,
    default: 'es',
  },
});

const emit = defineEmits(['input']);
const { t } = useLocale();

const activeMode = ref<Mode>('exact');
const keyword = ref('');
let isEmitting = false;

const modeButtons: Array<{ id: Mode; label: string; sample: string }> = [
  { id: 'exact', label: '精确', sample: '' },
  { id: 'prefix', label: '前缀', sample: 'abc*' },
  { id: 'suffix', label: '后缀', sample: '*abc' },
  { id: 'contains', label: '包含', sample: '*abc*' },
  { id: 'custom', label: '自定义', sample: '' },
];

const engineType = computed<EngineType>(() => (String(props.type).toLowerCase() === 'doris' ? 'doris' : 'es'));

const computeQuery = (mode: Mode, text: string) => {
  const value = String(text ?? '');
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

const inferModeAndKeyword = (query: string): { mode: Mode; keyword: string } => {
  const text = String(query ?? '');
  if (!text) {
    return { mode: 'exact', keyword: '' };
  }

  const startsWithWildcard = text.startsWith('*');
  const endsWithWildcard = text.endsWith('*');

  if (startsWithWildcard && endsWithWildcard && text.length >= 2) {
    const inner = text.slice(1, -1);
    if (!inner.includes('*') && !inner.includes('?')) {
      return { mode: 'contains', keyword: inner };
    }
  }

  if (startsWithWildcard && !endsWithWildcard) {
    const inner = text.slice(1);
    if (!inner.includes('*') && !inner.includes('?')) {
      return { mode: 'suffix', keyword: inner };
    }
  }

  if (!startsWithWildcard && endsWithWildcard) {
    const inner = text.slice(0, -1);
    if (!inner.includes('*') && !inner.includes('?')) {
      return { mode: 'prefix', keyword: inner };
    }
  }

  if (text.includes('*') || text.includes('?')) {
    return { mode: 'custom', keyword: text };
  }

  return { mode: 'exact', keyword: text };
};

const syncFromValue = (value: string) => {
  const result = inferModeAndKeyword(value);
  activeMode.value = result.mode;
  keyword.value = result.keyword;
};

watch(
  () => props.value,
  (value) => {
    if (isEmitting) {
      return;
    }

    syncFromValue(value);
  },
  { immediate: true },
);

const actualQuery = computed(() => computeQuery(activeMode.value, keyword.value));

const inputPlaceholder = computed(() => {
  if (activeMode.value === 'custom') {
    return t('可手写 * / ?，如 user_*_error');
  }

  if (activeMode.value === 'exact') {
    return t('请输入关键词');
  }

  return t('只输入关键词即可，无需自己写 *');
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
  emit('input', actualQuery.value);
  nextTick(() => {
    isEmitting = false;
  });
};

const handleModeClick = (mode: Mode) => {
  activeMode.value = mode;
  emitValue();
};

const handleInput = (value: string) => {
  keyword.value = String(value ?? '');
  emitValue();
};

const handleClear = () => {
  keyword.value = '';
  emitValue();
};

const handleBatchInputChange = (selectData: string[]) => {
  const values = Array.isArray(selectData) ? selectData.filter(item => item !== undefined && item !== null).map(item => String(item)) : [];
  if (!values.length) {
    return;
  }

  keyword.value = values.join('\n');
  emitValue();
};

defineExpose({
  computeQuery,
  inferModeAndKeyword,
});
</script>

<template>
  <div class="fuzzy-match-mode">
    <div class="fuzzy-match-header">
      <span class="fuzzy-match-actions">
        <span class="fuzzy-match-label">{{ t('检索内容') }}</span>
        <BatchInput @value-change="handleBatchInputChange" />
        <bk-button
          text
          :disabled="!keyword.length"
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

    <bk-input
      class="fuzzy-match-textarea"
      type="textarea"
      :value="keyword"
      :placeholder="inputPlaceholder"
      :rows="3"
      @input="handleInput"
    />

    <div class="fuzzy-match-preview-card">
      <div class="fuzzy-match-preview">
        <span class="preview-label">{{ t('实际下发查询') }}：</span>
        <span class="preview-value">{{ actualQuery || t('(空)') }}</span>
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

.fuzzy-match-textarea {
  width: 100%;
  margin-bottom: 12px;

  :deep(.bk-textarea-wrapper) {
    min-height: 70px;
  }

  :deep(textarea) {
    min-height: 70px;
    font-family: Menlo, Monaco, Consolas, Courier, monospace;
    font-size: 12px;
    line-height: 22px;
    resize: vertical;
  }
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
