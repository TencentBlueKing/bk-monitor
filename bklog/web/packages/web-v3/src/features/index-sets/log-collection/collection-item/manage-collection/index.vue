<!--
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
-->

<template>
  <div
    v-loading="{ loading: basicLoading, indicator: renderDrawerDetailSkeleton }"
    class="access-manage-container"
  >
    <auth-container-page
      v-if="authPageInfo"
      :info="authPageInfo"
    ></auth-container-page>
    <template v-else-if="!basicLoading && collectorData">
      <basic-tab
        :active.sync="activePanel"
        type="border-card"
      >
        <bk-tab-panel
          v-for="panel in panels"
          v-bind="panel"
          :key="panel.name"
        ></bk-tab-panel>
        <template #setting>
          <div class="go-search">
            <div class="search-text">
              <span class="bk-icon icon-info" aria-hidden="true"></span>
              <i18n path="数据采集好了，去 {0}">
                <button type="button" class="search-button" @click="handleGoSearch">
                  {{ $t('查看数据') }}
                </button>
              </i18n>
            </div>
          </div>
        </template>
      </basic-tab>
      <keep-alive>
        <component
          :is="dynamicComponent"
          class="tab-content"
          :collector-data="collectorData"
          :edit-auth="editAuth"
          :edit-auth-data="editAuthData"
          :index-set-data="collectorData"
          :index-set-id="collectorData.index_set_id"
          :is-show-edit-btn="!['bkdata', 'es', 'custom_report'].includes($route.query.typeKey)"
          @update-active-panel="activePanel = $event"
        ></component>
      </keep-alive>
    </template>
    <div v-else-if="!basicLoading" class="bklog-table-empty-region">
      <EmptyStatus empty-type="500" @operation="initPage" />
    </div>
  </div>
</template>

<script>
import { renderDrawerDetailSkeleton } from '@/shared/ui/loading/drawer-skeleton';
import { renderFieldListSkeleton } from '@/shared/ui/loading/list-skeleton';
import ChartSkeleton from '@/app/skeleton/chart-skeleton';
import EmptyStatus from '@/shared/ui/empty-status/index.vue';
import './detail-states.scss';

