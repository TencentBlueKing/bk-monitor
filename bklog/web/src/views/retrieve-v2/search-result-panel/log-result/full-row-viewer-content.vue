<template>
  <div class="bklog-full-row-viewer-content">
    <div class="full-row-toolbar">
      <div class="mode-group">
        <button
          :class="['mode-btn', { active: mode === 'json' }]"
          type="button"
          @click="mode = 'json'"
        >
          JSON
        </button>
        <span class="mode-divider">|</span>
        <button
          :class="['mode-btn', { active: mode === 'text' }]"
          type="button"
          @click="mode = 'text'"
        >
          {{ $t('文本') }}
        </button>
      </div>
      <span class="meta-size">{{ $t('大小') }}: {{ displaySize }}</span>
      <span
        v-if="loading"
        class="meta-status"
      >{{ $t('正在读取全量数据...') }}</span>
      <span
        v-if="loadError"
        class="meta-status load-error"
      >{{ loadError }}</span>
    </div>
    <div
      ref="scrollContainer"
      class="full-row-content"
      @scroll="handleScroll"
    >
      <div class="full-row-dom-content">
        <template v-if="mode === 'json' && jsonRenderRows.length">
          <div class="json-kv-content">
            <div class="json-struct-line">{</div>
            <div
              v-for="row in jsonRenderRows"
              :key="row.key"
              class="json-kv-item"
            >
              <span class="json-key">&quot;{{ row.fieldName }}&quot;</span><span class="json-colon">: </span><template v-if="row.wrapQuotes">&quot;</template><span
                v-for="chunk in row.chunks"
                :key="chunk.key"
                class="json-value"
                v-html="chunk.html"
              ></span><template v-if="row.wrapQuotes">&quot;</template><span
                v-if="row.showComma"
                class="json-comma"
              >,</span>
            </div>
            <div class="json-struct-line">}</div>
          </div>
        </template>
        <template v-else-if="mode === 'text'">
          <div
            v-if="lineNumbers.length"
            class="full-row-line-numbers"
          >
            <span
              v-for="lineNumber in lineNumbers"
              :key="lineNumber"
              class="line-number"
            >{{ lineNumber }}</span>
          </div>
          <div class="text-content-wrap">
            <pre class="content-text"><span
              v-for="chunk in textRenderChunks"
              :key="chunk.key"
              class="text-chunk"
              v-html="chunk.html"
            ></span></pre>
          </div>
        </template>
      </div>
      <div
        v-if="!hasVisibleContent"
        class="empty-content"
      >
        {{ searchKeyword ? $t('未匹配到内容') : $t('暂无内容') }}
      </div>
    </div>
  </div>
</template>

