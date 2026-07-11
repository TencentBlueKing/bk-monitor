/*
 * Static copy-row sanitize regression test.
 *
 * Run:
 *   node scripts/row-copy-sanitize-test.js
 */

const assert = require('node:assert/strict');

const getCopyFieldValue = (row, fieldName) => {
  if (Object.hasOwn(row, fieldName)) {
    return { exists: true, value: row[fieldName] };
  }
  if (!fieldName.includes('.')) return { exists: false, value: undefined };
  const path = fieldName.split('.');
  let current = row;
  for (const key of path) {
    if (!current || Object.prototype.toString.call(current) !== '[object Object]' || !Object.hasOwn(current, key)) {
      return { exists: false, value: undefined };
    }
    current = current[key];
  }
  return { exists: true, value: current };
};

const sanitizeCopyRow = (row, copyExcludedFields = [], includeFields = []) => {
  if (!row) return undefined;
  const excludedFieldSet = new Set(copyExcludedFields);
  const fieldNames = includeFields.length ? includeFields : Object.keys(row);
  return fieldNames.reduce((output, key) => {
    if (excludedFieldSet.has(key)) return output;
    const fieldValue = getCopyFieldValue(row, key);
    if (!fieldValue.exists) return output;
    output[key] = fieldValue.value;
    return output;
  }, {});
};

const getCopyRow = (entity, options = {}) => {
  if (!entity?.row) return undefined;
  return sanitizeCopyRow(entity.row, entity.copyExcludedFields, options.includeFields);
};

const rawRow = {
  __highlight: {
    log: ['abc<mark>def</mark>'],
  },
  __id__: 'doc-id',
  index: 'index-name',
  log: 'abcdef',
  level: 'DEBUG',
  empty: '',
  nullable: null,
  nested: {
    value: 'nested-value',
  },
};
const rawCopied = sanitizeCopyRow(rawRow);

assert.deepEqual(rawCopied, {
  __highlight: {
    log: ['abc<mark>def</mark>'],
  },
  __id__: 'doc-id',
  index: 'index-name',
  log: 'abcdef',
  level: 'DEBUG',
  empty: '',
  nullable: null,
  nested: {
    value: 'nested-value',
  },
});

const filteredCopied = sanitizeCopyRow(rawRow, ['__highlight']);

assert.deepEqual(filteredCopied, {
  __id__: 'doc-id',
  index: 'index-name',
  log: 'abcdef',
  level: 'DEBUG',
  empty: '',
  nullable: null,
  nested: {
    value: 'nested-value',
  },
});

assert.deepEqual(sanitizeCopyRow(rawRow, [], ['log', 'empty', 'nullable', 'missing', 'nested.value']), {
  log: 'abcdef',
  empty: '',
  nullable: null,
  'nested.value': 'nested-value',
});

assert.deepEqual(sanitizeCopyRow(rawRow, ['__highlight'], ['__highlight', 'log']), {
  log: 'abcdef',
});

assert.deepEqual(getCopyRow({ row: { __highlight: {}, log: 'abcdef' } }), { __highlight: {}, log: 'abcdef' });
assert.deepEqual(
  getCopyRow({
    row: { __highlight: {}, log: 'abcdef' },
    copyExcludedFields: [],
  }),
  { __highlight: {}, log: 'abcdef' },
);
assert.deepEqual(
  getCopyRow({
    row: { __highlight: {}, log: 'abcdef' },
    copyExcludedFields: ['__highlight'],
  }),
  { log: 'abcdef' },
);

console.log(JSON.stringify({ rawCopied, filteredCopied }, null, 2));
