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
  const collectGroupList = computed(() => [{ id: 'group1', name: '分组1' }]);

  // 新建提交逻辑
  const handleCreateRequest = () => {

  }

</script>
<template>
  <span class="disabled bklog-icon bklog-star-line"></span>
</template>
<style lang="scss" scoped></style>
