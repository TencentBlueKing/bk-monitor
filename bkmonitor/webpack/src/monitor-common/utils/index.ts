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

import { ISpaceItem } from '../typings';

import { LOCAL_BIZ_STORE_KEY } from './constant';
import { getUrlParam } from './utils';

// merge space list width biz list
export function mergeSpaceList(spaceList: ISpaceItem[]) {
  spaceList.sort((a, b) => {
    if (a.bk_biz_id > 0 && b.bk_biz_id > 0) return a.bk_biz_id - b.bk_biz_id;
    return b.bk_biz_id - a.bk_biz_id;
  });
  const list = (spaceList || []).map(item => ({
    ...item,
    id: item.bk_biz_id,
    text: item.space_name,
    name: item.space_name
  }));
  window.space_list = list;
  return list;
}
// 设置全局业务ID
export const setGlobalBizId = () => {
  let bizId = +getUrlParam('bizId')?.replace(/\//gim, '');
  const hasRouteHash = getUrlParam('routeHash');
  const isEmailSubscriptions = location.hash.indexOf('email-subscriptions') > -1;
  const isSpicialEvent = !!getUrlParam('specEvent');
  const isNoBusiness = location.hash.indexOf('no-business') > -1;
  const localBizId = localStorage.getItem(LOCAL_BIZ_STORE_KEY);
  const bizList = window.space_list || [];
  const authList = bizList.filter(item => !item.is_demo);
  const hasAuth = id => authList.some(item => +id === +item.bk_biz_id);
  const isInSpaceList = id => bizList.some(item => +id === +item.bk_biz_id);
  const isDemo = id => bizList.some(item => +item.bk_biz_id === +id && item.is_demo);
  const spaceUid = getUrlParam('space_uid');
  const spaceItem = spaceUid ? bizList.find(item => item.space_uid === spaceUid) : undefined;
  const isCanAllIn =
    ['#/', '#/event-center'].includes(location.hash.replace(/\?.*/, '')) ||
    /^#\/(event-center\/detail|share)\//.test(location.hash) ||
    !!window.__BK_WEWEB_DATA__?.token;
  const hasBizId = () => !(!bizId || bizId === -1);
  const setBizId = (id: string | number) => {
    window.cc_biz_id = +id;
    window.bk_biz_id = +id;
    !isDemo(id) && localStorage.setItem(LOCAL_BIZ_STORE_KEY, id.toString());
  };
  const setLocationSearch = (bizId: string | number) => {
    if (location.search) {
      location.search = location.search.replace(/(space_uid|bizId)=([^#&/]+)/gim, `bizId=${bizId}`);
    } else {
      location.href = `${location.origin}${location.pathname}?bizId=${bizId}${location.hash}`;
    }
    return false;
  };
  if (bizId !== window.bk_biz_id && !isInSpaceList(bizId) && hasAuth(window.bk_biz_id)) {
    if (hasAuth(localBizId)) {
      window.bk_biz_id = +localBizId;
      window.cc_biz_id = +localBizId;
    }
    const url = new URL(window.location.href);
    const { searchParams } = url;
    searchParams.set('bizId', window.bk_biz_id.toString());
    url.search = searchParams.toString();
    url.hash = '#/';
    history.replaceState({}, '', url.toString());
    bizId = window.bk_biz_id;
  }
  if (!isCanAllIn && !bizList?.length && !isNoBusiness) {
    location.href = `${location.origin}${location.pathname}#/no-business`;
    return true;
  }
  if (!hasBizId()) {
    if (isNoBusiness && !bizList.length) {
      return true;
    }
    const newBizId = spaceItem?.bk_biz_id || window.cc_biz_id;
    // search with space_uid
    if (spaceUid) {
      window.space_uid = spaceUid;
      return setLocationSearch(newBizId);
    }
    if (bizList.length && !bizList.some(item => +item.bk_biz_id === +newBizId)) {
      return setLocationSearch(bizList[0].bk_biz_id);
    }
    if (newBizId && newBizId !== -1) {
      return setLocationSearch(newBizId);
    }
    if (!bizList.length) {
      location.href = `${location.origin}${location.pathname}?${`bizId=${newBizId}`}#/no-business`;
      return ['#/no-business'].includes(location.hash.replace(/\?.*/, '')) ? newBizId : false;
    }

    bizId = newBizId;
  }
  if (!isSpicialEvent && !hasRouteHash && !isEmailSubscriptions) {
    const isDemoBizId = isDemo(bizId);
    if (!isDemoBizId && (!bizId || !hasAuth(bizId))) {
      if (!hasBizId() && localBizId && bizList.length && hasAuth(localBizId)) {
        bizId = +localBizId;
        location.href = `${location.origin}${location.pathname}?bizId=${localBizId}#/`;
        setBizId(bizId);
        return false;
      }
      if (!authList?.length) {
        if (!bizId && bizList.length) {
          bizId = bizList[0].bk_biz_id;
          location.href = `${location.origin}${location.pathname}?bizId=${bizId}#/`;
          setBizId(bizId);
          return;
        }
        if (!bizId) bizId = -1;
        // 事件中心 首页 临时分享允许所有链接进入
        if (!isCanAllIn) {
          location.href = `${location.origin}${location.pathname}?${`bizId=${bizId}`}#/no-business`;
          if (bizId !== -1) setBizId(bizId);
          return ['#/no-business'].includes(location.hash.replace(/\?.*/, '')) ? bizId : false;
        }
      } else if (!bizId) {
        bizId = +bizList[0].bk_biz_id;
        location.href = `${location.origin}${location.pathname}?bizId=${bizId}#/`;
        return false;
      } else if (!hasAuth(bizId)) {
        setBizId(bizId);
      } else {
        const isDemoBizId = bizList.some(item => +item.bk_biz_id === +bizId && item.is_demo);
        if (!isDemoBizId) {
          location.href = `${location.origin}${location.pathname}?bizId=${bizId}#/no-business`;
          return false;
        }
        if (isNoBusiness) {
          location.href = `${location.origin}${location.pathname}?bizId=${bizId}#/`;
          return false;
        }
      }
    } else if (isNoBusiness) {
      location.href = `${location.origin}${location.pathname}?bizId=${bizId}#/`;
      return false;
    }
  } else if (!bizId) {
    bizId = 0;
  }
  setBizId(bizId);
  return bizId;
};

/**
 * 淡化或加深指定颜色。
 * @param color - 要修改的颜色，格式为 "#RRGGBB" 或 "RRGGBB"。
 * @param amt - 要加深（正数）或淡化（负数）颜色的量。有效范围：-255 到 255。
 * @returns 与输入颜色相同格式的修改后的颜色，为 "#RRGGBB" 或 "RRGGBB"。
 */
export const lightenDarkenColor = (color: string, amt: number): string => {
  // 从颜色字符串中删除 '#' 并将其转换为数字
  const num = parseInt(color.replace(/^#/, ''), 16);

  // 辅助函数，确保颜色值保持在有效范围（0 到 255）内
  const clamp = (value: number): number => Math.max(0, Math.min(255, value));

  // 计算并限制新的红色、绿色和蓝色颜色值
  const r = clamp((num >> 16) + amt);
  const g = clamp(((num >> 8) & 0x00ff) + amt);
  const b = clamp((num & 0x0000ff) + amt);

  // 返回修改后的颜色，格式与输入颜色相同（"#" 开头或不带 "#"）
  return (color.startsWith('#') ? '#' : '') + ((r << 16) | (g << 8) | b).toString(16).padStart(6, '0');
};
export * from './constant';
export * from './docs-link';
export * from './utils';
export * from './xss';
