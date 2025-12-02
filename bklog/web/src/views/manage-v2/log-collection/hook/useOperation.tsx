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
 * 新建采集的自定义 Hook
 * 提供采集操作相关的通用功能，包括卡片渲染、字段获取、权限判断等
 */
import { computed, ref, type Ref } from 'vue';

import * as authorityMap from '@/common/authority-map';
import useStore from '@/hooks/use-store';

import $http from '@/api';

/**
 * 卡片配置项类型定义
 */
export interface ICardItem {
  /** 卡片唯一标识 */
  key: number | string;
  /** 卡片标题 */
  title: string;
  /** 卡片内容渲染函数 */
  renderFn: () => any;
  /** 卡片副标题渲染函数（可选） */
  subTitle?: () => any;
}

/**
 * API 请求参数类型
 */
interface IRequestParams {
  [key: string]: any;
}

/**
 * API 响应数据类型
 */
interface IApiResponse<T = any> {
  data?: T;
  [key: string]: any;
}

/**
 * 字段信息类型
 */
interface IFieldInfo {
  field_name?: string;
  field_type?: string;
  [key: string]: any;
}

/**
 * 结果表信息响应类型
 */
interface IResultTableInfoResponse {
  data?: {
    fields?: IFieldInfo[];
    [key: string]: any;
  };
  [key: string]: any;
}

/**
 * 索引组列表响应类型
 */
interface IIndexGroupListResponse {
  list?: any[];
  total?: number;
  [key: string]: any;
}

/**
 * 权限对象类型
 */
interface IPermissionItem {
  permission?: {
    [key: string]: boolean;
  };
  [key: string]: any;
}

/**
 * 数据回调函数类型
 */
type DataCallback<T = any> = (_data: T) => void;

/**
 * 响应转换回调函数类型
 */
type ResponseTransformCallback = (_response: IApiResponse) => any;

/**
 * 采集操作相关的自定义 Hook
 * @returns 返回操作相关的状态和方法
 */
export const useOperation = () => {
  const store = useStore();
  const spaceUid = computed(() => store.getters.spaceUid);

  // ==================== 状态管理 ====================

  /** 表格加载状态 */
  const tableLoading: Ref<boolean> = ref(false);

  /** 采集项列表加载状态 */
  const indexGroupLoading: Ref<boolean> = ref(false);

  // ==================== 卡片渲染相关 ====================

  /**
   * 渲染卡片配置列表
   * 根据配置数组生成卡片组件，用于展示分类信息
   * @param cardConfig - 卡片配置数组
   * @returns JSX 元素
   */
  const cardRender = (cardConfig: ICardItem[]) => (
    <div class='classify-main-box'>
      {cardConfig.map(item => (
        <div
          key={item.key}
          class='info-card'
        >
          <div class='card-title'>
            {item.title}
            {item?.subTitle?.()}
          </div>
          {item.renderFn()}
        </div>
      ))}
    </div>
  );

  // ==================== 数据获取相关 ====================

  /**
   * 选择采集项获取字段列表
   * 通过结果表ID获取对应的字段信息列表
   * @param params - 请求参数，通常包含 result_table_id 等
   * @param isList - 是否返回完整响应对象，默认为 false（仅返回字段数组）
   * @param callback - 可选的响应转换回调函数，用于自定义数据处理逻辑
   * @returns 当 isList 为 true 时返回完整响应，否则返回字段数组
   */
  const handleMultipleSelected = async (
    params: IRequestParams,
    isList: boolean = false,
    callback?: ResponseTransformCallback,
  ): Promise<IFieldInfo[] | IApiResponse | undefined> => {
    try {
      tableLoading.value = true;
      const res = (await $http.request('/resultTables/info', params)) as IResultTableInfoResponse;
      const data = callback?.(res) || res.data?.fields || [];
      return isList ? res : data;
    } catch (e) {
      console.log('获取字段列表失败:', e);
      return undefined;
    } finally {
      tableLoading.value = false;
    }
  };

  /**
   * 获取索引组列表数据
   * 根据当前空间UID获取采集项分组列表
   * @param callback - 成功回调函数，接收响应数据作为参数
   */
  const getIndexGroupList = (callback?: DataCallback<IIndexGroupListResponse>): void => {
    indexGroupLoading.value = true;
    $http
      .request('collect/getIndexGroupList', {
        query: {
          space_uid: spaceUid.value,
        },
      })
      .then((res: IApiResponse<IIndexGroupListResponse>) => {
        callback?.(res.data);
      })
      .catch((err: Error) => {
        console.log('获取索引组列表失败:', err);
      })
      .finally(() => {
        indexGroupLoading.value = false;
      });
  };

  // ==================== 权限相关 ====================

  /**
   * 判断项目是否拥有管理ES源的权限
   * 检查项目对象中是否包含管理ES源的权限标识
   * @param item - 待判断权限的项目对象（存储项或集群等）
   * @returns 是否拥有管理权限
   */
  const hasManageEsPermission = (item: IPermissionItem): boolean => {
    return Boolean(item.permission?.[authorityMap.MANAGE_ES_SOURCE_AUTH]);
  };

  /**
   * 按权限排序数据
   * 将有管理ES源权限的项目排在前面，无权限的排在后面
   * @param data - 待排序的数据数组
   * @returns 按权限排序后的数组
   */
  const sortByPermission = <T extends IPermissionItem>(data: T[]): T[] => {
    const withPermission: T[] = [];
    const withoutPermission: T[] = [];

    for (const item of data) {
      if (hasManageEsPermission(item)) {
        withPermission.push(item);
      } else {
        withoutPermission.push(item);
      }
    }

    return [...withPermission, ...withoutPermission];
  };

  // ==================== 返回值 ====================

  return {
    // 状态
    tableLoading,
    indexGroupLoading,
    // 方法
    cardRender,
    handleMultipleSelected,
    getIndexGroupList,
    sortByPermission,
  };
};
