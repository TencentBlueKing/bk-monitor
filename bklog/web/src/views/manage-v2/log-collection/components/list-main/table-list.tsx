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

import { defineComponent, onBeforeUnmount, onMounted, ref, nextTick, watch } from 'vue';

import useLocale from '@/hooks/use-locale';
// import useStore from '@/hooks/use-store';
import ItemSkeleton from '@/skeleton/item-skeleton';
import tippy, { type Instance } from 'tippy.js';
// import { useRouter } from 'vue-router/composables';

import { useCollectList } from '../../hook/useCollectList';
import { STATUS_ENUM, SETTING_FIELDS, MENU_LIST } from '../../utils';
import TagMore from '../common-comp/tag-more';

import './table-list.scss';

export default defineComponent({
  name: 'TableList',
  props: {
    indexSet: {
      type: Object,
      default: () => ({}),
    },
    data: {
      type: Array,
      default: () => [],
    },
    loading: {
      type: Boolean,
      default: false,
    },
  },

  emits: ['width-change'],

  setup(props) {
    const { t } = useLocale();
    // const router = useRouter();
    // const store = useStore();
    // 使用自定义 hook 管理状态
    const { authGlobalInfo, operateHandler, checkCreateAuth } = useCollectList();

    let tippyInstances: Instance[] = [];

    const pagination = {
      current: 1,
      count: props.data.length,
      limit: 10,
    };
    const settingFields = SETTING_FIELDS;
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
      const info = STATUS_ENUM.find(item => item.value === key);
      return info ? <span class={`table-status ${info.value}`}>{info.text}</span> : '--';
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
        'min-width': 100,
      },
      {
        label: t('总用量'),
        prop: 'total_usage',
        sortable: true,
        'min-width': 100,
      },
      {
        label: t('存储名'),
        prop: 'table_id_prefix',
        'min-width': 120,
      },
      {
        label: t('所属索引集'),
        prop: 'index_set_name',
        width: 200,
        renderFn: (row: any) => (
          <TagMore
            tags={row.index_set_name}
            title={t('所属索引集')}
          />
        ),
      },
      {
        label: t('接入类型'),
        prop: 'category_name',
        width: 100,
        filters: [
          { text: '日志采集', value: 'log' },
          { text: 'BCS', value: 'BCS' },
        ],
      },
      {
        label: t('日志类型'),
        prop: 'collector_scenario_name',
        width: 100,
        filters: [
          { text: '行日志', value: 'row' },
          { text: '段日志', value: 'segment' },
        ],
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
        showTips: false,
        renderFn: (row: any) => (
          <TagMore
            tags={row.tags}
            title={t('标签')}
          />
        ),
        width: 200,
      },
      {
        label: t('采集状态'),
        prop: 'status',
        width: 100,
        renderFn: (row: any) => renderStatus(row.status),
        filters: STATUS_ENUM,
      },
      {
        label: t('创建人'),
        prop: 'created_by',
        width: 100,
        filters: [
          { text: 'hello', value: 'hello' },
          { text: 'test', value: 'test' },
        ],
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
        filters: [
          { text: 'hello', value: 'hello' },
          { text: 'test', value: 'test' },
        ],
      },
      {
        label: t('更新时间'),
        prop: 'updated_at',
        sortable: true,
        width: 180,
      },
    ]);

    /** 销毁所有tippy */
    const destroyTippyInstances = () => {
      // biome-ignore lint/complexity/noForEach: <explanation>
      tippyInstances.forEach(i => {
        try {
          i.hide();
          i.destroy();
        } catch (_) {}
      });
      tippyInstances = [];
    };
    watch(
      () => props.loading,
      val => {
        if (!val) {
          nextTick(() => {
            initMenuPop();
          });
        }
      },
      { immediate: true },
    );

    /** 渲染操作下拉列表 */
    const initMenuPop = () => {
      // 销毁旧实例，避免重复绑定
      destroyTippyInstances();

      const targets = document.querySelectorAll(
        '.v2-log-collection-table .bk-table-fixed-body-wrapper .table-more-btn',
      );
      if (!targets.length) {
        return;
      }

      const instances = tippy(targets as unknown as HTMLElement[], {
        trigger: 'click',
        placement: 'bottom-end',
        theme: 'light table-menu-popover',
        interactive: true,
        hideOnClick: true,
        arrow: false,
        offset: [0, 4],
        appendTo: () => document.body,
        onShow(instance) {
          (instance.reference as HTMLElement).classList.add('is-hover');
        },
        onHide(instance) {
          (instance.reference as HTMLElement).classList.remove('is-hover');
        },
        content(reference) {
          const btn = reference as HTMLElement;
          // 约定：内容紧跟在按钮后的兄弟元素中
          const container = btn.nextElementSibling as HTMLElement | null;
          const contentNode = container?.querySelector('.row-menu-content') as HTMLElement | null;
          return (contentNode ?? container ?? document.createElement('div')) as unknown as Element;
        },
      });

      // tippy 返回单个或数组，这里统一转为数组
      tippyInstances = Array.isArray(instances) ? instances : [instances];
    };

    onMounted(() => {
      nextTick(() => {
        !authGlobalInfo.value && checkCreateAuth();
      });
    });

    onBeforeUnmount(() => {
      destroyTippyInstances();
    });

    const handleMenuClick = (key: string, row: any) => {
      // 关闭 tippy
      tippyInstances.forEach(i => i?.hide());
      // 业务处理
      console.log(key, row);
    };
    const handlePageChange = (page: number) => {
      console.log(page);
    };
    const handlePageLimitChange = (limit: number) => {
      console.log(limit);
    };
    /** 新增采集项 */
    const handleCreateOperation = () => {
      operateHandler({}, 'add');
    };
    /** 表格过滤 */
    const handleFilterMethod = (value, row, column) => {
      const property = column.property;
      // console.log(value, row, column, 'handleFilterMethod', property);
      return row[property] === value;
    };

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
              onClick={handleCreateOperation}
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
            placeholder={t('搜索 采集名、存储名、索引集、集群名、创建人、更新人')}
          />
        </div>
        <div class='v2-log-collection-table-main'>
          {props.loading ? (
            <ItemSkeleton
              style={{ padding: '0 16px' }}
              columns={5}
              gap={'14px'}
              rowHeight={'28px'}
              rows={6}
              widths={['25%', '25%', '20%', '20%', '10%']}
            />
          ) : (
            <bk-table
              ext-cls='collection-table-box'
              data={props.data}
              pagination={pagination}
              on-page-change={handlePageChange}
              on-page-limit-change={handlePageLimitChange}
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
                        return (item as any)?.renderFn(row);
                      }
                      return row[item.prop] ?? '--';
                    },
                  }}
                  filter-method={handleFilterMethod}
                  filters={item?.filters}
                  fixed={!!item.fixed}
                  label={item.label}
                  min-width={item['min-width']}
                  prop={item.prop}
                  show-overflow-tooltip={!!item.showTips}
                  sortable={!!item?.sortable}
                />
              ))}
              <bk-table-column
                width={70}
                class='table-operation'
                scopedSlots={{
                  default: ({ row }) => {
                    return (
                      <div>
                        <span class='link mr-6'>{t('检索')}</span>
                        <span class='link'>{t('编辑')}</span>
                        <span class='bk-icon icon-more more-btn table-more-btn' />
                        <div
                          style={{ display: 'none' }}
                          class='row-menu-popover'
                        >
                          <div class='row-menu-content'>
                            {MENU_LIST.map(item => (
                              <span
                                key={item.key}
                                class='menu-item'
                                on-Click={(e: MouseEvent) => handleMenuClick(item.key, row, e)}
                              >
                                {item.label}
                              </span>
                            ))}
                          </div>
                        </div>
                      </div>
                    );
                  },
                }}
                fixed={'right'}
                label={t('操作')}
              />
              <bk-table-column
                tippy-options={{ zIndex: 3000 }}
                type='setting'
              >
                <bk-table-setting-content
                  fields={settingFields}
                  // :selected="setting.selectedFields"
                  // @setting-change="handleSettingChange"
                />
              </bk-table-column>
            </bk-table>
          )}
        </div>
      </div>
    );
  },
});
