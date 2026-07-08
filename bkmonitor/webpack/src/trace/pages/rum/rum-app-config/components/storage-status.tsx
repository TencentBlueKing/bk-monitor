/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 *
 * Copyright (C) 2017-2025 Tencent.  All rights reserved.
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
import { type PropType, computed, defineComponent, onMounted, shallowRef } from 'vue';

import { Message } from 'bkui-vue';
import { byteConvert } from 'monitor-common/utils';
import { useI18n } from 'vue-i18n';

import CommonTable from '../../../alarm-center/components/alarm-table/components/common-table/common-table';
import {
  getFieldInfoData,
  getIndicesInfoData,
  getStorageInfoData,
  updateAppStorageConfig,
} from '../services/app-config';
import EditableField from './editable-field';
import EmptyStatus from '@/components/empty-status/empty-status';
import TableSkeleton from '@/components/skeleton/table-skeleton';
import TextOverflowCopy from '@/components/text-overflow-copy/text-overflow-copy';

import type { BaseTableColumn } from '../../../trace-explore/components/trace-explore-table/typing';
import type { IIndicesInfo, IRumAppConfig, IStorageField, IStorageInfo } from '../../typings/rum-app-config';

import './storage-status.scss';

/** 索引信息表格列名映射 */
export const indicesInfoTableColumnKey = {
  Index: 'index',
  Health: 'health',
  Pri: 'pri',
  Rep: 'rep',
  DocsCount: 'docs_count',
  StoreSize: 'store_size',
};

/** 字段信息表格列名映射 */
export const fieldInfoTableColumnKey = {
  FieldName: 'field_name',
  ChFieldName: 'ch_field_name',
  FieldType: 'field_type',
  AnalysisField: 'analysis_field',
  TimeField: 'time_field',
};

/**
 * 存储状态组件
 * 展示存储信息，支持编辑存储配置
 */
