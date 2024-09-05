<template>
  <div class="retrieve-tab-item-title">
    <span class="history-button">
      <span class="bklog-icon bklog-lishijilu"></span>
      <span @click="handleClickHistoryButton">{{ $t('历史查询') }}</span>
    </span>
    <div v-show="false">
      <ul
        ref="historyUlRef"
        class="retrieve-history-list"
      >
        <template v-if="isHistoryRecords">
          <li
            v-for="item in historyRecords"
            :key="item.id"
            class="list-item"
            @click="handleClickHistory(item)"
          >
            <div class="item-text text-overflow-hidden">{{ item.query_string }}</div>
          </li>
        </template>
        <li
          v-else
          class="list-item not-history"
        >
          {{ this.$t('暂无历史记录') }}
        </li>
      </ul>
    </div>
  </div>
</template>
<script>
  export default {
    data() {
      return {
        isHistoryRecords: true,
        popoverInstance: null,
        historyRecords: [],
      };
    },
    computed: {
      isUnionSearch() {
        return this.$store.getters.isUnionSearch;
      },
      unionIndexList() {
        return this.$store.getters.unionIndexList;
      },
      indexItem() {
        return this.$store.state.indexItem;
      },
      indexId() {
        return this.indexItem.ids[0];
      },
    },
    methods: {
      handleClickHistoryButton(e) {
        const popoverWidth = '300px';
        this.popoverInstance = this.$bkPopover(e.target, {
          content: this.$refs.historyUlRef,
          trigger: 'manual',
          arrow: true,
          width: popoverWidth,
          theme: 'light',
          sticky: true,
          duration: [275, 0],
          interactive: true,
          placement: 'bottom',
          extCls: 'retrieve-history-popover',
          onHidden: () => {
            this.popoverInstance?.destroy();
            this.popoverInstance = null;
          },
        });
        this.popoverInstance.show();
      },
      handleClickHistory(item) {
        this.$emit('updateSearchParam', item.params.keyword, item.params.addition, item.params.ip_chooser);
        this.$nextTick(() => {
          this.$emit('retrieve');
          this.popoverInstance?.destroy();
        });
      },
      requestSearchHistory() {
        const queryUrl = this.isUnionSearch ? 'unionSearch/unionSearchHistory' : 'retrieve/getSearchHistory';
        const params = this.isUnionSearch
          ? {
              index_set_ids: this.unionIndexList,
            }
          : {
              index_set_id: this.indexId,
            };
        this.$http
          .request(queryUrl, {
            params,
          })
          .then(res => {
            this.historyRecords = res.data;
            this.isHistoryRecords = !!this.historyRecords.length;
          });
      },
    },
    watch: {
      unionIndexList: {
        handler() {
          setTimeout(() => {
            console.log('indexId', this.indexId);
            this.requestSearchHistory();
          }, 0);
        },
      },
    },
    created() {},
  };
</script>

<style lang="scss" scoped>
  @import './query-history.scss';
</style>
