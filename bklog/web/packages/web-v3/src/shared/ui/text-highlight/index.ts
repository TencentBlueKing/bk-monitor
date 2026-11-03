/* Copyright (C) 2026 Tencent. BlueKing PaaS, MIT License. */
import { defineComponent, h, Text, type Component, type PropType, type StyleValue } from 'vue';
import 'vue-text-highlight/dist/style.css';
import { highlightChunks, type HighlightQueries } from './highlight-chunks';

/** Vue3 renderer for the V2 highlighter contract; no Vue2 lifecycle/slot access. */
export default defineComponent({
  name: 'TextHighlight',
  inheritAttrs: false,
  props: {
    queries: { type: [Array, String, RegExp] as PropType<HighlightQueries>, required: true },
    caseSensitive: Boolean,
    diacriticsSensitive: Boolean,
    highlightStyle: [Object, Array, String] as PropType<StyleValue>,
    highlightClass: [Object, Array, String],
    highlightComponent: { type: [String, Object] as PropType<string | Component>, default: 'mark' },
  },
  setup(props, { attrs, slots }) {
    return () => {
      const first = slots.default?.()[0];
      // V2 accepts plain text, not nested markup. Read the current slot on every
      // render so changing a Pattern does not leave the old highlighted string.
      const text = first?.type === Text ? String(first.children ?? '') : '';
      const rootAttributes: Record<string, unknown> = {};
      const listeners: Record<string, unknown> = {};
      for (const [key, value] of Object.entries(attrs)) {
        if (/^on[A-Z]/.test(key)) listeners[key] = value;
        else rootAttributes[key] = value;
      }
      const highlightAttributes = { ...rootAttributes };
      delete highlightAttributes.class;
      delete highlightAttributes.style;
      const children = highlightChunks(text, props.queries, props).map(chunk => {
        if (!chunk.isHighlighted) return chunk.text;
        return h(props.highlightComponent, {
          ...(typeof props.highlightComponent === 'string' ? {} : highlightAttributes),
          ...listeners,
          class: ['text__highlight', props.highlightClass],
          style: props.highlightStyle,
          key: chunk.highlightIndex,
          index: chunk.highlightIndex,
          text: chunk.text,
        }, typeof props.highlightComponent === 'string' ? chunk.text : { default: () => chunk.text });
      });
      return h('span', rootAttributes, children);
    };
  },
});
