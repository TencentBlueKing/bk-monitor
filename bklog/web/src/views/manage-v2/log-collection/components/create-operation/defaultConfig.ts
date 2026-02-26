/**
 * 主机采集配置
 */

export const HOST_COLLECTION_CONFIG = {
  params: {
    // 行首正则, char
    multiline_pattern: '',
    // 最多匹配行数, int
    multiline_max_lines: '50',
    // 最大耗时, int
    multiline_timeout: '2',
    // 日志路径
    paths: [{ value: '' }],
    // 日志黑名单路径
    // exclude_files: [{ value: '' }],
    exclude_files: [],
    // 补充元数据
    extra_labels: [
      // 附加日志标签
      {
        key: '',
        value: '',
      },
    ],
    conditions: {
      type: 'none', // 过滤方式类型 match separator
      match_type: 'include', // 过滤方式 可选字段 include, exclude
      match_content: '',
      separator: '|',
      separator_filters: [
        // 分隔符过滤条件
        { fieldindex: '', word: '', op: '=', logic_op: 'and' },
      ],
    },
  },
};

/**
 * 容器采集配置
 */
export const CONTAINER_COLLECTION_CONFIG = {
  // bcs_cluster_id: 'BCS-K8S-15854',
  bcs_cluster_id: 'BCS-K8S-90000',
  add_pod_label: false,
  add_pod_annotation: false,
  extra_labels: [
    // 附加日志标签
    {
      key: '',
      value: '',
    },
  ],
  configs: [
    // 配置项列表
    {
      namespaces: ['*'],
      collector_type: 'container_log_config',
      // namespaces: ['bcs-system', 'bk-system'],
      noQuestParams: {
        letterIndex: 0,
        scopeSelectShow: {
          namespace: false,
          label: true,
          load: true,
          containerName: true,
          annotation: true,
        },
        namespaceStr: '',
        namespacesExclude: '=',
        containerExclude: '=',
      },
      container: {
        workload_type: '',
        workload_name: '',
        container_name: '',
      },
      containerNameList: [], // 容器名列表
      label_selector: {
        match_labels: [
          // {
          //   key: 'app',
          //   operator: '=',
          //   value: 'ab-test',
          // },
          // {
          //   key: 'app.kubernetes.io/name',
          //   operator: '=',
          //   value: 'bcs-k8s-watch',
          // },
        ],
        match_expressions: [
          // {
          //   key: 'eeee',
          //   operator: 'In',
          //   value: 'eeee,11',
          // },
          // { key: 'ddd', operator: 'Exists', value: '' },
        ],
      },
      annotation_selector: {
        match_annotations: [
          // {
          //   key: 'heeee',
          //   operator: 'In',
          //   value: 'rrrr',
          // },
        ],
      },
      data_encoding: 'UTF-8',
      params: {
        paths: [{ value: '' }], // 日志路径
        exclude_files: [{ value: '' }], // 日志路径黑名单
        conditions: {
          type: 'none', // 过滤方式类型 none match separator
          match_type: 'include', // 过滤方式 可选字段 include, exclude
          match_content: '',
          separator: '|',
          separator_filters: [
            // 分隔符过滤条件
            { fieldindex: '', word: '', op: '=', logic_op: 'and' },
          ],
        },
        multiline_pattern: '', // 行首正则, char
        multiline_max_lines: '50', // 最多匹配行数, int
        multiline_timeout: '2', // 最大耗时, int
        winlog_name: [], // windows事件名称
        winlog_level: [], // windows事件等级
        winlog_event_id: [], // windows事件id
      },
    },
  ],
  yaml_config: '',
  yaml_config_enabled: false,
};
