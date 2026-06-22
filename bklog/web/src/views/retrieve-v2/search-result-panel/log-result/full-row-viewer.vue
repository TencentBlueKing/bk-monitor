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
        class="full-row-content"
        @scroll="handleScroll"
      >
        <div
          class="virtual-spacer"
          :style="{ height: `${totalHeight}px` }"
        >
          <pre
            v-for="item in renderChunks"
            :key="item.index"
            class="content-chunk"
            :style="{ transform: `translateY(${item.top}px)` }"
            v-html="item.html"
          ></pre>
        </div>
        <div
          v-if="!renderChunks.length"
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

  const CHUNK_SIZE = 8000;
  const CHUNK_HEIGHT = 132;
  const OVERSCAN = 4;

  const escapeHtml = value => String(value)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');

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

  export default {
    name: 'FullRowViewer',
    props: {
      visible: { type: Boolean, default: false },
      rowData: { type: Object, default: null },
      rowKey: { type: String, default: '' },
    },
    emits: ['update:visible'],
    data() {
      return {
        localVisible: this.visible,
        mode: 'json',
        searchValue: '',
        scrollTop: 0,
        searchTimer: null,
        searchVersion: 0,
        activeMatchIndex: -1,
        originRow: null,
        loading: false,
        loadError: '',
        loadSeq: 0,
      };
    },
    computed: {
      displayRow() {
        return this.originRow || this.rowData;
      },
      contentText() {
        if (!this.displayRow) return '';
        try {
          return this.mode === 'json'
            ? JSON.stringify(this.displayRow, null, 2)
            : JSON.stringify(this.displayRow);
        } catch {
          return String(this.displayRow);
        }
      },
      chunks() {
        const list = [];
        const text = this.contentText;
        for (let start = 0; start < text.length; start += CHUNK_SIZE) {
          list.push(text.slice(start, start + CHUNK_SIZE));
        }
        return list;
      },
      visibleIndexes() {
        return this.chunks.map((_, index) => index);
      },
      totalHeight() {
        return Math.max(1, this.visibleIndexes.length) * CHUNK_HEIGHT;
      },
      matches() {
        this.searchVersion;
        const keyword = this.searchValue;
        if (!keyword || !this.contentText) return [];
        const matches = [];
        const lowerText = this.contentText.toLowerCase();
        const lowerKeyword = keyword.toLowerCase();
        let offset = 0;
        while (offset <= lowerText.length) {
          const index = lowerText.indexOf(lowerKeyword, offset);
          if (index < 0) break;
          matches.push({ start: index, end: index + keyword.length });
          offset = index + Math.max(1, keyword.length);
        }
        return matches;
      },
      activeMatch() {
        if (this.activeMatchIndex < 0 || this.activeMatchIndex >= this.matches.length) return null;
        return this.matches[this.activeMatchIndex];
      },
      matchText() {
        return this.matches.length ? `${this.activeMatchIndex + 1}/${this.matches.length}` : '0/0';
      },
      renderChunks() {
        const container = this.$refs.scrollContainer;
        const clientHeight = container?.clientHeight ?? 520;
        const start = Math.max(0, Math.floor(this.scrollTop / CHUNK_HEIGHT) - OVERSCAN);
        const end = Math.min(
          this.visibleIndexes.length,
          Math.ceil((this.scrollTop + clientHeight) / CHUNK_HEIGHT) + OVERSCAN,
        );
        return this.visibleIndexes.slice(start, end).map((chunkIndex, offset) => ({
          index: chunkIndex,
          top: (start + offset) * CHUNK_HEIGHT,
          html: this.getChunkHtml(chunkIndex),
        }));
      },
      displaySize() {
        return formatBytes(new Blob([this.contentText]).size);
      },
    },
    watch: {
      visible(value) {
        this.localVisible = value;
        if (value) this.loadOriginRow();
      },
      localVisible(value) {
        this.$emit('update:visible', value);
        if (!value) this.resetViewer();
      },
      mode() {
        this.activeMatchIndex = this.matches.length ? 0 : -1;
        this.resetScroll();
      },
      rowData() {
        this.resetSearchState();
        this.resetScroll();
      },
      rowKey() {
        if (this.localVisible) this.loadOriginRow();
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
    },
    beforeDestroy() {
      if (this.searchTimer) {
        clearTimeout(this.searchTimer);
        this.searchTimer = null;
      }
      this.loadSeq += 1;
    },
    methods: {
      resetViewer() {
        this.searchValue = '';
        this.originRow = null;
        this.loadError = '';
        this.loading = false;
        this.resetSearchState();
        this.resetScroll();
      },
      resetSearchState() {
        this.activeMatchIndex = -1;
        this.searchVersion += 1;
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
      handleScroll(event) {
        this.scrollTop = event.target.scrollTop;
      },
      handleSearchInput() {
        if (this.searchTimer) clearTimeout(this.searchTimer);
        this.searchTimer = setTimeout(() => {
          this.searchVersion += 1;
          this.activeMatchIndex = this.matches.length ? 0 : -1;
          this.scrollToActiveMatch();
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
        const chunkIndex = Math.floor(match.start / CHUNK_SIZE);
        this.$nextTick(() => {
          if (this.$refs.scrollContainer) {
            this.$refs.scrollContainer.scrollTop = Math.max(0, chunkIndex * CHUNK_HEIGHT - CHUNK_HEIGHT);
          }
        });
      },
      getChunkHtml(chunkIndex) {
        const chunk = this.chunks[chunkIndex] ?? '';
        if (!this.searchValue || !this.matches.length) return escapeHtml(chunk);
        const chunkStart = chunkIndex * CHUNK_SIZE;
        const chunkEnd = chunkStart + chunk.length;
        const active = this.activeMatch;
        const relatedMatches = this.matches.filter(match => match.start < chunkEnd && match.end > chunkStart);
        if (!relatedMatches.length) return escapeHtml(chunk);
        let html = '';
        let cursor = 0;
        relatedMatches.forEach((match) => {
          const start = Math.max(0, match.start - chunkStart);
          const end = Math.min(chunk.length, match.end - chunkStart);
          if (start > cursor) html += escapeHtml(chunk.slice(cursor, start));
          const isActive = active && active.start === match.start;
          html += `<mark class="full-row-search-mark${isActive ? ' active' : ''}">${escapeHtml(chunk.slice(start, end))}</mark>`;
          cursor = end;
        });
        if (cursor < chunk.length) html += escapeHtml(chunk.slice(cursor));
        return html;
      },
      handleClose() {
        this.localVisible = false;
      },
      async copyContent() {
        try {
          await navigator.clipboard.writeText(this.contentText);
          this.$bkMessage?.({ theme: 'success', message: this.$t('复制成功') });
        } catch {
          this.$bkMessage?.({ theme: 'error', message: this.$t('复制失败') });
        }
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
    border-right: 1px solid #dcdee5;

    &:last-child {
      border-right: 0;
    }

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
  }

  .virtual-spacer {
    position: relative;
    min-width: 100%;
  }

  .content-chunk {
    position: absolute;
    box-sizing: border-box;
    width: 100%;
    height: 132px;
    padding: 8px 12px;
    margin: 0;
    overflow: hidden;
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

  ::v-deep .full-row-search-mark {
    padding: 0 1px;
    color: inherit;
    background: #fff3b8;
    border-radius: 2px;

    &.active {
      color: #000;
      background: #ff9c01;
    }
  }
</style>
