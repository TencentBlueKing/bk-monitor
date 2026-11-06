/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 *
 * Copyright (C) 2017-2025 Tencent.  All rights reserved.
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
type CellValue = boolean | null | number | string;
type ExcelRow = Record<string, CellValue>;

interface ZipEntry {
  compressedSize: number;
  crc: number;
  flags: number;
  method: number;
  offset: number;
  size: number;
}

// 只解压导入所需的 XML，限制累计解压体积，避免小压缩包占用过量内存。
const MAX_XML_SIZE = 100 * 1024 * 1024;
const crcTable = Uint32Array.from({ length: 256 }, (_, value) => {
  for (let bit = 0; bit < 8; bit++) value = value & 1 ? 0xedb88320 ^ (value >>> 1) : value >>> 1;
  return value >>> 0;
});

/** 仅用于拨测模板导入：读取首工作表的原始值，不渲染样式或计算公式。 */
export async function parseXlsx(buffer: ArrayBuffer): Promise<ExcelRow[]> {
  const readXml = createXmlReader(buffer);
  const rootRelationships = await readXml('_rels/.rels', 'Relationships');
  const workbookRelationship = children(rootRelationships, 'Relationship').find(item =>
    item.getAttribute('Type')?.endsWith('/officeDocument')
  );
  const workbookPath = relationshipPath('', workbookRelationship);
  const workbook = await readXml(workbookPath, 'workbook');
  const sheet = descendants(workbook, 'sheet')[0];
  check(sheet);
  const sheetId = Array.from(sheet.attributes).find(attribute => attribute.localName === 'id')?.value;
  check(sheetId);
  const slash = workbookPath.lastIndexOf('/') + 1;
  const relationships = children(
    await readXml(`${workbookPath.slice(0, slash)}_rels/${workbookPath.slice(slash)}.rels`, 'Relationships'),
    'Relationship'
  );
  const sheetRelationship = relationships.find(item => item.getAttribute('Id') === sheetId);
  check(sheetRelationship?.getAttribute('Type')?.endsWith('/worksheet'));
  const stringRelationship = relationships.find(item => item.getAttribute('Type')?.endsWith('/sharedStrings'));
  const strings = stringRelationship
    ? children(await readXml(relationshipPath(workbookPath, stringRelationship), 'sst'), 'si').map(stringValue)
    : [];
  return sheetRows(await readXml(relationshipPath(workbookPath, sheetRelationship), 'worksheet'), strings);
}

function cellValue(cell: Element, strings: string[]): CellValue | undefined {
  const value = children(cell, 'v')[0]?.textContent;
  const type = cell.getAttribute('t');
  if (type === 'inlineStr') {
    const inline = children(cell, 'is')[0];
    return inline ? stringValue(inline) : undefined;
  }
  if (value === undefined || value === null) return undefined;
  if (type === 's') {
    const index = Number(value);
    check(value !== '' && Number.isInteger(index) && index >= 0 && index < strings.length);
    return strings[index];
  }
  if (type === 'str')
    return value.replace(/_x([\da-f]{4})_/gi, (_, code) => String.fromCharCode(Number.parseInt(code, 16)));
  if (type === 'b') return value === '1' || value === 'true';
  if (type === 'e') return value === '#NULL!' ? null : undefined;
  check(!type || type === 'n');
  if (!value.trim()) return undefined;
  const number = Number(value);
  check(Number.isFinite(number));
  return number;
}

function check(condition: unknown): asserts condition {
  if (!condition) throw new Error('Invalid XLSX file');
}

function children(element: Element, name: string) {
  return Array.from(element.children).filter(child => child.localName === name);
}

function coordinate(reference: string) {
  const match = /^([A-Z]+)([1-9]\d*)$/.exec(reference);
  check(match);
  let column = 0;
  for (const character of match[1]) column = column * 26 + character.charCodeAt(0) - 64;
  const row = Number(match[2]);
  check(column <= 16384 && row <= 1048576);
  return { column, row };
}

