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

import { VIEW_BUSINESS } from './common/authority-map';
import { BK_LOG_STORAGE } from './store/store.type';

/** 外部版根据空间授权权限显示菜单 */
export const getExternalMenuListBySpace = space => {
  const list = [];
  (space.external_permission || []).forEach(permission => {
    if (permission === 'log_search') {
      list.push('retrieve');
    } else if (permission === 'log_extract') {
      list.push('manage');
    }
  });
  return list;
};

export default ({
  http,
  store,
}: {
  http: { request: (...args) => Promise<any> };
  store: any;
  isExternal?: boolean;
}) => {
  /**
   * 获取空间列表
   * return
   */
  const spaceRequest = http.request('space/getMySpaceList').then(resp => {
    const spaceList = resp.data;
    spaceList.forEach(item => {
      item.bk_biz_id = `${item.bk_biz_id}`;
      item.space_uid = `${item.space_uid}`;
      item.space_full_code_name = `${item.space_name}(#${item.space_id})`;
    });

    store.commit('updateMySpaceList', spaceList);

    const space_uid = store.state.storage[BK_LOG_STORAGE.BK_SPACE_UID];
    const bkBizId = store.state.storage[BK_LOG_STORAGE.BK_BIZ_ID];
    let space = null;

    if (space_uid) {
      space = (spaceList ?? []).find(item => item.space_uid === space_uid);
    }

    if (!space && bkBizId) {
      space = (spaceList ?? []).find(item => item.bk_biz_id === bkBizId);
    }

    if (!space?.permission?.[VIEW_BUSINESS]) {
      space = spaceList?.find(item => item?.permission?.[VIEW_BUSINESS]) ?? spaceList?.[0];
    }

    store.commit('updateSpace', space?.space_uid);

    if (space && (space_uid !== space.space_uid || bkBizId !== space.bk_biz_id)) {
      store.commit('updateStorage', {
        [BK_LOG_STORAGE.BK_BIZ_ID]: space.bk_biz_id,
        [BK_LOG_STORAGE.BK_SPACE_UID]: space.space_uid,
      });
    }

    return space;
  });

  const userInfoRequest = http.request('userInfo/getUsername').then(resp => {
    store.commit('updateUserMeta', resp.data);
    return resp.data;
  });

  const globalsRequest = http.request('collect/globals').then(res => {
    store.commit('globals/setGlobalsData', res.data);
    return res.data;
  });

  return Promise.all([spaceRequest, userInfoRequest, globalsRequest]);
};
