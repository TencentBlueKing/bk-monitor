/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 *
 * Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
 *
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) is licensed under the MIT License.
 *
 * License for 蓝鲸智云PaaS平台 (BlueKing PaaS):
 *
 * ---------------------------------------------------
 * Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated
 * documentation files (the "Software"), to deal in the Software without restriction, including without limitation
 * the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and
 * to permit persons to whom the Software is furnished to do so, subject to the following conditions:
 *
 * The above copyright notice and this permission notice shall be included in all copies or substantial portions of
 * the Software.
 *
 * THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO
 * THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
 * AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF
 * CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS
 * IN THE SOFTWARE.
 */

import { Ref } from "vue";

/**
 * 通知列表
 */

export interface ConfigInfo {
  id: number;
  created_at: string;
  created_by: string;
  updated_at: string;
  updated_by: string;
  is_deleted: boolean;
  deleted_at: null | string;
  deleted_by: null | string;
  group_fields: string[];
  collector_config_id: number;
  collector_config_name_en: string;
  index_set_id: number;
  min_members: number;
  max_dist_list: string;
  predefined_varibles: string;
  delimeter: string;
  max_log_length: number;
  is_case_sensitive: number;
  depth: number;
  max_child: number;
  clustering_fields: string;
  filter_rules: any[];
  bk_biz_id: number;
  related_space_pre_bk_biz_id: number;
  pre_treat_flow: null | any;
  new_cls_pattern_rt: string;
  new_cls_index_set_id: null | number;
  bkdata_data_id: number;
  bkdata_etl_result_table_id: string;
  bkdata_etl_processing_id: string;
  log_bk_data_id: null | number;
  signature_enable: boolean;
  pre_treat_flow_id: null | number;
  after_treat_flow: null | any;
  after_treat_flow_id: null | number;
  source_rt_name: string;
  category_id: string;
  python_backend: null | any;
  es_storage: string;
  modify_flow: null | any;
  options: null | any;
  task_records: {
    time: number;
    operate: string;
    task_id: string;
  }[];
  task_details: any;
  model_output_rt: string;
  clustered_rt: string;
  signature_pattern_rt: string;
  predict_flow: {
    es: {
      expires: string;
      has_replica: string;
      json_fields: string;
      analyzed_fields: string;
      doc_values_fields: string;
    };
    bk_biz_id: number;
    es_cluster: string;
    is_flink_env: boolean;
    result_table_id: string;
    format_signature: {
      fields: string;
      table_name: string;
      filter_rule: string;
      result_table_id: string;
    };
    table_name_no_id: string;
    clustering_predict: {
      model_id: string;
      table_name: string;
      input_fields: string;
      output_fields: string;
      result_table_id: string;
      model_release_id: number;
      clustering_training_params: {
        depth: number;
        st_list: string;
        delimeter: string;
        max_child: number;
        max_dist_list: string;
        max_log_length: number;
        is_case_sensitive: number;
        use_offline_model: number;
        predefined_variables: string;
      };
    };
    clustering_stream_source: {
      fields: string;
      table_name: string;
      filter_rule: string;
      result_table_id: string;
    };
  };
  predict_flow_id: number;
  online_task_id: number;
  log_count_aggregation_flow: {
    cluster: string;
    bk_biz_id: number;
    storage_type: string;
    result_table_id: string;
    tspider_storage: {
      cluster: string;
      expires: number;
    };
    table_name_no_id: string;
    log_count_signatures: string[];
    log_count_aggregation: {
      fields: string;
      table_name: string;
      filter_rule: string;
      result_table_id: string;
    };
  };
  log_count_aggregation_flow_id: number;
  new_cls_strategy_enable: boolean;
  new_cls_strategy_output: string;
  normal_strategy_enable: boolean;
  normal_strategy_output: string;
  access_finished: boolean;
  regex_rule_type: string;
  regex_template_id: number;
}
const getConfig = {
  url: "/clustering_config/:index_set_id/config/",
  method: "get",
};

