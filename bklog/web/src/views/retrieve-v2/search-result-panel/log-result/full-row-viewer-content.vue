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
      :class="['full-row-content', { 'is-webgl': usePixiRenderer }]"
      @scroll="handleScroll"
    >
      <canvas
        v-show="usePixiRenderer"
        ref="pixiCanvas"
        class="full-row-pixi-canvas"
      ></canvas>
      <div
        v-if="!usePixiRenderer"
        class="full-row-dom-content"
      >
        <div
          v-if="mode === 'json' && jsonFieldSegments.length"
          class="json-kv-content"
        >
          <div class="json-brace">{</div>
          <div
            v-for="(segment, index) in jsonFieldSegments"
            :key="segment.fieldName"
            class="json-kv-item"
          >
            <span class="json-key">&quot;{{ segment.fieldName }}&quot;</span><span class="json-colon">: </span><template v-if="segment.wrapQuotes">&quot;</template><span
              class="json-value"
              v-html="getFieldValueHtml(segment)"
            /><template v-if="segment.wrapQuotes">&quot;</template><span
              v-if="index < jsonFieldSegments.length - 1"
              class="json-comma"
            >,</span>
            <span
              v-if="segment.hasMore"
              class="field-load-actions"
            >
              <button
                class="field-load-action-btn"
                type="button"
                @click="loadMoreField(segment.fieldName)"
              >
                {{ $t('加载更多') }} ({{ formatBytes(segment.loadedSize) }} / {{ formatBytes(segment.totalSize) }})
              </button>
              <span class="field-load-divider">|</span>
              <button
                class="field-load-action-btn"
                type="button"
                @click="loadAllField(segment.fieldName)"
              >
                {{ $t('加载全部') }}
              </button>
            </span>
          </div>
          <div class="json-brace">}</div>
        </div>
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
          <pre
            class="content-text"
            v-html="contentHtml"
          ></pre>
        </template>
      </div>
      <div
        v-if="!usePixiRenderer && !hasVisibleContent"
        class="empty-content"
      >
        {{ searchKeyword ? $t('未匹配到内容') : $t('暂无内容') }}
      </div>
    </div>
  </div>
</template>

