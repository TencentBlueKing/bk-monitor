/**
 * 路由参数：Tab值
 */
export enum RouteQueryTab {
  /**
   * 原始日志
   */
  // eslint-disable-next-line no-unused-vars
  ORIGIN = 'origin',

  /**
   * 日志聚类
   */
  // eslint-disable-next-line no-unused-vars
  CLUSTERING = 'clustering',

  /**
   * 图表分析
   */
  // eslint-disable-next-line no-unused-vars
  GRAPH_ANALYSIS = 'graph_analysis',

  /**
   * 图表分析（兼容旧版本）
   */
  GRAPH_ANALYSIS_LEGACY = 'graphAnalysis',

  /**
   * Grep 报告
   */
  // eslint-disable-next-line no-unused-vars
  GREP = 'grep',
}

export type ISearchResultTab = typeof RouteQueryTab;
