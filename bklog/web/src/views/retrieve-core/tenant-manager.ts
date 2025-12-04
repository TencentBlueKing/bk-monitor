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
import { EventEmitter } from './event';

// 用户信息接口定义
interface UserDisplayInfo {
  login_name: string;
  full_name: string;
  display_name: string;
  groups?: string[]; // 用户所属的分组列表
  [key: string]: any;
}

// 事件类型定义
export type TenantManagerEvent = 'userInfoLoaded' | 'userInfoUpdated';

// 用户信息加载事件参数
export interface UserInfoLoadedEventData {
  tenantIds: string[];
  userInfo: Map<string, UserDisplayInfo>;
}

// 租户管理器
// 用于管理租户ID，并提供租户ID的设置和获取
export class TenantManager extends EventEmitter<TenantManagerEvent> {
  private tenantId: string | null | undefined;
  // 用户信息缓存：租户ID -> 用户信息
  private userCache: Map<string, UserDisplayInfo> = new Map();
  // 分组映射：分组名称 -> 该分组下的人员 login_name 集合
  private groupMap: Map<string, Set<string>> = new Map();
  // 默认分组名称
  private readonly DEFAULT_GROUP = 'default';
  // 请求队列：待请求的租户ID集合（去重）
  private requestQueue: Set<string> = new Set();
  // 正在请求的租户ID集合（避免重复请求）
  private pendingRequests: Set<string> = new Set();
  // 请求处理定时器ID
  private processTimer: number | null = null;
  // 正在进行的请求 Promise 集合（用于等待所有请求完成）
  private pendingPromises: Set<Promise<void>> = new Set();
  // 当前正在执行的 processQueue Promise（用于等待队列处理完成）
  private processQueuePromise: Promise<void> | null = null;
  // API基础路径
  private readonly API_BASE_URL = join(
    process.env.NODE_ENV === 'development' ? '/api/bk-user-web/prod' : window.BK_LOGIN_URL,
    '/api/v3/open-web/tenant/users',
  );
  // URL最大长度限制（保守估计，大多数浏览器和服务器支持至少2048字符）
  private readonly MAX_URL_LENGTH = 2000;

