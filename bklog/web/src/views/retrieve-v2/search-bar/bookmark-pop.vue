<script setup>
  import { computed } from 'vue';
  import useStore from '@/hooks/use-store';

  const props = defineProps({
    sql: {
      default: '',
      type: String,
      required: true,
    },
  });

  const store = useStore();

  // 用于展示索引集
  // 这里返回数组，展示 index_set_name 字段
  const indexSetItemList = computed(() => store.state.indexItem.items);

  // 数据格式: [{ group_id: '', group_name: '', group_type: '' }]
  const collectGroupList = computed(() => store.state.favoriteList);

  // 新建提交逻辑
  const handleCreateRequest = () => {};
</script>
<template>
  <span class="disabled bklog-icon bklog-star-line"></span>
</template>
<style lang="scss" scoped></style>
