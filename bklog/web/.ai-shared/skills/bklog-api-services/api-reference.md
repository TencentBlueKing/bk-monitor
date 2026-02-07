# API 接口参考

## 检索模块 (retrieve)

| API 名称 | 方法 | URL | 说明 |
|----------|------|-----|------|
| getIndexSetList | GET | /search/index_set/ | 获取索引集列表 |
| getLogTableHead | GET | /search/index_set/:id/fields/ | 获取字段信息 |
| getLogTableList | POST | /search/index_set/:id/search/ | 执行检索 |
| getLogChartList | POST | /search/index_set/:id/aggs/date_histogram/ | 趋势图 |
| getAggsTerms | POST | /search/index_set/:id/aggs/terms/ | 字段聚合 |
| getContentLog | POST | /search/index_set/:id/context/ | 上下文 |
| getRealTimeLog | POST | /search/index_set/:id/tail_f/ | 实时日志 |
| downloadLog | POST | /search/index_set/:id/export/ | 导出日志 |
| quickDownload | POST | /search/index_set/:id/quick_export/ | 快速导出 |
| exportAsync | POST | /search/index_set/:id/async_export/ | 异步导出 |

## 联合检索 (unionSearch)

| API 名称 | 方法 | URL | 说明 |
|----------|------|-----|------|
| unionMapping | POST | /search/index_set/union_search/fields/ | 联合字段映射 |
| unionSearch | POST | /search/index_set/union_search/ | 联合检索 |
| unionDownloadLog | POST | /search/index_set/union_search/export/ | 联合导出 |

## 收藏 (favorite)

| API 名称 | 方法 | URL | 说明 |
|----------|------|-----|------|
| getFavoriteByGroupList | GET | /favorite/ | 获取收藏列表 |
| createFavorite | POST | /favorite/ | 创建收藏 |
| updateFavorite | PUT | /favorite/:id/ | 更新收藏 |
| deleteFavorite | DELETE | /favorite/:id/ | 删除收藏 |

## 元信息 (meta)

| API 名称 | 方法 | URL | 说明 |
|----------|------|-----|------|
| menu | GET | /meta/menu/ | 获取菜单 |
| globals | GET | /meta/globals/ | 全局配置 |
| getUserGuide | GET | /meta/user_guide/ | 用户引导 |
| getEnvConstant | GET | /meta/env_constant/ | 环境常量 |

## 空间 (space)

| API 名称 | 方法 | URL | 说明 |
|----------|------|-----|------|
| getMySpaceList | GET | /meta/spaces/mine/ | 我的空间列表 |

## 索引集 (indexSet)

| API 名称 | 方法 | URL | 说明 |
|----------|------|-----|------|
| getSpaceByIndexId | GET | /index_set/:id/space/ | 根据索引获取空间 |
| markFavorite | POST | /index_set/:id/mark_favorite/ | 标记收藏 |
| cancelFavorite | POST | /index_set/:id/cancel_favorite/ | 取消收藏 |

## 采集 (collect)

| API 名称 | 方法 | URL | 说明 |
|----------|------|-----|------|
| getCollectorList | GET | /databus/collectors/ | 采集项列表 |
| getCollectorDetail | GET | /databus/collectors/:id/ | 采集项详情 |
| startCollector | POST | /databus/collectors/:id/start/ | 启动采集 |
| stopCollector | POST | /databus/collectors/:id/stop/ | 停止采集 |
| getTaskStatus | GET | /databus/collectors/:id/task_status/ | 下发状态 |

## 日志聚类 (logClustering)

| API 名称 | 方法 | URL | 说明 |
|----------|------|-----|------|
| getClusteringConfig | GET | /clustering_config/:id/ | 聚类配置 |
| createClusteringConfig | POST | /clustering_config/:id/access/create/ | 创建聚类 |
| updateClusteringConfig | POST | /clustering_config/:id/access/update/ | 更新聚类 |
| getClusteringConfigStatus | GET | /clustering_config/:id/access/status/ | 聚类状态 |

## 分享 (share)

| API 名称 | 方法 | URL | 说明 |
|----------|------|-----|------|
| createOrUpdateToken | POST | /share/create_or_update_token/ | 创建分享链接 |
| getShareParams | GET | /share/get_share_params/ | 获取分享参数 |