function createXmlReader(buffer: ArrayBuffer) {
  const view = new DataView(buffer);
  const entries = new Map<string, ZipEntry>();
  const decoder = new TextDecoder();
  let end = buffer.byteLength - 22;
  const earliestEnd = Math.max(0, end - 0xffff);
  for (; end >= earliestEnd; end--) {
    if (view.getUint32(end, true) === 0x06054b50 && end + 22 + view.getUint16(end + 20, true) === buffer.byteLength)
      break;
  }
  check(end >= earliestEnd);
  const count = view.getUint16(end + 10, true);
  const directorySize = view.getUint32(end + 12, true);
  const directoryOffset = view.getUint32(end + 16, true);
  // 拨测模板不使用分卷或 ZIP64；拒绝无法完整读取的目录，不能返回部分任务。
  check(view.getUint32(end + 4, true) === 0 && view.getUint16(end + 8, true) === count);
  check(count !== 0xffff && directoryOffset + directorySize === end);
  let cursor = directoryOffset;
  for (let index = 0; index < count; index++) {
    check(cursor + 46 <= end && view.getUint32(cursor, true) === 0x02014b50);
    const nameLength = view.getUint16(cursor + 28, true);
    const next = cursor + 46 + nameLength + view.getUint16(cursor + 30, true) + view.getUint16(cursor + 32, true);
    check(next <= end);
    const name = decoder.decode(new Uint8Array(buffer, cursor + 46, nameLength));
    check(!entries.has(name));
    entries.set(name, {
      flags: view.getUint16(cursor + 8, true),
      method: view.getUint16(cursor + 10, true),
      crc: view.getUint32(cursor + 16, true),
      compressedSize: view.getUint32(cursor + 20, true),
      size: view.getUint32(cursor + 24, true),
      offset: view.getUint32(cursor + 42, true),
    });
    cursor = next;
  }
  check(cursor === end);
  let totalSize = 0;

  return async (path: string, root: string) => {
    const entry = entries.get(path);
    check(entry && !(entry.flags & 1) && [0, 8].includes(entry.method));
    totalSize += entry.size;
    check(totalSize <= MAX_XML_SIZE);
    check(entry.offset + 30 <= directoryOffset && view.getUint32(entry.offset, true) === 0x04034b50);
    const start = entry.offset + 30 + view.getUint16(entry.offset + 26, true) + view.getUint16(entry.offset + 28, true);
    check(start + entry.compressedSize <= directoryOffset);
    const compressed = new Uint8Array(buffer, start, entry.compressedSize);
    let bytes: Uint8Array;
    if (entry.method === 0) {
      check(entry.size === entry.compressedSize);
      bytes = compressed;
    } else {
      const reader = new Blob([compressed]).stream().pipeThrough(new DecompressionStream('deflate-raw')).getReader();
      const chunks: Uint8Array[] = [];
      let size = 0;
      try {
        while (true) {
          const { done, value } = await reader.read();
          if (done) break;
          size += value.byteLength;
          check(size <= entry.size);
          chunks.push(value);
        }
        check(size === entry.size);
      } finally {
        await reader.cancel();
        reader.releaseLock();
      }
      bytes = new Uint8Array(size);
      let position = 0;
      for (const chunk of chunks) {
        bytes.set(chunk, position);
        position += chunk.byteLength;
      }
    }
    let crc = 0xffffffff;
    for (const byte of bytes) crc = crcTable[(crc ^ byte) & 0xff] ^ (crc >>> 8);
    check((crc ^ 0xffffffff) >>> 0 === entry.crc);
    const encoding =
      bytes[0] === 0xff && bytes[1] === 0xfe
        ? 'utf-16le'
        : bytes[0] === 0xfe && bytes[1] === 0xff
          ? 'utf-16be'
          : 'utf-8';
    const text = new TextDecoder(encoding, { fatal: true }).decode(bytes);
    check(!/<!DOCTYPE/i.test(text));
    const document = new DOMParser().parseFromString(text, 'application/xml');
    check(!descendants(document, 'parsererror').length && document.documentElement.localName === root);
    return document.documentElement;
  };
}

function descendants(element: Document | Element, name: string) {
  return Array.from(element.getElementsByTagNameNS('*', name));
}

