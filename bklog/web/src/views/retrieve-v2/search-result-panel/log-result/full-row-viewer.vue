<template>
  <bk-sideslider
    :is-show.sync="localVisible"
    :width="1000"
    class="bklog-full-row-viewer-sideslider"
    quick-close
    transfer
    @animation-end="handleAnimationEnd"
  >
    <div
      slot="header"
      class="full-row-sideslider-header"
    >
      <span class="full-row-sideslider-title">{{ $t('查看全量日志') }}</span>
      <div class="full-row-sideslider-search-bar">
        <input
          v-model.trim="searchValue"
          class="search-input"
          :placeholder="$t('搜索')"
          type="text"
          @input="handleSearchInput"
          @keydown.enter.prevent="handleSearchEnter"
        />
        <div class="search-suffix">
          <span class="search-count">{{ matchText }}</span>
          <span class="search-nav-divider" />
          <button
            class="nav-icon-btn"
            type="button"
            :disabled="!hasMatches"
            @click="goPrevMatch"
          >
            <span class="bk-icon icon-angle-up" />
          </button>
          <button
            class="nav-icon-btn"
            type="button"
            :disabled="!hasMatches"
            @click="goNextMatch"
          >
            <span class="bk-icon icon-angle-down" />
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
    <div
      slot="content"
      class="full-row-sideslider-body"
    >
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
  </bk-sideslider>
</template>

<script>
  import FullRowViewerContent from './full-row-viewer-content.vue';

  export default {
    name: 'FullRowViewer',
    components: {
      FullRowViewerContent,
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
    .bk-sideslider-content {
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
      color: #313238;
    }

    .full-row-sideslider-search-bar {
      display: flex;
      flex: 1;
      align-items: center;
      min-width: 0;
      height: 32px;
      overflow: hidden;
      border: 1px solid #c4c6cc;
      border-radius: 2px;

      &:focus-within {
        border-color: #3a84ff;
      }

      .search-input {
        flex: 1;
        min-width: 0;
        height: 100%;
        padding: 0 12px;
        font-size: 12px;
        border: 0;
        outline: none;
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
        color: #979ba5;
        text-align: center;
        white-space: nowrap;
      }

      .search-nav-divider {
        width: 1px;
        height: 16px;
        margin: 0 2px;
        background: #dcdee5;
      }

      .nav-icon-btn {
        display: inline-flex;
        align-items: center;
        justify-content: center;
        width: 24px;
        height: 24px;
        padding: 0;
        color: #63656e;
        cursor: pointer;
        background: transparent;
        border: 0;
        border-radius: 2px;

        .bk-icon {
          font-size: 18px;
          line-height: 1;
        }

        &:hover:not(:disabled) {
          color: #3a84ff;
          background: #edf4ff;
        }

        &:disabled {
          color: #c4c6cc;
          cursor: not-allowed;
        }
      }
    }

    .copy-btn {
      flex-shrink: 0;
      height: 32px;
      padding: 0 16px;
      font-size: 12px;
      color: #4d4f56;
      cursor: pointer;
      background: #fff;
      border: 1px solid #c4c6cc;
      border-radius: 2px;
      align-items: center;
      justify-content: center;
      display: inline-flex;
      
      &:hover {
        color: #3a84ff;
        border-color: #3a84ff;
      }
    }
  }
</style>
