/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 *
 * Copyright (C) 2017-2025 Tencent.  All rights reserved.
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
import { listSpaces } from 'monitor-api/modules/commons';
import { enhancedContext } from 'monitor-api/modules/model';
import { bkMessage } from 'monitor-api/utils/index';

import {
  getBizRouteHref,
  isAlarmCenterRouteHash,
  isShareRouteHash,
  mergeSpaceList,
  parseBizId,
  rememberRecentBizId,
  resolveEntryBizId,
  setGlobalBizId,
} from './index';
import { querySpaceDirectory } from './space-directory';
import { getUrlParam } from './utils';

import type { ISpaceItem } from '../typings';

type DirectoryUpdate = (spaces: ISpaceItem[]) => void;
type SpaceAccess = 'allowed' | 'denied' | 'error' | 'not_found';

export const assignWindowField = (data: Record<string, any>, isLowerCase = true) => {
  Object.assign(
    window,
    ...Object.entries(data).map(([key, value]) => ({ [isLowerCase ? key.toLowerCase() : key]: value }))
  );
};

export function applyBasicSpaceContext(data: Record<string, any>) {
  assignWindowField(data);
  mergeSpaceList(window.space_list);
  window.user_name = window.username = window.uin;
  window.cc_biz_id = parseBizId(window.bk_biz_id);
  window.bk_log_search_url = data.BKLOGSEARCH_HOST;
}

const targetBizId = (value: null | number | string | undefined) => {
  const id = parseBizId(value);
  return Number.isFinite(id) && id !== 0 && id !== -1 ? id : undefined;
};

export function getBasicSpaceContext(
  bizId = targetBizId(getUrlParam('bizId')),
  spaceUid = getUrlParam('space_uid'),
  options: { needMessage?: boolean } = {}
) {
  const preferred =
    !spaceUid && bizId == null ? (resolveEntryBizId(null) ?? targetBizId(process.env.defaultBizId)) : undefined;
  return enhancedContext(
    {
      context_type: 'basic',
      include_space_list: 0,
      space_uid: spaceUid || undefined,
      bk_biz_id: spaceUid ? undefined : bizId,
      preferred_biz_id: preferred,
    },
    { needBiz: false, ...options }
  );
}

const isPublicEntry = (hash: string) =>
  isShareRouteHash(hash) || isAlarmCenterRouteHash(hash) || Boolean(window.__BK_WEWEB_DATA__?.token);

let checkedBizId: number | undefined;
let checkedAccess: SpaceAccess;

/** 旧服务仍用完整目录选择业务。新服务已按请求目标判定准入。 */
export function initializeSpaceEntry(data: Record<string, any>) {
  const uid = getUrlParam('space_uid');
  const url = new URL(location.href);
  // 两个参数同时出现时以空间 UID 为准，避免路由守卫再次读取另一个业务。
  if (uid && url.searchParams.has('bizId')) {
    url.searchParams.delete('bizId');
    history.replaceState(history.state, '', url.href);
  }
  const deferred = data.SPACE_LIST_STATE === 'deferred';
  const missingLegacyUid = !deferred && uid && !window.space_list.some(s => s.space_uid === uid);
  if (!deferred && !missingLegacyUid) {
    // 旧服务忽略 preferred_biz_id。交给旧入口选择并跳转，落地页按显式业务重新获取 basic。
    const buildDefault = targetBizId(process.env.defaultBizId);
    return setGlobalBizId(window.space_list.some(s => s.bk_biz_id === buildDefault) ? buildDefault : undefined);
  }
  const access: SpaceAccess = missingLegacyUid ? 'denied' : data.SPACE_ACCESS;
  const requested = uid ? undefined : targetBizId(getUrlParam('bizId'));
  const id = missingLegacyUid ? undefined : (targetBizId(data.BK_BIZ_ID) ?? requested);
  checkedBizId = id;
  checkedAccess = access;
  if (deferred) {
    window.loadSpaceDirectory = loadSpaceDirectory;
    if (data.SPACE_LIST_PAGE_SUPPORTED === true) window.querySpaceDirectory = querySpaceDirectory;
  }
  if (access !== 'allowed' && !isPublicEntry(url.hash)) {
    if (access === 'error' || (access === 'not_found' && (requested != null || uid))) {
      showEntryProblem(access === 'error' ? '空间权限检查失败，请重试' : '空间不存在');
      return false;
    }
    if (['trace', 'apm'].includes(window.source_app)) {
      showEntryProblem('无业务或没有权限');
      return false;
    }
    url.hash = '/no-business';
  } else if (access === 'allowed') {
    if (!uid && !requested) url.searchParams.set('bizId', String(id));
    if (url.hash === '#/no-business') url.hash = '/';
    rememberRecentBizId(id, data.SPACE_LIST[0]?.is_demo);
  }
  if (url.href !== location.href) history.replaceState(history.state, '', url.href);
  window.cc_biz_id = window.bk_biz_id = id ?? (isAlarmCenterRouteHash(url.hash) ? 0 : -1);
  return window.cc_biz_id;
}

