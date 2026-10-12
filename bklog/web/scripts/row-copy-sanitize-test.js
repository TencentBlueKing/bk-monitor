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
  const output = fieldNames.reduce((result, key) => {
    if (excludedFieldSet.has(key)) return result;
    const fieldValue = getCopyFieldValue(row, key);
    if (!fieldValue.exists) return result;
    result[key] = fieldValue.value;
    return result;
  }, {});
  return Object.keys(output).length ? output : undefined;
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

assert.equal(sanitizeCopyRow(rawRow, [], ['missing']), undefined);
assert.equal(sanitizeCopyRow({}, [], ['log']), undefined);
assert.equal(sanitizeCopyRow(undefined), undefined);

const getCopyRowsFromMemory = (rowsByKey, keys, options = {}) => {
  return keys
    .map(key => sanitizeCopyRow(rowsByKey[key], [], options.includeFields ?? []))
    .filter(Boolean);
};

assert.deepEqual(
  getCopyRowsFromMemory({ 'query:0': rawRow }, ['query:0'], { includeFields: ['log', 'level'] }),
  [{ log: 'abcdef', level: 'DEBUG' }],
);
assert.deepEqual(getCopyRowsFromMemory({ 'query:0': rawRow }, ['query:0'], { includeFields: ['missing'] }), []);
assert.deepEqual(getCopyRowsFromMemory({}, ['query:0'], { includeFields: ['log'] }), []);

const hasCopyableRow = row => Boolean(row && typeof row === 'object' && Object.keys(row).length);
const resolveCopyPayloadFromMemory = (rowsByKey, key, includeFields) => {
  const [filteredRow] = getCopyRowsFromMemory(rowsByKey, [key], { includeFields });
  if (hasCopyableRow(filteredRow)) return filteredRow;
  const [fullRow] = getCopyRowsFromMemory(rowsByKey, [key]);
  return hasCopyableRow(fullRow) ? fullRow : undefined;
};

assert.deepEqual(resolveCopyPayloadFromMemory({ 'query:0': rawRow }, 'query:0', ['log']), { log: 'abcdef' });
assert.deepEqual(resolveCopyPayloadFromMemory({ 'query:0': rawRow }, 'query:0', ['missing']), {
  __highlight: rawRow.__highlight,
  __id__: 'doc-id',
  index: 'index-name',
  log: 'abcdef',
  level: 'DEBUG',
  empty: '',
  nullable: null,
  nested: { value: 'nested-value' },
});
assert.equal(resolveCopyPayloadFromMemory({}, 'query:0', ['log']), undefined);
assert.equal(hasCopyableRow({}), false);
assert.equal(hasCopyableRow(undefined), false);

const copyTextWithFallback = ({ text, clipboardWriteText, execCommand }) => {
  let clipboardText = '';
  let fallbackText = '';
  const fallbackCopy = () => {
    fallbackText = text;
    return execCommand();
  };
  const fallbackOk = fallbackCopy();
  if (typeof clipboardWriteText === 'function') {
    const result = clipboardWriteText(text);
    if (result && typeof result.then === 'function') {
      return result
        .then(() => {
          clipboardText = text;
          return { clipboardText, fallbackText, fallbackOk, copied: true };
        })
        .catch(() => ({ clipboardText, fallbackText, fallbackOk, copied: fallbackOk }));
    }
    clipboardText = text;
    return Promise.resolve({ clipboardText, fallbackText, fallbackOk, copied: true });
  }
  return Promise.resolve({ clipboardText, fallbackText, fallbackOk, copied: fallbackOk });
};

Promise.all([
  copyTextWithFallback({
    text: '{"log":"abcdef"}',
    clipboardWriteText: () => Promise.reject(new Error('lost user activation')),
    execCommand: () => true,
  }).then((result) => {
    assert.equal(result.copied, true);
    assert.equal(result.fallbackOk, true);
    assert.equal(result.fallbackText, '{"log":"abcdef"}');
  }),
  copyTextWithFallback({
    text: '{"log":"abcdef"}',
    clipboardWriteText: value => Promise.resolve(value),
    execCommand: () => false,
  }).then((result) => {
    assert.equal(result.copied, true);
    assert.equal(result.clipboardText, '{"log":"abcdef"}');
  }),
  copyTextWithFallback({
    text: '{"log":"abcdef"}',
    execCommand: () => true,
  }).then((result) => {
    assert.equal(result.copied, true);
    assert.equal(result.fallbackText, '{"log":"abcdef"}');
  }),
]).then(() => {
  console.log(JSON.stringify({ rawCopied, filteredCopied }, null, 2));
}).catch((error) => {
  console.error(error);
  process.exit(1);
});
