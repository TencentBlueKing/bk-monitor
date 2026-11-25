<template>
  <t-drawer
    v-if="localVisible"
    v-model:visible="localVisible"
    :footer="false"
    size="min(100vw, 1000px)"
    attach="body"
    class="bklog-full-row-viewer-sideslider"
    placement="right"
    @close="handleAnimationEnd"
  >
    <template #header>
      <div class="full-row-sideslider-header">
      <span class="full-row-sideslider-title">{{ $t('查看全量日志') }}</span>
      <div class="full-row-sideslider-search-bar">
        <input
          v-model.trim="searchValue"
          class="search-input"
          :aria-label="$t('搜索')"
          :placeholder="$t('搜索')"
          type="text"
          @input="handleSearchInput"
          @keydown.enter.prevent="handleSearchEnter"
        />
        <div class="search-suffix">
          <span class="search-count" role="status" aria-atomic="true">{{ matchText }}</span>
          <span class="search-nav-divider" aria-hidden="true" />
          <button
            class="nav-icon-btn"
            type="button"
            :disabled="!hasMatches"
            :aria-label="$t('上一个')"
            @click="goPrevMatch"
          >
            <span class="bk-icon icon-angle-up" aria-hidden="true" />
          </button>
          <button
            class="nav-icon-btn"
            type="button"
            :disabled="!hasMatches"
            :aria-label="$t('下一个')"
            @click="goNextMatch"
          >
            <span class="bk-icon icon-angle-down" aria-hidden="true" />
          </button>
        </div>
      </div>
      <button
        class="copy-btn"
        type="button"
        @click="handleCopy"
      >
        {{ $t('复制') }}
      </button>
      </div>
    </template>
    <div class="full-row-sideslider-body">
      <FullRowViewerContent
        ref="contentRef"
        :active="localVisible"
        :fields="fields"
        :row-data="rowData"
        :row-key="rowKey"
        :search-keyword="searchKeyword"
        :truncated-fields="truncatedFields"
        @match-update="handleMatchUpdate"
      />
    </div>
  </t-drawer>
</template>

<script>
  import { Drawer as TDrawer } from 'tdesign-vue-next';

  import FullRowViewerContent from './full-row-viewer-content.vue';

  export default {
    name: 'FullRowViewer',
    components: {
      FullRowViewerContent,
      TDrawer,
    },
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
        searchValue: '',
        searchKeyword: '',
        searchTimer: null,
        matchText: '0/0',
        hasMatches: false,
      };
    },
    watch: {
      visible(value) {
        this.localVisible = value;
        if (!value) {
          this.resetSearch();
        }
      },
      localVisible(value) {
        this.$emit('update:visible', value);
        if (!value) {
          this.resetSearch();
        }
      },
    },
    beforeDestroy() {
      if (this.searchTimer) {
        clearTimeout(this.searchTimer);
        this.searchTimer = null;
      }
    },
    methods: {
      resetSearch() {
        this.searchValue = '';
        this.searchKeyword = '';
        this.matchText = '0/0';
        this.hasMatches = false;
        if (this.searchTimer) {
          clearTimeout(this.searchTimer);
          this.searchTimer = null;
        }
      },
      handleMatchUpdate({ matchText, hasMatches }) {
        this.matchText = matchText;
        this.hasMatches = hasMatches;
      },
      goPrevMatch() {
        this.$refs.contentRef?.goPrevMatch?.();
      },
      goNextMatch() {
        this.$refs.contentRef?.goNextMatch?.();
      },
      handleSearchInput() {
        if (this.searchTimer) clearTimeout(this.searchTimer);
        this.searchTimer = setTimeout(() => {
          this.searchKeyword = this.searchValue;
        }, 160);
      },
      handleSearchEnter() {
        if (this.searchTimer) clearTimeout(this.searchTimer);
        this.searchKeyword = this.searchValue;
        this.$nextTick(() => {
          this.$refs.contentRef?.goNextMatch?.();
        });
      },
      handleAnimationEnd() {
        if (!this.localVisible) {
          this.resetSearch();
        }
      },
      handleCopy() {
        this.$refs.contentRef?.copyContent?.();
      },
    },
  };
