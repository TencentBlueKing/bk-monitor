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

import { ref, computed, type Ref, type ComputedRef } from 'vue';
import { useRoute } from 'vue-router/composables';

import $http from '@/api';
import useStore from '@/hooks/use-store';

// ==================== 类型定义 ====================

export interface IProxyHostUrl {
  protocol: string;
  report_url: string;
}

export interface IUseCustomTypeIntroOptions {
  /** 获取当前 custom_type 的函数或响应式引用 */
  getCustomType: () => string | undefined;
  /** 获取用于变量替换的数据对象 */
  getData: () => Record<string, any>;
}

export interface IUseCustomTypeIntroReturn {
  /** 代理主机列表 */
  proxyHost: Ref<any[]>;
  /** 处理后的帮助文档内容 */
  customTypeIntro: ComputedRef<string>;
  /** 初始化代理主机列表 */
  initProxyHost: () => Promise<void>;
  /** 替换变量占位符 */
  replaceVariables: (intro: string) => string;
  /** 替换云区域ID内容 */
  updateStringWithNewData: (originalString: string) => string;
}

/**
 * 自定义上报类型帮助文档 Hook
 * 用于获取和处理自定义上报类型的帮助文档内容
 *
 * @param options - 配置项
 * @returns 返回代理主机列表、帮助文档内容及相关方法
 *
 * @example
 * ```ts
 * const { customTypeIntro, initProxyHost } = useCustomTypeIntro({
 *   getCustomType: () => formData.value.custom_type,
 *   getData: () => formData.value as Record<string, any>,
 * });
 *
 * // 初始化
 * initProxyHost();
 *
 * // 使用帮助文档内容
 * console.log(customTypeIntro.value);
 * ```
 */
export const useCustomTypeIntro = (options: IUseCustomTypeIntroOptions): IUseCustomTypeIntroReturn => {
  const store = useStore();
  const route = useRoute();

  // ==================== 响应式数据 ====================

  /** 代理主机列表 */
  const proxyHost = ref<any[]>([]);

  /** 全局数据（包含自定义上报类型列表） */
  const globalsData = computed(() => store.getters['globals/globalsData']);

  // ==================== 方法 ====================

  /**
   * 获取代理主机列表
   */
  const initProxyHost = async (): Promise<void> => {
    try {
      const res = await $http.request('retrieve/getProxyHost', {
        query: {
          space_uid: route.query.spaceUid,
        },
      });
      proxyHost.value = res.data || [];
    } catch (error) {
      proxyHost.value = [];
      console.warn('获取代理主机列表失败:', error);
    }
  };

  /**
   * 替换云区域ID相关的 <code> 内容
   * @param originalString - 原始字符串
   * @returns 替换后的字符串
   */
  const updateStringWithNewData = (originalString: string): string => {
    const regex = /<code>[\s\S]*?云区域ID[\s\S]*?<\/code>/;

    // 格式化新的数据以便插入到 <code> 标签中
    const newDataContent = proxyHost.value
      .map(dataGroup =>
        dataGroup.urls
          .map((data: IProxyHostUrl) => `云区域ID ${dataGroup.bk_cloud_id} ${data.protocol}: ${data.report_url}`)
          .join('\n'),
      )
      .join('\n');

    const updatedString = originalString.replace(regex, `<code>${newDataContent}</code>`);
    return updatedString;
  };

  /**
   * 替换帮助文档中的变量占位符
   * @param intro - 原始字符串
   * @returns 替换后的字符串
   */
  const replaceVariables = (intro: string): string => {
    let str = updateStringWithNewData(intro);
    const varibleList = intro.match(/\{\{([^)]*)\}\}/g);
    const data = options.getData();

    varibleList?.forEach((item) => {
      const val = item.match(/\{\{([^)]*)\}\}/)?.[1];
      if (val && data[val]) {
        str = str.replace(item, data[val]);
      }
    });

    return str;
  };

  /**
   * 获取当前自定义类型的帮助文档内容
   */
  const customTypeIntro = computed((): string => {
    const dataTypeList: any[] = globalsData.value.databus_custom || [];
    const customType = options.getCustomType();
    const curType = dataTypeList.find((type: any) => type.id === customType);
    return curType ? replaceVariables(curType.introduction) : '';
  });

  // ==================== 返回值 ====================

  return {
    proxyHost,
    customTypeIntro,
    initProxyHost,
    replaceVariables,
    updateStringWithNewData,
  };
};

export default useCustomTypeIntro;