const getDefaultConfig = {
  url: "/clustering_config/default_config/",
  method: "get",
};

const debug = {
  url: "/clustering_config/debug/",
  method: "post",
};
export interface LogPattern {
  pattern: string; // 格式化后的日志模式（包含占位符如 #NUMBER#）
  origin_pattern: string; // 原始日志模式
  remark: any[]; // 备注信息（数组类型，具体结构未知）
  owners: Ref<any[]>; // 负责人列表（数组类型，具体结构未知）
  count: number; // 该模式出现的次数
  signature: string; // 模式签名（唯一标识符）
  percentage: number; // 占比（如 10.00168170960309 表示 10.00%）
  is_new_class: boolean; // 是否为新类别
  origin_log: string; // 原始日志
  year_on_year_count: number; // 同比数量
  year_on_year_percentage: number; // 同比百分比
  group: string[]; // 分组信息（包含主机ID、云ID、日志路径、服务器IP等）
  strategy_id: number; // 关联的策略ID
  strategy_enabled: boolean; // 策略是否启用
  id: number; // 前端加的唯一标识
}

const clusterSearch = {
  url: "/pattern/:index_set_id/search/",
  method: "post",
};

const closeClean = {
  url: "/databus/collectors/:collector_config_id/close_clean/",
  method: "post",
};

const updateStrategies = {
  url: "/clustering_monitor/:index_set_id/update_strategies/",
  method: "post",
};

const getFingerLabels = {
  url: "/pattern/:index_set_id/labels/",
  method: "post",
};

const updateNewClsStrategy = {
  url: "/clustering_monitor/:index_set_id/update_new_cls_strategy/",
  method: "post",
};

const checkRegexp = {
  url: "/clustering_config/check_regexp/",
  method: "post",
};

// 设置备注
const setRemark = {
  url: "/pattern/:index_set_id/remark/ ",
  method: "post",
};

// 更新备注
const updateRemark = {
  url: "/pattern/:index_set_id/update_remark/ ",
  method: "put",
};

// 删除备注
const deleteRemark = {
  url: "/pattern/:index_set_id/delete_remark/ ",
  method: "delete",
};

// 设置负责人
const setOwner = {
  url: "/pattern/:index_set_id/owner/",
  method: "post",
};

// 获取当前pattern所有负责人列表
const getOwnerList = {
  url: "/pattern/:index_set_id/list_owners/",
  method: "get",
};

// 第一次进数据指纹时候的分组
const updateInitGroup = {
  url: "/pattern/:index_set_id/group_fields/",
  method: "post",
};
export interface RuleTemplate {
  id: number;
  space_uid: string;
  template_name: string;
  predefined_varibles: string; // 看起来是经过编码的字符串（可能是base64或其他编码）
  related_index_set_list: {
    index_set_id: number;
    index_set_name: string;
  }[];
}

// 模板列表
const ruleTemplate = {
  url: "/regex_template/?space_uid=:space_uid",
  method: "get",
};

// 创建模板
const createTemplate = {
  url: "/regex_template/",
  method: "post",
};

// 更新模板（名称）
const updateTemplateName = {
  url: "/regex_template/:regex_template_id/",
  method: "patch",
};

// 删除模板
const deleteTemplate = {
  url: "/regex_template/:regex_template_id/",
  method: "delete",
};

// 日志聚类-告警策略开关
const updatePatternStrategy = {
  url: "/pattern/:index_set_id/pattern_strategy/",
  method: "post",
};
export {
  getConfig,
  getDefaultConfig,
  debug,
  clusterSearch,
  closeClean,
  updateStrategies,
  getFingerLabels,
  updateNewClsStrategy,
  checkRegexp,
  setRemark,
  setOwner,
  updateRemark,
  deleteRemark,
  getOwnerList,
  updateInitGroup,
  ruleTemplate,
  createTemplate,
  updateTemplateName,
  deleteTemplate,
  updatePatternStrategy,
};