<script>
  import { retrieveRowCacheService } from '@/storage';
  import { copyMessage } from '@/common/util';

  const MAX_SEARCH_MATCHES = 2000;
  const FIELD_CHUNK_SIZE = 16 * 1024;
  const HIGHLIGHT_FIELD_NAME = '__highlight';
  const SCROLL_LOAD_MORE_THRESHOLD = 240;

  const escapeHtml = value => String(value)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');

  const stripMarkTags = value => String(value)
    .replace(/<mark>/gi, '')
    .replace(/<\/mark>/gi, '');

  const stripMarkFromCopyValue = (value) => {
    if (typeof value === 'string') return stripMarkTags(value);
    if (Array.isArray(value)) return value.map(item => stripMarkFromCopyValue(item));
    if (value && Object.prototype.toString.call(value) === '[object Object]') {
      return Object.keys(value).reduce((output, key) => {
        output[key] = stripMarkFromCopyValue(value[key]);
        return output;
      }, {});
    }

    return value;
  };

  const parseMarkedText = (value) => {
    const source = String(value ?? '');
    const markRanges = [];
    let plainText = '';
    let cursor = 0;
    const markReg = /<mark>([\s\S]*?)<\/mark>/gi;
    let match = markReg.exec(source);

    while (match) {
      plainText += source.slice(cursor, match.index);
      const start = plainText.length;
      plainText += match[1];
      markRanges.push({ start, end: plainText.length });
      cursor = match.index + match[0].length;
      match = markReg.exec(source);
    }

    plainText += source.slice(cursor);
    return { plainText, markRanges };
  };

  const tryParseJsonString = (value) => {
    if (typeof value !== 'string') return value;
    const text = value.trim();
    if (!/^(\{|\[)/.test(text)) return value;

    try {
      return JSON.parse(text);
    } catch {
      try {
        return JSON.parse(stripMarkTags(text));
      } catch {
        return value;
      }
    }
  };

  const normalizeJsonValue = (value, depth = 0) => {
    if (depth > 3) return value;
    const parsedValue = tryParseJsonString(value);
    if (parsedValue !== value) return normalizeJsonValue(parsedValue, depth + 1);
    if (Array.isArray(value)) return value.map(item => normalizeJsonValue(item, depth + 1));
    if (value && Object.prototype.toString.call(value) === '[object Object]') {
      return Object.keys(value).reduce((output, key) => {
        output[key] = normalizeJsonValue(value[key], depth + 1);
        return output;
      }, {});
    }

    return value;
  };

  const formatBytes = bytes => {
    if (!Number.isFinite(bytes) || bytes <= 0) return '0 B';
    const units = ['B', 'KB', 'MB', 'GB'];
    let size = bytes;
    let unitIndex = 0;
    while (size >= 1024 && unitIndex < units.length - 1) {
      size /= 1024;
      unitIndex += 1;
    }
    return `${size.toFixed(size >= 10 || unitIndex === 0 ? 0 : 1)} ${units[unitIndex]}`;
  };

  const stringifyContentValue = (value, pretty = false) => {
    if (value === null || value === undefined) return '';
    if (typeof value === 'string') return value;
    if (typeof value === 'bigint') return value.toString();
    try {
      return JSON.stringify(value, (_key, val) => (typeof val === 'bigint' ? val.toString() : val), pretty ? 2 : 0);
    } catch {
      return String(value);
    }
  };

  const getFieldName = field => (typeof field === 'string' ? field : field?.field_name);

  const formatFieldPlainValue = (value) => {
    if (value === null) return { plainText: 'null', markRanges: [], wrapQuotes: false };
    if (value === undefined) return { plainText: '', markRanges: [], wrapQuotes: false };
    if (typeof value === 'boolean') return { plainText: value ? 'true' : 'false', markRanges: [], wrapQuotes: false };
    if (typeof value === 'number' || typeof value === 'bigint') return { plainText: String(value), markRanges: [], wrapQuotes: false };
    if (typeof value === 'string') {
      const { plainText, markRanges } = parseMarkedText(value);
      return { plainText, markRanges, wrapQuotes: true };
    }

    return { plainText: stringifyContentValue(value, false), markRanges: [], wrapQuotes: false };
  };

  export default {
    name: 'FullRowViewerContent',
    props: {
      rowData: { type: Object, default: null },
      rowKey: { type: String, default: '' },
      fields: { type: Array, default: () => [] },
      truncatedFields: { type: Array, default: () => [] },
      searchKeyword: { type: String, default: '' },
      active: { type: Boolean, default: false },
    },
    emits: ['match-update'],
    data() {
      return {
        mode: 'json',
        scrollTop: 0,
        searchVersion: 0,
        activeMatchIndex: -1,
        originRow: null,
        loading: false,
        loadError: '',
        loadSeq: 0,
        resizeObserver: null,
        resizeTimer: null,
        pendingScrollToMatch: false,
        textLoadedChunkCount: 1,
        jsonLoadedBytes: {},
        jsonVisibleFieldCount: 0,
        scrollLoadMoreTimer: null,
        isAppendingChunk: false,
        pendingAppendScrollTop: null,
      };
    },
    computed: {
      displayRow() {
        if (this.originRow) return this.buildDisplayRowWithRenderMarks(this.originRow, this.rowData);
        if (this.rowKey) return null;
        return this.rowData;
      },
      orderedFieldNames() {
        const fieldNames = this.fields.map(getFieldName).filter(fieldName => fieldName && fieldName !== HIGHLIGHT_FIELD_NAME);
        if (!this.displayRow) return fieldNames;
        const rowFieldNames = Object.keys(this.displayRow).filter(fieldName => fieldName !== HIGHLIGHT_FIELD_NAME);
        const orderedFields = fieldNames.filter(fieldName => Object.prototype.hasOwnProperty.call(this.displayRow, fieldName));
        const orderedFieldSet = new Set(orderedFields);
        const extraFields = rowFieldNames.filter(fieldName => !orderedFieldSet.has(fieldName));
        return [...orderedFields, ...extraFields];
      },
      displayRowData() {
        if (!this.displayRow) return null;
        return this.buildOrderedRow(this.displayRow, this.mode === 'json');
      },
      allJsonFieldNames() {
        if (!this.displayRowData) return [];
        const fieldNames = this.orderedFieldNames.length ? this.orderedFieldNames : Object.keys(this.displayRowData);
        return fieldNames.filter(fieldName => fieldName !== HIGHLIGHT_FIELD_NAME
          && Object.prototype.hasOwnProperty.call(this.displayRowData, fieldName));
      },
      textSourceInfo() {
        if (!this.displayRowData) return { plainText: '', markRanges: [] };
        return parseMarkedText(stringifyContentValue(this.displayRowData, false));
      },
      textVisibleLength() {
        return Math.min(this.textSourceInfo.plainText.length, this.textLoadedChunkCount * FIELD_CHUNK_SIZE);
      },
      textVisibleText() {
        return this.textSourceInfo.plainText.slice(0, this.textVisibleLength);
      },
      textVisibleMarkRanges() {
        return this.textSourceInfo.markRanges
          .filter(range => range.start < this.textVisibleLength)
          .map(range => ({ start: range.start, end: Math.min(range.end, this.textVisibleLength) }));
      },
      textRenderChunks() {
        if (this.mode !== 'text') return [];
        const chunks = [];
        for (let start = 0; start < this.textVisibleText.length; start += FIELD_CHUNK_SIZE) {
          const chunkText = this.textVisibleText.slice(start, start + FIELD_CHUNK_SIZE);
          chunks.push({
            key: `text-${start}`,
            html: this.buildHighlightedHtml({
              text: chunkText,
              markRanges: this.textVisibleMarkRanges
                .filter(range => range.end > start && range.start < start + chunkText.length)
                .map(range => ({ start: Math.max(0, range.start - start), end: Math.min(chunkText.length, range.end - start) })),
              globalOffset: start,
            }),
          });
        }
        return chunks;
      },
      jsonFieldMetaList() {
        if (!this.displayRowData) return [];
        let globalOffset = 0;
        return this.allJsonFieldNames.map((fieldName, index) => {
          const value = this.displayRowData[fieldName];
          const formatted = formatFieldPlainValue(value);
          const totalLength = formatted.plainText.length;
          const loadedLength = Math.min(totalLength, this.jsonLoadedBytes[fieldName] || 0);
          const visiblePlainText = formatted.plainText.slice(0, loadedLength);
          const valueGlobalStart = globalOffset + fieldName.length + 4 + (formatted.wrapQuotes ? 1 : 0);
          globalOffset += fieldName.length + 4 + (formatted.wrapQuotes ? 2 : 0) + visiblePlainText.length + (index < this.allJsonFieldNames.length - 1 ? 1 : 0);
          return {
            fieldName,
            plainText: formatted.plainText,
            wrapQuotes: formatted.wrapQuotes,
            totalLength,
            loadedLength,
            visiblePlainText,
            markRanges: formatted.markRanges
              .filter(range => range.start < loadedLength)
              .map(range => ({ start: range.start, end: Math.min(range.end, loadedLength) })),
            valueGlobalStart,
            hasMore: loadedLength < totalLength,
          };
        });
      },
      jsonVisibleFieldMetaList() {
        return this.jsonFieldMetaList.slice(0, this.jsonVisibleFieldCount);
      },
      jsonRenderRows() {
        if (this.mode !== 'json') return [];
        return this.jsonVisibleFieldMetaList.map((field, index) => ({
          key: `json-field-${field.fieldName}`,
          fieldName: field.fieldName,
          wrapQuotes: field.wrapQuotes,
          showComma: index < this.allJsonFieldNames.length - 1,
          chunks: this.buildJsonValueChunks(field),
        }));
      },
      textHasMore() {
        return this.textVisibleLength < this.textSourceInfo.plainText.length;
      },
      jsonHasMore() {
        if (this.jsonVisibleFieldCount < this.allJsonFieldNames.length) return true;
        return this.jsonVisibleFieldMetaList.some(item => item.hasMore);
      },
      hasMoreContent() {
        return this.mode === 'json' ? this.jsonHasMore : this.textHasMore;
      },
      visibleContentText() {
        if (this.mode === 'text') return this.textVisibleText;
        return this.jsonVisibleFieldMetaList.map((field) => {
          const valueText = field.wrapQuotes ? `"${field.visiblePlainText}"` : field.visiblePlainText;
          return `${field.fieldName}: ${valueText}`;
        }).join('\n');
      },
      hasVisibleContent() {
        if (this.mode === 'text') return Boolean(this.textVisibleText);
        return this.jsonRenderRows.length > 0;
      },
      lineNumbers() {
        if (this.mode !== 'text' || !this.textVisibleText) return [];
        return this.textVisibleText.split('\n').map((_, index) => index + 1);
      },
      matches() {
        this.searchVersion;
        this.searchKeyword;
        const keyword = this.searchKeyword;
        if (!keyword || !this.visibleContentText) return [];
        const matches = [];
        const lowerText = this.visibleContentText.toLowerCase();
        const lowerKeyword = keyword.toLowerCase();
        let offset = 0;
        while (offset <= lowerText.length && matches.length < MAX_SEARCH_MATCHES) {
          const index = lowerText.indexOf(lowerKeyword, offset);
          if (index < 0) break;
          matches.push({ start: index, end: index + keyword.length });
          offset = index + Math.max(1, keyword.length);
        }
        return matches;
      },
      searchMatchLimited() {
        const keyword = this.searchKeyword;
        if (!keyword || this.matches.length < MAX_SEARCH_MATCHES) return false;
        const lastMatch = this.matches[this.matches.length - 1];
        if (!lastMatch) return false;
        return this.visibleContentText.toLowerCase().indexOf(keyword.toLowerCase(), lastMatch.end) >= 0;
      },
      activeMatch() {
        if (this.activeMatchIndex < 0 || this.activeMatchIndex >= this.matches.length) return null;
        return this.matches[this.activeMatchIndex];
      },
      matchText() {
        return this.matches.length ? `${this.activeMatchIndex + 1}/${this.matches.length}${this.searchMatchLimited ? '+' : ''}` : '0/0';
      },
      displaySize() {
        if (!this.displayRowData) return '0 B';
        const fullText = stringifyContentValue(this.displayRowData, this.mode === 'json');
        return formatBytes(new Blob([parseMarkedText(fullText).plainText || fullText]).size);
      },
    },
    watch: {
      active(value) {
        if (value) {
          this.resetChunkState();
          this.loadOriginRow();
          this.observeContentResize();
        } else {
          this.resetViewer();
        }
      },
      mode() {
        this.resetChunkState();
        this.activeMatchIndex = this.matches.length ? 0 : -1;
        this.resetScroll();
      },
      rowData() {
        this.resetChunkState();
        this.resetSearchState();
        this.resetScroll();
      },
      truncatedFields() {
        this.resetChunkState();
        this.resetSearchState();
        this.resetScroll();
      },
      rowKey() {
        if (this.active) this.loadOriginRow();
      },
      searchKeyword() {
        this.searchVersion += 1;
        this.ensureSearchMatchesVisible();
        const nextIndex = this.matches.length ? 0 : -1;
        if (nextIndex === this.activeMatchIndex) this.queueScrollToActiveMatch();
        else this.activeMatchIndex = nextIndex;
      },
      matches(matches) {
        if (!matches.length) {
          this.activeMatchIndex = -1;
          return;
        }
        if (this.activeMatchIndex < 0 || this.activeMatchIndex >= matches.length) this.activeMatchIndex = 0;
      },
      matchText() {
        this.emitMatchUpdate();
      },
      activeMatchIndex() {
        this.emitMatchUpdate();
        this.queueScrollToActiveMatch();
      },
    },
    mounted() {
      if (this.active) {
        this.resetChunkState();
        this.loadOriginRow();
        this.observeContentResize();
      }
      this.emitMatchUpdate();
    },
    beforeDestroy() {
      if (this.resizeTimer) {
        clearTimeout(this.resizeTimer);
        this.resizeTimer = null;
      }
      if (this.scrollLoadMoreTimer) {
        clearTimeout(this.scrollLoadMoreTimer);
        this.scrollLoadMoreTimer = null;
      }
      this.resizeObserver?.disconnect?.();
      this.resizeObserver = null;
      this.loadSeq += 1;
    },
    methods: {
      formatBytes,
      emitMatchUpdate() {
        this.$emit('match-update', { matchText: this.matchText, hasMatches: this.matches.length > 0 });
      },
      buildOrderedRow(row, normalizeJson = false) {
        const fieldNames = this.orderedFieldNames.length ? this.orderedFieldNames : Object.keys(row ?? {});
        return fieldNames.reduce((output, fieldName) => {
          if (fieldName === HIGHLIGHT_FIELD_NAME) return output;
          const value = row?.[fieldName];
          output[fieldName] = normalizeJson ? normalizeJsonValue(value) : value;
          return output;
        }, {});
      },
      buildDisplayRowWithRenderMarks(originRow, renderRow) {
        if (!originRow) return originRow;
        if (!renderRow || typeof renderRow !== 'object') return originRow;
        const output = { ...originRow };
        Object.keys(renderRow).forEach((fieldName) => {
          const renderValue = renderRow[fieldName];
          const originValue = originRow[fieldName];
          if (typeof renderValue !== 'string' || !/<\/?mark>/i.test(renderValue)) return;
          const renderInfo = parseMarkedText(renderValue);
          if (typeof originValue === 'string' && originValue.length > renderInfo.plainText.length) {
            output[fieldName] = this.mergeFieldRenderMarks(originValue, renderInfo);
            return;
          }
          output[fieldName] = renderValue;
        });
        return output;
      },
      mergeFieldRenderMarks(originValue, renderInfo) {
        if (typeof originValue !== 'string') return originValue;
        if (!renderInfo?.markRanges?.length) return originValue;
        const originText = String(originValue);
        const plainRenderText = renderInfo.plainText;
        const directOffset = originText.startsWith(plainRenderText) ? 0 : originText.indexOf(plainRenderText);
        const mergedRanges = [];
        if (directOffset >= 0) {
          renderInfo.markRanges.forEach((range) => {
            mergedRanges.push({ start: directOffset + range.start, end: directOffset + range.end });
          });
        } else {
          let searchStart = 0;
          renderInfo.markRanges.forEach((range) => {
            const markedText = plainRenderText.slice(range.start, range.end);
            if (!markedText) return;
            const hitIndex = originText.indexOf(markedText, searchStart);
            if (hitIndex < 0) return;
            mergedRanges.push({ start: hitIndex, end: hitIndex + markedText.length });
            searchStart = hitIndex + markedText.length;
          });
        }
        if (!mergedRanges.length) return originValue;
        let cursor = 0;
        let output = '';
        mergedRanges.forEach((range) => {
          output += originText.slice(cursor, range.start);
          output += ['<mark>', originText.slice(range.start, range.end), '</mark>'].join('');
          cursor = range.end;
        });
        output += originText.slice(cursor);
        return output;
      },
      resetChunkState() {
        this.textLoadedChunkCount = 1;
        this.jsonLoadedBytes = {};
        this.jsonVisibleFieldCount = 0;
        this.isAppendingChunk = false;
        this.pendingAppendScrollTop = null;
        this.initializeJsonChunkState();
      },
      initializeJsonChunkState() {
        if (!this.displayRowData) return;
        this.appendJsonContentChunk(FIELD_CHUNK_SIZE);
      },
      getJsonFieldPlainLength(fieldName) {
        const value = this.displayRowData?.[fieldName];
        return formatFieldPlainValue(value).plainText.length;
      },
      appendJsonContentChunk(chunkSize = FIELD_CHUNK_SIZE) {
        if (!this.displayRowData) return;

        const fieldNames = this.allJsonFieldNames;
        let remainingSize = chunkSize;

        while (remainingSize > 0) {
          const lastVisibleFieldName = fieldNames[this.jsonVisibleFieldCount - 1];
          const lastVisibleTotalLength = lastVisibleFieldName ? this.getJsonFieldPlainLength(lastVisibleFieldName) : 0;
          const lastVisibleLoadedLength = lastVisibleFieldName ? (this.jsonLoadedBytes[lastVisibleFieldName] || 0) : 0;

          if (lastVisibleFieldName && lastVisibleLoadedLength < lastVisibleTotalLength) {
            const appendLength = Math.min(remainingSize, lastVisibleTotalLength - lastVisibleLoadedLength);
            this.$set(this.jsonLoadedBytes, lastVisibleFieldName, lastVisibleLoadedLength + appendLength);
            remainingSize -= appendLength;
            if (appendLength <= 0) break;
            continue;
          }

          if (this.jsonVisibleFieldCount >= fieldNames.length) break;

          const nextFieldName = fieldNames[this.jsonVisibleFieldCount];
          const nextFieldTotalLength = this.getJsonFieldPlainLength(nextFieldName);
          const nextFieldLoadedLength = Math.min(remainingSize, nextFieldTotalLength);
          this.jsonVisibleFieldCount += 1;
          this.$set(this.jsonLoadedBytes, nextFieldName, nextFieldLoadedLength);
          remainingSize -= nextFieldLoadedLength;

          if (nextFieldTotalLength === 0) continue;
          if (nextFieldLoadedLength <= 0 || nextFieldLoadedLength < nextFieldTotalLength) break;
        }
      },
      ensureFieldVisible(fieldName) {
        const fieldIndex = this.allJsonFieldNames.indexOf(fieldName);
        if (fieldIndex < 0) return;
        this.jsonVisibleFieldCount = Math.max(this.jsonVisibleFieldCount, fieldIndex + 1);
        if ((this.jsonLoadedBytes[fieldName] || 0) <= 0) this.$set(this.jsonLoadedBytes, fieldName, FIELD_CHUNK_SIZE);
      },
      buildJsonValueChunks(field) {
        const chunks = [];
        for (let start = 0; start < field.visiblePlainText.length; start += FIELD_CHUNK_SIZE) {
          const chunkText = field.visiblePlainText.slice(start, start + FIELD_CHUNK_SIZE);
          chunks.push({
            key: `${field.fieldName}-${start}`,
            html: this.buildHighlightedHtml({
              text: chunkText,
              markRanges: field.markRanges
                .filter(range => range.end > start && range.start < start + chunkText.length)
                .map(range => ({ start: Math.max(0, range.start - start), end: Math.min(chunkText.length, range.end - start) })),
              globalOffset: field.valueGlobalStart + start,
            }),
          });
        }
        return chunks;
      },
      ensureSearchMatchesVisible() {
        const keyword = this.searchKeyword?.trim();
        if (!keyword) return;
        const lowerKeyword = keyword.toLowerCase();
        if (this.mode === 'text') {
          const hitIndex = this.textSourceInfo.plainText.toLowerCase().indexOf(lowerKeyword);
          if (hitIndex < 0) return;
          this.textLoadedChunkCount = Math.max(this.textLoadedChunkCount, Math.ceil((hitIndex + keyword.length) / FIELD_CHUNK_SIZE));
          return;
        }
        this.allJsonFieldNames.forEach((fieldName) => {
          const value = this.displayRowData?.[fieldName];
          const { plainText } = formatFieldPlainValue(value);
          const hitIndex = plainText.toLowerCase().indexOf(lowerKeyword);
          if (hitIndex < 0) return;
          this.ensureFieldVisible(fieldName);
          this.$set(this.jsonLoadedBytes, fieldName, Math.max(this.jsonLoadedBytes[fieldName] || 0, Math.ceil((hitIndex + keyword.length) / FIELD_CHUNK_SIZE) * FIELD_CHUNK_SIZE));
        });
      },
      buildHighlightedHtml({ text, markRanges = [], globalOffset = 0 }) {
        if (!text) return '';
        const searchRanges = this.matches
          .map((range, index) => ({ ...range, searchIndex: index }))
          .filter(range => range.end > globalOffset && range.start < globalOffset + text.length)
          .map(range => ({ start: Math.max(0, range.start - globalOffset), end: Math.min(text.length, range.end - globalOffset), searchIndex: range.searchIndex }));
        const ranges = [...markRanges.map(range => ({ ...range, origin: true })), ...searchRanges];
        if (!ranges.length) return escapeHtml(text);
        const points = new Set([0, text.length]);
        ranges.forEach((range) => {
          points.add(Math.max(0, Math.min(text.length, range.start)));
          points.add(Math.max(0, Math.min(text.length, range.end)));
        });
        const sortedPoints = Array.from(points).sort((a, b) => a - b);
        let html = '';
        for (let index = 0; index < sortedPoints.length - 1; index += 1) {
          const start = sortedPoints[index];
          const end = sortedPoints[index + 1];
          if (start === end) continue;
          const classes = [];
          if (markRanges.some(range => range.start < end && range.end > start)) classes.push('full-row-origin-mark');
          const searchMatchIndex = searchRanges.findIndex(range => range.start < end && range.end > start);
          const isActiveMatch = searchMatchIndex >= 0 && searchRanges[searchMatchIndex].searchIndex === this.activeMatchIndex;
          if (searchMatchIndex >= 0) {
            classes.push('full-row-search-mark');
            if (isActiveMatch) classes.push('active');
          }
          const segment = text.slice(start, end);
          const activeMatchId = isActiveMatch ? ' id="full-row-active-match"' : '';
          html += classes.length ? `<mark class="${classes.join(' ')}"${activeMatchId}>${escapeHtml(segment)}</mark>` : escapeHtml(segment);
        }
        return html;
      },
      resetViewer() {
        this.originRow = null;
        this.loadError = '';
        this.loading = false;
        if (this.scrollLoadMoreTimer) {
          clearTimeout(this.scrollLoadMoreTimer);
          this.scrollLoadMoreTimer = null;
        }
        this.resetChunkState();
        this.resetSearchState();
        this.resetScroll();
      },
      resetSearchState() {
        this.activeMatchIndex = -1;
        this.searchVersion += 1;
      },
      observeContentResize() {
        if (typeof ResizeObserver === 'undefined') return;
        this.$nextTick(() => {
          const target = this.$refs.scrollContainer;
          if (!target || this.resizeObserver) return;
          this.resizeObserver = new ResizeObserver(() => {});
          this.resizeObserver.observe(target);
        });
      },
      resetScroll() {
        this.scrollTop = 0;
        this.$nextTick(() => {
          if (this.$refs.scrollContainer) this.$refs.scrollContainer.scrollTop = 0;
        });
      },
      async loadOriginRow() {
        const seq = this.loadSeq + 1;
        this.loadSeq = seq;
        this.loadError = '';
        this.originRow = null;
        if (!this.rowKey) return;
        this.loading = true;
        try {
          const [originRow] = await retrieveRowCacheService.getRows([this.rowKey]);
          if (seq !== this.loadSeq) return;
          if (originRow) this.originRow = originRow;
          else this.loadError = this.$t('未找到当前行全量数据');
        } catch (error) {
          if (seq !== this.loadSeq) return;
          this.loadError = this.$t('读取全量数据失败');
          console.warn('[FullRowViewerContent] load origin row failed', error);
        } finally {
          if (seq === this.loadSeq) {
            this.loading = false;
            this.resetChunkState();
            this.resetSearchState();
            this.resetScroll();
          }
        }
      },
      async getOriginCopyRow() {
        if (!this.rowKey) return null;
        const [originRow] = await retrieveRowCacheService.getCopyRows([this.rowKey]);
        return originRow || null;
      },
      handleScroll(event) {
        const target = event.target;
        this.scrollTop = target.scrollTop;
        this.loadMoreOnScroll(target);
      },
      loadMoreOnScroll(target = this.$refs.scrollContainer) {
        if (!target || !this.hasMoreContent || this.isAppendingChunk) return;
        const distanceToBottom = target.scrollHeight - target.scrollTop - target.clientHeight;
        if (distanceToBottom > SCROLL_LOAD_MORE_THRESHOLD) return;
        if (this.scrollLoadMoreTimer) return;
        this.scrollLoadMoreTimer = setTimeout(() => {
          this.scrollLoadMoreTimer = null;
          this.loadNextContentChunk();
        }, 80);
      },
      loadNextContentChunk() {
        if (this.isAppendingChunk) return;
        const target = this.$refs.scrollContainer;
        this.pendingAppendScrollTop = target ? target.scrollTop : null;
        this.isAppendingChunk = true;
        if (this.mode === 'text') {
          if (this.textHasMore) this.textLoadedChunkCount += 1;
          this.finishAppendChunk();
          return;
        }
        if (this.jsonHasMore) this.appendJsonContentChunk(FIELD_CHUNK_SIZE);
        this.finishAppendChunk();
      },
      finishAppendChunk() {
        this.$nextTick(() => {
          requestAnimationFrame(() => {
            const target = this.$refs.scrollContainer;
            if (target && this.pendingAppendScrollTop !== null) target.scrollTop = this.pendingAppendScrollTop;
            this.pendingAppendScrollTop = null;
            this.isAppendingChunk = false;
          });
        });
      },
      goPrevMatch() {
        if (!this.matches.length) return;
        this.activeMatchIndex = (this.activeMatchIndex - 1 + this.matches.length) % this.matches.length;
      },
      goNextMatch() {
        if (!this.matches.length) return;
        this.activeMatchIndex = (this.activeMatchIndex + 1) % this.matches.length;
      },
      queueScrollToActiveMatch() {
        this.pendingScrollToMatch = true;
        this.flushScrollToActiveMatch();
      },
      flushScrollToActiveMatch() {
        if (!this.pendingScrollToMatch) return;
        this.$nextTick(() => {
          this.$nextTick(() => {
            requestAnimationFrame(() => {
              if (!this.pendingScrollToMatch) return;
              this.pendingScrollToMatch = false;
              this.performScrollToActiveMatch();
            });
          });
        });
      },
      getEffectiveScrollContainer(container, target) {
        if (container.scrollHeight > container.clientHeight) return container;
        let node = target?.parentElement || container.parentElement;
        while (node) {
          const { overflowY } = window.getComputedStyle(node);
          const canScroll = (overflowY === 'auto' || overflowY === 'scroll') && node.scrollHeight > node.clientHeight;
          if (canScroll) return node;
          node = node.parentElement;
        }
        return container;
      },
      performScrollToActiveMatch() {
        if (this.activeMatchIndex < 0 || !this.matches.length) return;
        const container = this.$refs.scrollContainer;
        if (!container) return;
        const activeMark = container.querySelector('#full-row-active-match');
        if (!activeMark) {
          const scrollable = this.getEffectiveScrollContainer(container, container);
          this.scrollToActiveMatchByLineEstimate(scrollable);
          return;
        }
        const scrollable = this.getEffectiveScrollContainer(container, activeMark);
        if (scrollable.scrollHeight <= scrollable.clientHeight) {
          activeMark.scrollIntoView({ block: 'center', inline: 'nearest' });
          return;
        }
        const scrollRect = scrollable.getBoundingClientRect();
        const markRect = activeMark.getBoundingClientRect();
        const markTop = markRect.top - scrollRect.top + scrollable.scrollTop;
        const targetScrollTop = markTop - (scrollable.clientHeight / 2) + (markRect.height / 2);
        const maxScroll = Math.max(0, scrollable.scrollHeight - scrollable.clientHeight);
        scrollable.scrollTop = Math.max(0, Math.min(targetScrollTop, maxScroll));
      },
      scrollToActiveMatchByLineEstimate(container) {
        const match = this.activeMatch;
        if (!match || !container) return;
        const textBeforeMatch = this.visibleContentText.slice(0, match.start);
        const lineIndex = (textBeforeMatch.match(/\n/g) || []).length;
        const lineHeight = 20;
        const targetScrollTop = lineIndex * lineHeight - container.clientHeight / 2 + lineHeight / 2;
        const maxScroll = Math.max(0, container.scrollHeight - container.clientHeight);
        container.scrollTop = Math.max(0, Math.min(targetScrollTop, maxScroll));
      },
      async copyContent() {
        const originRow = await this.getOriginCopyRow();
        if (!originRow) {
          this.$bkMessage?.({ theme: 'warning', message: this.$t('正在读取全量数据...') });
          return;
        }
        const copyData = stripMarkFromCopyValue(this.buildOrderedRow(originRow, false));
        copyMessage(stringifyContentValue(copyData, this.mode === 'json'), this.$t('复制成功'));
      },
    },
  };
</script>

<style lang="scss" scoped>
  .bklog-full-row-viewer-content {
    display: flex;
    flex-direction: column;
    gap: 10px;
    height: 100%;
    min-height: 0;
  }

  .full-row-toolbar {
    display: flex;
    gap: 16px;
    align-items: center;
    flex-shrink: 0;
    font-size: 12px;
  }

  .mode-group {
    display: inline-flex;
    gap: 8px;
    align-items: center;
    font-size: 12px;
    color: #4d4f56;
  }

  .mode-btn {
    height: 28px;
    padding: 0;
    color: #979ba5;
    cursor: pointer;
    background: transparent;
    border: 0;

    &.active {
      color: #3a84ff;
      font-weight: 600;
    }
  }

  .mode-divider {
    color: #dcdee5;
    user-select: none;
  }

  .meta-size,
  .meta-status {
    color: #979ba5;
  }

  .meta-status.load-error {
    color: #ea3636;
  }

  .full-row-content {
    position: relative;
    flex: 1;
    min-height: 0;
    overflow: auto;
    font-family: Menlo, Monaco, Consolas, 'Courier New', monospace;
    font-size: 12px;
    line-height: 20px;
    color: #16171a;
    background: #fff;
    border: 1px solid #dcdee5;
    border-radius: 2px;

  }

  .full-row-dom-content {
    display: flex;
    min-width: 100%;
  }

  .json-kv-content {
    box-sizing: border-box;
    flex: 1;
    width: 100%;
    padding: 8px 12px;
    // white-space: pre-wrap;
    word-break: break-all;
  }

  .json-kv-item {
    padding-left: 16px;
  }

  .json-key {
    color: #1f6feb;
  }

  .json-colon,
  .json-comma,
  .json-struct-line {
    color: #16171a;
  }

  .json-value {
    color: #16171a;
  }

  .full-row-line-numbers {
    flex: 0 0 48px;
    padding: 8px 0;
    color: #979ba5;
    text-align: right;
    user-select: none;
    background: #f5f7fa;
    border-right: 1px solid #dcdee5;

    .line-number {
      display: block;
      padding-right: 12px;
      line-height: 20px;
    }
  }

  .text-content-wrap {
    display: flex;
    flex: 1;
    flex-direction: column;
    min-width: 0;
  }

  .content-text {
    box-sizing: border-box;
    flex: 1;
    width: 100%;
    padding: 8px 12px;
    margin: 0;
    white-space: pre-wrap;
    word-break: break-all;
  }


  .empty-content {
    position: absolute;
    top: 50%;
    left: 50%;
    color: #979ba5;
    transform: translate(-50%, -50%);
  }

  ::v-deep .full-row-origin-mark {
    padding: 0 1px;
    color: inherit;
    background: #fff3b8;
    border-radius: 2px;
  }

  ::v-deep .full-row-search-mark {
    padding: 0 1px;
    color: inherit;
    background: #ffe8cc;
    border-radius: 2px;

    &.active {
      color: #000;
      background: #ff9c01;
    }
  }
</style>
