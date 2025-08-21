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

import { computed, defineComponent, onBeforeUnmount, onMounted, ref } from 'vue';

import useLocale from '@/hooks/use-locale';

import { utcFormatDate } from '../../../../../common/util';
import { STATUS_ENUM } from '../../utils';
import { mockList } from './data.ts';

import './table-list.scss';

export default defineComponent({
  name: 'TableList',
  props: {
    indexSet: {
      type: Object,
      default: () => ({}),
    },
  },

  emits: ['width-change'],

  setup(props, { emit }) {
    const { t } = useLocale();
    /** 列表数据 */
    const data = mockList;
    const pagination = {
      current: 1,
      count: 500,
      limit: 20,
    };
    const settingFields = [
      // 数据ID
      {
        id: 'bk_data_id',
        label: t('数据ID'),
      },
      // 采集配置名称
      {
        id: 'collector_config_name',
        label: t('名称'),
        disabled: true,
      },
      // 用量展示
      {
        id: 'storage_usage',
        label: t('日用量/总用量'),
        disabled: true,
      },
      // 存储名
      {
        id: 'table_id',
        label: t('存储名'),
      },
      // 日志类型
      {
        id: 'collector_scenario_name',
        label: t('日志类型'),
      },
      // 过期时间
      {
        id: 'retention',
        label: t('过期时间'),
      },
      {
        id: 'label',
        label: t('标签'),
      },
      // 采集状态
      {
        id: 'es_host_state',
        label: t('采集状态'),
      },
      // 更新人
      {
        id: 'updated_by',
        label: t('更新人'),
      },
      // 更新时间
      {
        id: 'updated_at',
        label: t('更新时间'),
      },
      // 存储集群
      {
        id: 'storage_cluster_name',
        label: t('存储集群'),
      },
      // 数据类型
      {
        id: 'category_name',
        label: t('数据类型'),
      },
    ];
    const data2 = [
      {
        name: '实例状态',
        id: '1',
        multiable: true,
        children: [
          {
            name: '创建中',
            id: '1-2',
          },
          {
            name: '运行中',
            id: '1-3',
          },
          {
            name: '已关机',
            id: '1-4',
          },
        ],
      },
      {
        name: '实例业务',
        id: '2',
        multiable: true,
        children: [
          {
            name: '王者荣耀',
            id: '2-1',
          },
          {
            name: '刺激战场',
            id: '2-2',
          },
          {
            name: '绝地求生',
            id: '2-3',
          },
        ],
        conditions: [
          {
            name: '>',
            id: '>',
          },
          {
            name: '>=',
            id: '>=',
          },
        ],
      },
    ];
    /** 状态渲染 */
    const renderStatus = (key: string) => {
      const info = STATUS_ENUM.find(item => item.key === key);
      return info ? <span class={`table-status ${info.key}`}>{info.label}</span> : '--';
    };

    const columns = ref([
      {
        label: t('采集名'),
        prop: 'collector_config_name',
        sortable: true,
        renderFn: (row: any) => <span class='link'>{row.collector_config_name}</span>,
        fixed: 'left',
        'min-width': 180,
      },
      {
        label: t('日用量'),
        prop: 'daily_usage',
        sortable: true,
        'min-width': 80,
      },
      {
        label: t('总用量'),
        prop: 'total_usage',
        sortable: true,
        'min-width': 80,
      },
      {
        label: t('存储名'),
        prop: 'table_id_prefix',
        'min-width': 120,
      },
      {
        label: t('所属索引集'),
        prop: 'collector_config_name',
        'min-width': 140,
      },
      {
        label: t('接入类型'),
        prop: 'category_name',
        width: 100,
      },
      {
        label: t('日志类型'),
        prop: 'collector_scenario_name',
        width: 100,
      },
      {
        label: t('集群名'),
        prop: 'storage_cluster_name',
        'min-width': 140,
      },
      {
        label: t('过期时间'),
        prop: 'retention',
        renderFn: (row: any) => (
          <span class={{ 'text-disabled': row.status === 'stop' }}>
            {row.retention ? `${row.retention} ${t('天')}` : '--'}
          </span>
        ),
        width: 100,
      },
      {
        label: t('标签'),
        prop: 'tags',
        renderFn: (row: any) => (
          <span>
            {row.tags.map(item => (
              <span
                key={item.id}
                class='table-tag'
              >
                {item.name}
              </span>
            ))}
          </span>
        ),
        'min-width': 100,
      },
      {
        label: t('采集状态'),
        prop: 'status',
        width: 100,
        renderFn: (row: any) => renderStatus(row.status),
      },
      {
        label: t('创建人'),
        prop: 'created_by',
        width: 100,
      },
      {
        label: t('创建时间'),
        prop: 'created_at',
        sortable: true,
        width: 180,
      },
      {
        label: t('更新人'),
        width: 100,
        prop: 'updated_by',
      },
      {
        label: t('更新时间'),
        prop: 'updated_at',
        sortable: true,
        width: 180,
      },
    ]);
    return () => (
      <div class='v2-log-collection-table'>
        <div class='v2-log-collection-table-header'>
          {props.indexSet.label}
          <span class='table-header-count'>{props.indexSet.count}</span>
        </div>
        <div class='v2-log-collection-table-tool'>
          <div class='tool-btns'>
            <bk-button
              icon='plus'
              theme='primary'
            >
              {t('采集项')}
            </bk-button>
            {/* <bk-button
              class='ml-8'
              theme='default'
            >
              {t('批量编辑')}
            </bk-button> */}
          </div>
          <bk-search-select
            class='tool-search-select'
            data={data2}
            placeholder={t('搜索 采集名、存储名、索引集、接入类型、日志类型、集群名、采集状态、创建人、更新人')}
          ></bk-search-select>
        </div>
        <div class='v2-log-collection-table-main'>
          <bk-table
            ext-cls='v2-log-collection-table'
            data={data}
            pagination={pagination}
            // @row-mouse-enter="handleRowMouseEnter"
            // @row-mouse-leave="handleRowMouseLeave"
            // @page-change="handlePageChange"
            // @page-limit-change="handlePageLimitChange"
            // @selection-change="handleSelectionChange"
          >
            {columns.value.map((item, ind) => (
              <bk-table-column
                key={`${item.prop}_${ind}`}
                width={item.width}
                scopedSlots={{
                  default: ({ row }) => {
                    /** 自定义 */
                    if (item?.renderFn) {
                      return item?.renderFn(row);
                    }
                    return row[item.prop] === undefined || row[item.prop] === null ? '--' : row[item.prop];
                  },
                }}
                fixed={!!item.fixed}
                label={item.label}
                min-width={item['min-width']}
                prop={item.prop}
                show-overflow-tooltip={true}
                sortable={!!item?.sortable}
              />
            ))}
            <bk-table-column
              width={70}
              class='table-operation'
              fixed={'right'}
              label={t('操作')}
            >
              <span class='link mr-6'>{t('检索')}</span>
              <span class='link'>{t('编辑')}</span>
              <span class='bk-icon icon-more more-btn'></span>
            </bk-table-column>
            <bk-table-column
              tippy-options={{ zIndex: 3000 }}
              type='setting'
            >
              <bk-table-setting-content
                fields={settingFields}
                // :selected="setting.selectedFields"
                // @setting-change="handleSettingChange"
              ></bk-table-setting-content>
            </bk-table-column>
          </bk-table>
        </div>
      </div>
    );
  },
});
