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

import { defineComponent, ref, watch, computed, onMounted, onUnmounted } from 'vue';
import { bkMessage } from 'bk-magic-vue';

import { t } from '@/hooks/use-locale';
import useStore from '@/hooks/use-store';
import $http from '@/api';
import { handleTransformToTimestamp } from '@/components/time-range/utils';
import { useDownloadFile } from '../../manage-v2/client-log/hooks/use-download-file';

import type { LogItem, UrlState } from '../types';
import ClientLogViewer from './log-viewer';
import ClientLogToolbar from './toolbar';

import './index.scss';

/** 文件树节点 */
interface FileTreeNode {
  id: string;
  name: string;
  children: FileTreeNode[];
}

/**
 * 将扁平文件路径列表转换为 bk-big-tree 可用的树形结构
 * 最外层为一个名称为"根目录"的根节点
 *
 * @param fileList 文件路径列表，如 ["prod/app.log", "test/bbb.log"]
 * @returns 树形节点数组（只有一个根节点）
 */
const convertFileListToTree = (fileList: string[]): FileTreeNode[] => {
  const root: FileTreeNode = {
    id: 'root',
    name: t('根目录'),
    children: [],
  };

  // 用 Map 存储已创建的目录节点，避免重复
  const folderMap = new Map<string, FileTreeNode>();

  fileList.forEach((filePath) => {
    const parts = filePath.split('/');
    let currentParent = root;

    // 遍历路径的每一层
    for (let i = 0; i < parts.length; i++) {
      const partName = parts[i];
      // 构建当前层的完整路径作为唯一 ID
      const partPath = parts.slice(0, i + 1).join('/');
      const isFile = i === parts.length - 1;

      if (isFile) {
        // 文件节点：叶子节点，直接挂到当前父节点下
        currentParent.children.push({
          id: partPath,
          name: partName,
          children: [],
        });
      } else {
        // 目录节点：检查是否已存在
        if (!folderMap.has(partPath)) {
          const folderNode: FileTreeNode = {
            id: partPath,
            name: partName,
            children: [],
          };
          folderMap.set(partPath, folderNode);
          currentParent.children.push(folderNode);
        }
        currentParent = folderMap.get(partPath)!;
      }
    }
  });

  return [root];
};

/** 解析 extend_info：JSON 取 desc 字段，否则原样返回 */
const formatExtendInfo = (val: string) => {
  try {
    const parsed = JSON.parse(val);
    return parsed?.desc ?? val;
  } catch {
    return val;
  }
};

