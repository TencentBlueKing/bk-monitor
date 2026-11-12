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


import { useApplicationStore } from '@/app/state/domains/application-store';
import { useGlobalsStore } from '@/app/state/domains/globals-store';


import {
  Table as TTable,
  Popup as TPopup,
  Checkbox as TCheckbox,
  type PrimaryTableCol,
  type FilterValue,
} from 'tdesign-vue-next';
import { Progress as TProgress } from 'tdesign-vue-next';

import { Input as TInput, Button as TButton } from 'tdesign-vue-next';
import { SearchIcon } from 'tdesign-icons-vue-next';
import { ServicesInstance } from '@/platform/services';

import { defineComponent, ref, computed, onMounted, nextTick } from 'vue';

import * as authorityMap from '@/shared/lib/authority-map';
import { formatFileSize, isIPv6, getDefaultSettingSelectFiled, setDefaultSettingSelectFiled } from '@/shared/lib/util';
import EmptyStatus from '@/shared/ui/empty-status/index.vue';
import BklogLoading from '@/shared/ui/loading';
import useLocale from '@/shared/composables/use-locale';
import useRouter from '@/shared/composables/use-router';

import { bkInfoBox as InfoBox } from '@/platform/compat/tdesign/info-box';

import { useDrag } from '../../../management/manage-v2/hooks/use-drag';
import ClusterTypeTabs from './cluster-type-tabs.tsx';
import EsSlider from './es-slider.tsx';
import IntroPanel from './intro-panel.tsx';
import { CLUSTER_TYPES, ClusterType, useClusterType } from './use-cluster-type';

import './index.scss';

/** Source API row fields consumed by cluster actions and storage cells. */
interface ClusterActionRow {
  cluster_config: { cluster_id: number; domain_name: string };
  permission: Record<string, boolean>;
  storage_usage: number;
}

interface TText {
  text: string;
  value: string;
}

