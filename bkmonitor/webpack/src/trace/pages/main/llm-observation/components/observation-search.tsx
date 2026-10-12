import { computed, defineComponent, onBeforeUnmount, shallowRef, watch } from 'vue';

import { useI18n } from 'vue-i18n';

import './observation-search.scss';

/** LLM 观测页内查找：线框输入 + 右侧翻页 / 无结果 / 搜索图标（对齐 Figma SearchSelect） */
export default defineComponent({
  name: 'LlmObservationSearch',
  props: {
    /** 当前搜索词，由 Span 详情受控 */
    keyword: {
      type: String,
      default: '',
    },
    /** 当前命中下标，从 0 起；展示为 n / total */
    activeIndex: {
      type: Number,
      default: 0,
    },
    matchCount: {
      type: Number,
      default: 0,
    },
  },
  emits: {
    'update:keyword': (_value: string) => true,
    prev: () => true,
    next: () => true,
  },
  setup(props, { emit }) {
    const { t } = useI18n();
    /** 输入先写本地，避免父级重算命中卡住受控框回显 */
    const draftKeyword = shallowRef(props.keyword);
    /** 停输后再把草稿提交给父级，避免每个按键都重算命中 */
    const KEYWORD_COMMIT_DELAY = 500;
    let emitTimer = 0;

    watch(
      () => props.keyword,
      value => {
        if (value !== draftKeyword.value) {
          draftKeyword.value = value;
        }
      }
    );

    const clearEmitTimer = () => {
      if (emitTimer) {
        clearTimeout(emitTimer);
        emitTimer = 0;
      }
    };

    const commitKeyword = () => {
      clearEmitTimer();
      if (draftKeyword.value !== props.keyword) {
        emit('update:keyword', draftKeyword.value);
      }
    };

    const hasDraft = computed(() => Boolean(draftKeyword.value.trim()));
    const hasCommittedKeyword = computed(() => Boolean(props.keyword.trim()));
    const hasMatches = computed(() => hasCommittedKeyword.value && props.matchCount > 0);

    const handleInput = (event: Event) => {
      const target = event.target as HTMLInputElement;
      draftKeyword.value = target.value ?? '';
      clearEmitTimer();
      emitTimer = window.setTimeout(commitKeyword, KEYWORD_COMMIT_DELAY);
    };

    onBeforeUnmount(commitKeyword);

    /** Enter 下一条，Shift+Enter 上一条；与箭头按钮同一套循环翻页 */
    const handleKeydown = (event: KeyboardEvent) => {
      if (event.key !== 'Enter' || !hasDraft.value) return;
      event.preventDefault();
      commitKeyword();
      if (event.shiftKey) {
        emit('prev');
      } else {
        emit('next');
      }
    };

    // 手写线框容器，避开 bk-input suffix 灰底和蓝色 focus，对齐 Figma SearchSelect
    return () => (
      <div class='llm-observation-search'>
        <input
          class='llm-observation-search-field'
          spellcheck={false}
          type='text'
          value={draftKeyword.value}
          placeholder={t('搜索')}
          onInput={handleInput}
          onKeydown={handleKeydown}
        />
        <div class='llm-observation-search-addon'>
          {hasMatches.value ? (
            <div class='llm-observation-search-nav'>
              <i
                class='icon-monitor icon-arrow-left llm-observation-search-arrow'
                onClick={() => emit('prev')}
              />
              <span class='llm-observation-search-count'>
                {props.activeIndex + 1} / {props.matchCount}
              </span>
              <i
                class='icon-monitor icon-arrow-right llm-observation-search-arrow'
                onClick={() => emit('next')}
              />
            </div>
          ) : null}
          {hasCommittedKeyword.value && !hasMatches.value ? (
            <span class='llm-observation-search-empty'>{t('无结果')}</span>
          ) : null}
          <i class='icon-monitor icon-mc-search llm-observation-search-icon' />
        </div>
      </div>
    );
  },
});
