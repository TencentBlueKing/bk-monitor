export const testData = [
  {
    type: 'host',
    name: '主机监控',
    items: [
      {
        bk_biz_id: 2,
        bk_biz_name: '蓝鲸',
        name: '127.0.0.1',
        bk_host_innerip: '127.0.0.1',
        bk_cloud_id: 0,
        bk_cloud_name: '默认云区域',
        bk_host_name: '（demo/demo_k8s/k8s)',
        bk_host_id: 12345,
      },
      {
        bk_biz_id: 2,
        bk_biz_name: '蓝鲸',
        name: '127.0.0.1',
        bk_host_innerip: '127.0.0.1',
        bk_cloud_id: 0,
        bk_cloud_name: '默认云区域',
        bk_host_name: '（demo/demo_k8s/k8s)',
        bk_host_id: 12345,
      },
    ],
  },
  {
    type: 'strategy',
    name: '策略',
    items: [
      {
        bk_biz_id: 2,
        bk_biz_name: '王者荣耀',
        name: 'bcs_cluster_12示例-日志采集',
        strategy_id: '127001',
      },
    ],
  },
  {
    type: 'trace',
    name: '容器集群',
    items: [
      {
        bk_biz_id: 2,
        bk_biz_name: '蓝鲸',
        name: 'bcs_cluster_12',
        trace_id: '127.0.0.1',
        app_name: '默认云区域',
        app_alias: 'host-1',
        application_id: 12345,
      },
    ],
  },
];
