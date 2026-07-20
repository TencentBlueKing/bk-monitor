import { getStrategyAndEventCount } from 'monitor-api/modules/scene_view';

/** 获取主机场景告警、策略数量 */
export const getStrategyAndEventCountApi = async (params: {
  scene_id: 'host';
}): Promise<{ strategy_counts: number; event_counts: number }> => {
  return await getStrategyAndEventCount(params).catch(() => {
    return {
      strategy_counts: 0,
      event_counts: 0,
    };
  });
};