import { useApplicationStore } from '@/app/state/domains/application-store';
import { useCollectionStore } from '@/app/state/domains/collection-store';

  import { defineAsyncComponent, h } from 'vue';

  import { ServicesInstance } from '@/platform/services';

  import BasicTab from '@/shared/ui/basic-tab/index';
  import AuthContainerPage from '@/shared/ui/common/auth-container-page';
  import * as authorityMap from '../../../../../shared/lib/authority-map';

  const renderTrendPanelSkeleton = () =>
    h('section', { class: 'partial-content', 'aria-hidden': 'true' }, [
      h('div', { class: 'main-title' }, [
        h('span', { class: 'collection-detail-section-heading-placeholder' }, [
          h('span', { class: 'bklog-list-skeleton__bar collection-detail-chart-heading-placeholder' }),
        ]),
      ]),
      h('div', { class: 'charts-container collection-detail-chart-grid' },
        ['line', 'bar'].map(type => h('div', { class: 'chart-container', key: type }, [
          h('div', { class: 'chart-header' }, [
            h('span', { class: 'bklog-list-skeleton__bar collection-detail-chart-heading-placeholder' }),
          ]),
          h('div', { class: 'collection-detail-chart-body' }, [
            h('div', { class: 'chart-canvas-container big-chart' }),
            h('div', { class: 'collection-detail-chart-state is-skeleton' }, [
              h(ChartSkeleton, { type, height: 216 }),
            ]),
          ]),
        ])),
      ),
    ]);

  const renderUsagePanelSkeleton = () =>
    h('div', { class: 'collection-detail-trend-placeholder' }, [
      h(ChartSkeleton, { type: 'line', height: 168 }),
      h(ChartSkeleton, { type: 'bar', height: 168 }),
      h('div', { class: 'collection-detail-usage-pie-placeholder', 'aria-hidden': 'true' }, [
        h('div', { class: 'usage-chart-pie-skeleton' }),
      ]),
    ]);

  function defineDetailPanel(loader, indicator) {
    return defineAsyncComponent({
      loader,
      delay: 0,
      errorComponent: () => h('div', { class: 'bklog-table-empty-region' }, [
        h(EmptyStatus, { emptyType: '500', onOperation: () => window.location.reload() }),
      ]),
      loadingComponent: () => h('div', {
        class: 'collection-detail-loading-panel',
        role: 'status',
        'aria-busy': 'true',
      }, [indicator()]),
    });
  }

  const BasicInfo = defineDetailPanel(() => import('./basic-info'), renderDrawerDetailSkeleton);
  const CollectionStatus = defineDetailPanel(() => import('./collection-status'), renderFieldListSkeleton);
  const DataStorage = defineDetailPanel(() => import('./data-storage'), renderFieldListSkeleton);
  const DataStatus = defineDetailPanel(() => import('./data-status/index'), renderTrendPanelSkeleton);
  const FieldInfo = defineDetailPanel(() => import('./field-info.tsx'), renderFieldListSkeleton);
  const UsageDetails = defineDetailPanel(
    () => import('@/features/index-sets/components/usage-details/index'),
    renderUsagePanelSkeleton,
  );
  const IndexSetBasicInfo = defineDetailPanel(
    () => import('@/features/index-sets/components/index-set/manage/basic-info'),
    renderDrawerDetailSkeleton,
  );

  export default {
    name: 'CollectionItem',
    components: {
      AuthContainerPage,
      EmptyStatus,
      BasicInfo,
      IndexSetBasicInfo,
      CollectionStatus,
      DataStorage,
      DataStatus,
      UsageDetails,
      BasicTab,
      FieldInfo,
    },
    data() {
      return {
        basicLoading: true,
        authPageInfo: null,
        collectorData: null,
        activePanel: this.$route.query.type || 'basicInfo',
        /** 是否有编辑权限 */
        editAuth: false,
        /** 编辑无权限时的弹窗数据 */
        editAuthData: null,
      };
    },
    computed: {
      panels() {
        const type = this.$route.query.typeKey;
        // 第三方ES / 计算平台：仅3个 tab（与旧版 index-set/manage 对齐）
        if (['bkdata', 'es'].includes(type)) {
          return [
            { name: 'basicInfo', label: this.$t('配置信息') },
            { name: 'usageDetails', label: this.$t('使用详情') },
            { name: 'fieldInfo', label: this.$t('字段信息') },
          ];
        }
        // 自定义上报：5个 tab，无采集状态（与旧版 custom-report/detail.vue 对齐）
        if (type === 'custom_report') {
          return [
            { name: 'basicInfo', label: this.$t('配置信息') },
            { name: 'dataStorage', label: this.$t('数据存储') },
            { name: 'fieldInfo', label: this.$t('字段信息') },
            { name: 'dataStatus', label: this.$t('数据状态') },
            { name: 'usageDetails', label: this.$t('使用详情') },
          ];
        }
        // 标准日志采集：完整6个 tab
        return [
          { name: 'basicInfo', label: this.$t('配置信息') },
          { name: 'collectionStatus', label: this.$t('采集状态') },
          { name: 'fieldInfo', label: this.$t('字段信息') },
          { name: 'dataStorage', label: this.$t('数据存储') },
          { name: 'dataStatus', label: this.$t('数据状态') },
          { name: 'usageDetails', label: this.$t('使用详情') },
        ];
      },
      dynamicComponent() {
        const type = this.$route.query.typeKey;
        const isBkDataOrEs = ['bkdata', 'es'].includes(type);
        const componentMaP = {
          basicInfo: isBkDataOrEs ? 'IndexSetBasicInfo' : 'BasicInfo',
          collectionStatus: 'CollectionStatus',
          fieldInfo: 'FieldInfo',
          dataStorage: 'DataStorage',
          dataStatus: 'DataStatus',
          usageDetails: 'UsageDetails',
        };
        return componentMaP[this.activePanel] || (isBkDataOrEs ? 'IndexSetBasicInfo' : 'BasicInfo');
      },
    },
    created() {
      this.initPage();
    },
    methods: {
      renderDrawerDetailSkeleton,
      async initPage() {
        this.basicLoading = true;
        // 进入路由需要先判断权限（查看 + 编辑权限合并为一次 check_allowed 请求）
        try {
          const typeKey = this.$route.query.typeKey;
          const isBkDataOrEs = ['bkdata', 'es'].includes(typeKey);
          const collectorId = this.$route.params.collectorId;
          const resourceType = isBkDataOrEs ? 'indices' : 'collection';
          const resources = [{ type: resourceType, id: collectorId }];

          const viewAction = isBkDataOrEs ? authorityMap.MANAGE_INDICES_AUTH : authorityMap.VIEW_COLLECTION_AUTH;
          const manageAction = isBkDataOrEs ? authorityMap.MANAGE_INDICES_AUTH : authorityMap.MANAGE_COLLECTION_AUTH;
          const actionIds = isBkDataOrEs ? [viewAction] : [viewAction, manageAction];

          const { data: checkResult } = await ServicesInstance.auth.checkAllowed({
            data: { action_ids: actionIds, resources },
          });

          const allowedMap = {};
          (checkResult || []).forEach(item => {
            allowedMap[item.action_id] = item.is_allowed;
          });

          const canView = Boolean(allowedMap[viewAction]);
          const canManage = Boolean(allowedMap[manageAction]);

          if (!canView) {
            const applyRes = await useApplicationStore().getApplyData({
              action_ids: [viewAction],
              resources,
            });
            this.authPageInfo = applyRes.data;
            return;
          }

          this.editAuth = isBkDataOrEs ? true : canManage;
          if (!canManage && !isBkDataOrEs) {
            const applyRes = await useApplicationStore().getApplyData({
              action_ids: [manageAction],
              resources,
            });
            this.editAuthData = applyRes.data;
          }

          if (isBkDataOrEs) {
            const [{ data: indexSetData }] = await Promise.all([
              ServicesInstance.indexSet.info({
                params: {
                  index_set_id: collectorId,
                },
              }),
              this.fetchScenarioMap(),
            ]);
            this.collectorData = indexSetData;
            useCollectionStore().updateCurIndexSet(indexSetData);
          } else {
            const { data: collectorData } = await ServicesInstance.collect.details({
              params: {
                collector_config_id: collectorId,
              },
            });
            this.collectorData = collectorData;
            useCollectionStore().setCurCollect(collectorData);
          }
        } catch (err) {
          console.warn(err);
        } finally {
          this.basicLoading = false;
        }
      },
      handleGoSearch() {
        const params = {
          indexId: this.collectorData.index_set_id
            ? this.collectorData.index_set_id
            : this.collectorData.bkdata_index_set_ids[0],
        };
        this.$router.push({
          name: 'retrieve',
          params,
          query: {
            spaceUid: useApplicationStore().spaceUid,
            bizId: useApplicationStore().bkBizId,
          },
        });
      },
      async fetchScenarioMap() {
        const scenarioMap = useCollectionStore().$state.scenarioMap;
        if (!scenarioMap) {
          const { data } = await ServicesInstance.meta.scenario();
          const map = {};
          data.forEach(item => {
            map[item.scenario_id] = item.scenario_name;
          });
          useCollectionStore().updateScenarioMap(map);
        }
      },
    },
  };
</script>
