import { defineComponent, inject } from 'vue';

import { LLM_OBSERVATION_SEARCH_KEY, splitHighlightParts } from '../utils/search';

import './highlight-text.scss';

/** 按搜索词拆分文本并高亮；当前命中用更深的背景色 */
export default defineComponent({
  name: 'LlmHighlightText',
  props: {
    text: {
      type: String,
      default: '',
    },
    /** 与 collectObservationHits 的 blockId 对齐，用于判断哪一段是当前命中 */
    blockId: {
      type: String,
      required: true,
    },
  },
  setup(props) {
    const search = inject(LLM_OBSERVATION_SEARCH_KEY, null);

    return () => {
      const keyword = search?.keyword.value.trim() ?? '';
      if (!keyword || !props.text) return props.text;

      const parts = splitHighlightParts(props.text, keyword);
      const blockHits = (search?.hits.value ?? []).filter(item => item.blockId === props.blockId);
      // 同块多处命中按收集顺序对应全局 index，才能标出当前条
      let matchIndex = 0;

      return (
        <>
          {parts.map((part, index) => {
            if (!part.match) return part.text;
            const hit = blockHits[matchIndex];
            matchIndex += 1;
            const current = hit?.index === search?.activeIndex.value;
            return (
              <span
                key={`${props.blockId}-${index}`}
                class={['llm-highlight-text-mark', { 'is-current': current }]}
                // 定位入口：locateCurrentHit / JSON 块内滚动都查这个标记
                data-llm-search-hit={current ? 'current' : undefined}
              >
                {part.text}
              </span>
            );
          })}
        </>
      );
    };
  },
});
