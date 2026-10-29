/* Copyright (C) 2021 THL A29 Limited, a Tencent company.
 * 蓝鲸智云PaaS平台 (BlueKing PaaS), MIT License. */
export type EtlParams = {
  retain_original_text?: boolean;
  original_text_is_case_sensitive?: boolean;
  retain_extra_json?: boolean;
  ext_json_config?: Record<string, unknown>;
  separator?: string;
  separator_regexp?: string;
  is_grok?: boolean;
  path_regexp?: string | null;
  metadata_fields?: EtlField[];
  original_text_tokenize_on_chars?: string;
  enable_retain_content?: boolean;
  record_parse_failure?: boolean;
  [key: string]: unknown;
};

export type EtlField = {
  alias_name?: string;
  description?: string;
  field_type?: string;
  field_index?: number;
  is_built_in?: boolean;
  is_delete?: boolean;
  is_analyzed?: boolean;
  is_case_sensitive?: boolean;
  metadata_type?: string;
  tokenize_on_chars?: string;
  value?: string;
  field_name?: string;
  is_time?: boolean;
  option?: {
    time_format?: string;
    time_zone?: number | string;
    [key: string]: unknown;
  };
  [key: string]: unknown;
};

export type EtlConfigInput = {
  clean_type?: string;
  etl_config?: string;
  etl_params?: EtlParams;
  etl_fields?: EtlField[];
};

export interface CleanFormState {
  table_id: string;
  etl_config: string;
  etl_params: EtlParams;
  etl_fields: EtlField[];
  fields: EtlField[];
  visible_type: string;
  visible_bk_biz_id: (string | number)[];
  log_original: string;
  log_reporting_time: boolean;
  field_name: string;
  time_format: string;
  time_zone: string | number;
}
export interface CleanTemplate extends EtlConfigInput {
  clean_template_id: number;
  name: string;
  description?: string;
  clean_type: string;
}

export type TemplateConfigSnapshot = {
  clean_type: string;
  etl_params: EtlParams;
  etl_fields: EtlField[];
};

