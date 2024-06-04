import { request } from '../base';

export const statistics = request('GET', 'fta/home/statistics/');
export const favorite = request('POST', 'fta/home/favorite/');
export const sticky = request('POST', 'fta/home/sticky/');
export const bizWithAlertStatistics = request('GET', 'fta/home/biz_with_alert_statistics/');

export default {
  statistics,
  favorite,
  sticky,
  bizWithAlertStatistics,
};
