<template>
  <bk-dialog
    v-model="localVisible"
    class="bklog-full-row-viewer-dialog"
    :title="$t('全量日志')"
    width="960px"
    :mask-close="false"
    :show-footer="false"
    header-position="left"
    @close="handleClose"
    @after-leave="handleClose"
  >
    <div class="bklog-full-row-viewer">
      <div class="full-row-toolbar">
        <div class="mode-group">
          <button
            :class="['mode-btn', { active: mode === 'json' }]"
            type="button"
            @click="mode = 'json'"
          >
            JSON
          </button>
          <button
            :class="['mode-btn', { active: mode === 'text' }]"
            type="button"
            @click="mode = 'text'"
          >
            {{ $t('文本') }}
          </button>
        </div>
        <input
          v-model.trim="searchValue"
          class="search-input"
          :placeholder="$t('搜索当前行内容')"
          type="text"
          @input="handleSearchInput"
          @keydown.enter.prevent="goNextMatch"
        />
        <span class="search-count">{{ matchText }}</span>
        <button
          class="nav-btn"
          type="button"
          :disabled="!matches.length"
          @click="goPrevMatch"
        >
          {{ $t('上一个') }}
        </button>
        <button
          class="nav-btn"
          type="button"
          :disabled="!matches.length"
          @click="goNextMatch"
        >
          {{ $t('下一个') }}
        </button>
        <button
          class="copy-btn"
          type="button"
          @click="copyContent"
        >
          {{ $t('复制') }}
        </button>
      </div>
      <div class="full-row-meta">
        <span>{{ $t('大小') }}: {{ displaySize }}</span>
        <span>{{ $t('分块') }}: {{ visibleIndexes.length }}/{{ chunks.length }}</span>
        <span v-if="loading">{{ $t('正在读取全量数据...') }}</span>
        <span v-if="loadError" class="load-error">{{ loadError }}</span>
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
          <pre
            class="content-text"
            v-html="contentHtml"
          ></pre>
        </div>
        <div
          v-if="!usePixiRenderer && !contentText"
          class="empty-content"
        >
          {{ searchValue ? $t('未匹配到内容') : $t('暂无内容') }}
        </div>
      </div>
    </div>
  </bk-dialog>
</template>

