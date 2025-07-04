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
import UserDisplayName, { type ConfigOptions } from '@blueking/bk-user-display-name';

/** 判断 item 是否为用户组 */
export const USER_GROUP_TYPE = new Set(['userGroup', 'group']);

export const getUserComponentConfig = (): ConfigOptions => {
  if (window.enable_multi_tenant_mode) {
    return {
      tenantId: window.bk_tenant_id,
      apiBaseUrl: process.env.NODE_ENV === 'development' ? '/api/bk-user-web/prod' : window.bk_user_web_api_url,
      cacheDuration: 1000 * 60 * 60 * 24, // 缓存24小时
      emptyText: '--',
    };
  }
  return {
    tenantId: '',
    apiBaseUrl: `${window.site_url}rest/v2/commons/user/list_users/`,
    cacheDuration: 1000 * 60 * 60 * 24, // 缓存24小时
    emptyText: '--',
  };
};
export const userDisplayNameConfigure = () => {
  UserDisplayName.configure(getUserComponentConfig());
};

let BkUserDisplayNameInstance: Readonly<UserDisplayName>;

export const getBkUserDisplayNameInstance = () => {
  if (!BkUserDisplayNameInstance) {
    // 跨 shadow dom 直接运行会报错
    if (window.__POWERED_BY_BK_WEWEB__) {
      const cls = customElements.get('bk-user-display-name') as any;
      BkUserDisplayNameInstance = Object.freeze(new cls());
    } else {
      BkUserDisplayNameInstance = Object.freeze(new UserDisplayName());
    }
  }
  return BkUserDisplayNameInstance;
};

export const getUserCache = () => UserDisplayName.userCache;

export default UserDisplayName;
