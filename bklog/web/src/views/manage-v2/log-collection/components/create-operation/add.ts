export const add = {
  collector_config_name: "test0909",
  collector_config_name_en: "test0909",
  collector_scenario_id: "section",
  description: "",
  environment: "linux",
  data_link_id: 6,
  category_id: "host_process",
  target_node_type: "INSTANCE",
  target_object_type: "HOST",
  target_nodes: [
    {
      bk_host_id: 2000059165,
    },
    {
      bk_host_id: 2000061920,
    },
  ],
  data_encoding: "UTF-8",
  params: {
    multiline_pattern: "test",
    multiline_max_lines: "50",
    multiline_timeout: "2",
    paths: ["/path", "/log"],
    exclude_files: ["/test/", "/hello"],
    conditions: {
      type: "match",
      separator: "|",
      separator_filters: [
        {
          fieldindex: "-1",
          word: "111",
          op: "=",
          logic_op: "and",
        },
        {
          fieldindex: "-1",
          word: "222",
          op: "=",
          logic_op: "and",
        },
        {
          fieldindex: "-1",
          word: "344",
          op: "=",
          logic_op: "or",
        },
        {
          fieldindex: "-1",
          word: "555",
          op: "=",
          logic_op: "and",
        },
      ],
    },
    winlog_name: [],
    winlog_level: [],
    winlog_event_id: [],
    extra_labels: [
      {
        key: "bk_module_id",
        value: "scope",
      },
      {
        key: "value",
        value: "2",
        duplicateKey: false,
      },
      {
        key: "timestamp",
        value: "11",
        duplicateKey: false,
      },
    ],
  },
  bk_biz_id: "100605",
};
// {
//   "view_roles": [],
//   "space_uid": "bkcc__100605",
//   "scenario_id": "es",
//   "index_set_name": "ts0924",
//   "category_id": "host_process",
//   "storage_cluster_id": 48,
//   "indexes": [
//       {
//           "bk_biz_id": "100605",
//           "result_table_id": "*bklog*",
//           "scenarioId": "es"
//       }
//   ],
//   "target_fields": [
//       "ad"
//   ],
//   "sort_fields": [
//       "__ext_json"
//   ],
//   "time_field": "dtEventTimeStamp",
//   "time_field_type": "date",
//   "time_field_unit": "microsecond"
// }
