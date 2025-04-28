import { computed, ComputedRef } from 'vue';

export default ({ indexSetList }: { indexSetList: ComputedRef<any[]> }) => {
  const indexSetTagList: ComputedRef<{ id: number; name: string; color: string }[]> = computed(() => {
    const listMap: Map<number, { id: number; name: string; color: string }> = indexSetList.value.reduce((acc, item) => {
      item.tags.forEach(tag => {
        if (!acc.has(tag.tag_id)) {
          acc.set(tag.tag_id, tag);
        }
      });

      return acc;
    }, new Map<number, { id: number; name: string; color: string }>());

    return Array.from(listMap.values());
  });

  return { indexSetTagList };
};
