/*
 * Static field metadata regression test.
 *
 * Run:
 *   node scripts/field-meta-static-mock-test.js
 */

const assert = require('node:assert/strict');
const Module = require('node:module');
const path = require('node:path');
const ts = require('typescript');

const srcRoot = path.resolve(__dirname, '../src');
const originalResolveFilename = Module._resolveFilename;
const originalLoad = Module._load;
const resolveWithExtension = (filename) => {
  const fs = require('node:fs');
  if (fs.existsSync(filename) && fs.statSync(filename).isFile()) return filename;
  if (fs.existsSync(`${filename}.ts`)) return `${filename}.ts`;
  if (fs.existsSync(`${filename}.js`)) return `${filename}.js`;
  if (fs.existsSync(path.join(filename, 'index.ts'))) return path.join(filename, 'index.ts');
  if (fs.existsSync(path.join(filename, 'index.js'))) return path.join(filename, 'index.js');
  return filename;
};
Module._resolveFilename = function resolveFilename(request, parent, isMain, options) {
  if (request.startsWith('@/')) {
    return resolveWithExtension(path.resolve(srcRoot, request.slice(2)));
  }
  return originalResolveFilename.call(this, request, parent, isMain, options);
};

const compileTsOrJs = (module, filename) => {
  filename = resolveWithExtension(filename);
  const source = require('node:fs').readFileSync(filename, 'utf8');
  const output = ts.transpileModule(source, {
    compilerOptions: {
      allowJs: true,
      module: ts.ModuleKind.CommonJS,
      target: ts.ScriptTarget.ES2020,
      esModuleInterop: true,
    },
    fileName: filename,
  });
  module._compile(output.outputText, filename);
};
require.extensions['.ts'] = compileTsOrJs;
require.extensions['.js'] = (module, filename) => {
  if (filename.startsWith(srcRoot)) {
    compileTsOrJs(module, filename);
    return;
  }
  const source = require('node:fs').readFileSync(filename, 'utf8');
  module._compile(source, filename);
};

const {
  createRetrieveFieldMeta,
  normalizeRetrieveFields,
} = require(path.resolve(__dirname, '../src/storage/utils/retrieve-field-meta.ts'));
const { retrieveFieldCacheService } = require(path.resolve(
  __dirname,
  '../src/storage/services/retrieve-field-cache.service.ts',
));
Module._load = function load(request, parent, isMain) {
  if (request === '@/storage') {
    return {
      retrieveFieldCacheService,
      storeCacheService: {},
    };
  }
  return originalLoad.call(this, request, parent, isMain);
};
const {
  resolveFieldTree,
  resolveFilteredFieldList,
  resolveRawFieldList,
} = require(path.resolve(__dirname, '../src/store/services/retrieve-query.service.js'));

const response = {
  result: true,
  data: {
    fields: [
      {
        field_type: 'object',
        field_name: '__ext',
        field_alias: '',
        query_alias: '',
        is_display: false,
        es_doc_values: false,
        is_analyzed: false,
        is_built_in: true,
      },
      {
        field_type: 'date',
        field_name: 'time',
        field_alias: '数据上报时间',
        query_alias: '',
        is_display: false,
        es_doc_values: true,
        is_analyzed: false,
        field_operator: [{ operator: '=', label: '=' }],
        is_built_in: true,
      },
      {
        field_type: 'keyword',
        field_name: '__ext.io_kubernetes_pod',
        field_alias: '',
        query_alias: '',
        is_display: true,
        origin_field: '__ext',
        es_doc_values: true,
        is_analyzed: false,
        field_operator: [{ operator: '=', label: '=' }],
        is_built_in: true,
      },
      {
        field_type: 'keyword',
        field_name: '__ext.io_kubernetes_pod_ip',
        field_alias: '',
        query_alias: '',
        is_display: false,
        origin_field: '__ext',
        es_doc_values: true,
        is_analyzed: false,
        field_operator: [{ operator: '=', label: '=' }],
        is_built_in: true,
      },
      {
        field_type: 'text',
        field_name: 'log',
        field_alias: 'original_text',
        query_alias: '',
        is_display: true,
        es_doc_values: false,
        is_analyzed: true,
        field_operator: [{ operator: 'contains match phrase', label: '包含' }],
        is_built_in: true,
      },
      {
        field_type: 'date',
        field_name: 'dtEventTimeStamp',
        field_alias: '数据时间',
        query_alias: '',
        is_display: true,
        es_doc_values: true,
        is_analyzed: false,
        field_operator: [{ operator: '=', label: '=' }],
        is_time: true,
        is_built_in: true,
      },
      {
        field_type: '__virtual__',
        field_name: '__module__',
        field_alias: '模块',
        is_display: false,
        es_doc_values: false,
        is_analyzed: false,
        is_built_in: false,
      },
    ],
    display_fields: ['dtEventTimeStamp', '__ext.io_kubernetes_pod', 'log'],
    default_sort_list: [['dtEventTimeStamp', 'desc']],
    sort_list: [['dtEventTimeStamp', 'desc']],
    time_field: 'dtEventTimeStamp',
    time_field_type: 'date',
    user_custom_config: {
      displayFields: ['dtEventTimeStamp', 'log', '__ext.io_kubernetes_pod_ip'],
      fieldsWidth: {
        log: 991.6875,
        dtEventTimeStamp: 192,
        '__ext.io_kubernetes_pod': 394,
      },
    },
  },
};

