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
      // {
      //   key: '',
      //   value: '',
      // },
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
      // namespaces: [],
      collector_type: 'container_log_config',
      namespaces: ['bcs-system', 'bk-system'],
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
      // container: {
      //   workload_type: '',
      //   workload_name: '',
      //   container_name: '',
      // }, // 容器
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
  // configs: [
  //   {
  //     container: {
  //       workload_type: 'Deployment',
  //       workload_name: 'bk-aiops-serving-kpi',
  //       container_name: '',
  //     },
  //     label_selector: {
  //       match_labels: [],
  //       match_expressions: [],
  //     },
  //     match_labels: [],
  //     match_expressions: [],
  //     data_encoding: 'UTF-8',
  //     params: {
  //       paths: [{ value: '' }],
  //       exclude_files: [{ value: '' }],
  //       conditions: {
  //         type: 'none',
  //       },
  //       winlog_name: [],
  //       winlog_level: [],
  //       winlog_event_id: [],
  //       extra_labels: [],
  //       // 行首正则, char
  //       multiline_pattern: '',
  //       // 最多匹配行数, int
  //       multiline_max_lines: '50',
  //       // 最大耗时, int
  //       multiline_timeout: '2',
  //     },
  //     collector_type: 'container_log_config',
  //     namespaces: ['blueking'],
  //     annotation_selector: {
  //       match_annotations: [],
  //     },
  //   },
  // ],
  yaml_config: '',
  yaml_config_enabled: false,
};

// config: {
//   collector_type: 'container_log_config',
// },
// // 集群ID
// bcs_cluster_id: '',
// params: {
//   // 行首正则, char
//   multiline_pattern: '',
//   // 最多匹配行数, int
//   multiline_max_lines: '50',
//   // 最大耗时, int
//   multiline_timeout: '2',
//   winlog_name: selectLogSpeciesList.value,
//   // 日志路径
//   paths: [{ value: '' }],
//   // 日志黑名单路径
//   exclude_files: [{ value: '' }],
//   // 补充元数据
//   extra_labels: [
//     // 附加日志标签
//     {
//       key: '',
//       value: '',
//     },
//   ],
//   conditions: {
//     type: 'none', // 过滤方式类型 match separator
//     match_type: 'include', // 过滤方式 可选字段 include, exclude
//     match_content: '',
//     separator: '|',
//     separator_filters: [
//       // 分隔符过滤条件
//       { fieldindex: '', word: '', op: '=', logic_op: 'and' },
//     ],
//   },
//   // 是否自动添加Pod中的labels
//   add_pod_label: false,
//   // 是否自动添加Pod中的labels
//   add_pod_annotation: false,
//   // yaml base64
//   yaml_config: '',
//   // 是否以yaml模式结尾
//   yaml_config_enabled: false,
//   configs: [
//     // 配置项列表
//     {
//       namespaces: [],
//       noQuestParams: {
//         letterIndex: 0,
//         scopeSelectShow: {
//           namespace: false,
//           label: true,
//           load: true,
//           containerName: true,
//           annotation: true,
//         },
//         namespaceStr: '',
//         namespacesExclude: '=',
//         containerExclude: '=',
//       },
//       container: {
//         workload_type: '',
//         workload_name: '',
//         container_name: '',
//       }, // 容器
//       containerNameList: [], // 容器名列表
//       labelSelector: [], // 展示用的标签或表达式数组
//       label_selector: {
//         // 指定标签或表达式
//         match_labels: [],
//         match_expressions: [],
//       },
//       match_labels: [],
//       match_expressions: [], // config 为空时回填的标签数组
//       annotationSelector: [],
//       data_encoding: 'UTF-8',
//       params: {
//         paths: [{ value: '' }], // 日志路径
//         exclude_files: [{ value: '' }], // 日志路径黑名单
//         conditions: {
//           type: 'none', // 过滤方式类型 none match separator
//           match_type: 'include', // 过滤方式 可选字段 include, exclude
//           match_content: '',
//           separator: '|',
//           separator_filters: [
//             // 分隔符过滤条件
//             { fieldindex: '', word: '', op: '=', logic_op: 'and' },
//           ],
//         },
//         multiline_pattern: '', // 行首正则, char
//         multiline_max_lines: '50', // 最多匹配行数, int
//         multiline_timeout: '2', // 最大耗时, int
//         winlog_name: [], // windows事件名称
//         winlog_level: [], // windows事件等级
//         winlog_event_id: [], // windows事件id
//       },
//     },
//   ],
// },
