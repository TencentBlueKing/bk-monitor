/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 *
 * Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
 *
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) is licensed under the MIT License.
 */

export type IndexSetTag = { tag_id: number; name: string; color: string };

export type TagFilterState = {
  tag_id: number | undefined;
  name: string | undefined;
  color: string | undefined;
};

export type ResolveTagSearchResult = {
  tagItem: TagFilterState;
  tagAppliedBySearch: boolean;
  /** 命中完整标签名时，列表过滤跳过关键字 */
  skipKeywordFilter: boolean;
  /** 需要滚入可视区的标签 id；未命中则为 undefined */
  scrollToTagId?: number;
};

const EMPTY_TAG: TagFilterState = {
  tag_id: undefined,
  name: undefined,
  color: '',
};

/** 标签名小写 → 标签，供 O(1) 完整匹配 */
export const buildTagNameMap = (tags: IndexSetTag[]): Map<string, IndexSetTag> => {
  const map = new Map<string, IndexSetTag>();
  for (const tag of tags) {
    map.set(String(tag.name ?? '').toLowerCase(), tag);
  }
  return map;
};

/**
 * 搜索关键字与标签完整匹配同步：
 * - 完整匹配：选中标签、跳过关键字过滤（不走标签点击 toggle）
 * - 未匹配且当前为搜索回填：清除标签，回退关键字过滤
 * - 清空关键字：保留已选标签，仅复位搜索回填标记
 */
export const resolveTagSearchSync = (params: {
  keyword: string;
  tagNameMap: Map<string, IndexSetTag>;
  tagItem: TagFilterState;
  tagAppliedBySearch: boolean;
}): ResolveTagSearchResult => {
  const keyword = params.keyword.trim();

  if (!keyword) {
    return {
      tagItem: { ...params.tagItem },
      tagAppliedBySearch: false,
      skipKeywordFilter: false,
    };
  }

  const matched = params.tagNameMap.get(keyword.toLowerCase());
  if (matched) {
    const sameTag = params.tagItem.tag_id === matched.tag_id;
    const tagItem = sameTag
      ? { ...params.tagItem }
      : { tag_id: matched.tag_id, name: matched.name, color: matched.color };
    return {
      tagItem,
      tagAppliedBySearch: true,
      skipKeywordFilter: true,
      scrollToTagId: matched.tag_id,
    };
  }

  if (params.tagAppliedBySearch) {
    return {
      tagItem: { ...EMPTY_TAG },
      tagAppliedBySearch: false,
      skipKeywordFilter: false,
    };
  }

  return {
    tagItem: { ...params.tagItem },
    tagAppliedBySearch: false,
    skipKeywordFilter: false,
  };
};