</script>

<style lang="scss">
  .bklog-full-row-viewer-sideslider {
    .t-drawer__body {
      display: flex;
      flex-direction: column;
      height: calc(100vh - 60px);
      padding: 16px 24px 24px;
      overflow: hidden;
      box-sizing: border-box;
    }

    .full-row-sideslider-body {
      display: flex;
      flex: 1;
      flex-direction: column;
      min-height: 0;
      overflow: hidden;
    }

    .full-row-sideslider-header {
      display: flex;
      gap: 12px;
      align-items: center;
      width: 100%;
      padding-right: 40px;
    }

    .full-row-sideslider-title {
      flex-shrink: 0;
      font-size: 16px;
      font-weight: 700;
      color: var(--td-text-color-primary);
    }

    .full-row-sideslider-search-bar {
      display: flex;
      flex: 1;
      align-items: center;
      min-width: 0;
      height: var(--bklog-control-size-medium);
      overflow: hidden;
      border: 1px solid var(--td-border-level-2-color);
      border-radius: var(--bklog-standard-control-radius);

      &:focus-within {
        border-color: var(--td-brand-color);
      }

      .search-input {
        flex: 1;
        min-width: 0;
        height: 100%;
        padding: 0 12px;
        font-size: var(--bklog-font-body);
        color: var(--td-text-color-primary);
        background: var(--td-bg-color-container);
        border: 0;
        outline: none;

        &::placeholder { color: var(--td-text-color-placeholder); }
      }

      .search-suffix {
        display: inline-flex;
        flex-shrink: 0;
        align-items: center;
        height: 100%;
        padding-right: 4px;
      }

      .search-count {
        min-width: 36px;
        padding: 0 8px;
        font-size: 12px;
        color: var(--td-text-color-secondary);
        text-align: center;
        white-space: nowrap;
      }

      .search-nav-divider {
        width: 1px;
        height: 16px;
        margin: 0 2px;
        background: var(--td-component-stroke);
      }

      .nav-icon-btn {
        display: inline-flex;
        align-items: center;
        justify-content: center;
        width: 24px;
        height: 24px;
        padding: 0;
        color: var(--td-text-color-secondary);
        cursor: pointer;
        background: transparent;
        border: 0;
        border-radius: var(--bklog-standard-control-radius);

        .bk-icon {
          font-size: 18px;
          line-height: 1;
        }

        &:hover:not(:disabled) {
          color: var(--td-brand-color);
          background: var(--td-brand-color-light);
        }

        &:disabled {
          color: var(--td-text-color-disabled);
          cursor: not-allowed;
        }
      }
    }

    :is(.nav-icon-btn, .copy-btn):focus-visible {
      outline: var(--bklog-border-width) solid var(--td-brand-color);
      outline-offset: -2px;
    }

    @media (max-width: 640px) {
      .full-row-sideslider-header {
        display: grid;
        grid-template-columns: minmax(0, 1fr) auto;
        padding-inline-end: var(--bklog-space-24);
      }

      .full-row-sideslider-title {
        grid-column: 1 / -1;
      }

      .full-row-sideslider-search-bar {
        .search-input {
          padding-inline: var(--bklog-space-8);
        }

        .search-count {
          padding-inline: var(--bklog-space-4);
        }
      }

      .full-row-sideslider-header .copy-btn {
        padding-inline: var(--bklog-space-8);
      }
    }

    .copy-btn {
      flex-shrink: 0;
      height: var(--bklog-control-size-medium);
      padding: 0 16px;
      font-size: 12px;
      color: var(--td-text-color-secondary);
      cursor: pointer;
      background: var(--td-bg-color-container);
      border: 1px solid var(--td-border-level-2-color);
      border-radius: var(--bklog-standard-control-radius);
      align-items: center;
      justify-content: center;
      display: inline-flex;

      &:hover {
        color: var(--td-brand-color);
        border-color: var(--td-brand-color);
      }
    }
  }
</style>
