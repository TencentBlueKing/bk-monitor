/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 *
 * Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
 *
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) is licensed under the MIT License.
 */

const getCookie = (name: string) => {
  if (typeof document === 'undefined') return '';
  const matched = document.cookie.match(new RegExp(`(?:^|; )${name}=([^;]*)`));
  return matched ? decodeURIComponent(matched[1]) : '';
};

export const buildOriginLogSearchHeaders = (state: Record<string, any>, options: { csrfToken?: string } = {}) => {
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    'X-Requested-With': 'XMLHttpRequest',
  };
  const csrfToken = options.csrfToken ?? getCookie('bklog_csrftoken');
  if (csrfToken) {
    headers['X-CSRFToken'] = csrfToken;
  }
  if (state.isExternal && state.spaceUid) {
    headers['X-Bk-Space-Uid'] = state.spaceUid;
  }
  if (state.indexItem?.timezone) {
    headers['X-BKLOG-TIMEZONE'] = state.indexItem.timezone;
  }
  return headers;
};
