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

import { join } from '@/global/utils/path';
import { requestJson } from '@/request';

// 用户信息接口定义
interface UserDisplayInfo {
  username: string;
  display_name: string;
  [key: string]: any;
}

// 租户管理器
// 用于管理租户ID，并提供租户ID的设置和获取
export class TenantManager {
  private tenantId: string | null | undefined;
  // 用户信息缓存：租户ID -> 用户信息
  private userCache: Map<string, UserDisplayInfo> = new Map();
  // 请求队列：待请求的租户ID集合（去重）
  private requestQueue: Set<string> = new Set();
  // 正在请求的租户ID集合（避免重复请求）
  private pendingRequests: Set<string> = new Set();
  // 请求处理定时器ID
  private processTimer: number | null = null;
  // API基础路径
  private readonly API_BASE_URL = join(
    process.env.NODE_ENV === 'development' ? '/api/bk-user-web/prod' : window.BK_LOGIN_URL,
    '/api/v3/open-web/tenant/users',
  );
  // URL最大长度限制（保守估计，大多数浏览器和服务器支持至少2048字符）
  private readonly MAX_URL_LENGTH = 2000;

  constructor(tenantId?: string | null) {
    this.tenantId = tenantId;
  }

  /**
   * 设置租户ID
   */
  setTenantId(tenantId: string | null | undefined) {
    this.tenantId = tenantId;
  }

  /**
   * 获取租户ID
   */
  getTenantId(): string | null | undefined {
    return this.tenantId;
  }

  /**
   * 判断是否为多租户环境
   */
  private isMultiTenant(): boolean {
    return !!this.tenantId && this.tenantId.trim() !== '';
  }

  /**
   * 计算安全的批次大小，避免URL长度超限
   * @param tenantIds 租户ID数组
   * @returns 批次大小
   */
  private calculateBatchSize(tenantIds: string[]): number {
    // 计算基础URL长度
    const baseUrlLength = `${this.API_BASE_URL}/-/display_info/?bk_usernames=`.length;
    // 可用长度 = 最大URL长度 - 基础URL长度 - 安全边界（100字符）
    const availableLength = this.MAX_URL_LENGTH - baseUrlLength - 100;

    if (tenantIds.length === 0) {
      return 50; // 默认值
    }

    // 计算实际的平均租户ID长度（包括逗号）
    const totalLength = tenantIds.reduce((sum, id) => sum + id.length + 1, 0);
    const avgLengthPerId = totalLength / tenantIds.length;

    // 计算批次大小
    const batchSize = Math.floor(availableLength / avgLengthPerId);

    // 确保批次大小在合理范围内（最小10，最大100）
    return Math.max(10, Math.min(100, batchSize));
  }

  /**
   * 获取用户显示信息
   * @param tenantId 租户ID（在多租户环境下）或用户名（在非多租户环境下）
   * @returns 用户显示信息
   */
  async getUserDisplayInfo(tenantId: string): Promise<UserDisplayInfo | null> {
    // 非多租户环境，直接返回租户ID作为用户名
    if (!this.isMultiTenant()) {
      return {
        username: tenantId,
        display_name: tenantId,
      };
    }

    // 检查缓存
    if (this.userCache.has(tenantId)) {
      return this.userCache.get(tenantId)!;
    }

    // 添加到请求队列
    this.requestQueue.add(tenantId);

    // 触发异步处理（低优先级）
    this.scheduleProcess();

    // 返回一个默认值，实际数据会在请求完成后更新缓存
    return {
      username: tenantId,
      display_name: tenantId,
    };
  }

  /**
   * 批量获取用户显示信息
   * @param tenantIds 租户ID数组
   * @returns 用户显示信息Map
   */
  async batchGetUserDisplayInfo(tenantIds: string[]): Promise<Map<string, UserDisplayInfo>> {
    const result = new Map<string, UserDisplayInfo>();

    // 非多租户环境，直接返回租户ID作为用户名
    if (!this.isMultiTenant()) {
      tenantIds.forEach((id) => {
        result.set(id, {
          username: id,
          display_name: id,
        });
      });
      return result;
    }

    // 过滤已缓存的租户ID
    const uncachedIds: string[] = [];
    tenantIds.forEach((id) => {
      if (this.userCache.has(id)) {
        result.set(id, this.userCache.get(id)!);
      } else {
        uncachedIds.push(id);
      }
    });

    // 如果有未缓存的ID，添加到请求队列
    if (uncachedIds.length > 0) {
      uncachedIds.forEach((id) => {
        this.requestQueue.add(id);
      });
      // 触发异步处理（低优先级）
      this.scheduleProcess();
    }

    // 对于未缓存的ID，先返回默认值
    uncachedIds.forEach((id) => {
      result.set(id, {
        username: id,
        display_name: id,
      });
    });

    return result;
  }

