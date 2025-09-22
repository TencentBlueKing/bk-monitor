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

import { defineComponent, ref, watch } from 'vue';

import * as authorityMap from '@/common/authority-map';
import useLocale from '@/hooks/use-locale';
import { useRouter, useRoute } from 'vue-router/composables';

import { useCollectList } from '../../hook/useCollectList';
import { useOperation } from '../../hook/useOperation';
import BaseInfo from '../business-comp/step2/base-info';
import BkdataSelectDialog from '../business-comp/step2/third-party-logs/bkdata-select-dialog';
import EsSelectDialog from '../business-comp/step2/third-party-logs/es-select-dialog';
import DragTag from '../common-comp/drag-tag';
import InfoTips from '../common-comp/info-tips';
import $http from '@/api';

import './step2-bk-data-collection.scss';

export default defineComponent({
  name: 'StepBkDataCollection',
  props: {
    scenarioId: {
      type: String,
      default: 'host_log',
    },
  },

  emits: ['next', 'prev', 'cancel'],

  setup(props, { emit }) {
    const { t } = useLocale();
    const router = useRouter();
    const route = useRoute();
    const { bkBizId, spaceUid } = useCollectList();
    const { cardRender, handleMultipleSelected, tableLoading } = useOperation();
    const isShowDialog = ref(false);
    const currentActiveShowID = ref('');
    const baseInfoRef = ref();
    const submitLoading = ref(false);
    const clusterList = ref<any[]>([]);
    const clusterLoading = ref(false);
    const createEditRegex = /create|edit/;
    // 匹配到的索引 id，result table id list
    const currentMatchedTableIds = ref([]);
    const collectionTableData = ref<any[]>([]);
    const targetFieldSelectList = ref<{ id: string; name: string }[]>([]);
    const selectCollectionRef = ref();
    const isEdit = ref(false);
    const configData = ref({
      view_roles: [],
      index_set_name: '',
      storage_cluster_id: null,
      scenario_id: props.scenarioId,
      category_id: 'application_check',
      indexes: [
        // {
        //   result_table_id: '100605_bcs_file_log_oICV',
        //   result_table_name_alias: 'bcs_file_log_oICV',
        //   bk_biz_id: '100605',
        //   scenarioId: 'bkdata',
        // },
        // {
        //   result_table_id: '100605_bcs_file_log_uat8',
        //   result_table_name_alias: 'bcs_file_log_uat8',
        //   bk_biz_id: '100605',
        //   scenarioId: 'bkdata',
        // },
      ],
      target_fields: [],
      sort_fields: [],
      // target_fields: ['container_id', 'dtEventTimeStamp'],
      // sort_fields: ['container_id', 'log'],
    });

    /** 基本信息Render */
    const renderBaseInfo = () => (
      <BaseInfo
        ref={baseInfoRef}
        data={configData.value}
        typeKey='bk-data'
        on-change={data => {
          configData.value = { ...configData.value, ...data };
        }}
      />
    );
    /** 数据源Render */
    const renderDataSource = () => (
      <div class='data-source-box'>
        {props.scenarioId === 'es' && (
          <div class='label-form-box'>
            <span class='label-title'>{t('集群')}</span>
            <div class='form-box'>
              <bk-select
                class='w-40'
                loading={clusterLoading.value}
                value={configData.value.storage_cluster_id}
                on-selected={val => {
                  configData.value.storage_cluster_id = val;
                }}
              >
                {(clusterList.value || []).map(option => (
                  <bk-option
                    id={option.storage_cluster_id}
                    key={option.storage_cluster_id}
                    class='custom-no-padding-option'
                    name={option.storage_cluster_name}
                  />
                ))}
              </bk-select>
            </div>
          </div>
        )}
        <div class='label-form-box'>
          <span class='label-title'>{t('数据源')}</span>
          <div class='form-box'>
            <DragTag
              addType={'custom'}
              idKey={'result_table_id'}
              nameKey={'result_table_id'}
              sortable={false}
              value={configData.value.indexes}
              on-custom-add={handleAddDataSource}
            />
            <div class='data-source-table'>
              {props.scenarioId === 'bkdata' ? (
                <bk-table
                  v-bkloading={{ isLoading: tableLoading.value }}
                  data={collectionTableData.value}
                  max-height={400}
                >
                  <bk-table-column
                    label={t('字段')}
                    prop='field_name'
                  />
                  <bk-table-column
                    label={t('类型')}
                    prop='field_type'
                  />
                </bk-table>
              ) : (
                <bk-table
                  v-bkloading={{ isLoading: tableLoading.value }}
                  data={currentMatchedTableIds.value}
                  max-height={400}
                >
                  <bk-table-column
                    label={t('匹配到的索引')}
                    max-width={490}
                    property='result_table_id'
                  />
                </bk-table>
              )}
            </div>
          </div>
        </div>
        {props.scenarioId === 'es' && (
          <div class='label-form-box'>
            <span class='label-title no-require'>{t('时间字段')}</span>
            <div class='form-box'>
              <span class='time-field'>--</span>
            </div>
          </div>
        )}
      </div>
    );
    /** 字段设置Render */
    const renderFieldSetting = () => (
      <div class='field-setting-box'>
        <bk-alert
          class='field-setting-alert'
          title={t('未匹配到对应字段，请手动指定字段后提交。')}
          type='warning'
        />
        <div class='label-form-box'>
          <span class='label-title no-require'>{t('目标字段')}</span>
          <div class='form-box'>
            <bk-select
              class='select-sort'
              clearable={false}
              value={configData.value.target_fields}
              collapse-tag
              display-tag
              multiple
              searchable
              on-selected={value => {
                configData.value.target_fields = value;
              }}
            >
              {targetFieldSelectList.value.map(option => (
                <bk-option
                  id={option.id}
                  key={option.id}
                  name={option.name}
                />
              ))}
            </bk-select>
            <InfoTips
              class='block'
              tips={t('用于标识日志文件来源及唯一性')}
            />
          </div>
        </div>
        <div class='label-form-box'>
          <span class='label-title no-require'>{t('排序字段')}</span>
          <div class='form-box'>
            <DragTag
              addType={'select'}
              selectList={targetFieldSelectList.value}
              value={configData.value.sort_fields}
              on-change={value => {
                configData.value.sort_fields = value;
              }}
            />
            <InfoTips
              class='block'
              tips={t('用于控制日志排序的字段')}
            />
          </div>
        </div>
      </div>
    );
    const cardConfig = [
      {
        title: t('基础信息'),
        key: 'baseInfo',
        renderFn: renderBaseInfo,
      },
      {
        title: t('数据源'),
        key: 'dataSource',
        renderFn: renderDataSource,
      },
      {
        title: t('字段设置'),
        key: 'fieldSetting',
        renderFn: renderFieldSetting,
      },
    ];

    /**
     * 异步获取集群列表数据并处理
     * 功能：请求ES集群列表，按权限排序，过滤平台集群，根据路由参数设置默认集群
     */
    const fetchPageData = async () => {
      try {
        // 显示加载状态
        clusterLoading.value = true;

        // 请求集群列表数据
        const clusterRes = await $http.request('/source/logList', {
          query: {
            bk_biz_id: bkBizId.value,
            scenario_id: 'es',
          },
        });

        /**
         * 判断集群是否有管理权限
         * @param {Object} cluster - 集群对象
         * @returns {boolean} 是否有管理权限
         */
        const hasManagePermission = cluster => {
          return cluster.permission?.[authorityMap.MANAGE_ES_SOURCE_AUTH];
        };

        // 按权限拆分集群：有管理权限的优先展示
        const clustersWithPermission = [];
        const clustersWithoutPermission = [];

        for (const cluster of clusterRes.data) {
          if (hasManagePermission(cluster)) {
            clustersWithPermission.push(cluster);
          } else {
            clustersWithoutPermission.push(cluster);
          }
        }

        // 合并并过滤非平台集群
        clusterList.value = [...clustersWithPermission, ...clustersWithoutPermission].filter(
          cluster => !cluster.is_platform,
        );

        // 处理路由中的集群ID参数，设置默认选中的集群
        const targetClusterId = route.query.cluster;
        if (targetClusterId) {
          const numericClusterId = Number(targetClusterId);
          // 检查目标集群是否在有效列表中
          const isClusterValid = clusterList.value.some(cluster => cluster.storage_cluster_id === numericClusterId);

          if (isClusterValid) {
            configData.value.storage_cluster_id = numericClusterId;
          }
        }
      } catch (error) {
        console.warn('获取集群列表失败:', error);
      } finally {
        // 无论成功失败，都关闭加载状态
        clusterLoading.value = false;
      }
    };

    /**
     * 显示新增索引弹窗
     */
    const handleAddDataSource = () => {
      isShowDialog.value = true;
    };
    /**
     * 关闭新增索引弹窗
     */
    const handleCancel = () => {
      isShowDialog.value = false;
    };

    const returnIndexList = () => {
      const { editName: _, ...rest } = route.query;
      router.push({
        name: route.name.replace(createEditRegex, 'list'),
        query: { ...rest },
      });
    };

    /**
     * 处理创建成功的回调函数
     * @param {Object} params - 包含授权URL和索引集ID的参数对象
     * @param {string} params.bkdata_auth_url - 数据平台授权地址
     * @param {string} params.index_set_id - 索引集ID
     */
    const handleCreateSuccess = ({ bkdata_auth_url: authUrl, index_set_id: indexSetId }) => {
      // 如果没有授权URL，直接返回索引列表
      if (!authUrl) {
        returnIndexList();
        return;
      }

      /**
       * 规范化站点URL，确保格式正确
       * @param {string} url - 原始站点URL
       * @returns {string} 规范化后的站点URL
       */
      const normalizeSiteUrl = (url: string) => {
        // 处理非HTTP开头的URL，添加协议和主机
        if (!url.startsWith('http')) {
          // 确保以斜杠开头
          if (!url.startsWith('/')) {
            url = `/${url}`;
          }
          url = `${window.origin}${url}`;
        }

        // 确保以斜杠结尾
        return url.endsWith('/') ? url : `${url}/`;
      };

      /**
       * 构建完整的URL
       * @param {string} baseUrl - 基础URL
       * @param {string} path - 路径
       * @returns {string} 完整的URL
       */
      const buildFullUrl = (baseUrl, path) => {
        const normalizedBase = normalizeSiteUrl(baseUrl);
        return `${normalizedBase}${path}`;
      };

      // 获取站点URL
      const siteUrl = window.SITE_URL;

      // 构建重定向URL
      let redirectUrl;
      if (process.env.NODE_ENV === 'development') {
        redirectUrl = `${authUrl}&redirect_url=${window.origin}/static/auth.html`;
      } else {
        redirectUrl = `${authUrl}&redirect_url=${buildFullUrl(siteUrl, 'bkdata_auth/')}`;
      }

      // 构建索引集路径
      const { href: indexSetHref } = router.resolve({
        name: `${props.scenarioId}-index-set-list`,
      });
      const indexSetPath = buildFullUrl(siteUrl, indexSetHref);

      // 构建并编码URL参数
      const urlParams = new URLSearchParams({
        indexSetId,
        ajaxUrl: window.AJAX_URL_PREFIX,
        redirectUrl: indexSetPath,
      }).toString();

      // 完成重定向URL的构建
      redirectUrl += encodeURIComponent(`?${urlParams}`);

      // 根据是否在iframe中采取不同的跳转方式
      if (self !== top) {
        // 在iframe中，打开新窗口
        window.open(redirectUrl);
        returnIndexList();
      } else {
        // 在顶层窗口，直接重定向
        window.location.assign(redirectUrl);
      }
    };

    /**
     * 保存配置
     */
    const handleSave = () => {
      try {
        if (!configData.value.indexes.length) {
          // return this.messageError(t('请选择索引'));
        }
        baseInfoRef.value
          .validate()
          .then(async () => {
            submitLoading.value = true;
            const params = {
              space_uid: spaceUid.value,
              ...configData.value,
            };
            if (props.scenarioId !== 'es' && 'storage_cluster_id' in params) {
              params.storage_cluster_id = undefined;
            }
            const res = isEdit.value
              ? await $http.request('/indexSet/update', {
                  params: {
                    index_set_id: route.params.indexSetId,
                  },
                  data: params,
                })
              : await $http.request('/indexSet/create', { data: params });
            console.log(res, 'save');
            handleCreateSuccess(res.data);
          })
          .catch(err => {
            console.log(err, 'validate');
          });
      } catch (e) {
        console.log(e);
      } finally {
        submitLoading.value = false;
      }
    };

    const fetchList = async resultTableId => {
      tableLoading.value = true;
      try {
        const res = await $http.request('/resultTables/list', {
          query: {
            scenario_id: props.scenarioId,
            bk_biz_id: bkBizId.value,
            storage_cluster_id: configData.value.storage_cluster_id,
            result_table_id: resultTableId,
          },
        });
        currentMatchedTableIds.value = res.data;
      } catch (e) {
        console.warn(e);
        return [];
      } finally {
        tableLoading.value = false;
      }
    };
    /**
     * 数据源 - 计算平台日志接入 获取要展示的字段列表
     * @returns
     */
    const collectList = async () => {
      tableLoading.value = true;
      try {
        const resultTableID = configData.value.indexes.map(item => item.result_table_id);
        const requests = resultTableID.map(id =>
          $http.request('/resultTables/info', {
            params: { result_table_id: id },
            query: {
              scenario_id: props.scenarioId,
              bk_biz_id: bkBizId.value,
            },
          }),
        );
        const res = await Promise.all(requests);
        const collectionMap = new Map<string, any>();
        for (const item of res) {
          const fields = item?.data?.fields || [];
          for (const el of fields) {
            if (!collectionMap.has(el.field_name)) {
              collectionMap.set(el.field_name, el);
            }
          }
        }
        collectionTableData.value = Array.from(collectionMap.values());
      } catch (error) {
        console.warn(error);
        return [];
      } finally {
        tableLoading.value = false;
      }
    };
    /**
     *  @desc: 初始化字段设置所需的字段
     * 功能：获取所有关联结果表的字段，合并已有目标字段和排序字段，生成去重的选择列表
     */
    const initTargetFieldSelectList = async () => {
      // 提取所有结果表ID
      const resultTableIds = configData.value.indexes.map(item => item.result_table_id);

      // 判断是否为ES场景
      const isEsScenario = props.scenarioId === 'es';

      /**
       * 构建字段查询配置
       * @param {string} resultTableId - 结果表ID
       * @returns {Object} 查询配置参数
       */
      const getFieldQueryConfig = resultTableId => ({
        params: { result_table_id: resultTableId },
        query: {
          scenario_id: props.scenarioId,
          bk_biz_id: bkBizId.value,
          // 仅ES场景需要存储集群ID
          ...(isEsScenario && {
            storage_cluster_id: configData.value.storage_cluster_id,
          }),
        },
      });

      // 生成所有结果表的查询配置
      const fieldQueries = resultTableIds.map(getFieldQueryConfig);

      // 根据场景类型生成对应的请求Promise数组
      const fetchPromises = isEsScenario
        ? fieldQueries.map(query => selectCollectionRef.value.fetchInfo(query))
        : fieldQueries.map(query => handleMultipleSelected(query, true));

      // 等待所有请求完成
      const fieldResults: Array<{
        data: { fields: Array<{ field_name: string }> };
      }> = await Promise.all(fetchPromises);

      // 提取已有目标字段和排序字段，初始化Set用于去重
      const { target_fields: targetFields = [], sort_fields: sortFields = [] } = configData.value;
      const targetFieldSet = new Set([...sortFields, ...targetFields]);

      // 合并所有查询结果中的字段（去重）- 使用for...of替代forEach
      for (const result of fieldResults) {
        for (const field of result.data.fields) {
          targetFieldSet.add(field.field_name);
        }
      }

      // 转换为选择列表所需格式 - 使用map保持简洁
      targetFieldSelectList.value = Array.from(targetFieldSet).map(fieldName => ({
        id: fieldName,
        name: fieldName,
      }));
    };

    /**
     * 数据源
     * 获取要展示的字段列表
     */
    const handleChangeShowTableList = async (resultTableId, isInitTarget = false) => {
      currentActiveShowID.value = resultTableId;
      if (props.scenarioId === 'es') {
        await fetchList(resultTableId);
      } else {
        await collectList();
      }
      if (isInitTarget) {
        initTargetFieldSelectList();
      }
    };
    /**
     * 选中索引
     * @param data
     */
    const handleSelect = data => {
      configData.value.indexes.push(data);
      handleChangeShowTableList(data.result_table_id, true);
    };
    /**
     * 取消
     */
    const handleClose = () => {
      emit('cancel');
    };

    watch(
      () => props.scenarioId,
      val => {
        if (val === 'es') {
          fetchPageData();
        }
      },
      { immediate: true },
    );
    return () => (
      <div class='operation-step2-bk-data-collection'>
        {cardRender(cardConfig)}
        <div class='classify-btns-fixed'>
          <bk-button
            class='mr-8'
            on-click={() => {
              emit('prev');
            }}
          >
            {t('上一步')}
          </bk-button>
          <bk-button
            class='width-88 mr-8'
            loading={submitLoading.value}
            theme='primary'
            on-click={handleSave}
          >
            {t('提交')}
          </bk-button>
          <bk-button on-click={handleClose}>{t('取消')}</bk-button>
        </div>
        {props.scenarioId === 'bkdata' ? (
          /** 计算平台日志接入的索引选择 */
          <BkdataSelectDialog
            ref={selectCollectionRef}
            configData={configData.value}
            isShowDialog={isShowDialog.value}
            scenarioId={props.scenarioId}
            on-cancel={handleCancel}
            on-selected={handleSelect}
          />
        ) : (
          <EsSelectDialog
            configData={configData.value}
            isShowDialog={isShowDialog.value}
            scenarioId={props.scenarioId}
          />
        )}
      </div>
    );
  },
});
