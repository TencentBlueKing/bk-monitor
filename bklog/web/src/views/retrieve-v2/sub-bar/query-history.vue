<template>
  <div class="retrieve-tab-item-title">
    <span class="history-button" @click="handleClickHistoryButton">
      <span class="bklog-icon bklog-history-2"></span>
      <span >{{ $t('历史查询') }}</span>
    </span>
    <div v-show="false">
      <div ref="historyUlRef">
          <div class="input-box">
            <bk-input
              behavior="simplicity"
              :left-icon="'bklog-icon bklog-shoudongchaxun'"
              :clearable="true"
              :placeholder="$t('请输入关键字')"
              v-model="searchInput"
              ext-cls="search-input"
            ></bk-input>
          </div>
        <ul
          ref="historyUlRef"
          class="retrieve-history-list"
          v-bkloading="{ isLoading: historyLoading, size: 'mini' }"
        >
          <template v-if="isHistoryRecords">
            <li
              v-for="item in filterHistoryRecords"
              :key="item.id"
              class="list-item"
              @click="handleClickHistory(item)"
            >
              <div class="item-text"
                v-bk-tooltips="{
                  allowHTML:true,
                  placement:'top',
                  content: getContent(item),
                  disabled: item.query_string.length < 5,
                }"
              >
                <span
                  class="bklog-icon"
                  :class="getClass(item.search_mode)"
                >
                  <!-- {{ getText(item.search_mode) }} -->
                </span>

                <div
                  class="text"
                >
                  {{ item.query_string }}
                </div>
                <BookmarkPop
                v-if="!isMonitorComponent"
                :sql="item.query_string"
                :addition="item.params.addition"
                searchMode='sql'
                active-favorite="history"
                @instanceShow="instanceShow"
                ></BookmarkPop>
              </div>
            </li>
          </template>
          <li
            v-else
            class="list-item not-history"
          >
            {{ $t('暂无历史记录') }}
          </li>
        </ul>
      </div>
    </div>
  </div>
</template>
<script>
import { ConditionOperator } from '@/store/condition-operator';
// #if MONITOR_APP !== 'apm' && MONITOR_APP !== 'trace'
import BookmarkPop from '../search-bar/bookmark-pop.vue';
// #else
// #code const BookmarkPop = () => null;
// #endif
import dayjs from 'dayjs';
export default {
  data() {
    return {
      historyLoading: false,
      isHistoryRecords: true,
      popoverInstance: null,
      historyRecords: [],
      searchInput: '',
      bookmarkPopRefsShow: false,
      isMonitorComponent: false,
    };
  },
  components: {
    BookmarkPop,
  },
  mounted() {
    this.isMonitorComponent = window.__IS_MONITOR_COMPONENT__;
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
    filterHistoryRecords() {
      if (!this.searchInput?.trim()) return this.historyRecords;
      const searchTerm = this.searchInput.toLowerCase();
      return this.historyRecords.filter(item => {
        return item.query_string?.toLowerCase().includes(searchTerm);
      });
    },
  },
  methods: {
    getClass(searchMode) {
      const classMap = {
        ui: 'bklog-ui1',
        sql: 'bklog-yuju1',
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
    getContent(item) {
      return `<div><div>${this.$t('检索时间')}：${dayjs(item.created_at).format('YYYY-MM-DD HH:mm:ss')}</div>
                <div>${this.$t('语句')}：${item.query_string}</div></div>`;
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
        onHide: () => {
          if (this.bookmarkPopRefsShow) {
            return false;
          }
        },
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
    instanceShow(val) {
      this.bookmarkPopRefsShow = val;
    },
  },
};
</script>

<style lang="scss">
  @import './query-history.scss';
</style>
