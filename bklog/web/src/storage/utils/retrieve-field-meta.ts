/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 */

type FieldItem = Record<string, any>;

export interface RetrieveFieldMetaPayload {
  rawPayload: Record<string, any>;
  normalizedPayload: Record<string, any>;
  rawFields: FieldItem[];
  rawFieldList: FieldItem[];
  aliasFieldList: FieldItem[];
  fieldTree: FieldItem[];
  fieldNameIndex: Record<string, FieldItem>;
  queryAliasIndex: Record<string, FieldItem>;
  widthHints: Record<string, { serverMaxLength?: number }>;
}

const cloneField = (field: FieldItem = {}) => ({ ...field });

const isObject = (value: any) => Object.prototype.toString.call(value) === '[object Object]';

const normalizeRawField = (fieldName: string, field: FieldItem = {}) => {
  const sourceField: FieldItem = isObject(field) ? field : {};
  return {
    ...sourceField,
    field_name: sourceField.field_name ?? fieldName,
    field_alias: sourceField.field_alias ?? sourceField.field_name ?? fieldName,
    query_alias: sourceField.query_alias ?? '',
    field_type: sourceField.field_type ?? sourceField.type ?? 'keyword',
    filterVisible: sourceField.filterVisible ?? true,
    has_repeat_alias_field: false,
    alias_mapping_field: null,
    is_virtual_alias_field: false,
    source_field_names: sourceField.source_field_names ?? [],
  };
};

export const normalizeRetrieveFields = (payload: Record<string, any> = {}) => {
  const { fields } = payload;
  if (Array.isArray(fields)) {
    return fields.map(field => normalizeRawField(field?.field_name, field)).filter(field => field.field_name);
  }

  if (isObject(fields)) {
    return Object.keys(fields)
      .map(fieldName => normalizeRawField(fieldName, fields[fieldName]))
      .filter(field => field.field_name);
  }

  return [];
};

const createObjectNode = (fieldName: string, parentFieldName: string | null, depth: number): FieldItem => {
  const pathParts = fieldName.split('.');
  return {
    field_name: fieldName,
    field_alias: fieldName,
    query_alias: fieldName,
    field_type: 'object',
    filterVisible: true,
    is_virtual_obj_node: true,
    is_built_in: true,
    parentFieldName,
    parent_field_name: parentFieldName,
    fullName: fieldName,
    full_name: fieldName,
    depth,
    path_parts: pathParts,
    child_field_names: [],
    children_count: 0,
  };
};

const ensureObjectNode = (
  fieldMap: Map<string, FieldItem>,
  fieldName: string,
  parentFieldName: string | null,
  depth: number,
) => {
  const existing = fieldMap.get(fieldName);
  if (existing) {
    existing.child_field_names = existing.child_field_names ?? [];
    existing.children_count = existing.children_count ?? existing.child_field_names.length;
    existing.parentFieldName = existing.parentFieldName ?? parentFieldName;
    existing.parent_field_name = existing.parent_field_name ?? parentFieldName;
    existing.fullName = existing.fullName ?? fieldName;
    existing.full_name = existing.full_name ?? fieldName;
    existing.depth = existing.depth ?? depth;
    existing.path_parts = existing.path_parts ?? fieldName.split('.');
    return existing;
  }

  const node = createObjectNode(fieldName, parentFieldName, depth);
  fieldMap.set(fieldName, node);
  return node;
};

export const buildFieldNameIndex = (fields: FieldItem[] = []) =>
  fields.reduce(
    (output, field) => {
      if (field?.field_name) {
        output[field.field_name] = field;
      }
      return output;
    },
    {} as Record<string, FieldItem>,
  );

export const buildQueryAliasIndex = (fields: FieldItem[] = []) =>
  fields.reduce(
    (output, field) => {
      if (field?.query_alias) {
        output[field.query_alias] = field;
      }
      return output;
    },
    {} as Record<string, FieldItem>,
  );

