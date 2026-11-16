import type { InjectionKey } from 'vue';

import type { Span } from '../../../../components/trace-view/typings';

type OpenSpanDetail = (span: Partial<Span>) => void;

export const LLM_OPEN_SPAN_DETAIL_KEY: InjectionKey<OpenSpanDetail> = Symbol('llm-open-span-detail');
