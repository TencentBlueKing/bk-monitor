<template>
  <div class="retrieve-tab-item-title">
    <TPopup
      :visible="visible"
      trigger="click"
      placement="bottom"
      show-arrow
      :popper-options="{ modifiers: [{ name: 'offset', options: { offset: [0, -6] } }] }"
      :overlay-inner-style="{ width: '560px', padding: '6px 0' }"
      overlay-class-name="retrieve-history-popover"
      @visible-change="handleVisibleChange"
    >
      <span
        class="history-button"
        role="button"
        tabindex="0"
        @keydown.enter.prevent="handleVisibleChange(!visible)"
        @keydown.space.prevent="handleVisibleChange(!visible)"
      >
        <span class="bklog-icon bklog-history-2"></span>
        <span>{{ $t('历史查询') }}</span>
      </span>
      <template #content>
        <div class="query-history-content" data-testid="query-history-content">
          <div class="input-box">
            <TInput v-model="searchInput" clearable :placeholder="$t('请输入关键字')" class="search-input">
              <template #prefix-icon><span class="bklog-icon bklog-shoudongchaxun"></span></template>
            </TInput>
          </div>
          <BklogLoading :loading="historyLoading" size="small">
            <ul class="retrieve-history-list">
              <template v-if="historyRecords.length">
                <li
                  v-for="item in filterHistoryRecords"
                  :key="item.id"
                  class="list-item"
                  @click="handleClickHistory(item)"
                >
                  <TTooltip placement="top" :disabled="item.query_string.length < 5">
                    <template #content>
                      <div>{{ $t('检索时间') }}：{{ formatTime(item.created_at) }}</div>
                      <div>{{ $t('语句') }}："{{ item.query_string }}"</div>
                    </template>
                    <div class="item-text">
                      <span class="bklog-icon" :class="getClass(item.params.search_mode || item.search_mode)"></span>
                      <div class="text">{{ item.query_string }}</div>
                      <span v-if="!isMonitorComponent" class="history-bookmark" @click.stop>
                        <BookmarkPop
                          :sql="(item.params.search_mode || item.search_mode) === 'sql' ? item.query_string : ''"
                          :addition="item.params.addition"
                          :search-mode="item.params.search_mode || item.search_mode || 'sql'"
                          active-favorite="history"
                          @instance-show="bookmarkPopRefsShow = $event"
                        />
                      </span>
                    </div>
                  </TTooltip>
                </li>
              </template>
              <li v-else-if="!historyLoading" class="list-item not-history">{{ $t('暂无历史记录') }}</li>
            </ul>
          </BklogLoading>
        </div>
      </template>
    </TPopup>
  </div>
</template>
<script setup lang="ts">

import { useApplicationStore } from '@/app/state/domains/application-store';
import { computed } from 'vue';
import dayjs from 'dayjs';
import { Popup as TPopup, Input as TInput, Tooltip as TTooltip } from 'tdesign-vue-next';
import BklogLoading from '@/shared/ui/loading';

import useLocale from '@/shared/composables/use-locale';
// #if MONITOR_APP !== 'apm' && MONITOR_APP !== 'trace'
import BookmarkPop from '../search-bar/components/bookmark-pop.vue';
// #else
// #code const BookmarkPop = () => null;
// #endif
import { useQueryHistory, type HistoryQueryParams } from './use-query-history';
const emit = defineEmits<{ change: [params: HistoryQueryParams] }>();
const store = useApplicationStore();
const { $t } = useLocale();
const isMonitorComponent = computed(() => !!window.__IS_MONITOR_COMPONENT__);
const {
  visible,
  historyLoading,
  historyRecords,
  searchInput,
  filterHistoryRecords,
  bookmarkPopRefsShow,
  handleVisibleChange,
  handleClickHistory,
} = useQueryHistory(
  () => ({
    isSceneMode: store.isSceneMode,
    isUnionSearch: store.isUnionSearch,
    indexId: store.indexItem.ids[0],
    unionIndexList: store.unionIndexList,
    retrieveParams: store.retrieveParams,
  }),
  (params) => emit('change', params),
);
const getClass = (mode?: string) => (mode === 'ui' ? 'bklog-ui1' : mode === 'sql' ? 'bklog-yuju1' : '');
const formatTime = (value: string) => dayjs(value).format('YYYY-MM-DD HH:mm:ssZZ');
</script>
<style lang="scss">
@use './query-history.scss' as *;
.query-history-content .search-input .t-input {
  border-color: transparent transparent #3a84ff;
  box-shadow: none;
}
.query-history-content .item-text {
  width: 100%;
}
.query-history-content .history-bookmark {
  position: absolute;
  right: 10px;
  top: 0;
  height: 32px;
  display: flex;
  align-items: center;
}
</style>