export const buildFieldHierarchy = (fields: FieldItem[] = []) => {
  const fieldMap = new Map<string, FieldItem>();
  const rootNodes: FieldItem[] = [];
  const rootNodeMap = new Map<string, FieldItem>();

  const appendTreeNode = (field: FieldItem) => {
    const parts = field.field_name.split('.');
    let level = rootNodes;
    let levelMap = rootNodeMap;
    let parentFullName: string | null = null;

    parts.forEach((part, index) => {
      const fullName = parentFullName ? `${parentFullName}.${part}` : part;
      const isLeaf = index === parts.length - 1;
      let node = levelMap.get(fullName);
      if (!node) {
        node = isLeaf
          ? {
              ...field,
              parentFieldName: parentFullName,
              parent_field_name: parentFullName,
              fullName,
              full_name: fullName,
              depth: index,
              path_parts: parts,
            }
          : createObjectNode(fullName, parentFullName, index);
        node.children = node.children ?? [];
        levelMap.set(fullName, node);
        level.push(node);
      } else if (isLeaf) {
        Object.assign(node, field, {
          parentFieldName: parentFullName,
          parent_field_name: parentFullName,
          fullName,
          full_name: fullName,
          depth: index,
          path_parts: parts,
        });
      }

      parentFullName = fullName;
      node.children = node.children ?? [];
      node.__childMap = node.__childMap ?? new Map();
      level = node.children;
      levelMap = node.__childMap;
    });
  };

  const rawFieldList: FieldItem[] = [];
  fields.forEach(sourceField => {
    if (!sourceField?.field_name) return;
    const field = cloneField(sourceField);
    const parts = field.field_name.split('.');
    let parentFieldName: string | null = null;

    if (parts.length > 1) {
      parts.slice(0, -1).forEach((_, index) => {
        const fullName = parts.slice(0, index + 1).join('.');
        const objectNode = ensureObjectNode(fieldMap, fullName, parentFieldName, index);
        if (!rawFieldList.includes(objectNode)) {
          rawFieldList.push(objectNode);
        }
        parentFieldName = fullName;
      });
      Object.assign(field, {
        parentFieldName,
        parent_field_name: parentFieldName,
        fullName: field.field_name,
        full_name: field.field_name,
        depth: parts.length - 1,
        path_parts: parts,
      });
    }

    fieldMap.set(field.field_name, field);
    rawFieldList.push(field);
  });

  rawFieldList.forEach(field => {
    const parentName = field.parent_field_name || field.parentFieldName;
    if (parentName && fieldMap.has(parentName)) {
      const parent = fieldMap.get(parentName);
      parent.child_field_names = parent.child_field_names ?? [];
      if (!parent.child_field_names.includes(field.field_name)) {
        parent.child_field_names.push(field.field_name);
        parent.children_count = parent.child_field_names.length;
      }
    }
    appendTreeNode(field);
  });

  const cleanupTree = (nodes: FieldItem[]) =>
    nodes.map(node => {
      const { __childMap, ...rest } = node;
      return {
        ...rest,
        children: node.children?.length ? cleanupTree(node.children) : undefined,
      };
    });

  return {
    rawFieldList,
    fieldTree: cleanupTree(rootNodes),
  };
};

export const buildAliasFieldList = (fields: FieldItem[] = []) => {
  const output = fields.map(cloneField);
  const aliasMap = new Map<string, { fields: FieldItem[] }>();

  output.forEach(field => {
    Object.assign(field, {
      has_repeat_alias_field: false,
      alias_mapping_field: null,
      is_virtual_alias_field: !!field.is_virtual_alias_field,
      source_field_names: field.source_field_names ?? [],
    });

    if (!field.query_alias || field.is_virtual_obj_node) return;
    const group = aliasMap.get(field.query_alias) ?? { fields: [] };
    group.fields.push(field);
    aliasMap.set(field.query_alias, group);
  });

  aliasMap.forEach((group, alias) => {
    if (group.fields.length <= 1) return;
    const firstField = group.fields[0];
    const target = {
      ...firstField,
      field_name: alias,
      field_alias: '',
      query_alias: '',
      is_virtual_alias_field: true,
      has_repeat_alias_field: false,
      alias_mapping_field: null,
      source_field_names: [],
      is_virtual_obj_node: false,
    };

    group.fields.forEach(field => {
      field.has_repeat_alias_field = true;
      field.alias_mapping_field = target;
      if (!target.source_field_names.includes(field.field_name)) {
        target.source_field_names.push(field.field_name);
      }
    });
    output.push(target);
  });

  return output;
};

export const extractWidthHints = (payload: Record<string, any> = {}) => {
  const output: Record<string, { serverMaxLength?: number }> = {};
  const fieldInfo = payload.fields;

  if (Array.isArray(fieldInfo)) {
    fieldInfo.forEach(field => {
      const maxLength = field?.max_length;
      if (field?.field_name && Number.isFinite(Number(maxLength))) {
        output[field.field_name] = { serverMaxLength: Number(maxLength) };
      }
    });
    return output;
  }

  if (isObject(fieldInfo)) {
    Object.keys(fieldInfo).forEach(fieldName => {
      const maxLength = fieldInfo[fieldName]?.max_length;
      if (Number.isFinite(Number(maxLength))) {
        output[fieldName] = { serverMaxLength: Number(maxLength) };
      }
    });
  }

  return output;
};

export const createRetrieveFieldMeta = (payload: Record<string, any> = {}): RetrieveFieldMetaPayload => {
  const rawPayload = { ...payload };
  const rawFields = normalizeRetrieveFields(payload);
  const { rawFieldList, fieldTree } = buildFieldHierarchy(rawFields);
  const aliasFieldList = buildAliasFieldList(rawFieldList);
  const fieldNameIndex = buildFieldNameIndex(aliasFieldList);
  const queryAliasIndex = buildQueryAliasIndex(aliasFieldList);
  const normalizedPayload = {
    ...payload,
    fields: aliasFieldList,
    fieldNameIndex,
    queryAliasIndex,
    fieldTree,
  };

  return {
    rawPayload,
    normalizedPayload,
    rawFields,
    rawFieldList,
    aliasFieldList,
    fieldTree,
    fieldNameIndex,
    queryAliasIndex,
    widthHints: extractWidthHints(payload),
  };
};