function relationshipPath(part: string, relationship: Element | undefined) {
  check(relationship && relationship.getAttribute('TargetMode') !== 'External');
  const target = relationship.getAttribute('Target');
  check(target);
  const path = decodeURIComponent(target.startsWith('/') ? target : part.slice(0, part.lastIndexOf('/') + 1) + target);
  const segments: string[] = [];
  for (const segment of path.split('/')) {
    if (segment === '..') check(segments.pop());
    else if (segment && segment !== '.') segments.push(segment);
  }
  return segments.join('/');
}

function sheetRows(sheet: Element, strings: string[]): ExcelRow[] {
  const data = children(sheet, 'sheetData')[0];
  check(data);
  const rows = new Map<number, Map<number, CellValue>>();
  let nextRow = 1;
  let firstRow = Infinity;
  let firstColumn = Infinity;
  let lastColumn = 0;
  let lastRow = 0;
  for (const row of children(data, 'row')) {
    const rowNumber = row.hasAttribute('r') ? Number(row.getAttribute('r')) : nextRow;
    check(Number.isInteger(rowNumber) && rowNumber > 0 && rowNumber <= 1048576 && !rows.has(rowNumber));
    nextRow = rowNumber + 1;
    const values = new Map<number, CellValue>();
    let nextColumn = 1;
    for (const cell of children(row, 'c')) {
      const reference = cell.getAttribute('r');
      const position = reference ? coordinate(reference) : { column: nextColumn, row: rowNumber };
      check(position.row === rowNumber && position.column <= 16384 && !values.has(position.column));
      nextColumn = position.column + 1;
      const value = cellValue(cell, strings);
      if (value === undefined) continue;
      values.set(position.column, value);
      firstRow = Math.min(firstRow, rowNumber);
      lastRow = Math.max(lastRow, rowNumber);
      firstColumn = Math.min(firstColumn, position.column);
      lastColumn = Math.max(lastColumn, position.column);
    }
    rows.set(rowNumber, values);
  }
  const dimension = children(sheet, 'dimension')[0]?.getAttribute('ref');
  // 部分编辑器另存后只记录末单元格（如 M5）；与旧解析器一致，此时使用实际单元格范围。
  if (dimension?.includes(':')) {
    const [start, end = start] = dimension.split(':').map(coordinate);
    check(start.row <= end.row && start.column <= end.column);
    firstRow = start.row;
    lastRow = end.row;
    firstColumn = start.column;
    lastColumn = end.column;
  }
  if (!Number.isFinite(firstRow)) return [];
  const header = rows.get(firstRow);
  const names = new Map<number, string>();
  const used = new Set<string>();
  for (let column = firstColumn; column <= lastColumn; column++) {
    const value = header?.get(column);
    const name =
      value === undefined || value === null
        ? '__EMPTY'
        : typeof value === 'boolean'
          ? String(value).toUpperCase()
          : String(value);
    let unique = name;
    let suffix = 1;
    while (used.has(unique)) unique = `${name}_${suffix++}`;
    used.add(unique);
    names.set(column, unique);
  }
  const result: ExcelRow[] = [];
  for (const [index, values] of [...rows].sort(([a], [b]) => a - b)) {
    if (index <= firstRow || index > lastRow) continue;
    const cells = [...values].filter(([column]) => names.has(column));
    if (!cells.some(([, value]) => value !== null)) continue;
    // fromEntries 不会把用户填写的 __proto__ 表头解释为原型赋值。
    const row = Object.fromEntries(cells.map(([column, value]) => [names.get(column), value]));
    Object.defineProperty(row, '__rowNum__', { value: index - 1 });
    result.push(row);
  }
  return result;
}

function stringValue(element: Element) {
  // rPh 是拼音注音，不属于单元格内容；保留各文本片段原有的空格和换行。
  const text = Array.from(element.children)
    .map(child =>
      child.localName === 't'
        ? child.textContent
        : child.localName === 'r'
          ? children(child, 't')
              .map(t => t.textContent)
              .join('')
          : ''
    )
    .join('');
  return text.replace(/_x([\da-f]{4})_/gi, (_, code) => String.fromCharCode(Number.parseInt(code, 16)));
}
