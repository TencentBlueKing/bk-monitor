import { request } from '../base';

export const listTraces = request('POST', 'apm/llm/list_traces');
export const listSpans = request('POST', 'apm/llm/list_spans');
export const timeSeries = request('POST', 'apm/llm/time_series');
export const calculateByRange = request('POST', 'apm/llm/calculate_by_range');

export default {
  listTraces,
  listSpans,
  timeSeries,
  calculateByRange,
};
