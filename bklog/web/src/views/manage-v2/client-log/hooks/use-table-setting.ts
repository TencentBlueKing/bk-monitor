/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 *
 * Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
 *
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) is licensed under the MIT License.
 *
 * License for 蓝鲸智云PaaS平台 (BlueKing PaaS):
 *
 * ---------------------------------------------------
 * Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated
 * documentation files (the "Software"), to deal in the Software without restriction, including without limitation
 * the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and
 * to permit persons to whom the Software is furnished to do so, subject to the following conditions:
 *
 * The above copyright notice and this permission notice shall be included in all copies or substantial portions of
 * the Software.
 *
 * THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO
 * THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
 * AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF
 * CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS
 * IN THE SOFTWARE.
 */

import { ref, onMounted } from 'vue';
import { getDefaultSettingSelectFiled, setDefaultSettingSelectFiled } from '@/common/util';

export interface SettingField {
  id: string;
  label: string;
  disabled?: boolean;
}

export interface UseTableSettingOptions {
  /** 缓存键名 */
  cacheKey: string;
  /** 所有字段配置 */
  fields: SettingField[];
  /** 默认选中的字段ID列表 */
  defaultSelectedIds?: string[];
}

/**
 * 表格列设置 hook
 * @param options 配置选项
 */
export function useTableSetting(options: UseTableSettingOptions) {
  const { cacheKey, fields, defaultSelectedIds } = options;

  // 计算默认选中的字段
  const getDefaultSelectedFields = (): SettingField[] => {
    if (defaultSelectedIds && defaultSelectedIds.length > 0) {
      // 按 defaultSelectedIds 的顺序返回对应的字段
      return defaultSelectedIds
        .map(id => fields.find(field => field.id === id))
        .filter((field): field is SettingField => !!field);
    }
    // 如果没有指定默认选中，则全部显示
    return fields;
  };

  const settingFields = ref<SettingField[]>(fields);

  const columnSetting = ref({
    fields: settingFields.value,
    selectedFields: getDefaultSelectedFields(),
  });

  /**
   * 检查字段是否显示
   */
  const checkFields = (fieldId: string): boolean => {
    return columnSetting.value.selectedFields.some(item => item.id === fieldId);
  };

  /**
   * 设置变化处理
   */
  const handleSettingChange = ({ fields: newFields }: { fields: SettingField[] }) => {
    columnSetting.value.selectedFields.splice(0, columnSetting.value.selectedFields.length, ...newFields);
    setDefaultSettingSelectFiled(cacheKey, newFields);
  };

  onMounted(() => {
    const cachedFields = getDefaultSettingSelectFiled(cacheKey, columnSetting.value.selectedFields);
    if (cachedFields) {
      columnSetting.value.selectedFields = cachedFields;
    }
  });

  return {
    settingFields,
    columnSetting,
    checkFields,
    handleSettingChange,
  };
}

export default useTableSetting;
