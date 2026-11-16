import { getByPath } from './helpers';

import type { Span } from '../../../../components/trace-view/typings';

function readSpanId(span: Span): string {
  return String(span.span_id || span.spanID || '').trim();
}

function isChildOf(span: Span, parentId: string): boolean {
  return (span.references || []).some(ref => ref.refType === 'CHILD_OF' && ref.spanID === parentId);
}

function readAttr(span: Span, key: string): string {
  const llmVal = span.llm_detail?.attributes ? getByPath(span.llm_detail.attributes, key) : undefined;
  if (llmVal != null && llmVal !== '') return String(llmVal);
  const tag = span.tags?.find(item => item.key === key)?.value;
  if (tag != null && tag !== '') return String(tag);
  const attr = span.attributes?.find(item => item.key === key)?.value;
  if (attr != null && attr !== '') return String(attr);
  return '';
}

/** 按 part.spanId 或当前 Span 下同名 TOOL 子 Span 查找关联详情 */
export function findRelatedToolSpan(
  spans: Span[],
  currentSpanId: string,
  part: { spanId?: string; toolName?: string }
): Span | undefined {
  const spanId = String(part.spanId || '').trim();
  if (spanId) {
    const matched = spans.find(span => readSpanId(span) === spanId);
    if (matched) return matched;
  }

  const toolName = String(part.toolName || '').trim();
  if (!currentSpanId || !toolName) return undefined;

  return spans.find(span => {
    if (!isChildOf(span, currentSpanId)) return false;
    const name = readAttr(span, 'gen_ai.tool.name') || span.operationName || '';
    if (name !== toolName) return false;
    return !span.llm_detail?.span_type || span.llm_detail.span_type === 'TOOL';
  });
}
