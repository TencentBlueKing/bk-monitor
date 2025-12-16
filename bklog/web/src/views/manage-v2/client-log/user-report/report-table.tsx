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

import { computed, defineComponent, onMounted, ref, watch } from 'vue';

import { getDefaultSettingSelectFiled, setDefaultSettingSelectFiled } from '@/common/util';
import EmptyStatus from '@/components/empty-status/index.vue';

import { t } from '@/hooks/use-locale';

import './report-table.scss';

export default defineComponent({
  name: 'ReportTable',
  components: {
    EmptyStatus,
  },
  props: {
    data: {
      type: Array,
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
  },
  emits: ['page-change', 'page-limit-change', 'search'],
  setup(props, { emit }) {
    const reportTableRef = ref(null);
    const settingCacheKey = 'userReport';

    // 分页配置
    const pagination = ref({
      current: 1,
      count: props.total,
      limit: 10,
      limitList: [10, 20, 50, 100],
    });

    // 表格字段配置
    const settingFields = ref([
      { id: 'openid', label: 'openid', disabled: true },
      { id: 'file_name', label: t('文件名称') },
      { id: 'file_path', label: t('文件路径') },
      { id: 'file_size', label: t('文件大小') },
      { id: 'md5', label: t('文件MD5') },
      { id: 'report_time', label: t('文件上传时间') },
      { id: 'xid', label: t('设备ID') },
      { id: 'extend_info', label: t('扩展信息') },
      { id: 'manufacturer', label: t('手机厂商') },
      { id: 'model', label: t('型号') },
      { id: 'os_version', label: t('系统版本') },
      { id: 'os_sdk', label: t('SDK版本') },
      { id: 'os_type', label: t('系统类型') },
    ]);

    // 列设置配置
    const columnSetting = ref({
      fields: settingFields.value,
      selectedFields: settingFields.value.slice(0, 8), // 默认显示前8个字段
    });

    // 检查字段是否显示
    const checkFields = (field: string) => {
      return columnSetting.value.selectedFields.some(item => item.id === field);
    };

    // 设置变化处理
    const handleSettingChange = ({ fields }) => {
      columnSetting.value.selectedFields.splice(0, columnSetting.value.selectedFields.length, ...fields);
      setDefaultSettingSelectFiled(settingCacheKey, fields);
    };

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
      default: ({ row }) => <span class='overflow-hidden-text'>{row.openid}</span>,
    };

    // 文件名称插槽
    const fileNameSlot = {
      default: ({ row }) => <span class='overflow-hidden-text'>{row.file_name}</span>,
    };

    // 文件路径插槽
    const filePathSlot = {
      default: ({ row }) => <span class='overflow-hidden-text'>{row.file_path}</span>,
    };

    // 扩展信息插槽
    const extendInfoSlot = {
      default: ({ row }) => <span class='overflow-hidden-text'>{row.extend_info}</span>,
    };

    // 监听 total 变化，更新分页配置
    watch(
      () => props.total,
      (newTotal) => {
        pagination.value.count = newTotal;
      },
    );

    onMounted(() => {
      const { selectedFields } = columnSetting.value;
      columnSetting.value.selectedFields = getDefaultSettingSelectFiled(settingCacheKey, selectedFields);
    });

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
            class-name='filter-column overflow-hidden-text'
            min-width='140'
            label='openid'
            prop='openid'
            scopedSlots={openidSlot}
          />
          {checkFields('file_name') && (
            <bk-table-column
              key='file_name'
              class-name='filter-column overflow-hidden-text'
              min-width='120'
              label={t('文件名称')}
              prop='file_name'
              scopedSlots={fileNameSlot}
            />
          )}
          {checkFields('file_path') && (
            <bk-table-column
              key='file_path'
              class-name='filter-column overflow-hidden-text'
              min-width='200'
              label={t('文件路径')}
              prop='file_path'
              scopedSlots={filePathSlot}
            />
          )}
          {checkFields('file_size') && (
            <bk-table-column
              key='file_size'
              class-name='filter-column overflow-hidden-text'
              width='100'
              label={t('文件大小')}
              prop='file_size'
            />
          )}
          {checkFields('md5') && (
            <bk-table-column
              key='md5'
              class-name='filter-column overflow-hidden-text'
              min-width='200'
              label={t('文件MD5')}
              prop='md5'
            />
          )}
          {checkFields('report_time') && (
            <bk-table-column
              key='report_time'
              class-name='filter-column overflow-hidden-text'
              width='160'
              label={t('文件上传时间')}
              prop='report_time'
            />
          )}
          {checkFields('xid') && (
            <bk-table-column
              key='xid'
              class-name='filter-column overflow-hidden-text'
              min-width='120'
              label={t('设备ID')}
              prop='xid'
            />
          )}
          {checkFields('extend_info') && (
            <bk-table-column
              key='extend_info'
              class-name='filter-column overflow-hidden-text'
              min-width='120'
              label={t('扩展信息')}
              prop='extend_info'
              scopedSlots={extendInfoSlot}
            />
          )}
          {checkFields('manufacturer') && (
            <bk-table-column
              key='manufacturer'
              class-name='filter-column overflow-hidden-text'
              width='100'
              label={t('手机厂商')}
              prop='manufacturer'
            />
          )}
          {checkFields('model') && (
            <bk-table-column
              key='model'
              class-name='filter-column overflow-hidden-text'
              width='100'
              label={t('型号')}
              prop='model'
            />
          )}
          {checkFields('os_version') && (
            <bk-table-column
              key='os_version'
              class-name='filter-column overflow-hidden-text'
              width='100'
              label={t('系统版本')}
              prop='os_version'
            />
          )}
          {checkFields('os_sdk') && (
            <bk-table-column
              key='os_sdk'
              class-name='filter-column overflow-hidden-text'
              width='100'
              label={t('SDK版本')}
              prop='os_sdk'
            />
          )}
          {checkFields('os_type') && (
            <bk-table-column
              key='os_type'
              class-name='filter-column overflow-hidden-text'
              width='100'
              label={t('系统类型')}
              prop='os_type'
            />
          )}
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
