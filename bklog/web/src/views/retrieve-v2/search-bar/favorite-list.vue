<script setup>
  import { computed, ref } from 'vue';
  import useStore from '@/hooks/use-store';
  // @ts-ignore
  import { getRegExp } from '@/common/util';

  import imgEnterKey from '@/images/icons/enter-key.svg';
  import imgUpDownKey from '@/images/icons/up-down-key.svg';

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

  const regExpString = computed(() => props.value?.replace(/$\s*|\s*$/ig, '') ?? '');

  // 数据格式: [{ group_id: '', group_name: '', group_type: '' }]
  const favoriteList = computed(() =>
    favoriteGroupList.value
      .filter(item => {
        return (
          (item.search_mode === 'sql' && indexSetItemIdList.value.includes(`${item.index_set_id}`)) ||
          item.index_set_ids?.some(id => indexSetItemIdList.value.includes(`${id}`))
        );
      })
      .filter(child => {
        const regExp = getRegExp(regExpString.value);
        return regExp.test(child.params?.keyword);
      }),
  );

  const svgImg = ref({ imgUpDownKey, imgEnterKey });
  const handleClickFavorite = item => {
    emit('change', item);
  };
</script>
<template>
  <div class="favorite-footer">
    <!-- 收藏查询列表 -->
    <div class="favorite-query-list">
      <div class="query-list-title">{{ $t('收藏查询') }} ({{ favoriteList.length || 0 }})</div>
      <div class="favorite-list">
        <template v-if="favoriteList.length">
          <div
            class="list-item"
            v-for="item in favoriteList"
            @click="handleClickFavorite(item)"
          >
            <div><span class="active bklog-icon bklog-lc-star-shape"></span></div>
            <div class="list-item-type">检索语句</div>
            <div class="list-item-information">{{ item.params?.keyword }}</div>
          </div>
        </template>
        <template v-else>
          <bk-exception
            class="exception-wrap-item exception-part exception-gray"
            type="empty"
            scene="part"
          >
          </bk-exception>
        </template>
      </div>
    </div>
    <!-- 移动光标and确认结果提示 -->
    <div class="ui-shortcut-key">
      <span><img :src="svgImg.imgUpDownKey" />{{ $t('移动光标') }}</span>
      <span><img :src="svgImg.imgEnterKey" />{{ $t('确认结果') }}</span>
    </div>
  </div>
</template>
<style lang="scss" scoped>
  .favorite-footer {
    /* 收藏查询列表 样式 */
    .favorite-query-list {
      min-height: 150px;
      max-height: 200px;
      overflow: auto;
      border-top: 1px solid #ecedf2;

      .query-list-title {
        height: 32px;
        padding: 5px 12px 7px 12px;
        font-size: 12px;
        line-height: 20px;
        color: #979ba5;
      }

      .favorite-list {
        margin-bottom: 8px;
      }

      .list-item {
        display: flex;
        align-items: center;
        height: 32px;
        padding: 4px 13px;

        .active {
          font-size: 14px;
          color: #ffb848;
        }

        .list-item-type {
          width: 64px;
          height: 22px;
          margin: 0px 5px;
          font-size: 12px;
          line-height: 22px;
          color: #3a84ff;
          text-align: center;

          background: #f0f5ff;
          border-radius: 2px;
        }

        .list-item-information {
          margin-right: 7px;
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
    }

    /* 移动光标and确认结果提示 样式 */
    .ui-shortcut-key {
      padding: 9px 0 7px 15px;
      background-color: #fafbfd;
      border-top: 1px solid #ecedf2;

      span {
        display: inline-flex;
        align-items: center;
        margin-right: 24px;
        font-size: 12px;
        line-height: 20px;
        color: #63656e;
        letter-spacing: 0;

        img {
          display: inline-flex;
          width: 16px;
          height: 16px;
          margin-right: 4px;
          background: #ffffff;
          border: 1px solid #dcdee5;
          border-radius: 2px;
        }
      }
    }
  }
</style>
