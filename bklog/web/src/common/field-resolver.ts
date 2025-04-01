export type FieldItem = {
  field_type: string;
  field_name: string;
  field_alias: string;
  is_display: boolean;
  is_editable: boolean;
  tag: string;
  origin_field: string;
  es_doc_values: boolean;
  is_analyzed: boolean;
  is_virtual_obj_node: boolean;
  field_operator: string[]; // 使用 `any[]` 可以存储任意类型的数组，如果有特定类型可以进一步细化
  is_built_in: boolean;
  is_case_sensitive: boolean;
  tokenize_on_chars: string;
  description: string;
  filterVisible: boolean;
};

/**
 * 格式化层级结构
 * @param field
 */
export const formatHierarchy = (fieldList: Partial<FieldItem>[]) => {
  const result = [];
  for (const field of fieldList) {
    const splitList = field.field_name.split('.');

    if (splitList.length === 1) {
      result.push(field);
      continue;
    }

    let leftName = [];

    for (const name of splitList) {
      leftName.push(name);
      const fieldName = leftName.join('.');
      if (result.findIndex(item => item.field_name === fieldName) === -1) {
        const fieldAlias = fieldName === field.field_name ? field.field_alias : fieldName;
        const fieldType = fieldName === field.field_name ? field.field_type : 'object';
        result.push(
          Object.assign({}, field, {
            field_name: fieldName,
            field_alias: fieldAlias,
            is_virtual_obj_node: fieldName !== field.field_name,
            field_type: fieldType,
          }),
        );
      }
    }
  }

  return result;
};
