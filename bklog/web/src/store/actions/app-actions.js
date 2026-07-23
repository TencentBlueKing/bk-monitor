/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 */
import http from '@/api';
import { storeCacheService } from '@/storage';

import { formatTimeZoneString } from '@/global/utils/time';
import { isSceneRetrieve } from '../helper.ts';
import { mergeMenuWithDefaultConfig } from '../menu-config.ts';

const cacheApi = (name, scope, data, meta = {}) => {
  storeCacheService.setApiCache(name, scope || 'default', data, meta).catch((error) => {
    console.warn('[store-cache] cache api failed', name, error);
  });
};

export function userInfoAction({ commit }, params, config = {}) {
  return http.request('userInfo/getUserInfo', { query: params, config }).then((response) => {
    const userData = response.data || {};
    commit('updateState', { user: userData });
    cacheApi('userInfo/getUserInfo', 'current', userData);
    return userData;
  });
}

export function getMenuListAction(_, spaceUid) {
  return http.request('meta/menu', {
    query: {
      space_uid: spaceUid,
    },
  }).then((res) => {
    cacheApi('meta/menu/raw', spaceUid || 'default', res.data || []);
    return res;
  });
}

export function requestMenuListAction({ commit }, spaceUid) {
  if (!spaceUid) {
    return Promise.resolve([]);
  }

  const routeMap = {
    search: 'retrieve',
    manage_access: 'manage',
    manage_index_set: 'indexSet',
    manage_data_link: 'linkConfiguration',
    manage_user_group: 'permissionGroup',
    manage_migrate: 'migrate',
    manage_extract: 'manageExtract',
  };

  const replaceMenuId = (list) => {
    list.forEach((item) => {
      if (item.id === 'search') {
        item.id = 'retrieve';
      }
      item.id = item.id.replace(/_/g, '-');
      if (item.children) {
        replaceMenuId(item.children);
      }
    });
    return list;
  };

  const deepUpdateMenu = (oldMenu, resMenu) => {
    resMenu.name = oldMenu.name;
    resMenu.dropDown = oldMenu.dropDown;
    resMenu.dropDown = oldMenu.dropDown;
    resMenu.level = oldMenu.level;
    resMenu.isDashboard = oldMenu.isDashboard;
    if (resMenu.children) {
      if (oldMenu.children) {
        resMenu.children.forEach((item) => {
          item.id = routeMap[item.id] || item.id;
          const menu = oldMenu.children.find(menuItem => menuItem.id === item.id);
          if (menu) {
            deepUpdateMenu(menu, item);
          }
        });
      }
    } else if (oldMenu.children) {
      resMenu.children = oldMenu.children;
    }
  };

  return http
    .request('meta/menu', {
      query: {
        space_uid: spaceUid,
      },
    })
    .then((res) => {
      const rawMenu = res.data || [];
      const menuList = replaceMenuId(rawMenu);

      mergeMenuWithDefaultConfig(menuList, routeMap, deepUpdateMenu);

      commit('updateState', { topMenu: menuList });
      commit('updateState', { menuProject: rawMenu });
      cacheApi('meta/menu', spaceUid, { topMenu: menuList, menuProject: rawMenu });

      return menuList;
    });
}

export function getGlobalsDataAction({ commit }) {
  return http.request('collect/globals', { query: {} }).then((response) => {
    const globalsData = response.data || {};
    commit('updateGlobalsData', globalsData);
    cacheApi('collect/globals', 'default', globalsData);
    return globalsData;
  });
}

export function checkAllowedAction(context, paramData) {
  return http
    .request('auth/checkAllowed', {
      data: paramData,
    })
    .then((checkRes) => {
      cacheApi('auth/checkAllowed', JSON.stringify(paramData || {}), checkRes.data || []);
      for (const item of checkRes.data) {
        if (item.is_allowed === false) {
          return {
            isAllowed: false,
          };
        }
      }
      return {
        isAllowed: true,
      };
    })
    .catch(err => Promise.reject(err));
}

export function getApplyDataAction(context, paramData) {
  return http.request('auth/getApplyData', {
    data: paramData,
  }).then((res) => {
    cacheApi('auth/getApplyData', JSON.stringify(paramData || {}), res.data || {});
    return res;
  });
}

export function checkAndGetDataAction(context, paramData) {
  return http
    .request('auth/checkAllowed', {
      data: paramData,
    })
    .then((checkRes) => {
      cacheApi('auth/checkAllowed', JSON.stringify(paramData || {}), checkRes.data || []);
      for (const item of checkRes.data) {
        if (item.is_allowed === false) {
          return http
            .request('auth/getApplyData', {
              data: paramData,
            })
            .then((applyDataRes) => {
              cacheApi('auth/getApplyData', JSON.stringify(paramData || {}), applyDataRes.data || {});
              return {
                isAllowed: false,
                data: applyDataRes.data,
              };
            });
        }
      }
      return {
        isAllowed: true,
      };
    })
    .catch(err => Promise.reject(err));
}

export function requestFavoriteListAction({ commit, state }, payload) {
  commit('updateFavoriteList', []);
  const favoriteSortType = payload?.sort ?? (localStorage.getItem('favoriteSortType') || 'NAME_ASC');
  storeCacheService.setLocalStorageMirror('favoriteSortType', favoriteSortType).catch(() => {});
  return http
    .request('favorite/getFavoriteByGroupList', {
      query: {
        space_uid: payload?.spaceUid ?? state.spaceUid,
        order_type: favoriteSortType,
        source_type: isSceneRetrieve(state) ? 'scene' : 'index_set',
      },
    })
    .then((resp) => {
      const results = (resp.data || []).map((item) => {
        item.favorites?.forEach((sub) => {
          sub.full_name = `${item.group_name}/${sub.name}`;
          sub.created_at = formatTimeZoneString(sub.created_at, state.userMeta.time_zone);
          sub.updated_at = formatTimeZoneString(sub.updated_at, state.userMeta.time_zone);
        });
        return item;
      });
      commit('updateFavoriteList', results);
      cacheApi('favorite/getFavoriteByGroupList', `${payload?.spaceUid ?? state.spaceUid}:${payload?.sort ?? 'NAME_ASC'}`, results);
      return resp;
    });
}
