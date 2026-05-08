import { request } from '../base';

export const rumAlertQuery = request('POST', 'rum/metric/metric/alert_query/');

export default {
  rumAlertQuery,
};
