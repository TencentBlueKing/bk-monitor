import type { ErrorData } from '../types/g6';

export type TopologyFailure = 'no_result' | 'sync_failed' | 'invalid_data' | 'layout_failed' | 'query_failed';

export function topologyFailure(reason: TopologyFailure, t: (message: string) => string): ErrorData {
  const messages = {
    no_result: [t('暂无图谱结果'), t('当前时间范围内没有可展示的图谱快照')],
    sync_failed: [t('图谱快照同步失败'), t('图谱结果尚未完整同步，请联系管理员检查快照同步链路')],
    invalid_data: [t('图谱快照数据异常'), t('快照中的节点、边或分组不完整，请联系管理员检查')],
    layout_failed: [t('图谱布局失败'), t('图谱数据已获取，但布局未完成，请刷新重试')],
    query_failed: [t('图谱查询失败'), t('暂时无法读取图谱，请检查网络或稍后重试')],
  };
  const [title, msg] = messages[reason];
  return { reason, title, msg, isError: reason !== 'no_result', isNoData: reason === 'no_result' };
}