export default defineComponent({
  name: 'EsClusterMess',
  components: {
    EsSlider,
    IntroPanel,
    EmptyStatus,
    ClusterTypeTabs,
  },

  setup() {
    const store = useApplicationStore();
    const router = useRouter();
    const { t } = useLocale();

    const { maxIntroWidth, introWidth, isDraging, dragBegin } = useDrag();

    const tableLoading = ref(true); // 表格加载状态
    const tableDataOrigin = ref([]); // 原始数据
    const tableDataSearched = ref([]); // 搜索过滤数据
    const tableDataPaged = ref([]); // 前端分页
    const pagination = ref({
      count: 0,
      limit: 10,
      current: 1,
      limitList: [10, 20, 50, 100],
    });
    const stateMap = ref({}); // 连接状态映射
    const params = ref({
      keyword: '',
    });
    const isAllowedCreate = ref<boolean | null>(null); // 是否有权限新建
    const showSlider = ref(false); // 显示编辑或新建ES源侧边栏
    const editClusterId = ref(null); // 编辑ES源ID
    const editClusterData = ref<
      ({ cluster_config: { cluster_id: any }; permission: { [x: string]: any } } | null) | null
    >(null); // 编辑的集群行数据
    const isOpenWindow = ref(false); // 是否打开窗口
    const emptyType = ref('empty'); // 空状态类型
    const filterParams = ref({}); // 过滤参数对象
    const isFilterSearch = ref(false); // 是否过滤搜索
    const settingCacheKey = 'collection'; // 设置缓存键
    const searchTimer = ref<NodeJS.Timeout | null>(null); // 搜索定时器
    const accessContainerRef = ref(null); // 容器引用
    const tableFilters = ref<FilterValue>({});
    const settingsVisible = ref(false);
    const settingsDraft = ref<string[]>([]);

    // 来源状态过滤器
    const sourceStateFilters = ref([
      { text: t('正常'), value: true },
      { text: t('失败'), value: false },
    ]);

    // 设置字段配置
    const settingFields = ref([
      { id: 'cluster_id', label: 'ID', disabled: true },
      { id: 'collector_config_name', label: t('名称'), disabled: true },
      { id: 'cluster_name', label: t('英文名称') },
      { id: 'domain_name', label: t('地址'), disabled: true },
      { id: 'source_type', label: t('来源') },
      { id: 'port', label: t('端口') },
      { id: 'schema', label: t('协议') },
      { id: 'cluster_config', label: t('连接状态') },
      { id: 'enable_hot_warm', label: t('冷热数据') },
      { id: 'storage_total', label: t('总量') },
      { id: 'storage_usage', label: t('空闲率') },
      { id: 'creator', label: t('创建人') },
      { id: 'create_time', label: t('创建时间') },
    ]);

    // 集群设置
    const clusterSetting = ref({
      fields: settingFields.value,
      selectedFields: settingFields.value.slice(0, 10),
    });

    const bkBizId = computed(() => store.bkBizId); // 业务ID
    const spaceUid = computed(() => store.spaceUid); // 空间ID
    const globalsData = computed(() => useGlobalsStore().globalsData);
    const authorityMapComputed = computed(() => authorityMap); // 权限映射

    // 从路由查询参数获取初始 tab 值
    const getInitialTab = (): ClusterType => {
      const tabQuery = router.currentRoute.query.tab;
      if (tabQuery === 'doris') return CLUSTER_TYPES.DORIS;
      return CLUSTER_TYPES.ES;
    };

    const { activeTab, isDorisEnabled, checkDorisAccess, handleTabClick } = useClusterType({
      bkBizId,
      spaceUid,
      initialTab: getInitialTab(),
      onAccessDenied: () => {
        const { tab, ...restQuery } = router.currentRoute.query;
        router.replace({
          name: router.currentRoute.name,
          params: router.currentRoute.params,
          query: restQuery,
        });
      },
      onTabChange: (type) => {
        const currentQuery = { ...router.currentRoute.query };
        currentQuery.tab = type === CLUSTER_TYPES.DORIS ? 'doris' : 'es';
        router.replace({
          name: router.currentRoute.name,
          params: router.currentRoute.params,
          query: currentQuery,
        });

        params.value.keyword = '';
        tableFilters.value = {};
        filterParams.value = {};
        isFilterSearch.value = false;
        tableDataOrigin.value = [];
        tableDataSearched.value = [];
        tableDataPaged.value = [];
        pagination.value.current = 1;
        pagination.value.count = 0;

        getTableData();
      },
    });

    // 来源过滤器
    const sourceFilters = computed(() => {
      const { es_source_type: esSourceType } = globalsData.value;
      const target: TText[] = [];
      for (const data of esSourceType ?? []) {
        target.push({
          text: data.name,
          value: data.id,
        });
      }
      return target;
    });

    // 检查创建权限
    const checkCreateAuth = async () => {
      try {
        const res = await store.checkAllowed({
          action_ids: [authorityMapComputed.value.CREATE_ES_SOURCE_AUTH],
          resources: [
            {
              type: 'space',
              id: spaceUid.value,
            },
          ],
        });
        isAllowedCreate.value = res.isAllowed;
      } catch (err) {
        console.warn(err);
        isAllowedCreate.value = false;
      }
    };

    // 获取存储集群列表
    const getTableData = async () => {
      try {
        tableLoading.value = true;
        const tableRes = await ServicesInstance.source.list({
          query: {
            bk_biz_id: bkBizId.value,
            cluster_type: activeTab.value,
          },
        });
        tableLoading.value = false;
        const list = tableRes.data;
        if (!list.length) {
          return;
        }
        tableDataOrigin.value = list;
        tableDataSearched.value = list;
        pagination.value.count = list.length;
        computePageData();

        // 连接状态
        try {
          const stateRes = await ServicesInstance.source.connectionStatus({
            query: {
              bk_biz_id: bkBizId.value,
            },
            data: {
              cluster_list: list.map((item: { cluster_config: { cluster_id: any } }) => item.cluster_config.cluster_id),
            },
          });
          stateMap.value = stateRes.data;
        } catch (e) {
          console.warn(e);
          stateMap.value = {};
        }
      } catch (e) {
        console.warn(e);
        tableLoading.value = false;
        tableDataOrigin.value.splice(0);
        tableDataSearched.value.splice(0);
        pagination.value.count = 0;
      }
    };

    // 获取状态文本
    const getStateText = (id: string | number) => {
      const info = stateMap.value[id];
      const state = typeof info === 'boolean' ? info : info?.status;

      return (
        <div>
          {state === true && (
            <div class='state-container'>
              <span class='bk-badge bk-danger' /> 正常
            </div>
          )}
          {state === false && (
            <div class='state-container'>
              <span class='bk-badge bk-warning' /> 失败
            </div>
          )}
          {state !== true && state !== false && <div class='state-container'>--</div>}
        </div>
      );
    };

    // 页面变化处理
    const handlePageChange = (page: number) => {
      if (pagination.value.current === page) {
        return;
      }
      tableLoading.value = true;
      pagination.value.current = page;
      setTimeout(() => {
        computePageData();
        tableLoading.value = false;
      }, 300);
    };

    // 每页条数变化处理
    const handleLimitChange = (limit: number) => {
      if (pagination.value.limit === limit) {
        return;
      }
      tableLoading.value = true;
      pagination.value.current = 1;
      pagination.value.limit = limit;
      setTimeout(() => {
        computePageData();
        tableLoading.value = false;
      }, 300);
    };

    // 搜索处理
    const handleSearch = () => {
      // 开始加载
      tableLoading.value = true;
      // 清除之前的搜索定时器
      searchTimer.value && clearTimeout(searchTimer.value);
      // 设置新的搜索定时器
      searchTimer.value = setTimeout(() => {
        searchCallback(); // 执行搜索逻辑
        tableLoading.value = false; // 搜索完成后关闭加载状态
      }, 300);
    };

    // 搜索回调
    const searchCallback = () => {
      let filteredData = tableDataOrigin.value;

      // 先进行过滤处理
      if (isFilterSearch.value) {
        filteredData = filteredData.filter((item) =>
          Object.keys(filterParams.value).every((key) =>
            filterIsNotCompared(filterParams.value[key]) ? true : compareFilter(item, filterParams.value[key], key),
          ),
        );
      }

      // 再进行搜索处理
      const keyword = params.value.keyword.trim();
      if (keyword) {
        filteredData = filteredData.filter((item) => {
          if (isIPv6(keyword)) {
            return completeIPv6Address(item.cluster_config.domain_name) === completeIPv6Address(keyword);
          }

          // 分别判断各个字段，只要有一项满足条件即可
          const keywordLower = keyword.toLowerCase();
          const clusterName = (item.cluster_config.cluster_name || '').toLowerCase();
          const displayName = (item.cluster_config.display_name || '').toLowerCase();
          const domainName = (item.cluster_config.domain_name || '').toLowerCase();
          const creator = (item.cluster_config.creator || '').toLowerCase();

          return (
            clusterName.includes(keywordLower) ||
            displayName.includes(keywordLower) ||
            domainName.includes(keywordLower) ||
            creator.includes(keywordLower)
          );
        });
      }

      tableDataSearched.value = filteredData;
      emptyType.value = params.value.keyword || isFilterSearch.value ? 'search-empty' : 'empty';
      pagination.value.current = 1;
      pagination.value.count = filteredData.length;
      computePageData();
    };

    // ipv6补全
    const completeIPv6Address = (address: string) => {
      const sections = address.split(':');
      const missingSections = 8 - sections.length;

      for (let i = 0; i < missingSections; i++) {
        sections.splice(sections.indexOf(''), 1, '0000');
      }

      return sections
        .map((section) => {
          if (section.length < 4) {
            return '0'.repeat(4 - section.length) + section;
          }
          return section;
        })
        .join(':');
    };

    // 根据分页数据过滤表格
    const computePageData = () => {
      const { current, limit } = pagination.value;
      const start = (current - 1) * limit;
      const end = pagination.value.current * pagination.value.limit;
      tableDataPaged.value = tableDataSearched.value.slice(start, end);
    };

    // 新建ES源
    const addDataSource = async () => {
      if (isAllowedCreate.value) {
        editClusterId.value = null;
        editClusterData.value = null;
        showSlider.value = true;
      } else {
        try {
          tableLoading.value = true;
          const res = await store.getApplyData({
            action_ids: [authorityMapComputed.value.CREATE_ES_SOURCE_AUTH],
            resources: [
              {
                type: 'space',
                id: spaceUid.value,
              },
            ],
          });
          store.updateState({ authDialogData: res.data });
        } catch (err) {
          console.warn(err);
        } finally {
          tableLoading.value = false;
        }
      }
    };

    // 创建索引集
    const createIndexSet = (row: { cluster_config: { cluster_id: any } }) => {
      router.push({
        name: 'es-index-set-create',
        query: {
          spaceUid: store.spaceUid,
          cluster: row.cluster_config.cluster_id,
        },
      });
    };

    // 编辑ES源
    const editDataSource = async (
      item: { cluster_config: { cluster_id: any }; permission: { [x: string]: any } } | null,
    ) => {
      const id = item.cluster_config.cluster_id;
      if (!item.permission?.[authorityMapComputed.value.MANAGE_ES_SOURCE_AUTH]) {
        try {
          const paramData = {
            action_ids: [authorityMapComputed.value.MANAGE_ES_SOURCE_AUTH],
            resources: [
              {
                type: 'es_source',
                id,
              },
            ],
          };
          tableLoading.value = true;
          const res = await store.getApplyData(paramData);
          store.updateState({ authDialogData: res.data });
        } catch (err) {
          console.warn(err);
        } finally {
          tableLoading.value = false;
        }
        return;
      }

      editClusterId.value = id;
      editClusterData.value = item;
      showSlider.value = true;
    };

    // 删除ES源
    const deleteDataSource = async (row: {
      cluster_config: { cluster_id: any; domain_name: any };
      permission: { [x: string]: any };
    }) => {
      const id = row.cluster_config.cluster_id;
      if (!row.permission?.[authorityMapComputed.value.MANAGE_ES_SOURCE_AUTH]) {
        try {
          const paramData = {
            action_ids: [authorityMapComputed.value.MANAGE_ES_SOURCE_AUTH],
            resources: [
              {
                type: 'es_source',
                id,
              },
            ],
          };
          tableLoading.value = true;
          const res = await store.getApplyData(paramData);
          store.updateState({ authDialogData: res.data });
        } catch (err) {
          console.warn(err);
        } finally {
          tableLoading.value = false;
        }
        return;
      }

      InfoBox({
        type: 'warning',
        subTitle: t('当前集群为{n}，确认要删除？', { n: row.cluster_config.domain_name }),
        confirmFn: () => {
          handleDelete(row);
        },
      });
    };

    // 处理删除
    const handleDelete = (row: { cluster_config: { cluster_id: any } }) => {
      ServicesInstance.source
        .deleteEs({
          params: {
            bk_biz_id: bkBizId.value,
            cluster_id: row.cluster_config.cluster_id,
          },
        })
        .then((res) => {
          if (res.result) {
            if (tableDataPaged.value.length <= 1) {
              pagination.value.current = pagination.value.current > 1 ? pagination.value.current - 1 : 1;
            }
            const deleteIndex = tableDataSearched.value.findIndex((item) => {
              return item.cluster_config.cluster_id === row.cluster_config.cluster_id;
            });
            tableDataSearched.value.splice(deleteIndex, 1);
            computePageData();
          }
        })
        .catch(() => {});
    };

    // 新建、编辑源更新
    const handleUpdated = () => {
      showSlider.value = false;
      pagination.value.count = 1;
      getTableData();
    };

    // 侧边栏隐藏处理
    const handleSliderHidden = () => {
      showSlider.value = false;
    };

    // 设置变化处理
    const handleSettingChange = ({ fields }) => {
      clusterSetting.value.selectedFields = fields;
      setDefaultSettingSelectFiled(settingCacheKey, fields);
    };

    // 激活详情处理
    const handleActiveDetails = (state: boolean) => {
      isOpenWindow.value = state;
      introWidth.value = state ? 360 : 1;
    };

    // 检查字段显示
    const checkcFields = (field: string) => {
      return clusterSetting.value.selectedFields.some((item) => item.id === field);
    };

    // 判断过滤值是否为空
    const filterIsNotCompared = (val: unknown) => {
      if (typeof val === 'string' && val === '') return true;
      if (typeof val === 'object' && JSON.stringify(val) === '{}') return true;
      if (Array.isArray(val) && !val.length) return true;
      return false;
    };

    // 比较过滤值与数据值
    const compareFilter = (item: never, fCompare: unknown, key: string) => {
      if (key === 'cluster_config.cluster_id') {
        const info = stateMap.value[item.cluster_config.cluster_id];
        const state = typeof info === 'boolean' ? info : info?.status;
        return state.toString() === fCompare;
      }
      return item[key] === fCompare;
    };

    // 获取百分比
    const getPercent = (row: { storage_usage: number }) => {
      return (100 - row.storage_usage) / 100;
    };

    // 过滤变化处理
    const handleFilterChange = (data: { [x: string]: any }) => {
      Object.keys(data).forEach((key) => {
        filterParams.value[key] = Array.isArray(data[key]) ? data[key].join('') : data[key];
      });
      isFilterSearch.value = !!Object.values(filterParams.value).some((item) => !filterIsNotCompared(item));
      searchCallback();
    };

    // 操作处理
    const handleOperation = (type: string) => {
      if (type === 'clear-filter') {
        params.value.keyword = '';
        tableFilters.value = {};
        filterParams.value = {};
        isFilterSearch.value = false;
        getTableData();
        return;
      }

      if (type === 'refresh') {
        emptyType.value = 'empty';
        getTableData();
        return;
      }
    };

    onMounted(() => {
      checkDorisAccess();
      checkCreateAuth();
      getTableData();
      const { selectedFields } = clusterSetting.value;
      clusterSetting.value.selectedFields = getDefaultSettingSelectFiled(settingCacheKey, selectedFields);
      nextTick(() => {
        maxIntroWidth.value = accessContainerRef.value.clientWidth - 580;
      });
    });

    // 表头渲染函数

    // TDesign columns explicitly preserve V2 cells, permission checks and conditional fields.
    const renderColumnSettings = () => (
      <TPopup
        visible={settingsVisible.value}
        trigger='click'
        placement='bottom-right'
        zIndex={3000}
        onVisibleChange={(visible) => {
          settingsVisible.value = visible;
          if (visible) settingsDraft.value = clusterSetting.value.selectedFields.map((field) => field.id);
        }}
        content={() => (
          <div class='cluster-column-settings'>
            <div class='settings-heading'>{t('字段显示设置')}</div>
            <TCheckbox
              checked={clusterSetting.value.fields
                .filter((field) => !field.disabled)
                .every((field) => settingsDraft.value.includes(field.id))}
              onChange={(checked) => {
                settingsDraft.value = clusterSetting.value.fields
                  .filter((field) => (field.disabled ? settingsDraft.value.includes(field.id) : checked))
                  .map((field) => field.id);
              }}
            >
              {t('全选')}
            </TCheckbox>
            <div class='settings-fields'>
              {clusterSetting.value.fields.map((field) => (
                <TCheckbox
                  key={field.id}
                  disabled={field.disabled}
                  checked={settingsDraft.value.includes(field.id)}
                  onChange={(checked) => {
                    settingsDraft.value = checked
                      ? [...settingsDraft.value, field.id]
                      : settingsDraft.value.filter((id) => id !== field.id);
                  }}
                >
                  {field.label}
                </TCheckbox>
              ))}
            </div>
            <div class='settings-actions'>
              <TButton
                size='small'
                onClick={() => {
                  handleSettingChange({
                    fields: clusterSetting.value.fields.filter((field) => settingsDraft.value.includes(field.id)),
                  });
                  settingsVisible.value = false;
                }}
              >
                {t('确定')}
              </TButton>
              <TButton theme="default"
                size='small'
                variant='outline'
                onClick={() => {
                  settingsVisible.value = false;
                }}
              >
                {t('取消')}
              </TButton>
            </div>
          </div>
        )}
      >
        <TButton variant='text' shape='square' aria-label={t('字段显示设置')}>
          <i class='bklog-icon bklog-shezhi' />
        </TButton>
      </TPopup>
    );
    const handleNativeFilterChange = (values: FilterValue) => {
      tableFilters.value = values;
      filterParams.value = {};
      handleFilterChange(
        Object.fromEntries(Object.entries(values).map(([key, value]) => [key, value == null ? '' : String(value)])),
      );
    };
    const tableColumns = computed<PrimaryTableCol[]>(() => [
      {
        colKey: 'id',
        cell: (_h, { row }) => row.cluster_config.cluster_id,
        title: 'ID',
        minWidth: '60',
      } satisfies PrimaryTableCol,
      {
        colKey: 'cluster_config.display_name',
        title: t('名称'),
        minWidth: '170',
        cell: (_h, props) => props.row.cluster_config.display_name || '--',
      } satisfies PrimaryTableCol,
      ...(checkcFields('cluster_name')
        ? [
            {
              colKey: 'cluster_config.cluster_name',
              title: t('英文名称'),
              minWidth: '170',
              cell: (_h, props) => props.row.cluster_config.cluster_name || '--',
            } satisfies PrimaryTableCol,
          ]
        : []),
      {
        colKey: 'address',
        title: t('地址'),
        minWidth: '170',
        cell: (_h, props) => props.row.cluster_config.domain_name || '--',
      } satisfies PrimaryTableCol,
      ...(checkcFields('source_type')
        ? [
            {
              colKey: 'source_type',
              title: t('来源'),
              minWidth: '80',
              className: 'filter-column',
              cell: (_h, props) => props.row.source_name || '--',
              filter: {
                type: 'single',
                list: sourceFilters.value.map((item) => ({ label: item.text, value: item.value })),
              },
            } satisfies PrimaryTableCol,
          ]
        : []),
      ...(checkcFields('port')
        ? [{ colKey: 'cluster_config.port', title: t('端口'), minWidth: '80' } satisfies PrimaryTableCol]
        : []),
      ...(checkcFields('schema')
        ? [{ colKey: 'cluster_config.schema', title: t('协议'), minWidth: '80' } satisfies PrimaryTableCol]
        : []),
      ...(checkcFields('cluster_config')
        ? [
            {
              colKey: 'cluster_config.cluster_id',
              title: t('连接状态'),
              minWidth: '110',
              className: 'filter-column',
              cell: (_h, { row }) => getStateText(row.cluster_config.cluster_id),
              filter: {
                type: 'single',
                list: sourceStateFilters.value.map((item) => ({ label: item.text, value: String(item.value) })),
              },
            } satisfies PrimaryTableCol,
          ]
        : []),
      ...(activeTab.value !== CLUSTER_TYPES.DORIS && checkcFields('enable_hot_warm')
        ? [
            {
              colKey: 'hot_warm',
              title: t('冷热数据'),
              minWidth: '80',
              cell: (_h, { row }) => (row.cluster_config.enable_hot_warm ? t('开') : t('关')),
            } satisfies PrimaryTableCol,
          ]
        : []),
      ...(checkcFields('storage_total')
        ? [
            {
              colKey: 'storage_total',
              title: t('总量'),
              width: '90',
              cell: (_h, { row }) => <span>{formatFileSize(row.storage_total)}</span>,
            } satisfies PrimaryTableCol,
          ]
        : []),
      ...(checkcFields('storage_usage')
        ? [
            {
              colKey: 'storage_usage',
              title: t('空闲率'),
              width: '110',
              cell: (_h, { row }) => (
                <div class='percent'>
                  <div class='percent-progress'>
                    <TProgress
                      percentage={Number((getPercent(row as ClusterActionRow) * 100).toFixed(0))}
                      label={false}
                      color={'#2dcb56'}
                    />
                  </div>
                  <span>{`${100 - row.storage_usage}%`}</span>
                </div>
              ),
            } satisfies PrimaryTableCol,
          ]
        : []),
      ...(checkcFields('creator')
        ? [
            {
              colKey: 'cluster_config.creator',
              title: t('创建人'),
              minWidth: '80',
              cell: (_h, props) => (
                <bk-user-display-name user-id={props.row.cluster_config.creator}></bk-user-display-name>
              ),
            } satisfies PrimaryTableCol,
          ]
        : []),
      ...(checkcFields('create_time')
        ? [
            {
              colKey: 'cluster_config.create_time',
              title: t('创建时间'),
              width: '190',
              className: 'filter-column',
              sorter: (a, b) =>
                String(a.cluster_config.create_time ?? '').localeCompare(String(b.cluster_config.create_time ?? '')),
            } satisfies PrimaryTableCol,
          ]
        : []),
      ...(activeTab.value === CLUSTER_TYPES.DORIS
        ? [
            {
              colKey: 'operate',
              title: t('操作'),
              width: '100',
              cell: (_h, props) => (
                <div class='collect-table-operate'>
                  <log-button
                    v-cursor={{
                      active: !props.row.permission?.[authorityMapComputed.value.MANAGE_ES_SOURCE_AUTH],
                    }}
                    button-text={t('编辑')}
                    theme='primary'
                    text
                    onOnClick={() => editDataSource(props.row as ClusterActionRow)}
                  />
                </div>
              ),
            } satisfies PrimaryTableCol,
          ]
        : [
            {
              colKey: 'operate',
              title: t('操作'),
              width: '180',
              cell: (_h, props) => (
                <div class='collect-table-operate'>
                  <log-button
                    class='mr10'
                    tips-conf={
                      props.row.is_platform
                        ? t('公共集群，禁止创建自定义索引集')
                        : t('平台默认的集群不允许编辑和删除，请联系管理员。')
                    }
                    button-text={t('新建索引集')}
                    disabled={!props.row.is_editable || props.row.is_platform}
                    theme='primary'
                    text
                    onOnClick={() => createIndexSet(props.row as ClusterActionRow)}
                  />
                  <log-button
                    class='mr10'
                    v-cursor={{
                      active: !props.row.permission?.[authorityMapComputed.value.MANAGE_ES_SOURCE_AUTH],
                    }}
                    button-text={t('编辑')}
                    disabled={!props.row.is_editable}
                    theme='primary'
                    tips-conf={t('平台默认的集群不允许编辑和删除，请联系管理员。')}
                    text
                    onOnClick={() => editDataSource(props.row as ClusterActionRow)}
                  />
                  <log-button
                    class='mr10'
                    v-cursor={{
                      active: !props.row.permission?.[authorityMapComputed.value.MANAGE_ES_SOURCE_AUTH],
                    }}
                    button-text={t('删除')}
                    disabled={!props.row.is_editable}
                    theme='primary'
                    tips-conf={t('平台默认的集群不允许编辑和删除，请联系管理员。')}
                    text
                    onOnClick={() => deleteDataSource(props.row as ClusterActionRow)}
                  />
                </div>
              ),
            } satisfies PrimaryTableCol,
          ]),
      { colKey: 'setting', width: 44, title: renderColumnSettings, cell: () => null } satisfies PrimaryTableCol,
    ]);

    return () => (
      <div ref={accessContainerRef} class='es-access-container' data-test-id='esAccess_div_esAccessBox'>
        <div style={`width: calc(100% - ${introWidth.value}px);`} class='es-cluster-list-container'>
          <ClusterTypeTabs
            activeTab={activeTab.value}
            isDorisEnabled={isDorisEnabled.value}
            onTabClick={handleTabClick}
          />
          <div class='main-operator-container'>
            {activeTab.value !== CLUSTER_TYPES.DORIS && (
              <TButton
                style='width: 120px'
                data-test-id='esAccessBox_button_addNewEsAccess'
                disabled={isAllowedCreate.value === null || tableLoading.value}
                theme='primary'
                v-cursor={{ active: isAllowedCreate.value === false }}
                onClick={addDataSource}
              >
                {t('新建')}
              </TButton>
            )}

            <TInput
              style='float: right; width: 360px'
              clearable={true}
              data-test-id='esAccessBox_input_search'
              placeholder={t('搜索名称、英文名称、地址、创建人')}
              value={params.value.keyword}
              onChange={(val) => { params.value.keyword = String(val); }}
              onClear={handleSearch}
              onEnter={handleSearch}
              v-slots={{suffix: () => (
                <button type='button' class='cluster-search-submit' aria-label={t('搜索')}
                  onMousedown={(event: MouseEvent) => event.preventDefault()} onClick={handleSearch}>
                  <SearchIcon />
                </button>
              )}}
            />
          </div>
          <BklogLoading data-testid='cluster-table-loading' loading={tableLoading.value}>
            <TTable
              rowKey='cluster_config.cluster_id'
              columns={tableColumns.value}
              filterValue={tableFilters.value}
              class='king-table'
              v-slots={{
                empty: () => (
                  <div>
                    <EmptyStatus emptyType={emptyType.value} onOperation={handleOperation} />
                  </div>
                ),
              }}
              data={tableDataPaged.value}
              data-test-id='esAccessBox_table_esAccessTableBox'
              pagination={tableDataPaged.value.length && pagination.value.count > 0 ? {
                current: pagination.value.current,
                pageSize: pagination.value.limit,
                total: pagination.value.count,
                pageSizeOptions: pagination.value.limitList,
              } : undefined}
              onFilterChange={handleNativeFilterChange}
              onPageChange={({ current, pageSize }) => {
                if (pageSize !== pagination.value.limit) handleLimitChange(pageSize);
                else handlePageChange(current);
              }}
            />
          </BklogLoading>
        </div>

        <div style={`width: ${introWidth.value}px`} class={['intro-container', isDraging.value && 'draging-move']}>
          <div style={`right: ${introWidth.value - 18}px`} class={`drag-item ${!introWidth.value && 'hidden-drag'}`}>
            <span
              class='bk-icon icon-more'
              onMousedown={(e) => {
                if (e.button === 0) {
                  dragBegin(e);
                }
              }}
            />
          </div>
          <IntroPanel isOpenWindow={isOpenWindow.value} onHandle-active-details={handleActiveDetails} />
        </div>

        <EsSlider
          clusterData={editClusterData.value}
          clusterType={activeTab.value}
          editClusterId={editClusterId.value}
          showSlider={showSlider.value}
          onHandleCancelSlider={handleSliderHidden}
          onHandleUpdatedTable={handleUpdated}
        />
      </div>
    );
  },
});
