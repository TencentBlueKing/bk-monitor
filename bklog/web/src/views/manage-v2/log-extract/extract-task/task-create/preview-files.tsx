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

import { debounce } from 'lodash-es';
import { defineComponent, ref, computed, watch, nextTick, onBeforeUnmount } from 'vue';

import { formatDate } from '@/common/util';
import EmptyStatus from '@/components/empty-status/index.vue';
import useLocale from '@/hooks/use-locale';
import useStore from '@/hooks/use-store';

import FileDatePicker from './file-date-picker.tsx';
import FilesInput from './files-input.tsx';
import http from '@/api';

import './preview-files.scss';

export default defineComponent({
  name: 'PreviewFiles',
  props: {
    availablePaths: { type: Array, default: () => [] },
    downloadFiles: { type: Array, default: () => [] },
    ipList: { type: Array, required: true },
    fileOrPath: { type: String, required: true },
    ipSelectNewNameList: { type: Array, required: true },
  },
  setup(props, { emit, expose }) {
    const store = useStore();
    const { t } = useLocale();
    const isLoading = ref(false);
    const previewIp = ref<any[]>([]);
    const timeRange = ref('1w');
    const currentTime = Date.now();
    const timeValue = ref([
      formatDate(new Date(currentTime - 1000 * 60 * 60 * 24 * 7)),
      formatDate(new Date(currentTime)),
    ]);
    const isSearchChild = ref(false);
    const explorerList = ref<any[]>([]);
    const historyStack = ref<{ exploreList: any[]; fileOrPath: string }[]>([]);
    const emptyType = ref('empty');
    const filterInputValue = ref('');
    const filterKeyword = ref('');
    const extractionDirection = ref('forward');
    const selectedFilePathSet = ref(new Set<string>());
    const currentPage = ref(1);
    const pageLimit = ref(10);
    const sortState = ref({ prop: '', order: '' });
    const previewTableRef = ref<any>(null);
    let isSyncingTableSelection = false;
    let selectionSyncVersion = 0;
    let explorerRequestVersion = 0;

    const timeStringValue = computed(() => [timeValue.value[0], timeValue.value[1]]);
    const getFilePath = (row: any) => String(row?.path ?? '');
    const isDirectory = (row: any) => row?.type === 'dir' || (!row?.type && row?.size === '0');
    const isSelectableFile = (row: any) => Boolean(getFilePath(row)) && !isDirectory(row);
    const hasParentDirectory = computed(() => historyStack.value.length > 1);

    const filteredExplorerList = computed(() => {
      const keyword = filterKeyword.value;
      if (!keyword) {
        return explorerList.value;
      }
      return explorerList.value.filter(item => {
        const fileName = String(item?.path ?? '').toLowerCase();
        const modifiedTime = String(item?.mtime ?? '').toLowerCase();
        return fileName.includes(keyword) || modifiedTime.includes(keyword);
      });
    });

    const getSortValue = (row: any, prop: string) => {
      if (prop === 'size') {
        const size = String(row.size ?? '0').match(/^([\d.]+)\s*(B|KB|MB|GB|TB)?$/i);
        const unit = size?.[2]?.toUpperCase() ?? 'B';
        return size ? Number(size[1]) * 1024 ** ['B', 'KB', 'MB', 'GB', 'TB'].indexOf(unit) : 0;
      }
      return String(row[prop] ?? '');
    };

    const sortedExplorerList = computed(() => {
      const { prop, order } = sortState.value;
      if (!prop || !order) {
        return filteredExplorerList.value;
      }
      const keys = [prop, ...['path', 'mtime', 'size'].filter(key => key !== prop)];
      const direction = order === 'ascending' ? 1 : -1;
      return [...filteredExplorerList.value].sort((left, right) => {
        for (const key of keys) {
          const leftValue = getSortValue(left, key);
          const rightValue = getSortValue(right, key);
          if (leftValue !== rightValue) {
            return (leftValue > rightValue ? 1 : -1) * direction;
          }
        }
        return 0;
      });
    });

    const pageRows = computed(() => {
      const start = (currentPage.value - 1) * pageLimit.value;
      return sortedExplorerList.value.slice(start, start + pageLimit.value);
    });
    const pagination = computed(() => ({
      current: currentPage.value,
      count: filteredExplorerList.value.length,
      limit: pageLimit.value,
      small: true,
      showTotalCount: true,
      limitList: [10, 20, 50, 100],
    }));
    const selectedFiles = computed(() => {
      const filesByPath = new Map(explorerList.value.map(row => [getFilePath(row), row]));
      return Array.from(selectedFilePathSet.value, path => filesByPath.get(path) ?? { path, ip: '' });
    });

    const getDownloadFiles = () => {
      if (isLoading.value) {
        return [];
      }
      if (extractionDirection.value === 'forward') {
        return Array.from(selectedFilePathSet.value);
      }
      return Array.from(
        new Set(
          explorerList.value
            .filter(row => isSelectableFile(row) && !selectedFilePathSet.value.has(getFilePath(row)))
            .map(getFilePath),
        ),
      );
    };

    const emitSelectedFiles = () => emit('update:downloadFiles', Array.from(selectedFilePathSet.value));
    const setSelectedFilePaths = (paths: string[]) => {
      selectedFilePathSet.value = new Set((paths ?? []).filter(Boolean));
    };

    // 表格数据变化会触发 selection-change，同步过程中不能覆盖跨页选择。
    const syncTableSelection = async () => {
      selectionSyncVersion += 1;
      const version = selectionSyncVersion;
      isSyncingTableSelection = true;
      await nextTick();
      if (version !== selectionSyncVersion) {
        return;
      }
      if (previewTableRef.value) {
        previewTableRef.value.clearSelection?.();
        for (const item of pageRows.value) {
          if (isSelectableFile(item) && selectedFilePathSet.value.has(getFilePath(item))) {
            previewTableRef.value.toggleRowSelection?.(item, true);
          }
        }
        await new Promise(resolve => requestAnimationFrame(resolve));
        await nextTick();
      }
      if (version === selectionSyncVersion) {
        isSyncingTableSelection = false;
      }
    };

    const updateFilterKeyword = debounce((val: string) => {
      isSyncingTableSelection = true;
      currentPage.value = 1;
      filterKeyword.value = String(val ?? '')
        .trim()
        .toLowerCase();
      syncTableSelection();
    }, 200);
    const handleFilterChange = (val: string) => {
      filterInputValue.value = val;
      updateFilterKeyword(val);
    };

    const handlePageChange = (page: number) => {
      isSyncingTableSelection = true;
      const maxPage = Math.max(1, Math.ceil(filteredExplorerList.value.length / pageLimit.value));
      currentPage.value = Math.max(1, Math.min(page, maxPage));
      syncTableSelection();
    };
    const handlePageLimitChange = (limit: number) => {
      isSyncingTableSelection = true;
      pageLimit.value = limit;
      currentPage.value = 1;
      syncTableSelection();
    };
    const handleSortChange = ({ prop, order }: { prop: string; order: string }) => {
      isSyncingTableSelection = true;
      sortState.value = { prop, order };
      currentPage.value = 1;
      syncTableSelection();
    };

    const clearSelectedFiles = () => {
      setSelectedFilePaths([]);
      emitSelectedFiles();
      syncTableSelection();
    };
    const removeSelectedFile = (path: string) => {
      const paths = new Set(selectedFilePathSet.value);
      paths.delete(path);
      selectedFilePathSet.value = paths;
      emitSelectedFiles();
      syncTableSelection();
    };

    const getIpListID = (option: any) => [option.bk_host_id ?? '', option.ip ?? '', option.bk_cloud_id ?? ''].join('_');
    const getFindIpList = () =>
      previewIp.value.map(id => props.ipList.find((item: any) => getIpListID(item) === id)).filter(Boolean);

    watch(
      () => props.ipList,
      val => {
        explorerRequestVersion += 1;
        isLoading.value = false;
        previewIp.value = val.length ? [getIpListID(val[0])] : [];
        currentPage.value = 1;
        clearSelectedFiles();
        explorerList.value = [];
        historyStack.value = [];
      },
    );

    // 首条历史是检索起点；返回时用弹出记录恢复列表，用剩余栈顶恢复路径。
    const getExplorerList = (row: any = {}) => {
      if (row.path === '../' && !hasParentDirectory.value) {
        return;
      }
      explorerRequestVersion += 1;
      const version = explorerRequestVersion;
      const path = row.path ?? props.fileOrPath;
      const cache = { exploreList: [...explorerList.value], fileOrPath: path };
      currentPage.value = 1;
      clearSelectedFiles();

      if (path === '../') {
        const parent = historyStack.value.pop();
        explorerList.value = parent.exploreList;
        emit('update:fileOrPath', historyStack.value.at(-1).fileOrPath);
        emptyType.value = 'search-empty';
        isLoading.value = false;
        return;
      }

      const enteringDirectory = isDirectory(row);
      if (!enteringDirectory) {
        historyStack.value = [];
      }
      explorerList.value = [];
      emit('update:fileOrPath', path);
      isLoading.value = true;
      emptyType.value = 'search-empty';
      return http
        .request('extract/getExplorerList', {
          data: {
            bk_biz_id: store.state.bkBizId,
            ip_list: getFindIpList(),
            path,
            time_range: timeRange.value,
            start_time: timeStringValue.value[0],
            end_time: timeStringValue.value[1],
            is_search_child: isSearchChild.value,
          },
        })
        .then(res => {
          if (version !== explorerRequestVersion) {
            return;
          }
          historyStack.value.push(cache);
          explorerList.value = res.data;
        })
        .catch(err => {
          if (version !== explorerRequestVersion) {
            return;
          }
          console.warn(err);
          emptyType.value = '500';
          if (enteringDirectory) {
            explorerList.value = cache.exploreList;
            emit('update:fileOrPath', historyStack.value.at(-1)?.fileOrPath ?? path);
          }
        })
        .finally(() => {
          if (version === explorerRequestVersion) {
            isLoading.value = false;
          }
        });
    };

    const findPreviewIpListValue = (previewIpList: any[], ipList: any[]) =>
      (previewIpList ?? [])
        .map(item =>
          ipList.find(
            host =>
              (item.bk_host_id && item.bk_host_id === host.bk_host_id) ||
              [item.ip, item.bk_cloud_id].join('_') === [host.ip, host.bk_cloud_id].join('_'),
          ),
        )
        .filter(Boolean);

    const handleClone = ({
      ip_list: ipList,
      preview_ip_list: previewIpList,
      preview_directory: path,
      preview_time_range: timeRangeVal,
      preview_start_time: startTime,
      preview_end_time: endTime,
      preview_is_search_child: isSearchChildVal,
      file_path: downloadFiles,
    }: any) => {
      extractionDirection.value = 'forward';
      explorerRequestVersion += 1;
      const version = explorerRequestVersion;
      timeRange.value = timeRangeVal;
      timeValue.value = [formatDate(new Date(startTime), false), formatDate(new Date(endTime), false)];
      isSearchChild.value = isSearchChildVal;
      const findIpList = findPreviewIpListValue(previewIpList, ipList);
      previewIp.value = findIpList.map(getIpListID);
      currentPage.value = 1;
      historyStack.value = [];
      isLoading.value = true;
      emptyType.value = 'search-empty';
      return http
        .request('extract/getExplorerList', {
          data: {
            bk_biz_id: store.state.bkBizId,
            ip_list: findIpList,
            path,
            time_range: timeRangeVal,
            start_time: startTime,
            end_time: endTime,
            is_search_child: isSearchChildVal,
          },
        })
        .then(res => {
          if (version !== explorerRequestVersion) {
            return;
          }
          historyStack.value = [{ exploreList: [], fileOrPath: path }];
          explorerList.value = res.data;
          setSelectedFilePaths(downloadFiles);
          emitSelectedFiles();
          syncTableSelection();
        })
        .catch(err => {
          if (version === explorerRequestVersion) {
            console.warn(err);
            emptyType.value = '500';
          }
        })
        .finally(() => {
          if (version === explorerRequestVersion) {
            isLoading.value = false;
          }
        });
    };

    const handleOperation = (type: string) => {
      if (type === 'clear-filter' || type === 'refresh') {
        getExplorerList({});
      }
    };

    const handleSelect = (selection: any[]) => {
      if (isSyncingTableSelection) {
        return;
      }
      const paths = new Set(selectedFilePathSet.value);
      const visiblePaths = new Set(pageRows.value.filter(isSelectableFile).map(getFilePath));
      for (const path of visiblePaths) {
        paths.delete(path);
      }
      for (const item of selection) {
        const path = getFilePath(item);
        if (visiblePaths.has(path) && isSelectableFile(item)) {
          paths.add(path);
        }
      }
      selectedFilePathSet.value = paths;
      emitSelectedFiles();
    };

    watch(
      () => props.downloadFiles,
      val => {
        setSelectedFilePaths(val as string[]);
        syncTableSelection();
      },
      { immediate: true },
    );
    watch(pageRows, syncTableSelection);
    onBeforeUnmount(() => {
      updateFilterKeyword.cancel();
      explorerRequestVersion += 1;
      selectionSyncVersion += 1;
    });
    expose({
      getExplorerList,
      handleClone,
      getFindIpList,
      getDownloadFiles,
      extractionDirection,
      timeRange,
      timeStringValue,
      isSearchChild,
    });

    return () => (
      <div class='preview-file-content'>
        <div class='file-selection-panel'>
          <div class='preview-table-head'>
            <div class='preview-panel-heading'>
              <strong>{t('选择日志文件')}</strong>
              <span>{t('请在检索后，在文件列表选择日志文件')}</span>
            </div>
            <bk-input
              class='preview-file-filter-input'
              clearable
              placeholder={t('搜索文件名/最后修改时间')}
              right-icon='bk-icon icon-search'
              value={filterInputValue.value}
              on-input={handleFilterChange}
            />
          </div>
          <div class='file-search-fields'>
            <div class='file-search-path'>
              <div class='file-search-label'>
                {t('目录 / 文件名')}
                <span class='required'>*</span>
                <span
                  class='bklog-icon bklog-info-fill'
                  v-bk-tooltips={`${t('以')}/${t('结尾查询指定目录下内容，否则默认查询该目录及其子目录下所有文件')}`}
                />
              </div>
              <FilesInput
                availablePaths={props.availablePaths}
                value={props.fileOrPath}
                {...{
                  on: {
                    'update:value': (val: string) => emit('update:fileOrPath', val),
                    'update:select': (path: string) => getExplorerList({ path }),
                  },
                }}
              />
            </div>
            <div class='file-search-options'>
              <div class='file-search-option'>
                <div class='file-search-label'>{t('预览地址')}</div>
                <bk-select
                  clearable={false}
                  data-test-id='addNewExtraction_div_selectPreviewAddress'
                  value={previewIp.value}
                  multiple
                  show-select-all
                  onChange={val => (previewIp.value = val)}
                >
                  {props.ipSelectNewNameList.map((option: any) => (
                    <bk-option
                      id={option.selectID}
                      key={option.selectID}
                      name={option.name}
                    />
                  ))}
                </bk-select>
              </div>
              <div class='file-search-option'>
                <div class='file-search-label'>{t('时间范围')}</div>
                <FileDatePicker
                  timeRange={timeRange.value}
                  timeValue={timeValue.value}
                  {...{
                    on: {
                      'update:timeRange': (val: string) => (timeRange.value = val),
                      'update:timeValue': (val: string[]) => (timeValue.value = val),
                    },
                  }}
                />
              </div>
              <bk-checkbox
                class='search-child-checkbox'
                data-test-id='addNewExtraction_div_isSearchSubdirectory'
                value={isSearchChild.value}
                onChange={(val: boolean) => (isSearchChild.value = val)}
              >
                {t('搜索子目录')}
              </bk-checkbox>
              <bk-button
                data-test-id='addNewExtraction_button_searchFilterCondition'
                disabled={!(props.ipList.length && props.fileOrPath)}
                loading={isLoading.value}
                theme='primary'
                onClick={() => getExplorerList({})}
              >
                {t('检索')}
              </bk-button>
            </div>
          </div>
          <div
            class='preview-table-container'
            v-bkloading={{ isLoading: isLoading.value, opacity: 0.7, zIndex: 0 }}
          >
            <bk-table
              ref={previewTableRef}
              class='preview-scroll-table'
              data={pageRows.value}
              pagination={pagination.value}
              row-key='path'
              size='small'
              scopedSlots={{
                empty: () => (
                  <EmptyStatus
                    empty-type={emptyType.value}
                    on-operation={handleOperation}
                  >
                    {emptyType.value === 'search-empty' && (
                      <div>{t('可以尝试{0}或{1}', { 0: t('调整预览地址'), 1: t('调整文件日期') })}</div>
                    )}
                  </EmptyStatus>
                ),
              }}
              onPage-change={handlePageChange}
              onPage-limit-change={handlePageLimitChange}
              on-sort-change={handleSortChange}
              on-selection-change={handleSelect}
            >
              {hasParentDirectory.value && (
                <template slot='prepend'>
                  <div class='parent-directory-row'>
                    <bk-button
                      disabled={isLoading.value}
                      text
                      onClick={() => getExplorerList({ path: '../' })}
                    >
                      ../
                    </bk-button>
                  </div>
                </template>
              )}
              <bk-table-column
                width={42}
                selectable={isSelectableFile}
                type='selection'
              />
              <bk-table-column
                label={t('文件名')}
                min-width={220}
                prop='path'
                scopedSlots={{
                  default: ({ row }: any) =>
                    isDirectory(row) ? (
                      <span
                        class='file-name-text download-url-text'
                        v-bk-overflow-tips
                        onClick={() => getExplorerList(row)}
                      >
                        {row.path}
                      </span>
                    ) : (
                      <span
                        class='file-name-text'
                        v-bk-overflow-tips
                      >
                        {row.path}
                      </span>
                    ),
                }}
              />
              <bk-table-column
                label={t('最后修改时间')}
                width={180}
                prop='mtime'
                sortable='custom'
              />
              <bk-table-column
                label={t('文件大小')}
                width={100}
                prop='size'
                sortable='custom'
              />
              <bk-table-column
                label={t('命中目标')}
                min-width={150}
                prop='ip'
              />
            </bk-table>
          </div>
        </div>
        <aside class='selected-files-panel'>
          <div class='selected-files-heading'>
            <strong>{t('已选预览')}</strong>
            <bk-button
              disabled={!selectedFiles.value.length}
              text
              onClick={clearSelectedFiles}
            >
              {t('清空')}
            </bk-button>
          </div>
          <div class='selected-files-content'>
            <div class='extraction-direction-controls'>
              <bk-radio-group
                class='extraction-direction-group'
                value={extractionDirection.value}
                onChange={(val: string) => (extractionDirection.value = val)}
              >
                <bk-radio value='forward'>{t('正向提取')}</bk-radio>
                <bk-radio value='reverse'>{t('反向提取')}</bk-radio>
              </bk-radio-group>
              <bk-alert
                class='extraction-direction-tips'
                showIcon={false}
                type='info'
              >
                <template slot='title'>
                  <span class='bk-icon icon-info-circle extraction-tips-icon' />
                  <div class='extraction-tips-content'>
                    {extractionDirection.value === 'forward' ? (
                      <i18n
                        path='将向{0}符合提取范围的主机提取：以下{1}个文件'
                        tag='div'
                      >
                        <strong class='extraction-tips-emphasis'>{t('所有')}</strong>
                        <span class='selected-files-count'>{selectedFiles.value.length}</span>
                      </i18n>
                    ) : (
                      [
                        <i18n
                          path='将向{0}符合提取范围的主机提取：'
                          tag='div'
                        >
                          <strong class='extraction-tips-emphasis'>{t('所有')}</strong>
                        </i18n>,
                        <i18n
                          path='{0}之外的{1}文件'
                          tag='div'
                        >
                          <i18n
                            class='excluded-files-text'
                            path='除去以下{0}个文件'
                            tag='span'
                          >
                            <span class='selected-files-count'>{selectedFiles.value.length}</span>
                          </i18n>
                          <strong class='extraction-tips-emphasis'>{t('所有')}</strong>
                        </i18n>,
                      ]
                    )}
                  </div>
                </template>
              </bk-alert>
            </div>
            <div class='selected-files-list'>
              {selectedFiles.value.map(file => (
                <div
                  key={file.path}
                  class='selected-file-item'
                >
                  <div class='selected-file-info'>
                    <div
                      class='selected-file-path'
                      v-bk-overflow-tips
                    >
                      {file.path}
                    </div>
                    <div
                      class='selected-file-ip'
                      v-bk-overflow-tips
                    >
                      {file.ip || '--'}
                    </div>
                  </div>
                  <span
                    class='bk-icon icon-close remove-selected-file'
                    aria-label={t('移除')}
                    title={t('移除')}
                    onClick={() => removeSelectedFile(file.path)}
                  />
                </div>
              ))}
              {!selectedFiles.value.length && <div class='selected-files-empty'>{t('暂无已选文件')}</div>}
            </div>
          </div>
        </aside>
      </div>
    );
  },
});
