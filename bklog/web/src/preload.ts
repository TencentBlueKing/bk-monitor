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
import './polyfill';
import { URL_ARGS } from './store/default-values';
import { BK_LOG_STORAGE } from './store/store.type';

/** 外部版根据空间授权权限显示菜单 */
export const getExternalMenuListBySpace = space => {
  const list: string[] = [];
  (space.external_permission || []).forEach(permission => {
    if (permission === 'log_search') {
      list.push('retrieve');
    } else if (permission === 'log_extract') {
      list.push('manage');
    }
  });
  return list;
};

/**
 * 获取所有空间列表
 * @param http
 * @param store
 * @returns
 */
export const getAllSpaceList = (http, store) => {
  window.scheduler.postTask(() => {
    http.request('space/getMySpaceList').then(resp => {
      const spaceList = resp.data;
      spaceList.forEach(item => {
        item.bk_biz_id = `${item.bk_biz_id}`;
        item.space_uid = `${item.space_uid}`;
        item.space_full_code_name = `${item.space_name}(#${item.space_id})`;
      });

      store.commit('updateMySpaceList', spaceList);
    });
  });
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
   * 根据索引ID获取空间信息
   * 如果当前URL参数中没有spaceUid和bizId，则根据index_id获取空间信息
   * 如果当前URL参数中没有index_id，则跳过
   * @returns
   */
  const getSpaceByIndexId = () => {
    if (URL_ARGS.index_id && !URL_ARGS.spaceUid && !URL_ARGS.bizId) {
      return http
        .request('indexSet/getSpaceByIndexId', {
          params: {
            index_set_id: URL_ARGS.index_id,
          },
        })
        .then(resp => {
          if (resp.result) {
            store.commit('updateSpace', resp.data);
            store.commit('updateStorage', {
              [BK_LOG_STORAGE.BK_BIZ_ID]: resp.data.bk_biz_id,
              [BK_LOG_STORAGE.BK_SPACE_UID]: resp.data.space_uid,
            });
          }
        });
    }
    return Promise.resolve(true);
  };

  /**
   * 空间列表请求参数
   */
  const spaceRequestData = {
    query: {
      space_uid: URL_ARGS.spaceUid,
      has_permission: URL_ARGS.spaceUid ? undefined : 1,
      page: 1,
      page_size: 1,
    },
  };

  /**
   * 获取空间列表
   * return
   */
  const spaceRequest = http.request('space/getMySpaceList', spaceRequestData).then(resp => {
    const spaceList = resp.data;
    spaceList.forEach(item => {
      item.bk_biz_id = `${item.bk_biz_id}`;
      item.space_uid = `${item.space_uid}`;
      item.space_full_code_name = `${item.space_name}(#${item.space_id})`;
    });

    store.commit('updateMySpaceList', spaceList);

    return getSpaceByIndexId().then(() => {
      const space_uid = store.state.storage[BK_LOG_STORAGE.BK_SPACE_UID];
      const bkBizId = store.state.storage[BK_LOG_STORAGE.BK_BIZ_ID];
      let space: { [key: string]: any } | null = null;

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
  });

  /**
   * 获取用户信息
   */
  const userInfoRequest = http.request('userInfo/getUsername').then(resp => {
    store.commit('updateUserMeta', resp.data);
    return resp.data;
  });

  /**
   * 获取全局配置
   */
  const globalsRequest = http.request('collect/globals').then(res => {
    store.commit('globals/setGlobalsData', res.data);
    return res.data;
  });

  /**
   * 获取用户引导数据
   */
  const getUserGuideRequest = http.request('meta/getUserGuide').then(res => {
    store.commit('setUserGuideData', res.data);
    return res.data;
  });

  return Promise.allSettled([spaceRequest, userInfoRequest, globalsRequest, getUserGuideRequest]);
};
