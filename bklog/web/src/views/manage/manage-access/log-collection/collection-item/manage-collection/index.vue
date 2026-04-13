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
    class="access-manage-container"
    v-bkloading="{ isLoading: basicLoading }"
  >
    <auth-container-page
      v-if="authPageInfo"
      :info="authPageInfo"
    ></auth-container-page>
    <template v-if="!authPageInfo && !basicLoading && collectorData">
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
              <span class="bk-icon icon-info"></span>
              <i18n path="数据采集好了，去 {0}">
                <span
                  class="search-button"
                  @click="handleGoSearch"
                  >{{ $t('查看数据') }}</span
                >
              </i18n>
            </div>
          </div>
        </template>
      </basic-tab>
      <keep-alive>
        <component
          class="tab-content"
          :collector-data="collectorData"
          :edit-auth="editAuth"
          :edit-auth-data="editAuthData"
          :index-set-data="collectorData"
          :index-set-id="collectorData.index_set_id"
          :is="dynamicComponent"
          :is-show-edit-btn="!['bkdata', 'es', 'custom_report'].includes($route.query.typeKey)"
          @update-active-panel="activePanel = $event"
        ></component>
      </keep-alive>
    </template>
  </div>
</template>

<script>
  import BasicTab from '@/components/basic-tab';
  import AuthContainerPage from '@/components/common/auth-container-page';
  import UsageDetails from '@/views/manage/manage-access/components/usage-details';
  import IndexSetBasicInfo from '@/views/manage/manage-access/components/index-set/manage/basic-info';

  import * as authorityMap from '../../../../../../common/authority-map';
  import BasicInfo from './basic-info';
  import CollectionStatus from './collection-status';
  import DataStatus from './data-status';
  import DataStorage from './data-storage';
  import FieldInfo from './field-info.tsx';

  export default {
    name: 'CollectionItem',
    components: {
      AuthContainerPage,
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
        const type = this.$route.query.typeKey
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
      const typeKey = this.$route.query.typeKey;
      if (!['bkdata', 'es'].includes(typeKey)) {
        this.getEditAuth();
      }
    },
    methods: {
      async initPage() {
        // 进入路由需要先判断权限
        try {
          const typeKey = this.$route.query.typeKey;
          const isBkDataOrEs = ['bkdata', 'es'].includes(typeKey);
          const collectorId = this.$route.params.collectorId;

          const paramData = {
            action_ids: [isBkDataOrEs ? authorityMap.MANAGE_INDICES_AUTH : authorityMap.VIEW_COLLECTION_AUTH],
            resources: [
              {
                type: isBkDataOrEs ? 'indices' : 'collection',
                id: collectorId,
              },
            ],
          };
          const res = await this.$store.dispatch('checkAndGetData', paramData);
          if (res.isAllowed === false) {
            this.authPageInfo = res.data;
            // 显示无权限页面
          } else {
            // 正常显示页面
            // bkdata/es 的 initPage 已用 MANAGE_INDICES_AUTH 校验，直接复用结果
            if (isBkDataOrEs) {
              this.editAuth = true;
              const [{ data: indexSetData }] = await Promise.all([
                this.$http.request('indexSet/info', {
                  params: {
                    index_set_id: collectorId,
                  },
                }),
                this.fetchScenarioMap(),
              ]);
              this.collectorData = indexSetData;
              this.$store.commit('collect/updateCurIndexSet', indexSetData);
            } else {
              const { data: collectorData } = await this.$http.request('collect/details', {
                params: {
                  collector_config_id: collectorId,
                },
              });
              this.collectorData = collectorData;
              this.$store.commit('collect/setCurCollect', collectorData);
            }
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
            spaceUid: this.$store.state.spaceUid,
            bizId: this.$store.state.bkBizId,
          },
        });
      },
      async fetchScenarioMap() {
        const scenarioMap = this.$store.state.collect.scenarioMap;
        if (!scenarioMap) {
          const { data } = await this.$http.request('meta/scenario');
          const map = {};
          data.forEach(item => {
            map[item.scenario_id] = item.scenario_name;
          });
          this.$store.commit('collect/updateScenarioMap', map);
        }
      },
      async getEditAuth() {
        try {
          const typeKey = this.$route.query.typeKey;
          const isBkDataOrEs = ['bkdata', 'es'].includes(typeKey);
          const paramData = {
            action_ids: [isBkDataOrEs ? authorityMap.MANAGE_INDICES_AUTH : authorityMap.MANAGE_COLLECTION_AUTH],
            resources: [
              {
                type: isBkDataOrEs ? 'indices' : 'collection',
                id: this.$route.params.collectorId,
              },
            ],
          };
          const res = await this.$store.dispatch('checkAndGetData', paramData);
          if (!res.isAllowed) this.editAuthData = res.data;
          this.editAuth = res.isAllowed;
        } catch (error) {
          this.editAuth = false;
        }
      },
    },
  };
</script>
