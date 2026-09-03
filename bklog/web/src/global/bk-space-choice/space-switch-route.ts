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

/** 场景化检索默认场景（容器） */
export const DEFAULT_SCENE_ACTIVE = 'k8s';

/** 检索页切业务时允许跨业务保留的 query */
export const RETRIEVE_SPACE_SWITCH_KEEP_QUERY = [
  'start_time',
  'end_time',
  'format',
  'interval',
  'search_mode',
  'timezone',
  'from',
];

export const omitRouteIndexId = <T extends Record<string, unknown>>(params: T): Omit<T, 'indexId'> => {
  const next = { ...params };
  delete next.indexId;
  return next;
};

export const shouldKeepSceneOnSpaceChange = (retrieveType?: unknown, queryRetrieveType?: unknown): boolean =>
  retrieveType === 'scene' || queryRetrieveType === 'scene';

export const isSceneRetrieveSwitch = (options: {
  routeName?: string | null;
  queryRetrieveType?: unknown;
  storeRetrieveType?: unknown;
}): boolean =>
  options.routeName === 'retrieve' &&
  shouldKeepSceneOnSpaceChange(options.storeRetrieveType, options.queryRetrieveType);

export const buildSpaceSwitchQuery = (options: {
  routeName?: string | null;
  query?: Record<string, unknown>;
  storeRetrieveType?: unknown;
  space: { bk_biz_id: unknown; space_uid: string };
}): Record<string, unknown> => {
  const query = options.query ?? {};
  if (
    !isSceneRetrieveSwitch({
      routeName: options.routeName,
      queryRetrieveType: query.retrieve_type,
      storeRetrieveType: options.storeRetrieveType,
    })
  ) {
    return {
      ...query,
      bizId: options.space.bk_biz_id,
      spaceUid: options.space.space_uid,
    };
  }

  const nextQuery: Record<string, unknown> = {
    bizId: options.space.bk_biz_id,
    spaceUid: options.space.space_uid,
    retrieve_type: 'scene',
    scene_active: DEFAULT_SCENE_ACTIVE,
  };
  for (const key of RETRIEVE_SPACE_SWITCH_KEEP_QUERY) {
    if (query[key] !== undefined && query[key] !== '') {
      nextQuery[key] = query[key];
    }
  }
  return nextQuery;
};