  /**
   * 调度请求处理（低优先级，不阻塞渲染）
   */
  private scheduleProcess() {
    if (this.processTimer !== null) {
      return; // 已经调度过了
    }

    // 使用 requestIdleCallback（如果支持）或 setTimeout 延迟执行
    if (typeof requestIdleCallback !== 'undefined') {
      requestIdleCallback(
        () => {
          this.processTimer = null;
          this.processQueue();
        },
        { timeout: 5000 },
      );
    } else {
      this.processTimer = window.setTimeout(() => {
        this.processTimer = null;
        this.processQueue();
      }, 100);
    }
  }

  /**
   * 处理请求队列
   */
  private async processQueue() {
    if (this.requestQueue.size === 0) {
      return;
    }

    // 非多租户环境，清空队列但不请求
    if (!this.isMultiTenant()) {
      this.requestQueue.clear();
      return;
    }

    // 批量处理请求
    const batch: string[] = [];
    const idsToProcess: string[] = [];

    // 从队列中取出待处理的ID（去重，排除正在请求的）
    this.requestQueue.forEach((id) => {
      if (!this.pendingRequests.has(id) && !this.userCache.has(id)) {
        idsToProcess.push(id);
        this.pendingRequests.add(id);
      }
    });

    // 清空队列
    this.requestQueue.clear();

    if (idsToProcess.length === 0) {
      return;
    }

    // 动态计算批次大小
    const batchSize = this.calculateBatchSize(idsToProcess);

    // 分批处理
    for (let i = 0; i < idsToProcess.length; i += batchSize) {
      batch.length = 0;
      batch.push(...idsToProcess.slice(i, i + batchSize));

      try {
        await this.fetchBatchUserInfo(batch);
      } catch (err) {
        console.error('Failed to fetch user info:', err);
        // 请求失败时，从pending中移除，允许重试
        batch.forEach((id) => {
          this.pendingRequests.delete(id);
        });
      }
    }

    // 如果队列中还有待处理的，继续调度
    if (this.requestQueue.size > 0) {
      this.scheduleProcess();
    }
  }

  /**
   * 批量获取用户信息
   * @param tenantIds 租户ID数组
   */
  private async fetchBatchUserInfo(tenantIds: string[]): Promise<void> {
    if (tenantIds.length === 0) {
      return;
    }

    // 构建URL并检查长度
    const queryParam = tenantIds.join(',');
    const url = `${this.API_BASE_URL}/-/display_info/?bk_usernames=${queryParam}`;

    // 如果URL长度超过限制，分批处理
    if (url.length > this.MAX_URL_LENGTH) {
      // 将当前批次进一步拆分
      const midPoint = Math.floor(tenantIds.length / 2);
      await Promise.all([
        this.fetchBatchUserInfo(tenantIds.slice(0, midPoint)),
        this.fetchBatchUserInfo(tenantIds.slice(midPoint)),
      ]);
      return;
    }

    const headers: Record<string, string> = {
      'x-bk-tenant-id': this.tenantId!,
    };

    try {
      const response = await requestJson<{ results?: UserDisplayInfo[] }>({
        url,
        method: 'GET',
        headers,
      });

      // 处理响应结果
      if (response.data?.results && Array.isArray(response.data.results)) {
        response.data.results.forEach((userInfo: UserDisplayInfo) => {
          if (userInfo.username) {
            this.userCache.set(userInfo.username, userInfo);
          }
        });
      }
    } catch {
      // 如果批量请求失败，尝试单个请求
      if (tenantIds.length === 1) {
        await this.fetchSingleUserInfo(tenantIds[0]);
      } else {
        // 批量失败时，尝试单个请求
        for (const id of tenantIds) {
          try {
            await this.fetchSingleUserInfo(id);
          } catch (error) {
            console.error(`Failed to fetch user info for ${id}:`, error);
          }
        }
      }
    } finally {
      // 从pending中移除
      tenantIds.forEach((id) => {
        this.pendingRequests.delete(id);
      });
    }
  }

  /**
   * 单个获取用户信息
   * @param tenantId 租户ID
   */
  private async fetchSingleUserInfo(tenantId: string): Promise<void> {
    const url = `${this.API_BASE_URL}/${tenantId}/display_info/`;
    const headers: Record<string, string> = {
      'x-bk-tenant-id': this.tenantId!,
    };

    try {
      const response = await requestJson<UserDisplayInfo>({
        url,
        method: 'GET',
        headers,
      });

      if (response.data) {
        this.userCache.set(tenantId, response.data);
      }
    } catch (err) {
      console.error(`Failed to fetch user info for ${tenantId}:`, err);
      throw err;
    }
  }

  /**
   * 清除缓存
   */
  clearCache() {
    this.userCache.clear();
  }

  /**
   * 获取缓存大小
   */
  getCacheSize(): number {
    return this.userCache.size;
  }
}

export const tenantManager = new TenantManager();
