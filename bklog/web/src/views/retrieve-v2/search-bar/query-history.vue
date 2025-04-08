<template>
  <div class="retrieve-tab-item-title">
    <span class="history-button">
      <span class="bklog-icon bklog-history-2"></span>
      <span @click="handleClickHistoryButton">{{ $t('历史查询') }}</span>
    </span>
    <div v-show="false">
      <ul
        ref="historyUlRef"
        class="retrieve-history-list"
        v-bkloading="{ isLoading: historyLoading, size: 'mini' }"
      >
        <template v-if="isHistoryRecords">
          <li
            v-for="item in historyRecords"
            :key="item.id"
            class="list-item"
            @click="handleClickHistory(item)"
          >
            <div class="item-text">
              <div
                class="icon"
                :class="getClass(item.search_mode)"
              >
                {{ getText(item.search_mode) }}
              </div>

              <div
                class="text"
                v-bk-tooltips="{
                  content: item.query_string,
                  disabled: item.query_string.length < 5,
                }"
              >
                {{ item.query_string }}
              </div>
            </div>
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
  import { ConditionOperator } from '@/store/condition-operator';
  export default {
    data() {
      return {
        historyLoading: false,
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
      getClass(searchMode) {
        const classMap = {
          ui: 'bklog-c-ui',
          sql: 'bklog-c-sql',
        };
        return classMap[searchMode] || '';
      },
      getText(searchMode) {
        const textMap = {
          ui: 'UI',
          sql: '</>',
        };
        return textMap[searchMode] || '';
      },
      async handleClickHistoryButton(e) {
        await this.requestSearchHistory();
        const popoverWidth = '560px';
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
            this.historyRecords = [];
            this.isHistoryRecords = true;
            this.popoverInstance?.destroy();
            this.popoverInstance = null;
          },
        });
        this.popoverInstance.show();
      },
      handleClickHistory(item) {
        const { search_mode, params } = item;
        const { keyword, addition, ip_chooser } = params;
        this.$emit('change', { keyword, addition, ip_chooser, search_mode });
        this.popoverInstance.hide();
      },
      requestSearchHistory() {
        this.historyLoading = true;
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
            this.historyRecords = res.data
              .filter(item => item.query_string !== '*')
              .map(item => {
                item.params.addition = item.params.addition.map(element => {
                  const instance = new ConditionOperator(element);
                  return instance.formatApiOperatorToFront();
                });

                return item;
              });
            this.isHistoryRecords = !!this.historyRecords.length;
          })
          .finally(() => {
            this.historyLoading = false;
          });
      },
    },
  };
</script>

<style lang="scss">
  @import './query-history.scss';
</style>
