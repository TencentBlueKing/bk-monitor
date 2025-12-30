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

import { computed, defineComponent, ref, watch } from 'vue';

import { downFile, formatFileSize } from '@/common/util';
import EmptyStatus from '@/components/empty-status/index.vue';

import { t } from '@/hooks/use-locale';
import * as authorityMap from '../../../../common/authority-map';
import useStore from '@/hooks/use-store';
import { useTableSetting } from '../hooks/use-table-setting';
import { useSearchTask } from '../hooks/use-search-task';
import { FileUploadStatus, UserReportItem } from './types';

import './report-table.scss';

export default defineComponent({
  name: 'ReportTable',
  components: {
    EmptyStatus,
  },
  props: {
    data: {
      type: Array as () => UserReportItem[],
      default: () => [],
    },
    keyword: {
      type: String,
      default: '',
    },
    total: {
      type: Number,
      default: 0,
    },
    loading: {
      type: Boolean,
      default: false,
    },
    isAllowedDownload: {
      type: Boolean,
      default: false,
    },
    indexSetId: {
      type: String,
      default: '',
    },
    paginationConfig: {
      type: Object,
      default: () => ({
        limit: 10,
        limitList: [10, 20, 50, 100],
      }),
    },
  },
  emits: ['page-change', 'page-limit-change', 'search', 'sort-change', 'upload'],
  setup(props, { emit }) {
    const store = useStore();

    const reportTableRef = ref(null);

    // 分页配置
    const pagination = ref({
      current: 1,
      count: props.total,
      limit: props.paginationConfig.limit,
      limitList: props.paginationConfig.limitList,
    });

    // 表格字段配置
    const tableFields = [
      { id: 'openid', label: 'openid', disabled: true },
      { id: 'file_name', label: t('文件名称') },
      { id: 'file_path', label: t('文件路径') },
      { id: 'file_size', label: t('文件大小') },
      { id: 'md5', label: t('文件MD5') },
      { id: 'status', label: t('上传状态') },
      { id: 'report_time', label: t('文件上传时间') },
      { id: 'xid', label: t('设备ID') },
      { id: 'extend_info', label: t('扩展信息') },
      { id: 'manufacturer', label: t('手机厂商') },
      { id: 'model', label: t('型号') },
      { id: 'os_version', label: t('系统版本') },
      { id: 'os_sdk', label: t('SDK版本') },
      { id: 'os_type', label: t('系统类型') },
    ];

    // 默认显示的字段ID
    const defaultSelectedIds = ['openid', 'file_name', 'file_path', 'file_size', 'md5', 'status', 'report_time', 'xid'];

    // 使用表格设置 hook
    const { columnSetting, checkFields, handleSettingChange } = useTableSetting({
      cacheKey: 'userReport',
      fields: tableFields,
      defaultSelectedIds,
    });

    // 使用检索任务 Hook
    const { searchTask } = useSearchTask({
      indexSetId: props.indexSetId,
    });

    // 分页变化事件处理函数
    const handlePageChange = (current: number) => {
      pagination.value.current = current;
      emit('page-change', current);
    };

    // 分页限制变化事件处理函数
    const handlePageLimitChange = (limit: number) => {
      pagination.value.limit = limit;
      pagination.value.current = 1;
      emit('page-limit-change', limit);
    };

    // 清空搜索
    const clearSearch = () => {
      emit('search', '');
    };

    // 空状态类型
    const emptyType = computed(() => {
      return props.keyword ? 'search-empty' : 'empty';
    });

    // openid 插槽
    const openidSlot = {
      default: ({ row }) => (
        <div
          class='overflow-hidden-text'
          v-bk-overflow-tips
        >
          {row.openid}
        </div>
      ),
    };

    // 文件名称插槽
    const fileNameSlot = {
      default: ({ row }) => (
        <div
          class='overflow-hidden-text'
          v-bk-overflow-tips
        >
          {row.file_name}
        </div>
      ),
    };

    // 文件路径插槽
    const filePathSlot = {
      default: ({ row }) => (
        <div
          class='overflow-hidden-text'
          v-bk-overflow-tips
        >
          {row.file_path}
        </div>
      ),
    };

    // 文件MD5插槽
    const md5Slot = {
      default: ({ row }) => (
        <div
          class='overflow-hidden-text'
          v-bk-overflow-tips
        >
          {row.md5}
        </div>
      ),
    };

    // 上传状态插槽
    const statusSlot = {
      default: ({ row }: { row: UserReportItem }) => {
        const getStatusText = () => {
          if (row.status === FileUploadStatus.RUNNING) return t('上传中');
          if (row.status === FileUploadStatus.SUCCESS) return t('完成');
          if (row.status === FileUploadStatus.FAILED) return t('失败');
          return t('未上传');
        };

        return (
          <div
            class='status-container'
            key={row.status}
          >
            {row.status === FileUploadStatus.RUNNING ? (
              <bk-spin
                size='mini'
                class='status-spin'
              ></bk-spin>
            ) : (
              <div class='status-dot-wrapper'>
                <span class={`status-dot ${row.status}`}></span>
              </div>
            )}
            <span>{getStatusText()}</span>
          </div>
        );
      },
    };

    // 设备ID插槽
    const xidSlot = {
      default: ({ row }) => (
        <div
          class='overflow-hidden-text'
          v-bk-overflow-tips
        >
          {row.xid}
        </div>
      ),
    };

    // 扩展信息插槽
    const extendInfoSlot = {
      default: ({ row }) => (
        <div
          class='overflow-hidden-text'
          v-bk-overflow-tips
        >
          {row.extend_info}
        </div>
      ),
    };

    // 手机厂商插槽
    const manufacturerSlot = {
      default: ({ row }) => (
        <div
          class='overflow-hidden-text'
          v-bk-overflow-tips
        >
          {row.manufacturer}
        </div>
      ),
    };

    // 型号插槽
    const modelSlot = {
      default: ({ row }) => (
        <div
          class='overflow-hidden-text'
          v-bk-overflow-tips
        >
          {row.model}
        </div>
      ),
    };

    // 系统版本插槽
    const osVersionSlot = {
      default: ({ row }) => (
        <div
          class='overflow-hidden-text'
          v-bk-overflow-tips
        >
          {row.os_version}
        </div>
      ),
    };

    // SDK版本插槽
    const osSdkSlot = {
      default: ({ row }) => (
        <div
          class='overflow-hidden-text'
          v-bk-overflow-tips
        >
          {row.os_sdk}
        </div>
      ),
    };

    // 系统类型插槽
    const osTypeSlot = {
      default: ({ row }) => (
        <div
          class='overflow-hidden-text'
          v-bk-overflow-tips
        >
          {row.os_type}
        </div>
      ),
    };

    // 检索任务 - 直接传入查询条件
    const handleSearchTask = (row: UserReportItem) => {
      const conditions = [
        {
          field: 'openid',
          operator: 'is',
          value: row.openid,
        },
        {
          field: 'cos_file_name',
          operator: 'is',
          value: row.file_name,
        },
      ];
      searchTask(conditions);
    };

    // 下载文件
    const downloadFile = async (downloadUrl: string) => {
      if (props.isAllowedDownload) {
        if (downloadUrl) {
          const url = `${location.protocol}//${downloadUrl}`;
          downFile(url);
        }
      } else {
        const paramData = {
          action_ids: [authorityMap.DOWNLOAD_FILE_AUTH],
          resources: [
            {
              type: 'space',
              id: store.state.spaceUid,
            },
          ],
        };
        const res = await store.dispatch('getApplyData', paramData);
        store.commit('updateState', { authDialogData: res.data });
      }
    };

    // 排序变化事件处理函数
    const handleSortChange = (sort: any) => {
      const { prop, order } = sort;

      // 转换排序类型：descending -> DESC, ascending -> ASC
      const orderType = order === 'descending' ? 'DESC' : 'ASC';

      // 通知父组件排序变化
      emit('sort-change', {
        order_field: prop,
        order_type: orderType,
      });
    };

    // 上传文件
    const handleUpload = (row: UserReportItem) => {
      emit('upload', {
        file_name_list: row.file_name ? [row.file_name] : [],
        openid_list: [],
      });
    };

    // 获取上传按钮提示文本
    const getUploadTooltipText = (status: FileUploadStatus) => {
      switch (status) {
        case FileUploadStatus.RUNNING:
          return t('正在上传中无法操作');
        case FileUploadStatus.SUCCESS:
          return t('已上传成功，请直接检索');
        default:
          return '';
      }
    };

    const operateSlot = {
      default: ({ row }: { row: UserReportItem }) => (
        <div class='log-table-operate'>
          <span
            class='king-button'
            v-bk-tooltips={{
              content: t('请上传日志后检索'),
              disabled: row.status === FileUploadStatus.SUCCESS,
            }}
          >
            <bk-button
              text
              theme='primary'
              on-click={() => handleSearchTask(row)}
              disabled={row.status !== FileUploadStatus.SUCCESS}
            >
              {t('检索')}
            </bk-button>
          </span>
          <span
            class='king-button'
            v-bk-tooltips={{
              content: getUploadTooltipText(row.status),
              disabled: row.status !== FileUploadStatus.RUNNING && row.status !== FileUploadStatus.SUCCESS,
            }}
          >
            <bk-button
              text
              theme='primary'
              on-click={() => handleUpload(row)}
              disabled={row.status !== FileUploadStatus.FAILED && row.status !== FileUploadStatus.PENDING}
            >
              {t('上传')}
            </bk-button>
          </span>
          <span class='king-button'>
            <bk-button
              text
              class={[
                {
                  'disabled-download': !props.isAllowedDownload,
                },
              ]}
              theme='primary'
              v-cursor={{
                active: !props.isAllowedDownload,
              }}
              on-click={() => downloadFile(row.download_url)}
            >
              {t('下载文件')}
            </bk-button>
          </span>
        </div>
      ),
    };

    // 监听 total 变化，更新分页配置
    watch(
      () => props.total,
      (newTotal) => {
        pagination.value.count = newTotal;
      },
    );

    return () => (
      <div class='report-table'>
        <bk-table
          data={props.data}
          pagination={pagination.value}
          outer-border={false}
          ref={reportTableRef}
          v-bkloading={{ isLoading: props.loading }}
          onPage-change={handlePageChange}
          onPage-limit-change={handlePageLimitChange}
          onSort-change={handleSortChange}
          scopedSlots={{
            empty: () => (
              <div>
                <EmptyStatus
                  emptyType={emptyType.value}
                  on-operation={clearSearch}
                />
              </div>
            ),
          }}
        >
          <bk-table-column
            key='openid'
            class-name='filter-column'
            min-width='140'
            label='openid'
            prop='openid'
            scopedSlots={openidSlot}
          />
          {checkFields('file_name') && (
            <bk-table-column
              key='file_name'
              class-name='filter-column'
              min-width='120'
              label={t('文件名称')}
              prop='file_name'
              scopedSlots={fileNameSlot}
            />
          )}
          {checkFields('file_path') && (
            <bk-table-column
              key='file_path'
              class-name='filter-column'
              min-width='200'
              label={t('文件路径')}
              prop='file_path'
              scopedSlots={filePathSlot}
            />
          )}
          {checkFields('file_size') && (
            <bk-table-column
              key='file_size'
              class-name='filter-column'
              width='100'
              label={t('文件大小')}
              prop='file_size'
              sortable='custom'
              formatter={(row: UserReportItem) => formatFileSize(row.file_size)}
            />
          )}
          {checkFields('md5') && (
            <bk-table-column
              key='md5'
              class-name='filter-column'
              min-width='200'
              label={t('文件MD5')}
              prop='md5'
              scopedSlots={md5Slot}
            />
          )}
          {checkFields('status') && (
            <bk-table-column
              key='status'
              class-name='filter-column'
              width='100'
              label={t('上传状态')}
              prop='status'
              scopedSlots={statusSlot}
            />
          )}
          {checkFields('report_time') && (
            <bk-table-column
              key='report_time'
              class-name='filter-column'
              width='240'
              label={t('文件上传时间')}
              prop='report_time'
            />
          )}
          {checkFields('xid') && (
            <bk-table-column
              key='xid'
              class-name='filter-column'
              min-width='120'
              label={t('设备ID')}
              prop='xid'
              scopedSlots={xidSlot}
            />
          )}
          {checkFields('extend_info') && (
            <bk-table-column
              key='extend_info'
              class-name='filter-column'
              min-width='120'
              label={t('扩展信息')}
              prop='extend_info'
              scopedSlots={extendInfoSlot}
            />
          )}
          {checkFields('manufacturer') && (
            <bk-table-column
              key='manufacturer'
              class-name='filter-column'
              width='100'
              label={t('手机厂商')}
              prop='manufacturer'
              scopedSlots={manufacturerSlot}
            />
          )}
          {checkFields('model') && (
            <bk-table-column
              key='model'
              class-name='filter-column'
              width='100'
              label={t('型号')}
              prop='model'
              scopedSlots={modelSlot}
            />
          )}
          {checkFields('os_version') && (
            <bk-table-column
              key='os_version'
              class-name='filter-column'
              width='100'
              label={t('系统版本')}
              prop='os_version'
              scopedSlots={osVersionSlot}
            />
          )}
          {checkFields('os_sdk') && (
            <bk-table-column
              key='os_sdk'
              class-name='filter-column'
              width='100'
              label={t('SDK版本')}
              prop='os_sdk'
              scopedSlots={osSdkSlot}
            />
          )}
          {checkFields('os_type') && (
            <bk-table-column
              key='os_type'
              class-name='filter-column'
              width='100'
              label={t('系统类型')}
              prop='os_type'
              scopedSlots={osTypeSlot}
            />
          )}
          <bk-table-column
            label={t('操作')}
            width='150'
            fixed='right'
            scopedSlots={operateSlot}
          />
          <bk-table-column
            type='setting'
            key='setting'
            tippy-options={{ zIndex: 3000 }}
          >
            <bk-table-setting-content
              v-en-style='width: 530px'
              fields={columnSetting.value.fields}
              selected={columnSetting.value.selectedFields}
              on-setting-change={handleSettingChange}
            />
          </bk-table-column>
        </bk-table>
      </div>
    );
  },
});