export default defineComponent({
  name: 'LogDetailPanel',
  props: {
    /** 左侧任务列表是否收起 */
    isTaskListCollapsed: {
      type: Boolean,
      default: false,
    },
    /** 当前选中的日志条目 */
    selectedLogItem: {
      type: Object as () => LogItem | null,
      default: null,
    },
    /** 当前索引集ID */
    indexSetId: {
      type: String,
      default: '',
    },
    /** 时区 */
    timezone: {
      type: String,
      default: window.timezone,
    },
    /** 是否有下载权限 */
    isAllowedDownload: {
      type: Boolean,
      default: false,
    },
    /** URL 回填的初始状态 */
    initialUrlState: {
      type: Object as () => Partial<UrlState>,
      default: () => ({}),
    },
    /** 上次搜索的时间范围（时间戳格式，用于分享链接） */
    searchTimeRange: {
      type: Array as unknown as () => [string, string] | [number, number],
      default: () => [0, 0],
    },
    /** 是否隐藏采集按钮（非"全部"tab且列表为空时隐藏） */
    hideCollectButton: {
      type: Boolean,
      default: false,
    },
  },
  emits: ['expand', 'collect', 'url-sync', 'scroll-state-change'],
  setup(props, { emit }) {
    const store = useStore();

    /** URL 初始状态 */
    const urlState = (props.initialUrlState ?? {}) as Partial<UrlState>;

    /** 使用文件下载 Hook */
    const { downloadFile: download } = useDownloadFile();

    /** 文件列表数据 */
    const fileList = ref<string[]>([]);

    /** 左侧文件树是否收起 */
    const isFileTreeCollapsed = ref(false);

    /** 当前激活的标签页 */
    const activeTab = ref('original-log');

    /** 所有文件夹节点 ID（用于默认全部展开） */
    const allFolderIds = ref<string[]>([]);

    /** 当前选中的文件节点 ID - 默认选中第一个文件 */
    const selectedFileId = ref<string | null>('');

    /** 展开的文件夹节点 ID 集合 - 默认全部展开 */
    const expandedNodeIds = ref<Set<string>>(new Set());

    /** 文件树数据 */
    const fileTreeData = ref<FileTreeNode[]>([]);

    /** 工具栏引用 */
    const toolbarRef = ref<any>(null);

    /** 过滤状态 */
    const filterKey = ref<string[]>([]);
    const filterType = ref('include');
    const highlightList = ref<any[]>([]);

    /** 清空关键词过滤和高亮过滤条件 */
    const resetFilters = () => {
      filterKey.value = [];
      filterType.value = 'include';
      highlightList.value = [];
      toolbarRef.value?.reset?.();
    };

    let skipNextResetFilters = false;

    let skipNextFilterWatch = false;

    /** 向父组件同步 URL 状态 */
    const emitUrlSync = () => {
      const state: Partial<UrlState> = {};
      if (selectedFileId.value) {
        state.fileId = selectedFileId.value;
      }
      if (filterKey.value.length) {
        state.filterKey = [...filterKey.value];
        state.filterType = filterType.value;
      } else {
        state.filterKey = [];
        delete state.filterType;
      }
      if (highlightList.value.length) {
        state.highlightList = highlightList.value.map((item: any) => item.heightKey ?? item);
      } else {
        state.highlightList = [];
      }
      emit('url-sync', state);
    };

    /** 日志内容列表 */
    const logList = ref<Record<string, any>[]>([]);

    /** 当前分页偏移 */
    const currentBegin = ref(0);

    /** 每页条数 */
    const pageSize = 1000;

    /** 是否还有更多日志 */
    const hasMore = ref(false);

    /** 是否正在加载更多 */
    const isLoadMore = ref(false);

    /** 日志内容滚动容器引用 */
    const logContentScrollRef = ref<HTMLElement | null>(null);

    /** 是否显示回到顶部按钮 */
    const showScrollTop = ref(false);

    /** 展示用的日志列表 */
    const filteredLogList = computed(() => {
      return logList.value.filter(item => item?.message).map(item => ({
        message: item.message,
      }));
    });

    /** 过滤结果是否为空 */
    const isFilterEmpty = computed(() => {
      if (!filterKey.value.length) return false;
      return logList.value.length === 0;
    });

    /** 文件列表加载状态 */
    const isFileLoading = ref(false);

    /** 日志内容加载状态 */
    const isLogLoading = ref(false);

    /**
     * 请求文件列表
     */
    const fetchFileList = () => {
      const indexSetIdVal = props.indexSetId;
      if (!indexSetIdVal) return;

      isFileLoading.value = true;
      const bkBizId = store.state.bkBizId;
      const processedAt = props.selectedLogItem?.processed_at;

      const data: Record<string, any> = {
        fields: ['file'],
        addition: [
          {
            field: 'cos_file_name',
            operator: '=',
            value: props.selectedLogItem?.file_name ?? '',
          },
        ],
        bk_biz_id: bkBizId,
      };

      if (processedAt) {
        const [startTime, endTime] = handleTransformToTimestamp([processedAt, 'now']);
        if (startTime) {
          data.start_time = startTime;
        }
        if (endTime) {
          data.end_time = endTime;
        }
      }

      $http
        .request('retrieve/getAggsTerms', {
          params: { index_set_id: indexSetIdVal },
          data,
        })
        .then((res: any) => {
          fileList.value = res?.data?.aggs_items?.file ?? [];
        })
        .catch((_err: any) => {
          fileList.value = [];
        })
        .finally(() => {
          isFileLoading.value = false;
        });
    };

    /** 当前采集状态 */
    const currentStatus = computed(() => props.selectedLogItem?.process_status ?? 'init');

    /** 监听选中任务和采集状态变化，请求文件列表 */
    watch(
      [() => props.selectedLogItem, currentStatus],
      ([item, status]) => {
        selectedFileId.value = null;
        logList.value = [];
        resetFilters();
        if (!item) {
          fileList.value = [];
          return;
        }
        // 仅在采集状态为「已完成」时请求文件列表
        if (status === 'success') {
          fetchFileList();
        }
      },
      { immediate: true },
    );

    /** 监听 fileList 变化，转换树形数据并收集文件夹 ID */
    watch(fileList, (list) => {
      if (list.length === 0) {
        fileTreeData.value = [];
        allFolderIds.value = [];
        selectedFileId.value = null;
        return;
      }

      fileTreeData.value = convertFileListToTree(list);

      // 收集所有文件夹节点 ID（有 children 且 children 非空的节点）
      const folderIds: string[] = [];
      const collectFolders = (nodes: FileTreeNode[]) => {
        nodes.forEach((node) => {
          if (node.children && node.children.length > 0) {
            folderIds.push(node.id);
            collectFolders(node.children);
          }
        });
      };
      collectFolders(fileTreeData.value);
      allFolderIds.value = folderIds;
      expandedNodeIds.value = new Set(folderIds);

      // 查找第一个叶子节点（文件）
      const findFirstFile = (nodes: FileTreeNode[]): string | null => {
        for (const node of nodes) {
          if (!node.children || node.children.length === 0) {
            return node.id;
          }
          const found = findFirstFile(node.children);
          if (found) return found;
        }
        return null;
      };

      // 首次加载时优先使用 URL 中的 fileId，否则选中第一个文件
      if (urlState?.fileId) {
        const urlFileId = urlState.fileId;
        const fileExists = list.includes(urlFileId);

        skipNextResetFilters = true;
        // 跳过 setFilters 触发 handleFilter 导致的 filterKey/filterType watcher
        skipNextFilterWatch = true;

        //  通过 setFilters 设置过滤条件和高亮配置
        const toolbarFilters: { filterKey?: string[]; filterType?: string; highlightList?: string[] } = {};
        if (urlState.filterKey?.length) {
          toolbarFilters.filterKey = [...urlState.filterKey];
        }
        if (urlState.filterType && toolbarFilters.filterKey?.length) {
          toolbarFilters.filterType = urlState.filterType;
        }
        if (urlState.highlightList?.length) {
          toolbarFilters.highlightList = [...urlState.highlightList];
        }
        if (Object.keys(toolbarFilters).length) {
          toolbarRef.value?.setFilters?.(toolbarFilters);
        }

        // 过滤条件已就绪，再设置 selectedFileId 触发 fetchLogList
        if (fileExists) {
          selectedFileId.value = urlFileId;
        } else {
          selectedFileId.value = findFirstFile(fileTreeData.value);
        }

        delete urlState.fileId;
      } else {
        selectedFileId.value = findFirstFile(fileTreeData.value);
      }

      // 选中文件后同步 URL
      emitUrlSync();
    });

    /**
     * 构建消息过滤的 addition 条件
     */
    const getMessageAddition = () => {
      if (!filterKey.value.length) return [];
      return [{
        field: 'message',
        operator: filterType.value === 'include' ? 'all contains match phrase' : 'all not contains match phrase',
        value: filterKey.value,
      }];
    };

    /**
     * 请求日志内容
     * @param fileId 选中的文件路径
     * @param isLoadMoreAction 是否为加载更多（追加模式）
     */
    const fetchLogList = (fileId: string, isLoadMoreAction = false) => {
      const indexSetIdVal = props.indexSetId;
      if (!indexSetIdVal || !fileId) return;

      if (isLoadMoreAction) {
        isLoadMore.value = true;
      } else {
        isLogLoading.value = true;
        currentBegin.value = 0;
      }

      const bkBizId = store.state.bkBizId;
      const processedAt = props.selectedLogItem?.processed_at;

      const data: Record<string, any> = {
        bk_biz_id: bkBizId,
        begin: currentBegin.value,
        size: pageSize,
        keyword: '*',
        addition: [
          {
            field: 'cos_file_name',
            operator: '=',
            value: props.selectedLogItem?.file_name ?? '',
          },
          {
            field: 'file',
            operator: '=',
            value: [fileId],
          },
          ...getMessageAddition(),
        ],
        sort_list: [
          [
            'lineno',
            'asc',
          ],
        ],
        time_zone: props.timezone,
      };

      if (processedAt) {
        const [startTime, endTime] = handleTransformToTimestamp([processedAt, 'now']);
        if (startTime) {
          data.start_time = startTime;
        }
        if (endTime) {
          data.end_time = endTime;
        }
      }

      $http
        .request('retrieve/getLogTableList', {
          params: { index_set_id: indexSetIdVal },
          data,
        })
        .then((res: any) => {
          const newList = res?.data?.list ?? [];
          if (isLoadMoreAction) {
            logList.value = [...logList.value, ...newList];
          } else {
            logList.value = newList;
          }
          currentBegin.value += newList.length;
          hasMore.value = newList.length >= pageSize;
        })
        .catch((_err: any) => {
          if (!isLoadMoreAction) {
            logList.value = [];
          }
        })
        .finally(() => {
          isLogLoading.value = false;
          isLoadMore.value = false;
          if (highlightList.value.length) {
            setTimeout(() => {
              toolbarRef.value?.getHighlightControl?.()?.initLightItemList?.();
            });
          }
        });
    };

    /** 监听选中文件变化，加载对应日志内容 */
    watch(selectedFileId, (fileId) => {
      if (skipNextResetFilters) {
        // URL 回填阶段跳过 resetFilters，保留已设置的过滤/高亮值
        skipNextResetFilters = false;
      } else {
        // resetFilters 会修改 filterKey/filterType 从而触发 filter watcher，需跳过
        skipNextFilterWatch = true;
        resetFilters();
      }
      if (fileId) {
        hasMore.value = false;
        fetchLogList(fileId);
      } else {
        logList.value = [];
        hasMore.value = false;
      }
    });

    /** 监听过滤条件变化，重新请求日志 */
    watch(
      [filterKey, filterType],
      () => {
        if (skipNextFilterWatch) {
          skipNextFilterWatch = false;
          return;
        }
        const fileId = selectedFileId.value;
        if (!fileId) return;
        logList.value = [];
        hasMore.value = false;
        fetchLogList(fileId);
      },
      { deep: true },
    );

    /** 滚动触底加载更多日志 */
    let scrollTimer: ReturnType<typeof setTimeout> | null = null;
    let lastScrollTop = 0;
    const handleLogScroll = () => {
      const el = logContentScrollRef.value;
      if (!el) return;

      // 更新回到顶部按钮显示状态
      showScrollTop.value = el.scrollTop > 300;

      // 判断滚动方向，通知父组件折叠/展开 UserInfoCard
      const isScrollingDown = el.scrollTop > lastScrollTop && el.scrollTop > 50;
      const isScrolledToTop = el.scrollTop < 10;
      if (isScrollingDown) {
        emit('scroll-state-change', true);
      } else if (isScrolledToTop) {
        emit('scroll-state-change', false);
      }
      lastScrollTop = el.scrollTop;

      // 触底加载更多日志（防抖）
      if (scrollTimer) clearTimeout(scrollTimer);
      scrollTimer = setTimeout(() => {
        const el = logContentScrollRef.value;
        if (!el) return;

        if (isLoadMore.value || isLogLoading.value || !hasMore.value) return;

        const { scrollTop, scrollHeight, offsetHeight } = el;
        if (scrollHeight - scrollTop - offsetHeight < 50) {
          const fileId = selectedFileId.value;
          if (fileId) {
            fetchLogList(fileId, true);
          }
        }
      }, 300);
    };

    /** 回到顶部 */
    const handleScrollToTop = () => {
      const el = logContentScrollRef.value;
      if (el) {
        el.scrollTop = 0;
      }
    };

    /** 工具栏过滤事件处理 */
    const handleFilter = (field: string, value: any) => {
      switch (field) {
        case 'filterKey':
          filterKey.value = value;
          break;
        case 'filterType':
          filterType.value = value;
          break;
        case 'highlightList':
          highlightList.value = value;
          break;
        default:
          break;
      }
      // 手动更改过滤/高亮配置时同步 URL
      emitUrlSync();
    };

    /** 标签页列表 */
    const panels = ref([
      {
        name: 'original-log',
        label: t('原始日志'),
        icon: 'bklog-icon bklog-log',
      },
    ]);

    /** 是否全屏展示 */
    const isFullscreen = ref(false);

    /** 切换全屏 */
    const handleFullscreen = () => {
      isFullscreen.value = !isFullscreen.value;
    };

    /** Esc 键退出全屏 */
    const handleKeydown = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && isFullscreen.value) {
        isFullscreen.value = false;
      }
    };

    onMounted(() => {
      document.addEventListener('keydown', handleKeydown);
    });

    onUnmounted(() => {
      document.removeEventListener('keydown', handleKeydown);
    });

    /** 点击展开图标 */
    const handleExpand = () => {
      emit('expand');
    };

    /**
     * 下载按钮是否禁用
     * - task 类型：process_status !== 'success' 时禁用
     * - report 类型：不禁用
     */
    const isDownloadDisabled = () => {
      const item = props.selectedLogItem;
      if (!item) return true;
      return item.source === 'task' && item.process_status !== 'success';
    };

    /** 下载提示内容 */
    const downloadTooltipContent = () => {
      const item = props.selectedLogItem;
      if (!item) return '';
      if (item.source === 'task' && item.process_status !== 'success') {
        return t('暂无下载链接，请在任务完成后点击下载');
      }
      return '';
    };

    /** 点击下载按钮 */
    const handleDownload = () => {
      const item = props.selectedLogItem;
      if (!item) return;
      download(item.file_name, props.isAllowedDownload);
    };

    /** 点击分享按钮，将时间参数转为时间戳后复制链接 */
    const handleShare = () => {
      const [startTs, endTs] = props.searchTimeRange;
      const url = new URL(window.location.href);
      // 取出 hash 路由部分
      const [hashPath, hashQuery = ''] = url.hash.split('?');
      const hashSearchParams = new URLSearchParams(hashQuery);
      if (startTs) {
        hashSearchParams.set('startTime', String(startTs));
      }
      if (endTs) {
        hashSearchParams.set('endTime', String(endTs));
      }
      // 重新拼接 hash
      url.hash = `${hashPath}?${hashSearchParams.toString()}`;
      navigator.clipboard.writeText(url.toString()).then(() => {
        bkMessage({
          message: t('复制成功'),
          theme: 'success',
        });
      });
    };

    /** 文件树节点点击 */
    const handleNodeClick = (node: any) => {
      if (!node.children || !node.children.length) {
        selectedFileId.value = node.id;
        // 手动切换文件时同步 URL
        emitUrlSync();
      }
    };

    /** 文件树展开/收起变化 */
    const handleExpandChange = (node: any) => {
      if (node.expanded) {
        expandedNodeIds.value.add(node.id);
      } else {
        expandedNodeIds.value.delete(node.id);
      }
      expandedNodeIds.value = new Set(expandedNodeIds.value);
    };

    /** 渲染文件树节点图标 */
    const renderTreeNodeIcon = (data: any) => {
      const isFolder = data.children && data.children.length;
      if (isFolder) {
        const isExpanded = expandedNodeIds.value.has(data.id);
        return (
          <i
            class={`bklog-icon ${isExpanded ? 'bklog-file-open' : 'bklog-file-close'}`}
          />
        );
      }
      return <i class='bklog-icon bklog-file-wenjian' />;
    };

    /** 渲染文件树节点内容 */
    const renderTreeNodeContent = (data: any) => {
      const isFolder = data.children && data.children.length;
      const isActive = !isFolder && selectedFileId.value === data.id;
      return (
        <div class={['tree-node-content', { 'is-active': isActive }]}>
          {renderTreeNodeIcon(data)}
          <span class='node-name'>{data.name}</span>
        </div>
      );
    };

    /** 渲染设备信息标签 */
    const renderDeviceInfo = () => [
      props.selectedLogItem?.model && (
        <span class='device-info'>
          {props.selectedLogItem.model}
        </span>
      ),
      props.selectedLogItem?.os_version && (
        <span class='device-info'>{props.selectedLogItem.os_version}</span>
      ),
      props.selectedLogItem?.sdk_version && (
        <span class='device-info'>
          {props.selectedLogItem.sdk_version}
        </span>
      ),
    ];

    /** 渲染未采集状态内容 */
    const renderUncollectedContent = () => (
      <div class='uncollected-content'>
        <bk-exception type="empty">
          <div class='tip'>{t('暂未采集，无法获取日志')}</div>
          {!props.hideCollectButton && (
            <bk-button theme='primary' onClick={() => emit('collect', props.selectedLogItem)}>
              {t('立即采集')}
            </bk-button>
          )}
        </bk-exception>
      </div>
    );

    /** 渲染采集中状态内容 */
    const renderCollectingContent = () => (
      <div class='collecting-content'>
        <div class='collecting-spin'>
          <bk-spin size='normal'></bk-spin>
        </div>
        <div class='collecting-title'>{t('正在采集目标日志文件，预计2-3分钟')}</div>
      </div>
    );

    /** 渲染采集失败状态内容 */
    const renderCollectFailedContent = () => (
      <div class='uncollected-content'>
        <bk-exception type="empty">
          <div class='tip'>{t('日志采集失败，请重新采集')}</div>
          {!props.hideCollectButton && (
            <bk-button theme='primary' onClick={() => emit('collect', props.selectedLogItem)}>
              {t('立即采集')}
            </bk-button>
          )}
        </bk-exception>
      </div>
    );

    /** 渲染原始日志面板内容 */
    const renderOriginalLogContent = () => (
      <div class='original-log-content' v-bkloading={{ isLoading: isFileLoading.value || isLogLoading.value, color: '#212429' }}>
        {/* 左侧文件树 */}
        <div class={['file-tree-sidebar', { 'is-collapsed': isFileTreeCollapsed.value }]}>
          <bk-big-tree
            data={fileTreeData.value}
            default-expand-all={true}
            expand-on-click={true}
            padding={24}
            fixed-width
            enable-title-tip={true}
            on-node-click={handleNodeClick}
            on-expand-change={handleExpandChange}
            options={{ nameKey: 'name', idKey: 'id', childrenKey: 'children' }}
            scopedSlots={{
              default: ({ data }: any) => renderTreeNodeContent(data),
            }}
          />
        </div>
        {/* 右侧文件内容展示：上部工具栏 + 下部日志内容 */}
        <div class='file-content-area'>
          {/* 工具栏 */}
          <div class='toolbar-wrapper' key='toolbar'>
            <ClientLogToolbar
              ref={toolbarRef}
              isFileTreeCollapsed={isFileTreeCollapsed.value}
              on-handle-filter={handleFilter}
              on-toggle-file-tree={() => { isFileTreeCollapsed.value = !isFileTreeCollapsed.value; }}
            />
          </div>
          {/* 日志内容区 */}
          <div class='log-content-scroll' key='log-content' ref={logContentScrollRef} onScroll={handleLogScroll}>
            {logList.value.some(item => item?.message) ? (
              isFilterEmpty.value ? (
                <bk-exception
                  style='margin-top: 80px'
                  scene='part'
                  type='search-empty'
                >
                  <span>{t('搜索结果为空')}</span>
                </bk-exception>
              ) : (
                <ClientLogViewer
                  logList={filteredLogList.value}
                  filterKey={filterKey.value}
                  filterType={filterType.value}
                  highlightList={highlightList.value}
                />
              )
            ) : !isLogLoading.value ? (
              <bk-exception
                style='margin-top: 80px'
                scene='part'
                type='empty'
              >
                <span>{t('暂无数据')}</span>
              </bk-exception>
            ) : null}
            {/* 触底加载状态 */}
            {isLoadMore.value && (
              <div class='log-load-more'>loading...</div>
            )}
          </div>
          {/* 回到顶部按钮 */}
          {showScrollTop.value && (
            <span
              class='scroll-to-top-btn'
              v-bk-tooltips={t('返回顶部')}
              onClick={handleScrollToTop}
            >
              <i class='bklog-icon bklog-backtotop' />
            </span>
          )}
        </div>
      </div>
    );

    /** 根据采集状态渲染对应内容 */
    const renderStatusContent = () => {
      const status = currentStatus.value;
      if (!status || status === 'init' || status === 'pending') {
        return renderUncollectedContent();
      }
      if (status === 'running') {
        return renderCollectingContent();
      }
      if (status === 'failed') {
        return renderCollectFailedContent();
      }
      // success - 已采集
      return (
        <div class='tab-container'>
          <bk-tab
            active={activeTab.value}
            type='unborder-card'
            label-height={40}
            on-tab-change={(val: string) => {
              activeTab.value = val;
            }}
          >
            {panels.value.map(panel => (
              <bk-tab-panel
                key={panel.name}
                name={panel.name}
                label={panel.label}
                renderLabel={() => (
                  <div>
                    <i class={`bklog-icon ${panel.icon}`}></i>
                    <span class='panel-name'>{panel.label}</span>
                  </div>
                )}
              >
                {activeTab.value === 'original-log'
                  && renderOriginalLogContent()}
              </bk-tab-panel>
            ))}
          </bk-tab>
        </div>
      );
    };

    return () => (
      <div class={['card-base', 'log-detail-panel', { 'is-fullscreen': isFullscreen.value }]}>
        {/* 左上角展开图标 - 仅在左侧列表收起时显示 */}
        {props.isTaskListCollapsed && (
          <span class='expand-icon' onClick={handleExpand}>
            <i class='bklog-icon bklog-collapse'></i>
          </span>
        )}

        {/* 日志详情内容区域 */}
        <div class='log-detail-content'>
          {/* 头部 */}
          <header class='detail-header'>
            <div class='header-left'>
              <h2 class='title'>{t('日志详情')}</h2>
              {currentStatus.value === 'success' && renderDeviceInfo()}
            </div>
            {currentStatus.value === 'success' && (
              <div class='header-right'>
                <span
                  v-bk-tooltips={{
                    content: downloadTooltipContent(),
                    disabled: !isDownloadDisabled(),
                  }}
                >
                  <bk-button
                    disabled={isDownloadDisabled()}
                    class={[{ 'disabled-download': !props.isAllowedDownload }]}
                    v-cursor={{ active: !isDownloadDisabled() && !props.isAllowedDownload }}
                    onClick={handleDownload}
                  >
                    <i class='bk-icon icon-download'></i>
                    {t('下载')}
                  </bk-button>
                </span>
                <bk-button onClick={handleShare}>
                  <i class='bklog-icon bklog-share-fenxiang'></i>
                  {t('分享')}
                </bk-button>
                <bk-button
                  onClick={handleFullscreen}
                >
                  <i class={`bk-icon ${isFullscreen.value ? 'icon-unfull-screen' : 'icon-full-screen'}`}></i>
                  {isFullscreen.value ? t('退出') : t('全屏')}
                </bk-button>
              </div>
            )}
          </header>

          {currentStatus.value === 'success' && props.selectedLogItem?.extend_info && (
            <div class='ext-content'>
              <i class='bklog-icon bklog-miaoshu'></i>
              <span class='ext-label'>{t('扩展信息')}:</span>
              <span class='ext-value'>{formatExtendInfo(props.selectedLogItem.extend_info)}</span>
            </div>
          )}

          {renderStatusContent()}
        </div>
      </div>
    );
  },
});