<script>
  import { retrieveRowCacheService } from '@/storage';
  import { buildPixiApp, destroyPixiApp } from './pixi-renderer';
  import { copyMessage } from '@/common/util';

  const CHUNK_SIZE = 8000;
  const MAX_SEARCH_MATCHES = 2000;
  const LARGE_FIELD_THRESHOLD = 16384;
  const FIELD_CHUNK_SIZE = 64 * 1024;

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
    if (typeof value === 'boolean') {
      return { plainText: value ? 'true' : 'false', markRanges: [], wrapQuotes: false };
    }
    if (typeof value === 'number' || typeof value === 'bigint') {
      return { plainText: String(value), markRanges: [], wrapQuotes: false };
    }
    if (typeof value === 'string') {
      const { plainText, markRanges } = parseMarkedText(value);
      return { plainText, markRanges, wrapQuotes: true };
    }

    const plainText = stringifyContentValue(value, false);
    return { plainText, markRanges: [], wrapQuotes: false };
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
        pixiApp: null,
        pixiContainer: null,
        pixiError: '',
        resizeObserver: null,
        resizeTimer: null,
        pendingScrollToMatch: false,
        fieldLoadedChunks: {},
      };
    },
    computed: {
      displayRow() {
        if (this.originRow) return this.originRow;
        if (this.rowKey && this.loading) return null;
        return this.originRow || this.rowData;
      },
      orderedFieldNames() {
        const fieldNames = this.fields.map(getFieldName).filter(Boolean);
        if (!this.displayRow) return fieldNames;

        const rowFieldNames = Object.keys(this.displayRow);
        const orderedFields = fieldNames.filter(fieldName => Object.prototype.hasOwnProperty.call(this.displayRow, fieldName));
        const orderedFieldSet = new Set(orderedFields);
        const extraFields = rowFieldNames.filter(fieldName => !orderedFieldSet.has(fieldName));
        return [...orderedFields, ...extraFields];
      },
      displayRowData() {
        if (!this.displayRow) return null;
        return this.buildOrderedRow(this.displayRow, this.mode === 'json');
      },
      jsonFieldSegments() {
        if (this.mode !== 'json' || !this.displayRowData) return [];

        const fieldNames = this.orderedFieldNames.length
          ? this.orderedFieldNames
          : Object.keys(this.displayRowData);

        let valueGlobalCursor = 0;
        return fieldNames
          .filter(fieldName => Object.prototype.hasOwnProperty.call(this.displayRowData, fieldName))
          .map((fieldName) => {
            const value = this.displayRowData[fieldName];
            const { plainText, markRanges, wrapQuotes } = formatFieldPlainValue(value);
            const isLarge = plainText.length > LARGE_FIELD_THRESHOLD;
            const loadedChunks = this.fieldLoadedChunks[fieldName] || 1;
            const visibleLength = isLarge
              ? Math.min(plainText.length, loadedChunks * FIELD_CHUNK_SIZE)
              : plainText.length;
            const visiblePlainText = plainText.slice(0, visibleLength);
            const header = `${fieldName}: `;
            const valueGlobalStart = valueGlobalCursor + header.length + (wrapQuotes ? 1 : 0);

            valueGlobalCursor += header.length
              + (wrapQuotes ? 2 : 0)
              + visiblePlainText.length
              + 1;

            return {
              fieldName,
              plainText,
              visiblePlainText,
              markRanges: markRanges
                .filter(range => range.start < visibleLength)
                .map(range => ({
                  start: range.start,
                  end: Math.min(range.end, visibleLength),
                })),
              wrapQuotes,
              isLarge,
              hasMore: isLarge && visibleLength < plainText.length,
              loadedSize: visibleLength,
              totalSize: plainText.length,
              valueGlobalStart,
            };
          });
      },
      renderTextInfo() {
        return parseMarkedText(this.contentText);
      },
      visibleContentText() {
        if (this.mode === 'json') {
          return this.jsonFieldSegments.map((segment) => {
            const valueText = segment.wrapQuotes
              ? `"${segment.visiblePlainText}"`
              : segment.visiblePlainText;
            return `${segment.fieldName}: ${valueText}`;
          }).join('\n');
        }

        return this.renderTextInfo.plainText;
      },
      markRanges() {
        if (this.mode === 'json') return [];
        return this.renderTextInfo.markRanges;
      },
      usePixiRenderer() {
        return this.active && this.visibleContentText.length > CHUNK_SIZE && !this.pixiError;
      },
      contentText() {
        if (!this.displayRowData) return '';
        if (this.mode === 'json') return this.visibleContentText;
        return stringifyContentValue(this.displayRowData, false);
      },
      hasVisibleContent() {
        if (this.mode === 'json') return this.jsonFieldSegments.length > 0;
        return Boolean(this.contentText);
      },
      lineNumbers() {
        if (this.mode !== 'text' || !this.visibleContentText) return [];
        return this.visibleContentText.split('\n').map((_, index) => index + 1);
      },
      chunks() {
        const list = [];
        const text = this.visibleContentText;
        for (let start = 0; start < text.length; start += CHUNK_SIZE) {
          list.push(text.slice(start, start + CHUNK_SIZE));
        }
        return list;
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
        return this.matches.length
          ? `${this.activeMatchIndex + 1}/${this.matches.length}${this.searchMatchLimited ? '+' : ''}`
          : '0/0';
      },
      contentHtml() {
        const text = this.visibleContentText;
        if (!text) return '';
        return this.buildHighlightedHtml({
          text,
          markRanges: this.markRanges,
          globalOffset: 0,
        });
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
          this.loadOriginRow();
          this.observeContentResize();
        } else {
          this.resetViewer();
        }
      },
      mode() {
        this.resetFieldChunks();
        this.activeMatchIndex = this.matches.length ? 0 : -1;
        this.resetScroll();
        this.schedulePixiRender();
      },
      rowData() {
        this.resetFieldChunks();
        this.resetSearchState();
        this.resetScroll();
        this.schedulePixiRender();
      },
      truncatedFields() {
        this.resetFieldChunks();
        this.resetSearchState();
        this.resetScroll();
        this.schedulePixiRender();
      },
      rowKey() {
        if (this.active) this.loadOriginRow();
      },
      visibleContentText() {
        this.schedulePixiRender();
      },
      searchKeyword() {
        this.searchVersion += 1;
        if (this.mode === 'json') {
          this.ensureSearchMatchesVisible();
        }
        const nextIndex = this.matches.length ? 0 : -1;
        if (nextIndex === this.activeMatchIndex) {
          this.queueScrollToActiveMatch();
        } else {
          this.activeMatchIndex = nextIndex;
        }
        this.schedulePixiRender();
      },
      matches(matches) {
        if (!matches.length) {
          this.activeMatchIndex = -1;
          return;
        }
        if (this.activeMatchIndex < 0 || this.activeMatchIndex >= matches.length) {
          this.activeMatchIndex = 0;
        }
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
      this.resizeObserver?.disconnect?.();
      this.resizeObserver = null;
      this.loadSeq += 1;
      this.destroyPixi();
    },
    methods: {
      formatBytes,
      emitMatchUpdate() {
        this.$emit('match-update', {
          matchText: this.matchText,
          hasMatches: this.matches.length > 0,
        });
      },
      buildOrderedRow(row, normalizeJson = false) {
        const fieldNames = this.orderedFieldNames.length ? this.orderedFieldNames : Object.keys(row ?? {});
        return fieldNames.reduce((output, fieldName) => {
          const value = row?.[fieldName];
          output[fieldName] = normalizeJson ? normalizeJsonValue(value) : value;
          return output;
        }, {});
      },
      resetFieldChunks() {
        this.fieldLoadedChunks = {};
      },
      loadMoreField(fieldName) {
        const current = this.fieldLoadedChunks[fieldName] || 1;
        this.$set(this.fieldLoadedChunks, fieldName, current + 1);
      },
      loadAllField(fieldName) {
        const value = this.displayRowData?.[fieldName];
        const { plainText } = formatFieldPlainValue(value);
        const totalChunks = Math.max(1, Math.ceil(plainText.length / FIELD_CHUNK_SIZE));
        this.$set(this.fieldLoadedChunks, fieldName, totalChunks);
      },
      ensureSearchMatchesVisible() {
        const keyword = this.searchKeyword?.trim();
        if (!keyword || this.mode !== 'json') return;

        const lowerKeyword = keyword.toLowerCase();
        const fieldNames = this.orderedFieldNames.length
          ? this.orderedFieldNames
          : Object.keys(this.displayRowData ?? {});

        fieldNames.forEach((fieldName) => {
          const value = this.displayRowData?.[fieldName];
          const { plainText } = formatFieldPlainValue(value);
          if (plainText.length <= LARGE_FIELD_THRESHOLD) return;

          const hitIndex = plainText.toLowerCase().indexOf(lowerKeyword);
          if (hitIndex < 0) return;

          const neededChunks = Math.ceil((hitIndex + keyword.length) / FIELD_CHUNK_SIZE);
          const currentChunks = this.fieldLoadedChunks[fieldName] || 1;
          if (neededChunks > currentChunks) {
            this.$set(this.fieldLoadedChunks, fieldName, neededChunks);
          }
        });
      },
      getFieldValueHtml(segment) {
        return this.buildHighlightedHtml({
          text: segment.visiblePlainText,
          markRanges: segment.markRanges,
          globalOffset: segment.valueGlobalStart,
        });
      },
      buildHighlightedHtml({ text, markRanges = [], globalOffset = 0 }) {
        if (!text) return '';

        const searchRanges = this.matches
          .map((range, index) => ({ ...range, searchIndex: index }))
          .filter(range => range.end > globalOffset && range.start < globalOffset + text.length)
          .map(range => ({
            start: Math.max(0, range.start - globalOffset),
            end: Math.min(text.length, range.end - globalOffset),
            searchIndex: range.searchIndex,
          }));

        const ranges = [
          ...markRanges.map(range => ({ ...range, origin: true })),
          ...searchRanges,
        ];

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
          if (markRanges.some(range => range.start < end && range.end > start)) {
            classes.push('full-row-origin-mark');
          }

          const searchMatchIndex = searchRanges.findIndex(range => range.start < end && range.end > start);
          const isActiveMatch = searchMatchIndex >= 0
            && searchRanges[searchMatchIndex].searchIndex === this.activeMatchIndex;

          if (searchMatchIndex >= 0) {
            classes.push('full-row-search-mark');
            if (isActiveMatch) classes.push('active');
          }

          const segment = text.slice(start, end);
          const activeMatchId = isActiveMatch ? ' id="full-row-active-match"' : '';
          html += classes.length
            ? `<mark class="${classes.join(' ')}"${activeMatchId}>${escapeHtml(segment)}</mark>`
            : escapeHtml(segment);
        }

        return html;
      },
      resetViewer() {
        this.originRow = null;
        this.loadError = '';
        this.loading = false;
        this.pixiError = '';
        this.destroyPixi();
        this.resetFieldChunks();
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
          this.resizeObserver = new ResizeObserver(() => {
            if (this.resizeTimer) clearTimeout(this.resizeTimer);
            this.resizeTimer = setTimeout(() => {
              if (this.usePixiRenderer) this.schedulePixiRender();
            }, 120);
          });
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
          if (originRow) {
            this.originRow = originRow;
          } else {
            this.loadError = this.$t('未找到当前行全量数据，已显示当前渲染数据');
          }
        } catch (error) {
          if (seq !== this.loadSeq) return;
          this.loadError = this.$t('读取全量数据失败，已显示当前渲染数据');
          console.warn('[FullRowViewerContent] load origin row failed', error);
        } finally {
          if (seq === this.loadSeq) {
            this.loading = false;
            this.resetFieldChunks();
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
        this.scrollTop = event.target.scrollTop;
      },
      schedulePixiRender() {
        this.$nextTick(() => {
          if (this.usePixiRenderer) {
            this.renderPixi();
          } else {
            this.destroyPixi();
          }
        });
      },
      async renderPixi() {
        const canvas = this.$refs.pixiCanvas;
        if (!canvas || !this.contentText) return;
        try {
          this.destroyPixi();
          const rows = this.chunks.map(text => ({ text, isMark: false }));
          const result = await buildPixiApp(canvas, {
            rows,
            highlightKeywords: this.searchKeyword ? [this.searchKeyword] : [],
          });
          this.pixiApp = result.app;
          this.pixiContainer = result.container;
          this.pixiError = '';
          if (this.activeMatchIndex >= 0) {
            this.queueScrollToActiveMatch();
          }
        } catch (error) {
          this.pixiError = error?.message || String(error);
          console.warn('[FullRowViewerContent] Pixi render failed, fallback to DOM renderer', error);
          this.destroyPixi();
        }
      },
      destroyPixi() {
        if (this.pixiApp) {
          destroyPixiApp(this.pixiApp);
          this.pixiApp = null;
          this.pixiContainer = null;
        }
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
          const canScroll = (overflowY === 'auto' || overflowY === 'scroll')
            && node.scrollHeight > node.clientHeight;
          if (canScroll) return node;
          node = node.parentElement;
        }

        return container;
      },
      performScrollToActiveMatch() {
        if (this.activeMatchIndex < 0 || !this.matches.length) return;

        const container = this.$refs.scrollContainer;
        if (!container) return;

        if (this.usePixiRenderer) {
          const scrollable = this.getEffectiveScrollContainer(container, container);
          this.scrollToActiveMatchByLineEstimate(scrollable);
          return;
        }

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

    &.is-webgl {
      overflow: auto;
    }

    .full-row-pixi-canvas {
      display: block;
      max-width: none;
      min-height: 100%;
    }
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
    white-space: pre-wrap;
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
  .json-brace {
    color: #16171a;
  }

  .json-value {
    color: #16171a;
  }

  .field-load-actions {
    display: inline;
    margin-left: 4px;
    white-space: nowrap;
  }

  .field-load-action-btn {
    display: inline;
    padding: 0;
    font-family: inherit;
    font-size: 12px;
    color: #3a84ff;
    cursor: pointer;
    background: transparent;
    border: 0;

    &:hover {
      text-decoration: underline;
    }
  }

  .field-load-divider {
    margin: 0 6px;
    color: #dcdee5;
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