export default defineComponent({
  name: 'StorageStatus',
  props: {
    detail: {
      type: Object as PropType<IRumAppConfig>,
      default: () => ({}),
    },
    /** ES集群列表 */
    clusterList: {
      type: Array as PropType<{ storage_cluster_id: string; storage_display_name: string }[]>,
      default: () => [],
    },
  },
  setup(props) {
    const { t } = useI18n();

    // 存储配置数据
    const storageData = shallowRef<IStorageInfo>({
      es_number_of_replicas: 0,
      es_retention: 14,
      es_shards: 3,
      es_slice_size: 100,
      es_storage_cluster: '',
    });

    const storageDataLoading = shallowRef(false);

    // 集群下拉选项
    const clusterOptions = computed(() => {
      return props.clusterList.map(item => ({ label: item.storage_display_name, value: item.storage_cluster_id }));
    });

    /** 校验各个字段是否符合规范 */
    const checkField = (value: number | string, field: keyof IStorageInfo) => {
      const numValue = Number(value);
      switch (field) {
        case 'es_number_of_replicas':
          if (numValue < 0) return { isPass: false, msg: t('最小副本数不能小于0') };
          if (numValue > 1) return { isPass: false, msg: t('最大副本数不能超过1') };
          break;
        case 'es_slice_size':
          if (numValue < 1) return { isPass: false, msg: t('索引切分大小不能小于1') };
          break;
        case 'es_shards':
          if (numValue < 1) return { isPass: false, msg: t('分片数不能小于1') };
          if (numValue > 3) return { isPass: false, msg: t('最大分片数不能超过3') };
          break;
        default:
          break;
      }
      return { isPass: true, msg: '' };
    };

    /**
     *  处理字段编辑，请求接口更新数据，成功返回true，失败返回false
     * @param value
     * @param field
     * @returns
     */
    const handleFieldChange = async (value: number | string, field: keyof IStorageInfo) => {
      const res = checkField(value, field);
      if (!res.isPass) return res;
      const isSuccess = await updateAppStorageConfig({
        bk_biz_id: props.detail?.bk_biz_id,
        app_name: props.detail?.app_name,
        span_datasource_config: {
          ...storageData.value,
          [field]: value,
        },
      })
        .then(() => {
          storageData.value = {
            ...storageData.value,
            [field]: value,
          };
          Message({
            message: t('修改成功'),
            theme: 'success',
          });
          return true;
        })
        .catch(() => false);

      return {
        isPass: isSuccess,
        msg: '',
      };
    };

    /** 获取存储信息 */
    const fetchStorageInfoData = async () => {
      storageDataLoading.value = true;
      storageData.value = await getStorageInfoData(
        {
          bk_biz_id: props.detail?.bk_biz_id,
          app_name: props.detail?.app_name,
        },
        {
          es_number_of_replicas: 0,
          es_retention: 14,
          es_shards: 3,
          es_slice_size: 100,
          es_storage_cluster: '',
        }
      );
      storageDataLoading.value = false;
    };

    /** 判断行数据是否满足筛选条件 */
    const rowMatchesCriteria = (row, c): boolean => {
      const keys = Object.keys(c);
      for (const key of keys) {
        const vals = c[key];
        if (!vals?.length) continue;
        const rv = row[key];
        if (!vals.includes(rv)) return false;
      }
      return true;
    };

    /** 运行状态枚举 */
    const healthMaps = {
      green: t('健康'),
      yellow: t('部分异常'),
      red: t('异常'),
    };
    /** 索引列 */
    const indicesInfoColumns = shallowRef<BaseTableColumn[]>([
      {
        colKey: indicesInfoTableColumnKey.Index,
        title: t('索引'),
        width: 280,
        cellEllipsis: true,
        cellRenderer: (row => {
          return <TextOverflowCopy val={row.index} />;
        }) as unknown as BaseTableColumn['cellRenderer'],
      },
      {
        colKey: indicesInfoTableColumnKey.Health,
        title: t('运行状态'),
        filter: {
          type: 'multiple',
          list: Object.entries(healthMaps).map(([key, value]) => ({ label: value, value: key })),
          resetValue: [],
          showConfirmAndReset: true,
        },
        cellRenderer: (row => {
          return (
            <span class='status-wrap'>
              <span class={['status-icon', `status-${row.health}`]} />
              <span class='status-name'>{healthMaps[row.health]}</span>
            </span>
          );
        }) as unknown as BaseTableColumn['cellRenderer'],
      },
      {
        colKey: indicesInfoTableColumnKey.Pri,
        title: t('主分片'),
        sorter: true,
      },
      {
        colKey: indicesInfoTableColumnKey.Rep,
        title: t('副本分片'),
        sorter: true,
      },
      {
        colKey: indicesInfoTableColumnKey.DocsCount,
        title: t('文档数量'),
        sorter: true,
      },
      {
        colKey: indicesInfoTableColumnKey.StoreSize,
        title: t('存储大小'),
        sorter: true,
        cellRenderer: (row => {
          return <span>{byteConvert(row.store_size)}</span>;
        }) as unknown as BaseTableColumn['cellRenderer'],
      },
    ]);
    /** 索引列表 */
    /** 索引列表数据 */
    const indicesInfoData = shallowRef<IIndicesInfo[]>([]);
    /** 索引表格筛选条件 */
    const indicesTableFilters = shallowRef({});
    /** 索引表格排序条件 */
    const indicesTableSorts = shallowRef('');
    const indicesInfoDataLoading = shallowRef(false);
    /** 带筛选和排序的索引表格数据 */
    const indicesTableData = computed(() => {
      const filters = indicesTableFilters.value;
      let tableData = [...indicesInfoData.value];
      if (Object.keys(filters).length) {
        tableData = indicesInfoData.value.filter(r => rowMatchesCriteria(r, filters));
      }
      if (indicesTableSorts.value) {
        const arr = indicesTableSorts.value.split('-');
        tableData = tableData.sort((a, b) => {
          return arr.length === 2 ? b[arr[1]] - a[arr[1]] : a[arr[0]] - b[arr[0]];
        });
      }
      return tableData;
    });
    /** 获取物理索引数据 */
    const fetchIndicesInfoData = async () => {
      indicesInfoDataLoading.value = true;
      indicesInfoData.value = await getIndicesInfoData({
        app_name: props.detail?.app_name,
      });
      indicesInfoDataLoading.value = false;
    };
    /** 索引表格筛选变更 */
    const handleIndicesInfoFilterChange = filters => {
      indicesTableFilters.value = filters;
    };
    /** 索引表格排序变更 */
    const handleIndicesSortChange = sorts => {
      indicesTableSorts.value = sorts;
    };

    /** 字段信息 */
    const fieldInfoColumns = computed<BaseTableColumn[]>(() => [
      {
        colKey: fieldInfoTableColumnKey.FieldName,
        title: t('字段名'),
      },
      {
        colKey: fieldInfoTableColumnKey.ChFieldName,
        title: t('别名'),
        cellRenderer: (row => {
          return <span>{row.ch_field_name || '--'}</span>;
        }) as unknown as BaseTableColumn['cellRenderer'],
      },
      {
        colKey: fieldInfoTableColumnKey.FieldType,
        title: t('数据类型'),
        filter: {
          type: 'multiple',
          list: fieldFilterList.value,
          resetValue: [],
          showConfirmAndReset: true,
        },
      },
      {
        colKey: fieldInfoTableColumnKey.AnalysisField,
        title: t('分词'),
        filter: {
          type: 'multiple',
          list: [
            { label: t('是'), value: 'yes' },
            { label: t('否'), value: 'no' },
          ],
          resetValue: [],
          showConfirmAndReset: true,
        },
        cellRenderer: (row => {
          return <span>{row.analysis_field ? t('是') : t('否')}</span>;
        }) as unknown as BaseTableColumn['cellRenderer'],
      },
      {
        colKey: fieldInfoTableColumnKey.TimeField,
        title: t('时间'),
        filter: {
          type: 'multiple',
          list: [
            { label: t('是'), value: 'yes' },
            { label: t('否'), value: 'no' },
          ],
          resetValue: [],
          showConfirmAndReset: true,
        },
        cellRenderer: (row => {
          return <span>{row.time_field ? t('是') : t('否')}</span>;
        }) as unknown as BaseTableColumn['cellRenderer'],
      },
    ]);
    /** 字段信息数据 */
    const fieldInfoData = shallowRef<IStorageField[]>([]);
    const fieldInfoDataLoading = shallowRef(false);
    /** 字段表格筛选条件 */
    const filedTableFilters = shallowRef({});
    /** 字段类型筛选列表 */
    const fieldFilterList = shallowRef([]);
    /** 带筛选的字段表格数据 */
    const fieldTableData = computed(() => {
      const filters = filedTableFilters.value;
      if (!Object.keys(filters).length) return fieldInfoData.value;
      return fieldInfoData.value.filter(r => rowMatchesCriteria(r, filters));
    });
    /**
     * @desc: 获取字段过滤列表
     * @param { Array } list 被处理的列表
     * @returns { Array } 返回值
     */
    const getFieldFilterList = list => {
      const setList = new Set();
      const filterList = [];
      for (const item of list) {
        if (!setList.has(item.field_type) && item.field_type) {
          setList.add(item.field_type);
          filterList.push({
            label: item.field_type,
            value: item.field_type,
          });
        }
      }
      return filterList;
    };

    /** 获取字段信息数据并生成字段类型筛选列表 */
    const fetchFieldInfo = async () => {
      fieldInfoDataLoading.value = true;
      fieldInfoData.value = await getFieldInfoData({
        bk_biz_id: props.detail?.bk_biz_id,
        app_name: props.detail?.app_name,
      });
      fieldFilterList.value = getFieldFilterList(fieldInfoData.value);
      fieldInfoDataLoading.value = false;
    };

    /** 字段表格筛选变更，将 yes/no 字符串转为布尔值以匹配数据 */
    const handleFieldTableFilterChange = value => {
      const filters = JSON.parse(JSON.stringify(value));
      const booleanField = [fieldInfoTableColumnKey.AnalysisField, fieldInfoTableColumnKey.TimeField];
      for (const key of booleanField) {
        if (value[key]) {
          filters[key] = value[key].map(item => item === 'yes');
        }
      }
      filedTableFilters.value = filters;
    };

    onMounted(() => {
      fetchIndicesInfoData();
      fetchFieldInfo();
      fetchStorageInfoData();
    });

    return {
      t,
      storageData,
      storageDataLoading,
      clusterOptions,
      handleFieldChange,
      indicesInfoColumns,
      indicesInfoDataLoading,
      indicesTableData,
      indicesTableSorts,
      handleIndicesInfoFilterChange,
      handleIndicesSortChange,
      fieldInfoColumns,
      fieldTableData,
      fieldInfoDataLoading,
      handleFieldTableFilterChange,
    };
  },
  render() {
    return (
      <div class='storage-status'>
        <div class='storage-info'>
          <div class='storage-status-title'>{this.t('存储信息')}</div>
          <div class='storage-status-content'>
            <div class='storage-info-row'>
              <div class='storage-info-item'>
                <EditableField
                  editable={false}
                  label={this.t('存储索引名')}
                  skeletonLoading={this.storageDataLoading}
                  value={this.detail?.es_storage_index_name || '--'}
                />
              </div>
              <div class='storage-info-item'>
                <EditableField
                  confirm={v => this.handleFieldChange(v, 'es_storage_cluster')}
                  label={this.t('存储集群')}
                  options={this.clusterOptions}
                  skeletonLoading={this.storageDataLoading}
                  type='select'
                  value={this.storageData.es_storage_cluster}
                />
              </div>
            </div>
            <div class='storage-info-row'>
              <div class='storage-info-item'>
                <EditableField
                  confirm={v => this.handleFieldChange(v, 'es_retention')}
                  label={this.t('过期时间')}
                  maxExpired={3}
                  skeletonLoading={this.storageDataLoading}
                  suffix={this.t('天')}
                  type='expired'
                  value={this.storageData.es_retention}
                />
              </div>
              <div class='storage-info-item'>
                <EditableField
                  confirm={v => this.handleFieldChange(v, 'es_number_of_replicas')}
                  label={this.t('副本数')}
                  skeletonLoading={this.storageDataLoading}
                  value={this.storageData.es_number_of_replicas}
                />
              </div>
            </div>
            <div class='storage-info-row'>
              <div class='storage-info-item'>
                <EditableField
                  confirm={v => this.handleFieldChange(v, 'es_shards')}
                  label={this.t('分片数')}
                  skeletonLoading={this.storageDataLoading}
                  value={this.storageData.es_shards}
                />
              </div>
              <div class='storage-info-item'>
                <EditableField
                  confirm={v => this.handleFieldChange(v, 'es_slice_size')}
                  label={this.t('索引切分大小')}
                  skeletonLoading={this.storageDataLoading}
                  suffix='G'
                  value={this.storageData.es_slice_size}
                />
              </div>
            </div>
          </div>
        </div>

        <div class='physical-index'>
          <div class='storage-status-title'>{this.t('物理索引')}</div>
          <div class='storage-status-content'>
            {this.indicesInfoDataLoading ? (
              <TableSkeleton />
            ) : (
              <CommonTable
                columns={this.indicesInfoColumns}
                data={this.indicesTableData as unknown as Record<string, unknown>[]}
                rowKey={indicesInfoTableColumnKey.Index}
                sort={this.indicesTableSorts}
                autoFillSpace
                onFilterChange={this.handleIndicesInfoFilterChange}
                onSortChange={this.handleIndicesSortChange}
              >
                {{
                  empty: () => <EmptyStatus type='empty' />,
                }}
              </CommonTable>
            )}
          </div>
        </div>

        <div class='field-info'>
          <div class='storage-status-title'>{this.t('字段信息')}</div>
          <div class='storage-status-content'>
            {this.fieldInfoDataLoading ? (
              <TableSkeleton />
            ) : (
              <CommonTable
                columns={this.fieldInfoColumns}
                data={this.fieldTableData as unknown as Record<string, unknown>[]}
                rowKey={fieldInfoTableColumnKey.FieldName}
                autoFillSpace
                onFilterChange={this.handleFieldTableFilterChange}
              >
                {{
                  empty: () => <EmptyStatus type='empty' />,
                }}
              </CommonTable>
            )}
          </div>
        </div>
      </div>
    );
  },
});
