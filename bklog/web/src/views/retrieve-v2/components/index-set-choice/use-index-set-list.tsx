import { computed, ComputedRef } from 'vue';

export default (props, { emit }) => {
  /**
   * 索引集列表过滤标签
   */
  const indexSetTagList: ComputedRef<{ tag_id: number; name: string; color: string }[]> = computed(() => {
    const listMap: Map<number, { tag_id: number; name: string; color: string }> = props.list.reduce((acc, item) => {
      item.tags.forEach(tag => {
        if (!acc.has(tag.tag_id) && tag.tag_id !== 4) {
          acc.set(tag.tag_id, tag);
        }
      });

      return acc;
    }, new Map<number, { tag_id: number; name: string; color: string }>());

    return Array.from(listMap.values());
  });

  const clearAllValue = () => {
    emit('value-change', []);
  };

  /**
   * 多选：选中操作
   * @param item
   * @param value
   */
  const handleIndexSetItemCheck = (item, isChecked) => {
    const targetValue = [];

    // 如果是选中
    if (isChecked) {
      props.value.forEach((v: any) => {
        targetValue.push(v);
      });
      targetValue.push(item.index_set_id);
      emit('value-change', targetValue);
      return;
    }

    // 如果是取消选中
    props.value.forEach((v: any) => {
      if (v !== item.index_set_id) {
        targetValue.push(v);
      }
    });

    emit('value-change', targetValue);
  };

  return {
    clearAllValue,
    handleIndexSetItemCheck,
    indexSetTagList,
  };
};
