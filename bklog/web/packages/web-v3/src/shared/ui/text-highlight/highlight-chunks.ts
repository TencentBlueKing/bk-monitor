/* Copyright (C) 2026 Tencent. BlueKing PaaS, MIT License. */
import sourceHighlighter from 'vue-text-highlight/dist/component.js';

export type HighlightQuery = string | RegExp;
export type HighlightQueries = HighlightQuery | HighlightQuery[];
export interface HighlightChunk {
  text: string;
  isHighlighted: boolean;
  highlightIndex?: number;
}
export interface HighlightOptions {
  caseSensitive?: boolean;
  diacriticsSensitive?: boolean;
}

// 2.0.10 exports a plain options object. Its computed function is a pure matcher;
// it does not require a Vue2 instance. Retain its regex, accent normalization and
// overlapping-range behavior while replacing only the incompatible renderer.
const sourceMatcher = sourceHighlighter.computed.highlights;

export function highlightChunks(text: string, queries: HighlightQueries, options: HighlightOptions = {}): HighlightChunk[] {
  return sourceMatcher.call({ text, queries, ...options });
}
