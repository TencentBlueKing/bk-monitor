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

import { defineComponent, ref, computed, onMounted, nextTick } from 'vue';

import * as authorityMap from '@/common/authority-map';
import {
  formatFileSize,
  clearTableFilter,
  isIPv6,
  getDefaultSettingSelectFiled,
  setDefaultSettingSelectFiled,
} from '@/common/util';
import EmptyStatus from '@/components/empty-status/index.vue';
import useLocale from '@/hooks/use-locale';
import useRouter from '@/hooks/use-router';
import useStore from '@/hooks/use-store';
import { InfoBox } from 'bk-magic-vue';

import { useDrag } from '../../hooks/use-drag';
import EsSlider from './es-slider.tsx';
import IntroPanel from './intro-panel.tsx';
import http from '@/api';

import './index.scss';

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
  },
  setup() {
    const store = useStore();
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
    const isAllowedCreate = ref(null); // 是否有权限新建
    const showSlider = ref(false); // 显示编辑或新建ES源侧边栏
    const editClusterId = ref(null); // 编辑ES源ID
    const isOpenWindow = ref(false); // 是否打开窗口
    const emptyType = ref('empty'); // 空状态类型
    const filterSearchObj = ref({}); // 过滤搜索对象
    const isFilterSearch = ref(false); // 是否过滤搜索
    const settingCacheKey = 'collection'; // 设置缓存键
    const searchTimer = ref(null); // 搜索定时器
    const accessContainerRef = ref(null); // 容器引用
    const clusterTable = ref(null); // 表格引用

    // 来源状态过滤器
    const sourceStateFilters = ref([
      { text: t('正常'), value: true },
      { text: t('失败'), value: false },
    ]);

    // 设置字段配置
    const settingFields = ref([
      { id: 'cluster_id', label: 'ID', disabled: true },
      { id: 'collector_config_name', label: t('名称'), disabled: true },
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

    const bkBizId = computed(() => store.getters.bkBizId); // 业务ID
    const spaceUid = computed(() => store.getters.spaceUid); // 空间ID
    const globalsData = computed(() => store.getters.globalsData);
    const authorityMapComputed = computed(() => authorityMap); // 权限映射

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
        const res = await store.dispatch('checkAllowed', {
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
        const tableRes = await http.request('/source/list', {
          query: {
            bk_biz_id: bkBizId.value,
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
          const stateRes = await http.request('/source/connectionStatus', {
            query: {
              bk_biz_id: bkBizId.value,
            },
            data: {
              cluster_list: list.map(item => item.cluster_config.cluster_id),
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
    const getStateText = id => {
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
    const handlePageChange = page => {
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
    const handleLimitChange = limit => {
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

    // 来源过滤方法
    const sourceFilterMethod = (value, row, column) => {
      const { property } = column;
      handlePageChange(1);
      return row[property] === value;
    };

    // 搜索回调
    const searchCallback = () => {
      const keyword = params.value.keyword.trim();
      if (keyword) {
        tableDataSearched.value = tableDataOrigin.value.filter(item => {
          if (isIPv6(keyword)) {
            return completeIPv6Address(item.cluster_config.domain_name) === completeIPv6Address(keyword);
          }
          if (item.cluster_config.cluster_name) {
            return (
              item.cluster_config.cluster_name +
              item.cluster_config.creator +
              item.cluster_config.domain_name
            ).includes(keyword);
          }
          return (item.source_name + item.updated_by).includes(keyword);
        });
      } else {
        tableDataSearched.value = tableDataOrigin.value;
      }
      emptyType.value = params.value.keyword || isFilterSearch.value ? 'search-empty' : 'empty';
      pagination.value.current = 1;
      pagination.value.count = tableDataSearched.value.length;
      computePageData();
    };

    // ipv6补全
    const completeIPv6Address = address => {
      const sections = address.split(':');
      const missingSections = 8 - sections.length;

      for (let i = 0; i < missingSections; i++) {
        sections.splice(sections.indexOf(''), 1, '0000');
      }

      return sections
        .map(section => {
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
        showSlider.value = true;
        editClusterId.value = null;
      } else {
        try {
          tableLoading.value = true;
          const res = await store.dispatch('getApplyData', {
            action_ids: [authorityMapComputed.value.CREATE_ES_SOURCE_AUTH],
            resources: [
              {
                type: 'space',
                id: spaceUid.value,
              },
            ],
          });
          store.commit('updateState', { authDialogData: res.data });
        } catch (err) {
          console.warn(err);
        } finally {
          tableLoading.value = false;
        }
      }
    };

    // 创建索引集
    const createIndexSet = row => {
      router.push({
        name: 'es-index-set-create',
        query: {
          spaceUid: store.state.spaceUid,
          cluster: row.cluster_config.cluster_id,
        },
      });
    };

    // 编辑ES源
    const editDataSource = async item => {
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
          const res = await store.dispatch('getApplyData', paramData);
          store.commit('updateState', { authDialogData: res.data });
        } catch (err) {
          console.warn(err);
        } finally {
          tableLoading.value = false;
        }
        return;
      }

      showSlider.value = true;
      editClusterId.value = id;
    };

    // 删除ES源
    const deleteDataSource = async row => {
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
          const res = await store.dispatch('getApplyData', paramData);
          store.commit('updateState', { authDialogData: res.data });
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
    const handleDelete = row => {
      http
        .request('source/deleteEs', {
          params: {
            bk_biz_id: bkBizId.value,
            cluster_id: row.cluster_config.cluster_id,
          },
        })
        .then(res => {
          if (res.result) {
            if (tableDataPaged.value.length <= 1) {
              pagination.value.current = pagination.value.current > 1 ? pagination.value.current - 1 : 1;
            }
            const deleteIndex = tableDataSearched.value.findIndex(item => {
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
    const handleActiveDetails = state => {
      isOpenWindow.value = state;
      introWidth.value = state ? 360 : 1;
    };

    // 状态过滤方法
    const sourceStateFilterMethod = (value, row) => {
      const info = stateMap.value[row.cluster_config.cluster_id];
      const state = typeof info === 'boolean' ? info : info?.status;
      return state === value;
    };

    // 检查字段显示
    const checkcFields = field => {
      return clusterSetting.value.selectedFields.some(item => item.id === field);
    };

    // 获取百分比
    const getPercent = row => {
      return (100 - row.storage_usage) / 100;
    };

    // 过滤变化处理
    const handleFilterChange = data => {
      for (const [key, value] of Object.entries(data)) {
        filterSearchObj.value[key] = Array.isArray(value) ? value.length : 0;
      }
      isFilterSearch.value = !!Object.values(filterSearchObj.value).reduce((pre, cur) => Number(pre) + Number(cur), 0);
      searchCallback();
    };

    // 操作处理
    const handleOperation = type => {
      if (type === 'clear-filter') {
        params.value.keyword = '';
        clearTableFilter(clusterTable.value);
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
      checkCreateAuth();
      getTableData();
      const { selectedFields } = clusterSetting.value;
      clusterSetting.value.selectedFields = getDefaultSettingSelectFiled(settingCacheKey, selectedFields);
      nextTick(() => {
        maxIntroWidth.value = accessContainerRef.value.clientWidth - 580;
      });
    });

    // 表头渲染函数
    const renderHeader = (_: any, { column }: any) => <span>{column.label}</span>;

    return () => (
      <div
        ref={accessContainerRef}
        class='es-access-container'
        data-test-id='esAccess_div_esAccessBox'
      >
        <div
          style={`width: calc(100% - ${introWidth.value}px);`}
          class='es-cluster-list-container'
        >
          <div class='main-operator-container'>
            <bk-button
              style='width: 120px'
              data-test-id='esAccessBox_button_addNewEsAccess'
              disabled={isAllowedCreate.value === null || tableLoading.value}
              theme='primary'
              vCursor={{ active: isAllowedCreate.value === false }}
              onClick={addDataSource}
            >
              {t('新建')}
            </bk-button>
            <bk-input
              style='float: right; width: 360px'
              clearable={true}
              data-test-id='esAccessBox_input_search'
              placeholder={t('搜索ES源名称，地址，创建人')}
              right-icon='bk-icon icon-search'
              value={params.value.keyword}
              on-right-icon-click={handleSearch}
              onChange={val => (params.value.keyword = val)}
              onClear={handleSearch}
              onEnter={handleSearch}
            />
          </div>
          <bk-table
            ref={clusterTable}
            class='king-table'
            v-bkloading={{ isLoading: tableLoading.value }}
            scopedSlots={{
              empty: () => (
                <div>
                  <EmptyStatus
                    emptyType={emptyType.value}
                    on-operation={handleOperation}
                  />
                </div>
              ),
            }}
            data={tableDataPaged.value}
            data-test-id='esAccessBox_table_esAccessTableBox'
            pagination={pagination.value}
            onFilter-change={handleFilterChange}
            onPage-change={handlePageChange}
            onPage-limit-change={handleLimitChange}
          >
            <bk-table-column
              key='id'
              label='ID'
              min-width='60'
              prop='cluster_config.cluster_id'
              renderHeader={renderHeader}
            />
            <bk-table-column
              key='name'
              label={t('名称')}
              min-width='170'
              prop='cluster_config.cluster_name'
              renderHeader={renderHeader}
            />
            <bk-table-column
              key='address'
              label={t('地址')}
              min-width='170'
              renderHeader={renderHeader}
              scopedSlots={{ default: (props: any) => props.row.cluster_config.domain_name || '--' }}
            />
            {checkcFields('source_type') && (
              <bk-table-column
                key='source_type'
                class-name='filter-column'
                column-key='source_type'
                filter-method={sourceFilterMethod}
                filter-multiple={false}
                filters={sourceFilters.value}
                label={t('来源')}
                min-width='80'
                prop='source_type'
                renderHeader={renderHeader}
                scopedSlots={{ default: (props: any) => props.row.source_name || '--' }}
              />
            )}
            {checkcFields('port') && (
              <bk-table-column
                key='port'
                label={t('端口')}
                min-width='80'
                prop='cluster_config.port'
                renderHeader={renderHeader}
              />
            )}
            {checkcFields('schema') && (
              <bk-table-column
                key='schema'
                label={t('协议')}
                min-width='80'
                prop='cluster_config.schema'
                renderHeader={renderHeader}
              />
            )}
            {checkcFields('cluster_config') && (
              <bk-table-column
                key='status'
                scopedSlots={{
                  default: ({ row }: any) => getStateText(row.cluster_config.cluster_id),
                }}
                class-name='filter-column'
                column-key='cluster_config.cluster_id'
                filter-method={sourceStateFilterMethod}
                filter-multiple={false}
                filters={sourceStateFilters.value}
                label={t('连接状态')}
                min-width='110'
                prop='cluster_config.cluster_id'
                renderHeader={renderHeader}
              />
            )}
            {checkcFields('enable_hot_warm') && (
              <bk-table-column
                key='hot_warm'
                label={t('冷热数据')}
                min-width='80'
                renderHeader={renderHeader}
                scopedSlots={{ default: ({ row }: any) => (row.cluster_config.enable_hot_warm ? t('开') : t('关')) }}
              />
            )}
            {checkcFields('storage_total') && (
              <bk-table-column
                key='storage_total'
                width='90'
                label={t('总量')}
                renderHeader={renderHeader}
                scopedSlots={{ default: ({ row }: any) => <span>{formatFileSize(row.storage_total)}</span> }}
              />
            )}
            {checkcFields('storage_usage') && (
              <bk-table-column
                key='storage_usage'
                width='110'
                scopedSlots={{
                  default: ({ row }: any) => (
                    <div class='percent'>
                      <div class='percent-progress'>
                        <bk-progress
                          percent={getPercent(row)}
                          show-text={false}
                          theme='success'
                        />
                      </div>
                      <span>{`${100 - row.storage_usage}%`}</span>
                    </div>
                  ),
                }}
                label={t('空闲率')}
                renderHeader={renderHeader}
              />
            )}
            {checkcFields('creator') && (
              <bk-table-column
                key='creator'
                label={t('创建人')}
                min-width='80'
                prop='cluster_config.creator'
                renderHeader={renderHeader}
              />
            )}
            {checkcFields('create_time') && (
              <bk-table-column
                key='create_time'
                class-name='filter-column'
                label={t('创建时间')}
                min-width='170'
                prop='cluster_config.create_time'
                renderHeader={renderHeader}
                sortable
              />
            )}
            <bk-table-column
              key='operate'
              width='180'
              scopedSlots={{
                default: (props: any) => (
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
                      on-on-click={() => createIndexSet(props.row)}
                    />
                    <log-button
                      class='mr10'
                      vCursor={{
                        active: !props.row.permission?.[authorityMapComputed.value.MANAGE_ES_SOURCE_AUTH],
                      }}
                      button-text={t('编辑')}
                      disabled={!props.row.is_editable}
                      theme='primary'
                      tips-conf={t('平台默认的集群不允许编辑和删除，请联系管理员。')}
                      text
                      on-on-click={() => editDataSource(props.row)}
                    />
                    <log-button
                      class='mr10'
                      vCursor={{
                        active: !props.row.permission?.[authorityMapComputed.value.MANAGE_ES_SOURCE_AUTH],
                      }}
                      button-text={t('删除')}
                      disabled={!props.row.is_editable}
                      theme='primary'
                      tips-conf={t('平台默认的集群不允许编辑和删除，请联系管理员。')}
                      text
                      on-on-click={() => deleteDataSource(props.row)}
                    />
                  </div>
                ),
              }}
              label={t('操作')}
              renderHeader={renderHeader}
            />
            <bk-table-column
              key='setting'
              tippy-options={{ zIndex: 3000 }}
              type='setting'
            >
              <bk-table-setting-content
                v-en-style='width: 530px'
                fields={clusterSetting.value.fields}
                selected={clusterSetting.value.selectedFields}
                on-setting-change={handleSettingChange}
              />
            </bk-table-column>
          </bk-table>
        </div>

        <div
          style={`width: ${introWidth.value}px`}
          class={['intro-container', isDraging.value && 'draging-move']}
        >
          <div
            style={`right: ${introWidth.value - 18}px`}
            class={`drag-item ${!introWidth.value && 'hidden-drag'}`}
          >
            <span
              class='bk-icon icon-more'
              onMousedown={e => {
                if (e.button === 0) {
                  dragBegin(e);
                }
              }}
            />
          </div>
          <IntroPanel
            isOpenWindow={isOpenWindow.value}
            onHandle-active-details={handleActiveDetails}
          />
        </div>

        <EsSlider
          editClusterId={editClusterId.value}
          showSlider={showSlider.value}
          onHandleCancelSlider={handleSliderHidden}
          onHandleUpdatedTable={handleUpdated}
        />
      </div>
    );
  },
});
