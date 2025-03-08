export const mockParam = {
  bk_biz_id: 2,
  time_series_group_id: 10,
  metrics: ['cpu_load', 'connections', 'service_type', 'os'],
  group_by: [
    {
      field: 'database',
      split: true, // 拆图
    },
    {
      field: 'datacenter',
      split: false, // 不拆图
    },
  ],
  limit: {
    function: 'top', // top/bottom
    limit: 10, // 0不限制
  },
  where: [
    // {
    //   key: 'bk_target_ip',
    //   method: 'eq',
    //   value: ['127.0.0.1'],
    // },
    // {
    //   condition: 'or', // and/or
    //   key: 'bk_target_ip',
    //   method: 'eq', // eq/neq/include/exclude/reg/nreg
    //   value: ['127.0.0.2'],
    // },
  ],
  // 常用维度过滤
  common_conditions: [
    // { key: 'target', method: 'eq', value: ['127.0.0.1'] }
  ],
  // 对比配置
  compare: {
    type: 'time', // time/metric
    offset: [
      // d天/h小时
      '1d',
      '1h',
    ],
  },
  start_time: 1740567339,
  end_time: 1740567839,
};
