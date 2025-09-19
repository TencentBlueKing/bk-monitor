<script setup>
  import { computed } from 'vue';

  // @ts-ignore
  import useStore from '@/hooks/use-store';
  
  const props = defineProps({
    searchValue: {
      type: String,
      default: '',
    },
  });

  const store = useStore();
  const emit = defineEmits(['change']);

  const indexSetItemIdList = computed(() => store.state.indexItem.ids);
  const favoriteGroupList = computed(() => store.state.favoriteList.map(f => f.favorites).flat());

  const separator = /\s+(AND\s+NOT|OR|AND)\s+/i; // 区分查询语句条件
  const regFormat = str => `${str}`.replace(/[-[\]{}()*+?.,\\^$|#\s]/g, '\\$&');

  const regExpStringList = computed(() =>
    (props.searchValue ?? '')
      .split(separator)
      .filter(item => item.length)
      .map(k => new RegExp(regFormat(k).replace(':', '\\s*:\\s*'), 'ig')),
  );

  const isSqlMode = item => {
    return item.search_mode === 'sql' && !(item.params.chart_params?.type ?? false);
  };

  // 数据格式: [{ group_id: '', group_name: '', group_type: '' }]
  const favoriteList = computed(() => {
    const filter = favoriteGroupList.value
      .filter(item => {
        return (
          (isSqlMode(item) && indexSetItemIdList.value.includes(`${item.index_set_id}`)) ||
          item.index_set_ids?.some(id => indexSetItemIdList.value.includes(`${id}`))
        );
      })
      .filter(child => {
        if (child.favorite_type === 'chart') {
          return (
            regExpStringList.value.length &&
            regExpStringList.value.every(reg => reg.test(child.params?.chart_params?.sql))
          );
        }

        return (
          child.params?.keyword === '*' ||
          (regExpStringList.value.length && regExpStringList.value.every(reg => reg.test(child.params?.keyword)))
        );
      });

    return filter;
  });

  const handleClickFavorite = item => {
    emit('change', item);
  };
</script>
<template>
  <div class="favorite-footer">
    <!-- 收藏查询列表 -->
    <div :class="['favorite-query-list', { 'no-data': !favoriteList.length }]">
      <div
        v-if="favoriteList.length"
        class="query-list-title"
      >
        {{ $t('联想到以下') }}
        <span class="count">{{ favoriteList.length || 0 }}</span>
        {{ $t('个收藏') }}:
      </div>
      <div class="favorite-list">
        <template v-if="favoriteList.length">
          <div
            v-for="(item, index) in favoriteList"
            class="list-item"
            :key="index"
            @click="handleClickFavorite(item)"
          >
            <div><span class="active bklog-icon bklog-table-2"></span></div>
            <div class="list-item-type">{{ item.full_name || $t('检索语句') }}</div>
            <div class="list-item-information">{{ item.params?.keyword }}</div>
          </div>
        </template>
        <template v-else>
          <bk-exception
            class="exception-wrap-item exception-part exception-gray"
            scene="part"
            type="empty"
          >
            <span style="color: #979ba5">{{ $t('暂无匹配的收藏项') }}</span>
          </bk-exception>
        </template>
      </div>
    </div>
  </div>
</template>
<style lang="scss" scoped>
  .favorite-footer {
    /* 收藏查询列表 样式 */
    .favorite-query-list {
      position: relative;
      min-height: 95px;
      max-height: 200px;
      overflow: auto;
      border-top: 1px solid #ecedf2;

      .query-list-title {
        padding: 0 12px;
        margin-top: 7px;
        margin-bottom: 10px;
        font-size: 12px;
        line-height: 22px;
        color: #313238;

        .count {
          font-weight: bold;
          color: #3a84ff;
        }
      }

      .favorite-list {
        margin-bottom: 8px;

        :deep(.bk-exception) {
          .exception-image {
            width: 110px;
            height: 50px;
          }

          .bk-exception-text.part-text {
            font-size: 12px;
          }
        }
      }

      .list-item {
        display: flex;
        align-items: center;
        padding: 0 12px;
        line-height: 26px;

        .active {
          font-size: 14px;
          // color: #ffb848;
        }

        .list-item-type {
          min-width: 64px;
          margin-left: 4px;
          font-size: 12px;
          font-weight: 700;
          // color: #3a84ff;
          color: #313238;
          text-align: center;

          // background: #f0f5ff;
        }

        .list-item-information {
          margin: 0 8px;
          font-family: 'Roboto Mono', Consolas, Menlo, Courier, monospace;
          font-size: 12px;
          color: #4d4f56;
        }

        .list-item-text {
          color: #979ba5;
        }

        &:hover,
        &.active {
          background-color: #f4f6fa;
        }

        &:hover {
          cursor: pointer;
          background-color: #eaf3ff;
        }
      }

      &.no-data {
        .favorite-list {
          height: 95px;
          margin-bottom: 0;

          .bk-exception {
            justify-content: center;
            height: 100%;
          }
        }
      }
    }
  }
</style>
