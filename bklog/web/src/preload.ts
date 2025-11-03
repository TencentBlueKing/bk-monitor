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
import { SET_APP_STATE } from './store';
import { URL_ARGS } from './store/default-values';
import { BK_LOG_STORAGE } from './store/store.type';
window.__VUE_PROD_HYDRATION_MISMATCH_DETAILS__ = false;
import BkUserDisplayName from '@blueking/bk-user-display-name';

/** 外部版根据空间授权权限显示菜单 */
export const getExternalMenuListBySpace = space => {
  const list: string[] = [];
  for (const permission of space.external_permission || []) {
    if (permission === 'log_search') {
      list.push('retrieve');
    } else if (permission === 'log_extract') {
      list.push('manage');
    }
  }
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
      store.commit(SET_APP_STATE, { spaceListLoaded: true });
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
    if (URL_ARGS.index_id && !URL_ARGS.spaceUid) {
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
   * 获取空间UID
   * @returns space_uid
   */
  const getSpaceUid = () => {
    if (URL_ARGS.spaceUid) {
      return URL_ARGS.spaceUid;
    }

    return store.state.storage[BK_LOG_STORAGE.BK_SPACE_UID];
  };

  /**
   * 空间列表请求参数
   */
  const getSpaceRequestData = () => {
    const SPACE_UID = getSpaceUid();
    return {
      query: {
        space_uid: SPACE_UID,
        has_permission: SPACE_UID ? undefined : 1,
        page: 1,
        page_size: 1,
      },
    };
  };

  /**
   * 获取默认空间列表
   * 优先获取当前地址栏中的SpaceId信息，如果地址栏中没有SpaceId则在缓存中获取用户最后选择的SpaceId
   * 根据返回数据判定，如果返回数据为空，则重新请求当前用户有权限的第一个Space信息
   * @returns
   */
  const getDefaultSpaceList = () => {
    const requestSpaceList = params => http.request('space/getMySpaceList', params);
    const spaceRequestData = getSpaceRequestData();
    return requestSpaceList(spaceRequestData).then(resp => {
      const spaceList = resp.data;
      if (spaceList.length) {
        return Promise.resolve(resp);
      }

      if (spaceRequestData.query.space_uid) {
        spaceRequestData.query.space_uid = undefined;
        spaceRequestData.query.has_permission = 1;
        return requestSpaceList(spaceRequestData);
      }

      return Promise.resolve(resp);
    });
  };

  /**
   * 获取空间列表
   * return
   */
  const spaceRequest = getSpaceByIndexId().then(() => {
    return getDefaultSpaceList().then(resp => {
      const spaceList = resp.data;
      for (const item of spaceList) {
        item.bk_biz_id = `${item.bk_biz_id}`;
        item.space_uid = `${item.space_uid}`;
        item.space_full_code_name = `${item.space_name}(#${item.space_id})`;
      }

      store.commit('updateMySpaceList', spaceList);
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
    store.commit('updateState', { userMeta: resp.data });
    BkUserDisplayName.configure({
      // 必填，租户 ID
      tenantId: resp.data.bk_tenant_id,
      // 必填，网关地址
      apiBaseUrl: process.env.NODE_ENV === 'development' ? '' : window.BK_LOGIN_URL,
      // 可选，缓存时间，单位为毫秒, 默认 5 分钟, 只对单一值生效
      cacheDuration: 1000 * 60 * 5,
      // 可选，当输入为空时，显示的文本，默认为 '--'
      emptyText: '--',
    });

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
    store.commit('updateState', { userGuideData: res.data });
    return res.data;
  });

  return Promise.allSettled([spaceRequest, userInfoRequest, globalsRequest, getUserGuideRequest]);
};