const normalizedFields = normalizeRetrieveFields(response.data);
assert.equal(normalizedFields.length, response.data.fields.length, 'normalizeRetrieveFields 应保留接口字段数组');
assert.ok(normalizedFields.every(field => field.field_name), '每个字段都必须有 field_name');
assert.ok(normalizedFields.every(field => field.filterVisible === true), '每个字段都必须补齐 filterVisible=true');

const meta = createRetrieveFieldMeta({
  ...response.data,
  fields: normalizedFields,
});

assert.ok(meta.rawFields.length >= response.data.fields.length, 'rawFields 不能为空');
assert.ok(meta.rawFieldList.some(field => field.field_name === '__ext'), 'dotted 字段必须生成 __ext 父节点');
assert.ok(
  meta.rawFieldList.some(field => field.field_name === '__ext.io_kubernetes_pod'),
  'rawFieldList 必须包含 __ext.io_kubernetes_pod',
);
assert.ok(
  meta.aliasFieldList.some(field => field.field_name === '__ext.io_kubernetes_pod'),
  'aliasFieldList 必须包含 __ext.io_kubernetes_pod',
);
assert.ok(meta.fieldTree.length > 0, 'fieldTree 不能为空');

const filteredFieldList = meta.aliasFieldList.filter(field => !field.is_virtual_alias_field);
assert.ok(filteredFieldList.length > 0, 'filteredFieldList 不能为空');
assert.ok(filteredFieldList.some(field => field.filterVisible), 'field-filter 空态判断必须为有字段');

const visibleFieldNames = new Set(response.data.user_custom_config.displayFields);
const hiddenFields = filteredFieldList.filter(field => !visibleFieldNames.has(field.field_name));
assert.ok(hiddenFields.length > 0, 'field-filter 可选字段不能为空');

const scope = 'static-mock-scope';
retrieveFieldCacheService.setMeta(scope, {
  ...response.data,
  fields: normalizedFields,
});
const cachedFilteredFieldList = retrieveFieldCacheService.getFieldList(scope, true)
  .filter(field => !field.has_repeat_alias_field);
const cachedRawFieldList = retrieveFieldCacheService.getFieldList(scope, false);
const cachedFieldTree = retrieveFieldCacheService.getFieldTree(scope);

assert.equal(cachedFilteredFieldList.length, filteredFieldList.length, 'cache filteredFieldList 长度必须一致');
assert.ok(cachedRawFieldList.some(field => field.field_name === '__ext.io_kubernetes_pod'), 'cache rawFieldList 必须包含字段');
assert.ok(cachedFieldTree.length > 0, 'cache fieldTree 不能为空');

const mockState = {
  fieldMetaVersion: 1,
  indexId: '32971',
  indexFieldInfo: {
    field_scope: scope,
    field_meta_version: 1,
  },
  storage: {
    SHOW_FIELD_ALIAS: false,
  },
};
const getterFilteredFieldList = resolveFilteredFieldList(mockState);
const getterRawFieldList = resolveRawFieldList(mockState);
const getterFieldTree = resolveFieldTree(mockState);

assert.equal(getterFilteredFieldList.length, cachedFilteredFieldList.length, 'getter filteredFieldList 必须读到缓存字段');
assert.equal(getterRawFieldList.length, cachedRawFieldList.length, 'getter rawFieldList 必须读到缓存字段');
assert.equal(getterFieldTree.length, cachedFieldTree.length, 'getter fieldTree 必须读到缓存树');

