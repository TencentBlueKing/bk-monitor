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
import { monitorLink } from '../../retrieve-v2/monitor/utils';
export function getConditionRouterParams(searchList, searchMode, isNewLink, append = {}) {
  const indexItem = window.mainComponent.$store.state.indexItem;
  const getIPChooserStr = ipChooser => {
    if (typeof ipChooser === 'object') return JSON.stringify(ipChooser);
    return ipChooser;
  };
  // 获取有效的字段条件字符串
  const getFiledAdditionStr = (linkAdditionList = null) => {
    const filterAddition = indexItem.addition.filter(item => item.field !== '_ip-select_');
    if (!filterAddition.length && !linkAdditionList) return undefined;
    return JSON.stringify(linkAdditionList?.length ? filterAddition.concat(...linkAdditionList) : filterAddition);
  };
  const { params, query } = window.mainComponent.$route;
  // eslint-disable-next-line @typescript-eslint/naming-convention
  const { ip_chooser, addition, keyword, ...reset } = query;
  const filterQuery = reset; // 给query排序 让addition和ip_chooser排前面
  let newAddition;
  let newKeyWord;
  if (searchMode === 'ui') {
    newAddition = isNewLink ? JSON.stringify(searchList) : getFiledAdditionStr(searchList);
    newKeyWord = undefined;
  } else {
    newAddition = undefined;
    if (isNewLink) {
      newKeyWord = searchList.join(' AND ');
    } else {
      const keyword = indexItem.keyword.replace(/^\s*\*\s*$/, '');
      const keywords = keyword.length > 0 ? [keyword] : [];
      const newSearchKeywords = searchList.filter(item => keyword.indexOf(item) === -1);
      newKeyWord = keywords.concat(newSearchKeywords).join(' AND ');
    }
  }
  const newQueryObj = {
    keyword: newKeyWord,
    addition: newAddition,
    search_mode: searchMode,
  }; // 新的query对象
  const newIPChooser = ip_chooser;

  if (newIPChooser && Object.keys(newIPChooser).length && !isNewLink) {
    // ip值更新
    Object.assign(newQueryObj, {
      ip_chooser: getIPChooserStr(newIPChooser),
    });
  }

  Object.assign(filterQuery, newQueryObj, append ?? {});
  const routeData = {
    name: 'retrieve',
    params,
    query: filterQuery,
  };
  if (window.__IS_MONITOR_COMPONENT__) {
    return monitorLink(routeData);
  }
  return window.mainComponent.$router.resolve(routeData).href;
}
