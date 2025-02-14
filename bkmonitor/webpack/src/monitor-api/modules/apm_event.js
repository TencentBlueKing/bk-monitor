import { request } from '../base';

export const eventLogs = request('POST', 'apm/event/event/logs/');
export const eventTopK = request('POST', 'apm/event/event/topk/');
export const eventTotal = request('POST', 'apm/event/event/total/');
export const eventViewConfig = request('POST', 'apm/event/event/view_config/');
export const eventTimeSeries = request('POST', 'apm/event/event/time_series/');

export default {
  eventLogs,
  eventTopK,
  eventTotal,
  eventViewConfig,
  eventTimeSeries,
};
