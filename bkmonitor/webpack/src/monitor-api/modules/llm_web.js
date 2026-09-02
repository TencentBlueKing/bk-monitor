import { request } from '../base';

export const listTraces = request('POST', 'apm/llm/list_traces');
export const listSpans = request('POST', 'apm/llm/list_spans');

export default {
  listTraces,
  listSpans,
};
