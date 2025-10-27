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

import { defineComponent, ref, computed, watch, nextTick } from 'vue';

import { formatDate } from '@/common/util';
import EmptyStatus from '@/components/empty-status/index.vue';
import useLocale from '@/hooks/use-locale';
import useStore from '@/hooks/use-store';

import FileDatePicker from './file-date-picker.tsx';
import http from '@/api';

import './preview-files.scss';

export default defineComponent({
  name: 'PreviewFiles',
  components: {
    FileDatePicker,
    EmptyStatus,
  },
  props: {
    downloadFiles: {
      type: Array,
      default: () => [],
    },
    ipList: {
      type: Array,
      required: true,
    },
    fileOrPath: {
      type: String,
      required: true,
    },
    ipSelectNewNameList: {
      type: Array,
      required: true,
    },
  },

  setup(props, { emit, expose }) {
    const store = useStore();
    const { t } = useLocale();

    const isLoading = ref(false); // 加载状态
    const previewIp = ref<any[]>([]); // 预览IP列表
    const timeRange = ref('1w'); // 时间跨度 ["1d", "1w", "1m", "all", "custom"]
    const timeValue = ref<string[]>([]); // 时间值
    const isSearchChild = ref(false); // 是否搜索子目录
    const explorerList = ref<any[]>([]); // 文件列表
    const historyStack = ref<any[]>([]); // 预览地址历史
    const emptyType = ref('empty'); // 空状态类型

    const previewTableRef = ref<any>(null);

    // 初始化时间范围（默认一周）
    const initTimeRange = () => {
      const currentTime = Date.now();
      const startTime = new Date(currentTime - 1000 * 60 * 60 * 24 * 7);
      const endTime = new Date(currentTime);
      timeValue.value = [formatDate(startTime), formatDate(endTime)];
    };

    // 初始化时间范围
    initTimeRange();

    // 时间字符串值
    const timeStringValue = computed(() => {
      return [timeValue.value[0], timeValue.value[1]];
    });

    // 监听IP列表变化
    watch(
      () => props.ipList,
      val => {
        previewIp.value.splice(0);
        if (val.length) {
          previewIp.value.push(getIpListID(val[0]));
        }
        explorerList.value.splice(0); // 选择服务器后清空表格
        historyStack.value.splice(0); // 选择服务器后清空历史堆栈
      },
    );

    // 获取文件列表
    const getExplorerList = (row: any) => {
      const { path = props.fileOrPath, size } = row;
      const cacheList = {
        exploreList: explorerList.value.splice(0),
        fileOrPath: path,
      };
      emit('update:downloadFiles', []);
      if (path === '../' && historyStack.value.length) {
        // 返回上一级
        const cache = historyStack.value.pop();
        explorerList.value = cache.exploreList;
        const { fileOrPath } = historyStack.value.at(-1);
        emit('update:fileOrPath', fileOrPath);
        return;
      }
      emit('update:fileOrPath', path);
      const ipList = getFindIpList();

      isLoading.value = true;
      emptyType.value = 'search-empty';
      http
        .request('extract/getExplorerList', {
          data: {
            bk_biz_id: store.state.bkBizId,
            ip_list: ipList,
            path: path || props.fileOrPath,
            time_range: timeRange.value,
            start_time: timeStringValue.value[0],
            end_time: timeStringValue.value[1],
            is_search_child: isSearchChild.value,
          },
        })
        .then(res => {
          if (path) {
            // 指定目录搜索
            historyStack.value.push(cacheList);
            const temp = {
              ...row,
              path: '../',
            };

            if (size === '0') {
              explorerList.value = [temp, ...res.data];
            } else {
              explorerList.value = [...res.data];
            }
          } else {
            // 搜索按钮
            historyStack.value = [];
            explorerList.value = res.data;
          }
        })
        .catch(err => {
          console.warn(err);
          emptyType.value = '500';
        })
        .finally(() => {
          isLoading.value = false;
        });
    };

    // 获取选中的IP列表
    const getFindIpList = () => {
      const ipList: any[] = [];
      let i = 0;
      for (; i < previewIp.value.length; i++) {
        const target = props.ipList.find(item => getIpListID(item) === previewIp.value[i]);
        ipList.push(target);
      }
      return ipList;
    };

    // 拼接预览地址唯一key
    const getIpListID = (option: any) => {
      return `${option.bk_host_id ?? ''}_${option.ip ?? ''}_${option.bk_cloud_id ?? ''}`;
    };

    // 父组件克隆时调用
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
      timeRange.value = timeRangeVal;
      timeValue.value = [formatDate(new Date(startTime)), formatDate(new Date(endTime))];
      isSearchChild.value = isSearchChildVal;
      const findIpList = findPreviewIpListValue(previewIpList, ipList);
      previewIp.value = findIpList.map(item => getIpListID(item));

      isLoading.value = true;
      emptyType.value = 'search-empty';
      http
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
          historyStack.value = [];
          explorerList.value = res.data;
          nextTick(() => {
            for (const newPath of downloadFiles) {
              for (const item of explorerList.value) {
                if (item.path === newPath) {
                  previewTableRef.value?.toggleRowSelection(item, true);
                  break;
                }
              }
            }
          });
        })
        .catch(e => {
          console.warn(e);
          emptyType.value = '500';
        })
        .finally(() => {
          isLoading.value = false;
        });
    };

    // 查找预览IP列表对应的值
    const findPreviewIpListValue = (previewIpList: any[], ipList: any[]) => {
      // 获取previewIpList对应的ipList参数
      if (previewIpList?.length) {
        return previewIpList.map(item => {
          return ipList.find(dItem => {
            const hostMatch = item.bk_host_id === dItem.bk_host_id;
            const ipMatch = `${item.ip}_${item.bk_cloud_id}` === `${dItem.ip}_${dItem.bk_cloud_id}`;
            if (item?.bk_host_id) {
              return hostMatch || ipMatch;
            }
            return ipMatch;
          });
        });
      }
      return [];
    };

    // 处理操作
    const handleOperation = (type: string) => {
      if (type === 'clear-filter') {
        getExplorerList({});
        return;
      }

      if (type === 'refresh') {
        emptyType.value = 'empty';
        getExplorerList({});
        return;
      }
    };

    // 处理选择变化
    const handleSelect = (selection: any[]) => {
      emit(
        'update:downloadFiles',
        selection.map(item => item.path),
      );
    };

    // 暴露方法
    expose({ getExplorerList, handleClone, getFindIpList, timeRange, timeStringValue, isSearchChild });

    // 主渲染函数
    return () => (
      <div class='preview-file-content'>
        <div class='flex-box'>
          {/* 预览地址选择框 */}
          <bk-select
            style='width: 190px; margin-right: 20px; background-color: #fff'
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
          {/* 文件日期选择框 */}
          <span style='font-size: 12px'>{t('文件日期')}：</span>
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
          {/* 是否搜索子目录 */}
          <bk-checkbox
            style='margin-right: 20px'
            data-test-id='addNewExtraction_div_isSearchSubdirectory'
            value={isSearchChild.value}
            {...{
              on: {
                change: (val: boolean) => (isSearchChild.value = val),
              },
            }}
          >
            {t('是否搜索子目录')}
          </bk-checkbox>
          <bk-button
            data-test-id='addNewExtraction_button_searchFilterCondition'
            disabled={!(props.ipList.length && props.fileOrPath)}
            loading={isLoading.value}
            size='small'
            theme='primary'
            onClick={() => getExplorerList({})}
          >
            {t('搜索')}
          </bk-button>
        </div>

        {/* 表格标题 */}
        <span class='table-head-text'>{t('从下载目标中选择预览目标')}</span>

        {/* 文件列表表格 */}
        <div
          class='flex-box'
          v-bkloading={{ isLoading: isLoading.value, opacity: 0.7, zIndex: 0 }}
        >
          <bk-table
            ref={previewTableRef}
            style='background-color: #fff'
            height={360}
            class='preview-scroll-table'
            scopedSlots={{
              empty: () => (
                <div>
                  <EmptyStatus
                    empty-type={emptyType.value}
                    on-operation={handleOperation}
                  >
                    {emptyType.value === 'search-empty' && (
                      <div>{t('可以尝试{0}或{1}', { 0: t('调整预览地址'), 1: t('调整文件日期') })}</div>
                    )}
                  </EmptyStatus>
                </div>
              ),
            }}
            data={explorerList.value}
            on-selection-change={handleSelect}
          >
            {/* 选择列 */}
            <bk-table-column
              width={60}
              selectable={(row: any) => row.size !== '0'}
              type='selection'
            />

            {/* 文件名列 */}
            <bk-table-column
              scopedSlots={{
                default: ({ row }: any) => (
                  <div class='table-ceil-container'>
                    {row.size === '0' ? (
                      <span
                        class='download-url-text'
                        v-bk-overflow-tips
                        onClick={() => getExplorerList(row)}
                      >
                        {row.path}
                      </span>
                    ) : (
                      <span v-bk-overflow-tips>{row.path}</span>
                    )}
                  </div>
                ),
              }}
              label={t('文件名')}
              min-width={400}
              prop='path'
              renderHeader={() => <span>{t('文件名')}</span>}
              sortBy={['path', 'mtime', 'size']}
              sortable
            />

            {/* 最后修改时间列 */}
            <bk-table-column
              label={t('最后修改时间')}
              min-width={40}
              prop='mtime'
              renderHeader={() => <span>{t('最后修改时间')}</span>}
              sortBy={['mtime', 'path', 'size']}
              sortable
            />

            {/* 文件大小列 */}
            <bk-table-column
              label={t('文件大小')}
              min-width={30}
              prop='size'
              renderHeader={() => <span>{t('文件大小')}</span>}
              sortBy={['size', 'mtime', 'path']}
              sortable
            />
          </bk-table>
        </div>
      </div>
    );
  },
});
