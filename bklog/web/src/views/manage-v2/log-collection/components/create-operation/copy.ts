/**
 * 处理创建成功的回调函数
 * @param {Object} params - 包含授权URL和索引集ID的参数对象
 * @param {string} params.bkdata_auth_url - 数据平台授权地址
 * @param {string} params.index_set_id - 索引集ID
 */
const handleCreateSuccess = ({
  bkdata_auth_url: authUrl,
  index_set_id: indexSetId,
}) => {
  // 如果没有授权URL，直接返回索引列表
  if (!authUrl) {
    returnIndexList();
    return;
  }

  /**
   * 规范化站点URL，确保格式正确
   * @param {string} siteUrl - 原始站点URL
   * @returns {string} 规范化后的站点URL
   */
  const normalizeSiteUrl = (siteUrl) => {
    // 处理非HTTP开头的URL，添加协议和主机
    if (!siteUrl.startsWith("http")) {
      // 确保以斜杠开头
      if (!siteUrl.startsWith("/")) {
        siteUrl = `/${siteUrl}`;
      }
      siteUrl = `${window.origin}${siteUrl}`;
    }

    // 确保以斜杠结尾
    return siteUrl.endsWith("/") ? siteUrl : `${siteUrl}/`;
  };

  /**
   * 构建完整的URL
   * @param {string} baseUrl - 基础URL
   * @param {string} path - 路径
   * @returns {string} 完整的URL
   */
  const buildFullUrl = (baseUrl, path) => {
    const normalizedBase = normalizeSiteUrl(baseUrl);
    return `${normalizedBase}${path}`;
  };

  // 获取站点URL
  const siteUrl = window.SITE_URL;

  // 构建重定向URL
  let redirectUrl;
  if (process.env.NODE_ENV === "development") {
    redirectUrl = `${authUrl}&redirect_url=${window.origin}/static/auth.html`;
  } else {
    redirectUrl = `${authUrl}&redirect_url=${buildFullUrl(
      siteUrl,
      "bkdata_auth/"
    )}`;
  }

  // 构建索引集路径
  const { href: indexSetHref } = router.resolve({
    name: `${props.scenarioId}-index-set-list`,
  });
  const indexSetPath = buildFullUrl(siteUrl, indexSetHref);

  // 构建并编码URL参数
  const urlParams = new URLSearchParams({
    indexSetId,
    ajaxUrl: window.AJAX_URL_PREFIX,
    redirectUrl: indexSetPath,
  }).toString();

  // 完成重定向URL的构建
  redirectUrl += encodeURIComponent(`?${urlParams}`);

  // 根据是否在iframe中采取不同的跳转方式
  if (self !== top) {
    // 在iframe中，打开新窗口
    window.open(redirectUrl);
    returnIndexList();
  } else {
    // 在顶层窗口，直接重定向
    window.location.assign(redirectUrl);
  }
};
