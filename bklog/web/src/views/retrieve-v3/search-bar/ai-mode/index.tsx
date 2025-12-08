import { defineComponent, ref, computed, nextTick } from 'vue';
import useLocale from '@/hooks/use-locale';
import useResizeObserve from '@/hooks/use-resize-observe';

import './index.scss';

type AiModeStatus = 'default' | 'inputting' | 'searching';

export default defineComponent({
  name: 'V3AiMode',
  emits: ['height-change'],
  setup(props, { emit }) {
    const { t } = useLocale();
    const inputValue = ref('');
    const status = ref<AiModeStatus>('default');
    const textareaRef = ref<HTMLTextAreaElement | null>(null);
    const containerRef = ref<HTMLDivElement | null>(null);

    const handleHeightChange = (height: number) => {
      emit('height-change', height);
    };

    const containerClass = computed(() => {
      const baseClass = 'v3-ai-mode';
      if (status.value === 'inputting') {
        return `${baseClass} is-inputting`;
      }
      if (status.value === 'searching') {
        return `${baseClass} is-searching`;
      }
      return baseClass;
    });

    const adjustTextareaHeight = () => {
      nextTick(() => {
        if (textareaRef.value) {
          textareaRef.value.style.height = 'auto';
          textareaRef.value.style.height = `${Math.max(24, textareaRef.value.scrollHeight)}px`;
        }
      });
    };

    const handleInput = (e: Event) => {
      const target = e.target as HTMLTextAreaElement;
      inputValue.value = target.value;
      
      if (target.value.length > 0) {
        status.value = 'inputting';
      } else {
        status.value = 'default';
      }

      adjustTextareaHeight();
    };

    const handleFocus = () => {
      if (inputValue.value.length > 0) {
        status.value = 'inputting';
      }
    };

    const handleBlur = () => {
      if (inputValue.value.length === 0) {
        status.value = 'default';
      }
    };

    useResizeObserve(containerRef, () => {
      if (containerRef.value) {
        handleHeightChange(containerRef.value.offsetHeight);
      }
    });

    const handleAiModeToggle = () => {
      // AI模式切换逻辑
    };

    const handleAiExecute = () => {
      // AI执行逻辑
      if (inputValue.value.trim()) {
        status.value = 'searching';
      }
    };

    return () => (
      <div ref={containerRef} class={containerClass.value}>
        <div class="ai-mode-inner">
          <div class="ai-input-wrapper">
            <textarea
              ref={textareaRef}
              class="ai-input"
              value={inputValue.value}
              placeholder={t('/唤起,使用自然语言描述你的检索需求...')}
              onInput={handleInput}
              onFocus={handleFocus}
              onBlur={handleBlur}
              rows={1}
              style={{
                height: '24px',
              }}
            />
            <div class="ai-mode-toggle-btn" onClick={handleAiModeToggle}>
              <span class="ai-mode-icon"></span>
              <span class="ai-mode-text">{t('AI 模式 Tab')}</span>
            </div>

          </div>
          {status.value === 'searching' && [
            <div class="ai-loading-info" key="loading-info">
              <span class="ai-loading-text">{t('AI 解析中...')}</span>
            </div>,
            <div class="ai-progress-bar" key="progress-bar"></div>
          ]}
        </div>
        <button class="ai-execute-btn" onClick={handleAiExecute}>
              <svg width="20" height="20" viewBox="0 0 20 20" fill="none" xmlns="http://www.w3.org/2000/svg">
                <path d="M18 2L9 11M18 2L12 18L9 11M18 2L2 8L9 11" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
              </svg>
            </button>
      </div>
    );
  },
}); 