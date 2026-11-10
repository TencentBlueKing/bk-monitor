/* Copyright (C) 2021 THL A29 Limited, a Tencent company.
 * 蓝鲸智云PaaS平台 (BlueKing PaaS), MIT License. */
import { computed } from 'vue';
import { parseTableRowData } from '@/shared/lib/util';
import useStore from './use-store';
export function useTableRowDeepView() {
  const store = useStore();
  const isFormatDate = computed(() => store.state.isFormatDate);
  function tableRowDeepView(
    row: Parameters<typeof parseTableRowData>[0],
    key: Parameters<typeof parseTableRowData>[1],
    fieldType?: Parameters<typeof parseTableRowData>[2],
    formatDate = isFormatDate.value,
    emptyCharacter?: Parameters<typeof parseTableRowData>[4],
  ) {
    return parseTableRowData(row, key, fieldType, formatDate, emptyCharacter);
  }
  return { isFormatDate, tableRowDeepView };
}
