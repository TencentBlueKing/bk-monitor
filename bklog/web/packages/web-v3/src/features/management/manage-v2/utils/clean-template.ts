export type CleanTemplateStatus = 'DRAFT' | 'PUBLISHED';

export interface CleanTemplateSnapshot<TCleanType, TEtlParams, TField> {
  clean_type: TCleanType;
  etl_fields: TField[];
  etl_params: TEtlParams;
}

export interface DraftAwareCleanTemplate<TCleanType, TEtlParams, TField> {
  clean_type: TCleanType;
  etl_fields: TField[];
  etl_params: TEtlParams;
  snapshot?: CleanTemplateSnapshot<TCleanType, TEtlParams, TField> | null;
  status: CleanTemplateStatus;
}

/**
 * 获取模板管理场景使用的最新配置。
 *
 * 草稿仅用于模板列表、详情、编辑与导出；采集项绑定等生效配置场景不得调用此方法。
 */
export const resolveCleanTemplateDraft = <
  TCleanType,
  TEtlParams,
  TField,
  TTemplate extends DraftAwareCleanTemplate<TCleanType, TEtlParams, TField>,
>(
  template: TTemplate,
): TTemplate => {
  if (template.status !== 'DRAFT' || !template.snapshot) {
    return template;
  }

  return {
    ...template,
    clean_type: template.snapshot.clean_type,
    etl_fields: template.snapshot.etl_fields,
    etl_params: template.snapshot.etl_params,
  };
};