const mutationScope = 'static-mock-mutation-scope';
const mutationPayload = {
  ...response.data,
  fields: normalizedFields,
  field_scope: mutationScope,
  default_sort_list: response.data.default_sort_list,
};
const mutationState = {
  fieldMetaVersion: 0,
  indexId: '32971',
  indexFieldInfo: {
    field_scope: '',
    field_meta_version: 0,
  },
  storage: {
    SHOW_FIELD_ALIAS: false,
  },
};
retrieveFieldCacheService.setMeta(mutationScope, mutationPayload);
const stateData = {
  default_sort_list: mutationPayload.default_sort_list,
  display_fields: mutationPayload.display_fields,
  sort_list: mutationPayload.sort_list,
  time_field: mutationPayload.time_field,
  time_field_type: mutationPayload.time_field_type,
  user_custom_config: mutationPayload.user_custom_config,
};
Object.assign(mutationState.indexFieldInfo, stateData);
mutationState.indexFieldInfo.field_scope = mutationScope;
mutationState.fieldMetaVersion += 1;
mutationState.indexFieldInfo.field_meta_version = mutationState.fieldMetaVersion;

const mutationFilteredFieldList = resolveFilteredFieldList(mutationState);
const mutationRawFieldList = resolveRawFieldList(mutationState);
const mutationFieldTree = resolveFieldTree(mutationState);
const fieldFilterTotalFields = mutationFilteredFieldList.map(field => ({
  ...field,
  minWidth: field.minWidth ?? 0,
  filterExpand: field.filterExpand ?? false,
  filterVisible: field.filterVisible ?? true,
}));
const fieldFilterVisibleFieldNames = new Set(response.data.user_custom_config.displayFields);
const fieldFilterHiddenFields = fieldFilterTotalFields.filter(field => !fieldFilterVisibleFieldNames.has(field.field_name));
const defaultVisibleFieldsMap = new Map();
retrieveFieldCacheService.getFieldList(mutationScope, false).forEach((field) => {
  const existing = defaultVisibleFieldsMap.get(field.field_name);
  if (!existing || !field.is_virtual_alias_field) {
    defaultVisibleFieldsMap.set(field.field_name, field);
  }
});
const defaultVisibleFields = mutationState.indexFieldInfo.display_fields
  .map(displayName => defaultVisibleFieldsMap.get(displayName))
  .filter(Boolean);

assert.ok(mutationFilteredFieldList.length > 0, 'mutation 后 filteredFieldList 不能为空');
assert.ok(mutationRawFieldList.length > 0, 'mutation 后 rawFieldList 不能为空');
assert.ok(mutationFieldTree.length > 0, 'mutation 后 fieldTree 不能为空');
assert.ok(fieldFilterTotalFields.length > 0, 'FieldFilterComp totalFields 不能为空');
assert.ok(fieldFilterHiddenFields.length > 0, 'FieldFilterComp hiddenFields 不能为空');
assert.deepEqual(
  defaultVisibleFields.map(field => field.field_name),
  response.data.display_fields,
  '没有用户字段配置时必须使用接口 display_fields 生成默认展示字段',
);

const loadingOnlyPayload = { is_loading: false };
Object.assign(mutationState.indexFieldInfo, loadingOnlyPayload);
const afterLoadingOnlyFilteredFieldList = resolveFilteredFieldList(mutationState);
assert.equal(
  mutationState.indexFieldInfo.field_scope,
  mutationScope,
  '无 fields 的 updateIndexFieldInfo 不能覆盖 field_scope',
);
assert.equal(
  afterLoadingOnlyFilteredFieldList.length,
  mutationFilteredFieldList.length,
  'finally 里的 is_loading=false 不能清空字段列表',
);

console.log(JSON.stringify({
  normalizedFields: normalizedFields.length,
  rawFields: meta.rawFields.length,
  rawFieldList: meta.rawFieldList.length,
  aliasFieldList: meta.aliasFieldList.length,
  fieldTree: meta.fieldTree.length,
  filteredFieldList: filteredFieldList.length,
  hiddenFields: hiddenFields.length,
  cachedFilteredFieldList: cachedFilteredFieldList.length,
  cachedRawFieldList: cachedRawFieldList.length,
  cachedFieldTree: cachedFieldTree.length,
  getterFilteredFieldList: getterFilteredFieldList.length,
  getterRawFieldList: getterRawFieldList.length,
  getterFieldTree: getterFieldTree.length,
  mutationFilteredFieldList: mutationFilteredFieldList.length,
  mutationRawFieldList: mutationRawFieldList.length,
  mutationFieldTree: mutationFieldTree.length,
  fieldFilterTotalFields: fieldFilterTotalFields.length,
  fieldFilterHiddenFields: fieldFilterHiddenFields.length,
  defaultVisibleFields: defaultVisibleFields.length,
  afterLoadingOnlyFilteredFieldList: afterLoadingOnlyFilteredFieldList.length,
}, null, 2));
