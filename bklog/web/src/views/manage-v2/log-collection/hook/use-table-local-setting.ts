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

/**
 * 采集列表个人设置本地存储 hook
 * 归属、排序、字段设置、列宽、页大小五项个人设置，全局一份配置
 */

export interface ICollectTableSetting {
  /** 归属：'' | 'current_space' | 'related_space'（对应 filterValue.is_related_space） */
  source: string;
  /** 排序字段（对应 sortConfig.sortBy） */
  sortBy: string;
  /** 排序方向（对应 sortConfig.descending） */
  descending: boolean;
  /** 每页条数 */
  pageSize: number;
  /** 字段设置（settingFields 的 id 列表） */
  selectedFields: string[];
  /** 列宽 { [colKey]: number } */
  columnsWidth: Record<string, number>;
}

interface ICollectTableSettingStorage extends Partial<ICollectTableSetting> {
  /** 缓存结构版本，结构升级时递增使旧缓存失效 */
  version?: number;
}

const STORAGE_KEY = 'BKLOG_COLLECT_TABLE_SETTING';
const STORAGE_VERSION = 1;

/**
 * 采集列表个人设置本地存储 hook
 * 读取：无缓存 / JSON 解析失败 / 版本不符时返回 null
 * 写入：局部合并更新
 */
export const useTableLocalSetting = () => {
  /**
   * 读取个人设置
   * @returns 缓存的个人设置；无缓存/解析失败/版本不符返回 null
   */
  const getSetting = (): Partial<ICollectTableSetting> | null => {
    try {
      const settingStr = localStorage.getItem(STORAGE_KEY);
      if (!settingStr) {
        return null;
      }
      const setting = JSON.parse(settingStr) as ICollectTableSettingStorage;
      if (!setting || typeof setting !== 'object' || setting.version !== STORAGE_VERSION) {
        return null;
      }
      const { version: _version, ...rest } = setting;
      return rest;
    } catch (error) {
      console.log('读取采集列表个人设置失败:', error);
      return null;
    }
  };

  /**
   * 合并写入个人设置（局部更新）
   * @param partial - 需要更新的设置项
   */
  const updateSetting = (partial: Partial<ICollectTableSetting>) => {
    try {
      const settingStr = localStorage.getItem(STORAGE_KEY);
      let prevSetting: ICollectTableSettingStorage = {};
      if (settingStr) {
        const parsed = JSON.parse(settingStr) as ICollectTableSettingStorage;
        if (parsed && typeof parsed === 'object' && parsed.version === STORAGE_VERSION) {
          prevSetting = parsed;
        }
      }
      const nextSetting: ICollectTableSettingStorage = {
        ...prevSetting,
        ...partial,
        version: STORAGE_VERSION,
      };
      localStorage.setItem(STORAGE_KEY, JSON.stringify(nextSetting));
    } catch (error) {
      console.log('写入采集列表个人设置失败:', error);
    }
  };

  return {
    getSetting,
    updateSetting,
  };
};

export default useTableLocalSetting;