  constructor(tenantId?: string | null) {
    super();
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
   * 将用户添加到指定分组
   * @param loginName 用户登录名
   * @param group 分组名称
   */
  private addUserToGroup(loginName: string, group: string): void {
    if (!this.groupMap.has(group)) {
      this.groupMap.set(group, new Set());
    }
    this.groupMap.get(group)!.add(loginName);

    // 更新用户信息中的 groups 字段
    const userInfo = this.userCache.get(loginName);
    if (userInfo) {
      if (!userInfo.groups) {
        userInfo.groups = [];
      }
      if (!userInfo.groups.includes(group)) {
        userInfo.groups.push(group);
      }
    }
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
   * @param group 分组名称，默认为 'default'
   * @returns 用户显示信息
   */
  async getUserDisplayInfo(tenantId: string, group: string = this.DEFAULT_GROUP): Promise<UserDisplayInfo | null> {
    // 非多租户环境，直接返回租户ID作为用户名
    if (!this.isMultiTenant()) {
      const userInfo: UserDisplayInfo = {
        login_name: tenantId,
        full_name: tenantId,
        display_name: tenantId,
        groups: [group],
      };
      this.addUserToGroup(tenantId, group);
      return userInfo;
    }

    // 检查缓存
    if (this.userCache.has(tenantId)) {
      const userInfo = this.userCache.get(tenantId)!;
      // 将用户添加到指定分组
      this.addUserToGroup(tenantId, group);
      return userInfo;
    }

    // 添加到请求队列
    this.requestQueue.add(tenantId);

    // 触发异步处理（低优先级）
    this.scheduleProcess();

    // 返回一个默认值，实际数据会在请求完成后更新缓存
    // 注意：这里先添加到分组，即使数据还没加载完成
    this.addUserToGroup(tenantId, group);
    return {
      login_name: tenantId,
      full_name: tenantId,
      display_name: tenantId,
      groups: [group],
    };
  }

  /**
   * 批量获取用户显示信息
   * @param tenantIds 租户ID数组
   * @param group 分组名称，默认为 'default'
   * @returns 用户显示信息Map
   */
  async batchGetUserDisplayInfo(tenantIds: string[], group: string = this.DEFAULT_GROUP): Promise<Map<string, UserDisplayInfo>> {
    const result = new Map<string, UserDisplayInfo>();

    // 非多租户环境，直接返回租户ID作为用户名
    if (!this.isMultiTenant()) {
      tenantIds.forEach((id) => {
        const userInfo: UserDisplayInfo = {
          login_name: id,
          full_name: id,
          display_name: id,
          groups: [group],
        };
        result.set(id, userInfo);
        this.addUserToGroup(id, group);
      });

      this.emit('userInfoUpdated', {
        tenantIds: tenantIds,
        userInfo: result,
      } as UserInfoLoadedEventData);
      return result;
    }

    // 过滤已缓存的租户ID
    const uncachedIds: string[] = [];
    tenantIds.forEach((id) => {
      if (this.userCache.has(id)) {
        const userInfo = this.userCache.get(id)!;
        result.set(id, userInfo);
        // 将用户添加到指定分组
        this.addUserToGroup(id, group);
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

    // 对于未缓存的ID，先返回默认值，并添加到分组
    uncachedIds.forEach((id) => {
      const userInfo: UserDisplayInfo = {
        login_name: id,
        full_name: id,
        display_name: id,
        groups: [group],
      };
      result.set(id, userInfo);
      // 注意：这里先添加到分组，即使数据还没加载完成
      this.addUserToGroup(id, group);
    });

    return result;
  }

  /**
   * 调度请求处理（低优先级，不阻塞渲染）
   * @returns Promise，当队列处理完成时 resolve
   */
  private scheduleProcess(): Promise<void> {
    // 如果已经有正在执行的 processQueue Promise，返回它
    if (this.processQueuePromise !== null) {
      return this.processQueuePromise;
    }

    // 创建 processQueue Promise
    this.processQueuePromise = new Promise<void>((resolve) => {
      // 使用 requestIdleCallback（如果支持）或 Promise.resolve().then 延迟执行
      const executeProcess = () => {
        this.processTimer = null;
        this.processQueue()
          .then(() => {
            this.processQueuePromise = null;
            resolve();
          })
          .catch((err) => {
            this.processQueuePromise = null;
            console.error('Error in processQueue:', err);
            resolve(); // 即使出错也 resolve，避免阻塞
          });
      };

      if (typeof requestIdleCallback !== 'undefined') {
        const idleCallbackId = requestIdleCallback(executeProcess, { timeout: 5000 });
        // requestIdleCallback 返回的是 number 类型的 ID
        this.processTimer = idleCallbackId as unknown as number;
      } else {
        // 使用 Promise.resolve().then 而不是 setTimeout，这样可以被等待
        Promise.resolve().then(() => {
          this.processTimer = null;
          executeProcess();
        });
      }
    });

    return this.processQueuePromise;
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

    // 创建请求 Promise 并添加到跟踪集合
    const requestPromise = this.executeBatchRequest(tenantIds);
    this.pendingPromises.add(requestPromise);

    try {
      await requestPromise;
    } finally {
      // 请求完成后从跟踪集合中移除
      this.pendingPromises.delete(requestPromise);
    }
  }

  /**
   * 执行批量请求
   * @param tenantIds 租户ID数组
   */
  private async executeBatchRequest(tenantIds: string[]): Promise<void> {
    // 构建URL并检查长度
    const queryParam = tenantIds.join(',');
    const url = `${this.API_BASE_URL}/-/display_info/?bk_usernames=${queryParam}`;

    // 如果URL长度超过限制，分批处理
    if (url.length > this.MAX_URL_LENGTH) {
      // 将当前批次进一步拆分
      const midPoint = Math.floor(tenantIds.length / 2);
      await Promise.all([
        this.executeBatchRequest(tenantIds.slice(0, midPoint)),
        this.executeBatchRequest(tenantIds.slice(midPoint)),
      ]);
      return;
    }

    const headers: Record<string, string> = {
      'x-bk-tenant-id': this.tenantId!,
    };

    try {
      const response = await requestJson<{ data: UserDisplayInfo[] }>({
        url,
        method: 'GET',
        headers,
      });

      // 处理响应结果
      // response.data 是 { data: UserDisplayInfo[] }，所以需要 response.data.data
      const loadedTenantIds: string[] = [];
      if (response.data?.data && Array.isArray(response.data.data)) {
        response.data.data.forEach((userInfo: UserDisplayInfo) => {
          if (userInfo.login_name) {
            const loginName = userInfo.login_name;
            const wasCached = this.userCache.has(loginName);
            const cachedUserInfo = this.userCache.get(loginName);
            
            // 如果用户已缓存，保留原有的 groups 信息
            if (cachedUserInfo && cachedUserInfo.groups) {
              userInfo.groups = cachedUserInfo.groups;
            }
            
            this.userCache.set(loginName, userInfo);
            
            // 如果用户有 groups 信息，确保用户存在于这些分组中
            if (userInfo.groups && Array.isArray(userInfo.groups)) {
              userInfo.groups.forEach((group) => {
                this.addUserToGroup(loginName, group);
              });
            }
            
            if (!wasCached) {
              loadedTenantIds.push(loginName);
            }
          }
        });

        // 触发用户信息加载事件
        if (loadedTenantIds.length > 0) {
          const loadedUserInfo = new Map<string, UserDisplayInfo>();
          loadedTenantIds.forEach((id) => {
            const info = this.userCache.get(id);
            if (info) {
              loadedUserInfo.set(id, info);
            }
          });

          this.emit('userInfoUpdated', {
            tenantIds: loadedTenantIds,
            userInfo: loadedUserInfo,
          } as UserInfoLoadedEventData);
        }
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
      const response = await requestJson<{ data: UserDisplayInfo }>({
        url,
        method: 'GET',
        headers,
      });

      // response.data 是 { data: UserDisplayInfo }，所以需要 response.data.data
      if (response.data?.data && response.data.data.login_name) {
        const userInfo = response.data.data;
        const loginName = userInfo.login_name;
        const wasCached = this.userCache.has(loginName);
        const cachedUserInfo = this.userCache.get(loginName);
        
        // 如果用户已缓存，保留原有的 groups 信息
        if (cachedUserInfo && cachedUserInfo.groups) {
          userInfo.groups = cachedUserInfo.groups;
        }
        
        this.userCache.set(loginName, userInfo);
        
        // 如果用户有 groups 信息，确保用户存在于这些分组中
        if (userInfo.groups && Array.isArray(userInfo.groups)) {
          userInfo.groups.forEach((group) => {
            this.addUserToGroup(loginName, group);
          });
        }

        // 如果是新加载的用户信息，触发事件
        if (!wasCached) {
          const loadedUserInfo = new Map<string, UserDisplayInfo>();
          loadedUserInfo.set(loginName, userInfo);

          this.emit('userInfoUpdated', {
            tenantIds: [loginName],
            userInfo: loadedUserInfo,
          } as UserInfoLoadedEventData);
        }
      }
    } catch (err) {
      console.error(`Failed to fetch user info for ${tenantId}:`, err);
      throw err;
    }
  }

  /**
   * 获取指定分组下的所有用户信息
   * @param group 分组名称，默认为 'default'
   * @returns 用户信息Map（login_name -> 用户信息）
   */
  getUsersByGroup(group: string = this.DEFAULT_GROUP): Map<string, UserDisplayInfo> {
    const result = new Map<string, UserDisplayInfo>();
    const loginNames = this.groupMap.get(group);
    
    if (loginNames) {
      loginNames.forEach((loginName) => {
        const userInfo = this.userCache.get(loginName);
        if (userInfo) {
          result.set(loginName, userInfo);
        }
      });
    }
    
    return result;
  }

  /**
   * 获取所有用户信息
   * 如果当前有执行中的请求，等待任务执行完再返回；如果没有则直接返回
   * @param group 可选的分组名称，如果指定则只返回该分组下的用户信息
   * @returns Promise，返回用户信息的Map（login_name -> 用户信息）
   */
  async getAllUserInfo(group?: string): Promise<Map<string, UserDisplayInfo>> {
    // 如果没有正在进行的请求，直接返回
    if (this.pendingPromises.size === 0 && this.requestQueue.size === 0 && this.pendingRequests.size === 0 && this.processQueuePromise === null) {
      // 如果指定了分组，返回该分组下的用户信息
      if (group) {
        return this.getUsersByGroup(group);
      }
      return this.userCache;
    }

    // 使用 Promise 链式等待，完全避免轮询
    // 循环等待直到所有请求都完成（包括在等待过程中新加入的请求）
    while (this.pendingPromises.size > 0 || this.requestQueue.size > 0 || this.pendingRequests.size > 0 || this.processQueuePromise !== null) {
      // 如果有待处理的队列且没有正在处理的，触发处理并获取 Promise
      let processPromise: Promise<void> | null = null;
      if (this.requestQueue.size > 0 && this.processQueuePromise === null) {
        processPromise = this.scheduleProcess();
      } else if (this.processQueuePromise !== null) {
        processPromise = this.processQueuePromise;
      }

      // 收集所有需要等待的 Promise
      const waitPromises: Promise<void>[] = [];

      // 等待 processQueue 完成
      if (processPromise !== null) {
        waitPromises.push(processPromise);
      }

      // 等待所有正在进行的请求 Promise
      if (this.pendingPromises.size > 0) {
        waitPromises.push(...Array.from(this.pendingPromises));
      }

      // 等待所有 Promise 完成（如果没有 Promise，说明状态不一致，直接退出循环）
      if (waitPromises.length > 0) {
        await Promise.all(waitPromises);
      } else {
        // 如果没有 Promise 但还有待处理的状态，说明可能是非多租户环境或状态异常，直接退出
        break;
      }
    }

    // 如果指定了分组，返回该分组下的用户信息
    if (group) {
      return this.getUsersByGroup(group);
    }
    
    // 返回所有用户信息
    return this.userCache;
  }

  /**
   * 清除缓存
   */
  clearCache() {
    this.userCache.clear();
    this.groupMap.clear();
  }

  /**
   * 获取缓存大小
   */
  getCacheSize(): number {
    return this.userCache.size;
  }
}

export const tenantManager = new TenantManager();