export function isAidevPermissionPending(data: Record<string, any>) {
  const uid = getUrlParam('space_uid');
  const id = targetBizId(getUrlParam('bizId'));
  if ((!uid && id == null) || isPublicEntry(location.hash)) return false;
  if (data.SPACE_LIST_STATE === 'deferred') return data.SPACE_ACCESS === 'denied';
  return !data.SPACE_LIST.some(item => (uid ? item.space_uid === uid : +item.bk_biz_id === id));
}

let directoryRequest: Promise<ISpaceItem[]> | undefined;
let updateKnownSpaces: DirectoryUpdate | undefined;

/** 独立应用挂载后加载目录。微前端共享宿主发起的在途请求。 */
export function hydrateSpaceDirectory(update: DirectoryUpdate, host = window) {
  if (host?.space_list_page_supported === true) {
    updateKnownSpaces = update;
    return;
  }
  if (!host?.loadSpaceDirectory) return;
  void host
    .loadSpaceDirectory()
    .then(spaces => {
      window.space_list = spaces;
      window.space_list_state = 'full';
      update(spaces);
    })
    .catch(() => {
      bkMessage({ theme: 'error', message: window.i18n.t('空间目录加载失败，请刷新页面重试') });
    });
}

let switchRequest = 0;

export async function canSwitchSpace(id: number, isCurrent = () => true): Promise<boolean> {
  const access = await getSpaceSwitchAccess(id, location.hash, isCurrent);
  if (!isCurrent()) return false;
  if (access === 'error') showSpaceAccessError();
  if (access === 'denied' || access === 'not_found') location.href = getBizRouteHref('/no-business', id);
  return access === 'allowed';
}

/** 仅保存已核验的当前业务；切到另一业务时重新请求同一 basic。 */
export async function getSpaceSwitchAccess(
  id: number,
  hash = location.hash,
  isCurrent = () => true
): Promise<'stale' | SpaceAccess> {
  const request = ++switchRequest;
  if (window.space_access == null || targetBizId(id) == null) return 'allowed';
  if (id !== checkedBizId || checkedAccess !== 'allowed') {
    const data = await getBasicSpaceContext(id, '', { needMessage: false }).catch(() => null);
    if (request !== switchRequest || !isCurrent()) return 'stale';
    const access = !data
      ? 'error'
      : (data.SPACE_ACCESS ?? (data.SPACE_LIST.some(s => +s.bk_biz_id === id) ? 'allowed' : 'denied'));
    if (access === 'error') {
      return isPublicEntry(hash) ? 'allowed' : 'error';
    }
    if (access === 'allowed' && updateKnownSpaces) {
      const row = data.SPACE_LIST.find((space: ISpaceItem) => space.bk_biz_id === id);
      const known = window.space_list || [];
      if (row && !known.some(space => space.bk_biz_id === id)) {
        updateKnownSpaces(mergeSpaceList([...known, row]));
      }
    }
    checkedBizId = id;
    checkedAccess = access;
  }
  return isPublicEntry(hash) ? 'allowed' : checkedAccess;
}

export function showSpaceAccessError() {
  bkMessage({ theme: 'error', message: window.i18n.t('空间权限检查失败，请重试') });
}

function loadSpaceDirectory(): Promise<ISpaceItem[]> {
  if (window.space_list_state !== 'deferred') return Promise.resolve(window.space_list);
  directoryRequest ??= listSpaces({ show_all: false, show_detail: false }, { needBiz: false })
    .then(spaces => {
      const list = mergeSpaceList(spaces);
      window.space_list_state = 'full';
      return list;
    })
    .finally(() => {
      directoryRequest = undefined;
    });
  return directoryRequest;
}

function showEntryProblem(message: string) {
  const root = document.getElementById('app');
  const label = document.createElement('p');
  label.setAttribute('role', 'alert');
  label.textContent = String(window.i18n.t(message));
  const retry = document.createElement('button');
  retry.textContent = String(window.i18n.t('刷新页面'));
  retry.onclick = () => location.reload();
  root.replaceChildren(label, retry);
}
