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
          :index-set-id="collectorData.index_set_id"
          :is="dynamicComponent"
          :is-show-edit-btn="true"
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
      panels: [
        { name: 'basicInfo', label: this.$t('配置信息') },
        { name: 'collectionStatus', label: this.$t('采集状态') },
        { name: 'fieldInfo', label: this.$t('字段信息') },
        { name: 'dataStorage', label: this.$t('数据存储') },
        { name: 'dataStatus', label: this.$t('数据状态') },
        { name: 'usageDetails', label: this.$t('使用详情') },
      ],
    };
  },
  computed: {
    dynamicComponent() {
      const componentMaP = {
        basicInfo: 'BasicInfo',
        collectionStatus: 'CollectionStatus',
        fieldInfo: 'FieldInfo',
        dataStorage: 'DataStorage',
        dataStatus: 'DataStatus',
        usageDetails: 'UsageDetails',
      };
      return componentMaP[this.activePanel] || 'BasicInfo';
    },
  },
  created() {
    this.initPage();
    this.getEditAuth();
  },
  methods: {
    async initPage() {
      // 进入路由需要先判断权限
      try {
        const paramData = {
          action_ids: [authorityMap.VIEW_COLLECTION_AUTH],
          resources: [
            {
              type: 'collection',
              id: this.$route.params.collectorId,
            },
          ],
        };
        const res = await this.$store.dispatch('checkAndGetData', paramData);
        if (res.isAllowed === false) {
          this.authPageInfo = res.data;
          // 显示无权限页面
        } else {
          // 正常显示页面
          const { data: collectorData } = await this.$http.request('collect/details', {
            params: {
              collector_config_id: this.$route.params.collectorId,
            },
          });
          this.collectorData = collectorData;
          this.$store.commit('collect/setCurCollect', collectorData);
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
    async getEditAuth() {
      try {
        const paramData = {
          action_ids: [authorityMap.MANAGE_COLLECTION_AUTH],
          resources: [
            {
              type: 'collection',
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
