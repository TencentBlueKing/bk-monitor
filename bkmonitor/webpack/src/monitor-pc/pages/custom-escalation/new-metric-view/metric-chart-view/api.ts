export const api = {
  result: true,
  code: 200,
  message: 'OK',
  data: {
    groups: [
      {
        name: '12.31.342.12',
        panels: [
          {
            title: 'cpu_load',
            sub_title: 'custom:laymanmlai:cpu_load',
            targets: [
              {
                data: {
                  expression: 'A',
                  query_configs: [
                    {
                      metrics: [
                        {
                          field: 'value',
                          method: '$method',
                          alias: 'A',
                        },
                      ],
                      interval: '$interval',
                      table: '105_bkmonitor_time_series_568483.__default__',
                      data_label: 'channel_server_connect',
                      data_source_label: 'custom',
                      data_type_label: 'time_series',
                      group_by: ['$group_by'],
                      where: [],
                      functions: [
                        {
                          id: 'time_shift',
                          params: [
                            {
                              id: 'n',
                              value: '$time_shift',
                            },
                          ],
                        },
                      ],
                      filter_dict: {
                        targets: ['$current_target', '$compare_targets'],
                        variables: {},
                      },
                    },
                  ],
                },
                alias: '',
                datasource: 'time_series',
                data_type: 'time_series',
                api: 'grafana.graphUnifyQuery',
              },
            ],
          },
          {
            title: 'connections',
            sub_title: 'custom:laymanmlai:connections',
            targets: [
              {
                expression: 'a',
                alias: '',
                query_configs: [
                  {
                    metrics: [
                      {
                        field: 'connections',
                        method: '',
                        alias: 'a',
                      },
                    ],
                    interval: 'auto',
                    table: '2_bkmonitor_time_series_1572865.__default__',
                    data_label: 'laymanmlai',
                    data_source_label: 'custom',
                    data_type_label: 'time_series',
                    group_by: ['datacenter', 'target'],
                    where: [],
                    functions: [
                      {
                        id: 'top',
                        params: [
                          {
                            id: 'n',
                            value: 10,
                          },
                        ],
                      },
                    ],
                    filter_dict: {},
                  },
                ],
              },
            ],
          },
          {
            title: 'connections',
            sub_title: 'custom:laymanmlai:connections',
            targets: [
              {
                expression: 'a',
                alias: '',
                query_configs: [
                  {
                    metrics: [
                      {
                        field: 'connections',
                        method: '',
                        alias: 'a',
                      },
                    ],
                    interval: 'auto',
                    table: '2_bkmonitor_time_series_1572865.__default__',
                    data_label: 'laymanmlai',
                    data_source_label: 'custom',
                    data_type_label: 'time_series',
                    group_by: ['datacenter', 'target'],
                    where: [],
                    functions: [
                      {
                        id: 'top',
                        params: [
                          {
                            id: 'n',
                            value: 10,
                          },
                        ],
                      },
                    ],
                    filter_dict: {},
                  },
                ],
              },
            ],
          },
        ],
      },
      {
        name: '12.31.342.66',
        panels: [
          {
            title: 'cpu_load',
            sub_title: 'custom:laymanmlai:cpu_load',
            targets: [
              {
                data: {
                  expression: 'A',
                  query_configs: [
                    {
                      metrics: [
                        {
                          field: 'value',
                          method: '$method',
                          alias: 'A',
                        },
                      ],
                      interval: '$interval',
                      table: '105_bkmonitor_time_series_568483.__default__',
                      data_label: 'channel_server_connect',
                      data_source_label: 'custom',
                      data_type_label: 'time_series',
                      group_by: ['$group_by'],
                      where: [],
                      functions: [
                        {
                          id: 'time_shift',
                          params: [
                            {
                              id: 'n',
                              value: '$time_shift',
                            },
                          ],
                        },
                      ],
                      filter_dict: {
                        targets: ['$current_target', '$compare_targets'],
                        variables: {},
                      },
                    },
                  ],
                },
                alias: '',
                datasource: 'time_series',
                data_type: 'time_series',
                api: 'grafana.graphUnifyQuery',
              },
            ],
          },
          {
            title: 'connections',
            sub_title: 'custom:laymanmlai:connections',
            targets: [
              {
                expression: 'a',
                alias: '',
                query_configs: [
                  {
                    metrics: [
                      {
                        field: 'connections',
                        method: '',
                        alias: 'a',
                      },
                    ],
                    interval: 'auto',
                    table: '2_bkmonitor_time_series_1572865.__default__',
                    data_label: 'laymanmlai',
                    data_source_label: 'custom',
                    data_type_label: 'time_series',
                    group_by: ['datacenter', 'target'],
                    where: [],
                    functions: [
                      {
                        id: 'top',
                        params: [
                          {
                            id: 'n',
                            value: 10,
                          },
                        ],
                      },
                    ],
                    filter_dict: {},
                  },
                ],
              },
            ],
          },
        ],
      },
    ],
  },
};
export const mockParam = {
  bk_biz_id: 2,
  time_series_group_id: 10,
  metrics: ['cpu_load', 'connections', 'service_type', 'os'],
  group_by: [
    {
      field: 'database',
      split: false, // 拆图
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
