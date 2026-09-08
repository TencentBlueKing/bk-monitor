/**
 * 路由参数：Tab值
 */
export enum RouteQueryTab {
  /**
   * 原始日志
   */
  ORIGIN = 'origin',

  /**
   * 日志聚类
   */
  CLUSTERING = 'clustering',

  /**
   * 图表分析
   */
  GRAPH_ANALYSIS = 'graph_analysis',

  /**
   * 图表分析（兼容旧版本）
   */
  GRAPH_ANALYSIS_LEGACY = 'graphAnalysis',

  /**
   * Grep 报告
   */
  GREP = 'grep',
}

export type ISearchResultTab = typeof RouteQueryTab;