<script>
  import { retrieveRowCacheService } from '@/storage';
  import { buildPixiApp, destroyPixiApp } from './pixi-renderer';
  import { copyMessage } from '@/common/util';

  const CHUNK_SIZE = 8000;
  const MAX_SEARCH_MATCHES = 2000;

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

  export default {
    name: 'FullRowViewer',
    props: {
      visible: { type: Boolean, default: false },
      rowData: { type: Object, default: null },
      rowKey: { type: String, default: '' },
      fields: { type: Array, default: () => [] },
      truncatedFields: { type: Array, default: () => [] },
    },
    emits: ['update:visible'],
    data() {
      return {
        localVisible: this.visible,
        mode: 'json',
        searchValue: '',
        searchKeyword: '',
        scrollTop: 0,
        searchTimer: null,
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
      };
    },
    computed: {
      displayRow() {
        if (this.originRow) return this.originRow;
        if (this.rowKey && this.loading) return null;
        return this.originRow || this.rowData;
      },
      copyRow() {
        return this.originRow || (!this.rowKey ? this.rowData : null);
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
      copyRowData() {
        if (!this.copyRow) return null;
        return stripMarkFromCopyValue(this.buildOrderedRow(this.copyRow, false));
      },
      copyText() {
        if (!this.copyRowData) return '';
        return stringifyContentValue(this.copyRowData, this.mode === 'json');
      },
      renderTextInfo() {
        return parseMarkedText(this.contentText);
      },
      visibleContentText() {
        return this.renderTextInfo.plainText;
      },
      markRanges() {
        return this.renderTextInfo.markRanges;
      },
      usePixiRenderer() {
        return this.localVisible && this.visibleContentText.length > CHUNK_SIZE && !this.pixiError;
      },
      contentText() {
        if (!this.displayRowData) return '';
        return stringifyContentValue(this.displayRowData, this.mode === 'json');
      },
      chunks() {
        const list = [];
        const text = this.visibleContentText;
        for (let start = 0; start < text.length; start += CHUNK_SIZE) {
          list.push(text.slice(start, start + CHUNK_SIZE));
        }
        return list;
      },
      visibleIndexes() {
        return this.chunks.map((_, index) => index);
      },
      matches() {
        this.searchVersion;
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
        const ranges = [
          ...this.markRanges.map(range => ({ ...range, type: 'origin' })),
          ...this.matches.map((range, index) => ({ ...range, type: index === this.activeMatchIndex ? 'active-search' : 'search' })),
        ];
        if (!ranges.length) return escapeHtml(text);

        const points = new Set([0, text.length]);
        ranges.forEach((range) => {
          points.add(Math.max(0, Math.min(text.length, range.start)));
          points.add(Math.max(0, Math.min(text.length, range.end)));
        });

        const sortedPoints = Array.from(points).sort((a, b) => a - b);
        let html = '';
        for (let index = 0; index < sortedPoints.length - 1; index++) {
          const start = sortedPoints[index];
          const end = sortedPoints[index + 1];
          if (start === end) continue;
          const classes = [];
          if (this.markRanges.some(range => range.start < end && range.end > start)) {
            classes.push('full-row-origin-mark');
          }
          const searchMatchIndex = this.matches.findIndex(range => range.start < end && range.end > start);
          if (searchMatchIndex >= 0) {
            classes.push('full-row-search-mark');
            if (searchMatchIndex === this.activeMatchIndex) classes.push('active');
          }

          const escapedText = escapeHtml(text.slice(start, end));
          html += classes.length ? `<mark class="${classes.join(' ')}">${escapedText}</mark>` : escapedText;
        }

        return html;
      },
      displaySize() {
        return formatBytes(new Blob([this.visibleContentText]).size);
      },
    },
    watch: {
      visible(value) {
        this.localVisible = value;
        if (value) {
          this.loadOriginRow();
          this.observeContentResize();
        }
      },
      localVisible(value) {
        this.$emit('update:visible', value);
        if (!value) this.resetViewer();
      },
      mode() {
        this.activeMatchIndex = this.matches.length ? 0 : -1;
        this.resetScroll();
        this.schedulePixiRender();
      },
      rowData() {
        this.resetSearchState();
        this.resetScroll();
        this.schedulePixiRender();
      },
      truncatedFields() {
        this.resetSearchState();
        this.resetScroll();
        this.schedulePixiRender();
      },
      rowKey() {
        if (this.localVisible) this.loadOriginRow();
      },
      visibleContentText() {
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
    },
    mounted() {
      if (this.visible) this.loadOriginRow();
      this.observeContentResize();
    },
    beforeDestroy() {
      if (this.searchTimer) {
        clearTimeout(this.searchTimer);
        this.searchTimer = null;
      }
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
      buildOrderedRow(row, normalizeJson = false) {
        const fieldNames = this.orderedFieldNames.length ? this.orderedFieldNames : Object.keys(row ?? {});
        return fieldNames.reduce((output, fieldName) => {
          const value = row?.[fieldName];
          output[fieldName] = normalizeJson ? normalizeJsonValue(value) : value;
          return output;
        }, {});
      },
      resetViewer() {
        this.searchValue = '';
        this.searchKeyword = '';
        this.originRow = null;
        this.loadError = '';
        this.loading = false;
        this.pixiError = '';
        this.destroyPixi();
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
          console.warn('[FullRowViewer] load origin row failed', error);
        } finally {
          if (seq === this.loadSeq) {
            this.loading = false;
            this.resetSearchState();
            this.resetScroll();
          }
        }
      },
      async getOriginCopyRow() {
        if (this.originRow) return this.originRow;
        if (!this.rowKey) return this.rowData;

        const [originRow] = await retrieveRowCacheService.getRows([this.rowKey]);
        if (originRow) {
          this.originRow = originRow;
          return originRow;
        }

        return null;
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
        } catch (error) {
          this.pixiError = error?.message || String(error);
          console.warn('[FullRowViewer] Pixi render failed, fallback to DOM renderer', error);
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
      handleSearchInput() {
        if (this.searchTimer) clearTimeout(this.searchTimer);
        this.searchTimer = setTimeout(() => {
          this.searchKeyword = this.searchValue;
          this.searchVersion += 1;
          this.activeMatchIndex = this.matches.length ? 0 : -1;
          this.scrollToActiveMatch();
          this.schedulePixiRender();
        }, 160);
      },
      goPrevMatch() {
        if (!this.matches.length) return;
        this.activeMatchIndex = (this.activeMatchIndex - 1 + this.matches.length) % this.matches.length;
        this.scrollToActiveMatch();
      },
      goNextMatch() {
        if (!this.matches.length) return;
        this.activeMatchIndex = (this.activeMatchIndex + 1) % this.matches.length;
        this.scrollToActiveMatch();
      },
      scrollToActiveMatch() {
        const match = this.activeMatch;
        if (!match) return;
        this.$nextTick(() => {
          if (this.$refs.scrollContainer) {
            const container = this.$refs.scrollContainer;
            const scrollableHeight = Math.max(0, container.scrollHeight - container.clientHeight);
            const matchRatio = this.visibleContentText.length ? match.start / this.visibleContentText.length : 0;
            container.scrollTop = Math.max(0, scrollableHeight * matchRatio - 40);
          }
        });
      },
      handleClose() {
        if (!this.localVisible) return;
        this.localVisible = false;
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
  .bklog-full-row-viewer {
    display: flex;
    flex-direction: column;
    gap: 10px;
    height: 68vh;
    min-height: 480px;
  }

  .full-row-toolbar {
    display: flex;
    gap: 8px;
    align-items: center;
  }

  .mode-group {
    display: inline-flex;
    overflow: hidden;
    border: 1px solid #c4c6cc;
    border-radius: 2px;
  }

  .mode-btn,
  .nav-btn,
  .copy-btn {
    height: 28px;
    padding: 0 12px;
    color: #4d4f56;
    cursor: pointer;
    background: #fff;
    border: 0;

    // &:last-child {
    //   border-right: 0;
    // }

    &.active {
      color: #fff;
      background: #3a84ff;
    }
  }

  .nav-btn,
  .copy-btn {
    border: 1px solid #c4c6cc;
    border-radius: 2px;

    &:disabled {
      color: #c4c6cc;
      cursor: not-allowed;
      background: #f5f7fa;
    }
  }

  .search-count {
    min-width: 48px;
    font-size: 12px;
    color: #63656e;
    text-align: center;
  }

  .search-input {
    flex: 1;
    height: 28px;
    padding: 0 10px;
    border: 1px solid #c4c6cc;
    border-radius: 2px;
    outline: none;

    &:focus {
      border-color: #3a84ff;
    }
  }

  .full-row-meta {
    display: flex;
    gap: 16px;
    font-size: 12px;
    color: #979ba5;

    .load-error {
      color: #ea3636;
    }
  }

  .full-row-content {
    position: relative;
    flex: 1;
    overflow: auto;
    font-family: Menlo, Monaco, Consolas, 'Courier New', monospace;
    font-size: 12px;
    line-height: 18px;
    color: #313238;
    background: #f5f7fa;
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
    min-width: 100%;
  }

  .content-text {
    box-sizing: border-box;
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
