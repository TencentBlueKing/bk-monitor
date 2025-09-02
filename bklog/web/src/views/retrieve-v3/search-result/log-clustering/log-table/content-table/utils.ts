interface IRouterParams {
  name: string;
  params: Record<string, any>;
  query: Record<string, any>;
}

function monitorLink(routeParams: IRouterParams) {
  if (routeParams.name === 'retrieve') {
    const params = {
      ...window.mainComponent.$router.query,
      ...window.mainComponent.$router.params,
      ...routeParams,
      name: window.__IS_MONITOR_TRACE__ ? 'trace-retrieval' : 'apm-others',
      path: window.__IS_MONITOR_TRACE__ ? '/trace/home' : '/apm/service',
    };
    const url = window.mainComponent.$router.resolve(params).href;
    return url;
  }
  const url = window.mainComponent.$router.resolve(routeParams).href;
  const link = `${window.bk_log_search_url}${url}`;
  return link;
}

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
