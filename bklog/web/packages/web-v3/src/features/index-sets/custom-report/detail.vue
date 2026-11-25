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
    ref="detailRef"
    v-loading="{ loading: basicLoading, indicator: renderDrawerDetailSkeleton }"
    :style="{ paddingInlineEnd: `${(showReportDetail ? introWidth : 0) + 20}px` }"
    class="custom-report-detail-container access-manage-container"
  >
    <auth-container-page
      v-if="authPageInfo"
      :info="authPageInfo"
    ></auth-container-page>
    <template v-else-if="showReportDetail">
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
          :collector-data="reportDetail"
          :edit-auth="editAuth"
          :edit-auth-data="editAuthData"
          :index-set-id="reportDetail.index_set_id || ''"
          @update-active-panel="activePanel = $event"
        ></component>
      </keep-alive>
    </template>
    <div v-else-if="!basicLoading" class="bklog-table-empty-region">
      <EmptyStatus empty-type="500" @operation="initPage" />
    </div>

    <div
      v-if="showReportDetail"
      :style="`width: ${introWidth}px`"
      :class="['intro-container', isDraging && 'draging-move']"
    >
      <div
        :style="`right: ${introWidth - 18}px`"
        :class="`drag-item ${!introWidth && 'hidden-drag'}`"
      >
        <span
          class="bk-icon icon-more"
          @mousedown.left="dragBegin"
        ></span>
      </div>
      <intro-panel
        :data="reportDetail"
        :is-open-window="isOpenWindow"
        @handle-active-details="handleActiveDetails"
      />
    </div>
  </div>
</template>

<script>
import EmptyStatus from '@/shared/ui/empty-status/index.vue';
import { renderDrawerDetailSkeleton } from '@/shared/ui/loading/drawer-skeleton';
import { useApplicationStore } from '@/app/state/domains/application-store';
import { useCollectionStore } from '@/app/state/domains/collection-store';
import { ServicesInstance } from '@/platform/services';

  import BasicTab from '@/shared/ui/basic-tab/index';
  import AuthContainerPage from '@/shared/ui/common/auth-container-page';
  import { useIntroResize } from '@/shared/composables/use-intro-resize';
  import UsageDetails from '@/features/index-sets/components/usage-details/index';

  import * as authorityMap from '../../../shared/lib/authority-map';
  import BasicInfo from '../log-collection/collection-item/manage-collection/basic-info';
  import DataStatus from '../log-collection/collection-item/manage-collection/data-status/index';
  import DataStorage from '../log-collection/collection-item/manage-collection/data-storage';
  import FieldInfo from '../log-collection/collection-item/manage-collection/field-info.tsx';
  import IntroPanel from './components/intro-panel';

  export default {
    setup() { return useIntroResize(400); },
    name: 'CollectionItem',
    components: {
      EmptyStatus,
      AuthContainerPage,
      BasicInfo,
      DataStorage,
      DataStatus,
      UsageDetails,
      IntroPanel,
      BasicTab,
      FieldInfo,
    },
    data() {
      return {
        basicLoading: true,
        detailFailed: false,
        authPageInfo: null,
        reportDetail: null,
        activePanel: this.$route.query.type || 'basicInfo',
        isOpenWindow: true,
        editAuth: false,
        editAuthData: null,
        panels: [
          { name: 'basicInfo', label: this.$t('配置信息') },
          { name: 'dataStorage', label: this.$t('数据存储') },
          { name: 'fieldInfo', label: this.$t('字段信息') },
          { name: 'dataStatus', label: this.$t('数据状态') },
          { name: 'usageDetails', label: this.$t('使用详情') },
        ],
      };
    },
    computed: {
      showReportDetail() {
        return !this.basicLoading && !this.detailFailed && !this.authPageInfo && Boolean(this.reportDetail);
      },
      dynamicComponent() {
        const componentMaP = {
          basicInfo: 'BasicInfo',
          dataStorage: 'DataStorage',
          fieldInfo: 'FieldInfo',
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
    mounted() {
      this.$nextTick(() => {
        this.maxIntroWidth = this.$refs.detailRef.clientWidth - 380;
      });
    },
    methods: {
      renderDrawerDetailSkeleton,
      async initPage() {
        this.basicLoading = true;
        this.detailFailed = false;
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
          const res = await useApplicationStore().checkAndGetData(paramData);
          if (res.isAllowed === false) {
            this.authPageInfo = res.data;
            // 显示无权限页面
          } else {
            // 正常显示页面
            const { data: reportDetail } = await ServicesInstance.collect.details({
              params: {
                collector_config_id: this.$route.params.collectorId,
              },
            });
            this.reportDetail = reportDetail;
            useCollectionStore().setCurCollect(reportDetail);
          }
        } catch (err) {
          this.detailFailed = true;
          console.warn(err);
        } finally {
          this.basicLoading = false;
        }
      },
      handleActiveDetails(state) {
        this.isOpenWindow = state;
        this.introWidth = state ? 360 : 0;
      },
      handleGoSearch() {
        const params = {
          indexId: this.reportDetail.index_set_id
            ? this.reportDetail.index_set_id
            : this.reportDetail.bkdata_index_set_ids[0],
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
          const res = await useApplicationStore().checkAndGetData(paramData);
          if (!res.isAllowed) this.editAuthData = res.data;
          this.editAuth = res.isAllowed;
        } catch {
          this.editAuth = false;
        }
      },
    },
  };
</script>

<style lang="scss">
  .intro-container {
    position: fixed;
    top: 99px;
    right: 0;
    z-index: var(--bklog-z-dropdown);
    height: calc(100vh - 99px);
    overflow: hidden;

    .drag-item {
      position: absolute;
      top: 48%;
      right: 304px;
      z-index: var(--bklog-z-nav-top);
      display: inline-block;
      width: 20px;
      height: 40px;
      color: #c4c6cc;
      cursor: col-resize;
      user-select: none;

      &.hidden-drag {
        display: none;
      }

      .icon-more::after {
        position: absolute;
        top: 12px;
        left: 0;
        content: '\e189';
      }
    }

    &.draging-move {
      border-left-color: #3a84ff;
    }
  }
</style>
