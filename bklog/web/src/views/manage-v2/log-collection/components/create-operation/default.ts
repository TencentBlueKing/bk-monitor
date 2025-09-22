export const defaultConfig = {
  view_roles: [],
  space_uid: "bkcc__100605",
  scenario_id: "bkdata",
  index_set_name: "test0917",
  category_id: "host_process",
  indexes: [
    {
      result_table_id: "100605_bcs_file_log_oICV",
      result_table_name_alias: "bcs_file_log_oICV",
      bk_biz_id: "100605",
      scenarioId: "bkdata",
    },
    {
      result_table_id: "100605_bcs_file_log_uat8",
      result_table_name_alias: "bcs_file_log_uat8",
      bk_biz_id: "100605",
      scenarioId: "bkdata",
    },
  ],
  target_fields: ["container_id", "dtEventTimeStamp"],
  sort_fields: ["container_id", "log"],
};
