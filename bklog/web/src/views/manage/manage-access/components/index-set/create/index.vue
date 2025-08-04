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
    class="create-index-container"
    v-bkloading="{ isLoading: basicLoading }"
    data-test-id="logIndexSetBox_div_newlogIndexSetBox"
  >
    <auth-container-page
      v-if="authPageInfo"
      :info="authPageInfo"
    ></auth-container-page>
    <template v-else>
      <article class="article">
        <h3 class="title">{{ $t('基础信息') }}</h3>
        <bk-form
          ref="formRef"
          class="king-form"
          :label-width="160"
          :model="formData"
          :rules="formRules"
        >
          <bk-form-item
            :label="$t('索引集名称')"
            property="index_set_name"
            required
          >
            <bk-input
              v-model="formData.index_set_name"
              data-test-id="newlogIndexSetBox_input_indexSetName"
            >
            </bk-input>
          </bk-form-item>
          <bk-form-item
            :label="$t('数据分类')"
            property="category_id"
            required
          >
            <bk-select
              v-model="formData.category_id"
              :clearable="false"
              data-test-id="newlogIndexSetBox_select_dataClassification"
            >
              <template>
                <bk-option-group
                  v-for="item in globalsData.category"
                  :id="item.id"
                  :key="item.id"
                  :name="item.name"
                >
                  <bk-option
                    v-for="option in item.children"
                    :id="option.id"
                    :key="option.id"
                    :name="`${item.name}-${option.name}`"
                  >
                    {{ option.name }}
                  </bk-option>
                </bk-option-group>
              </template>
            </bk-select>
          </bk-form-item>
        </bk-form>
      </article>
      <article class="article">
        <h3 class="title">{{ subTitle }}</h3>
        <template>
          <div
            v-if="scenarioId === 'es'"
            class="collection-form"
          >
            <div class="collection-label">{{ $t('集群') }}</div>
            <div class="collection-select">
              <bk-select
                v-model="formData.storage_cluster_id"
                v-bk-tooltips.top="{
                  content: $t('不能跨集群添加多个索引，切换集群请先清空索引'),
                  delay: 300,
                  disabled: !formData.indexes.length,
                }"
                :clearable="false"
                :disabled="!!formData.indexes.length"
                data-test-id="newlogIndexSetBox_select_selectCluster"
                searchable
              >
                <bk-option
                  v-for="option in clusterList"
                  class="custom-no-padding-option"
                  v-show="option.storage_cluster_id"
                  :id="option.storage_cluster_id"
                  :key="option.storage_cluster_id"
                  :name="option.storage_cluster_name"
                >
                  <!-- <div
                    v-if="!(option.permission && option.permission[authorityMap.MANAGE_ES_SOURCE_AUTH])"
                    class="option-slot-container no-authority"
                    @click.stop
                  >
                    <span class="text">{{ option.storage_cluster_name }}</span>
                    <span
                      class="apply-text"
                      @click="applyClusterAccess(option)"
                      >{{ $t('申请权限') }}</span
                    >
                  </div> -->
                  <div
                    class="option-slot-container"
                  >
                    {{ option.storage_cluster_name }}
                  </div>
                </bk-option>
              </bk-select>
            </div>
          </div>
          <div class="collection-form">
            <div class="collection-label">{{ $t('已选索引') }}</div>
            <div class="selected-collection">
              <template>
                <bk-tag
                  v-for="(item, index) in formData.indexes"
                  :class="{ 'selected-tag': scenarioId === 'es' }"
                  :key="item.result_table_id"
                  :theme="getIndexActive(item.result_table_id)"
                  closable
                  @click="handleClickTag(item.result_table_id)"
                  @close="removeCollection(index, item.result_table_id)"
                >
                  <span
                    style="max-width: 360px"
                    class="title-overflow"
                    v-bk-overflow-tips
                  >
                    {{ item.result_table_id }}
                  </span>
                </bk-tag>
              </template>
              <bk-button
                class="king-button"
                data-test-id="newlogIndexSetBox_button_addNewIndex"
                icon="plus"
                @click="openDialog"
              ></bk-button>
            </div>
          </div>
          <div
            v-if="scenarioId !== 'es'"
            class="collection-form"
          >
            <div class="collection-label not-required"></div>
            <div
              style="width: 500px"
              class="selected-collection"
            >
              <bk-table
                v-bkloading="{ isLoading: tableLoading }"
                :data="collectionTableData"
                max-height="400"
              >
                <bk-table-column
                  :label="$t('字段')"
                  min-width="240"
                  prop="field_name"
                >
                  <template #default="props">
                    <span
                      class="title-overflow"
                      v-bk-overflow-tips
                      >{{ props.row.field_name }}</span
                    >
                  </template>
                </bk-table-column>
                <bk-table-column
                  :label="$t('类型')"
                  min-width="250"
                  prop="field_type"
                >
                  <template #default="props">
                    <span
                      class="title-overflow"
                      v-bk-overflow-tips
                      >{{ props.row.field_type }}</span
                    >
                  </template>
                </bk-table-column>
                <template #empty>
                  <div>
                    <span>{{ $t('暂无数据') }}</span>
                  </div>
                </template>
              </bk-table>
            </div>
          </div>
          <div
            v-else
            class="collection-form"
          >
            <div class="collection-label not-required"></div>
            <div
              style="width: 500px"
              class="selected-collection"
            >
              <bk-table
                v-bkloading="{ isLoading: tableLoading }"
                :data="currentMatchedTableIds"
                max-height="400"
              >
                <bk-table-column
                  :label="$t('匹配到的索引')"
                  max-width="490"
                  property="result_table_id"
                >
                </bk-table-column>
                <template #empty>
                  <div>
                    <span>{{ $t('暂无数据') }}</span>
                  </div>
                </template>
              </bk-table>
            </div>
          </div>
          <div
            v-if="scenarioId === 'es'"
            class="collection-form"
          >
            <div class="collection-label not-required">{{ $t('时间字段') }}</div>
            <div class="selected-collection time-filed">
              {{ getTimeFiled }}
            </div>
          </div>
        </template>
      </article>
      <article
        v-if="scenarioId !== 'log'"
        class="article"
      >
        <div class="title">
          <span>{{ $t('字段设置') }}</span>
          <span class="title-tips">
            <i class="bk-icon icon-exclamation-circle"></i>
            <span>{{ $t('未匹配到对应字段，请手动指定字段后提交') }}</span>
          </span>
        </div>
        <div class="collection-form">
          <div class="collection-label not-required">
            <span
              class="dotted-line"
              v-bk-tooltips="$t('用于标识日志文件来源及唯一性')"
            >
              {{ $t('目标字段') }}
            </span>
          </div>
          <div class="collection-select">
            <bk-select
              v-model="formData.target_fields"
              :collapse-tag="false"
              :is-tag-width-limit="false"
              display-tag
              multiple
              searchable
            >
              <bk-option
                v-for="option in targetFieldSelectList"
                :id="option.id"
                :key="option.id"
                :name="option.name"
              >
              </bk-option>
            </bk-select>
          </div>
        </div>
        <div class="collection-form">
          <div class="collection-label not-required">
            <span
              class="dotted-line"
              v-bk-tooltips="$t('用于控制日志排序的字段')"
            >
              {{ $t('排序字段') }}
            </span>
          </div>
          <div class="collection-select sort-box">
            <vue-draggable
              v-model="formData.sort_fields"
              animation="150"
              handle=".icon-grag-fill"
            >
              <transition-group>
                <bk-tag
                  v-for="item in formData.sort_fields"
                  ext-cls="tag-items"
                  :key="item"
                  closable
                  @close="handleCloseSortFiled(item)"
                >
                  <i class="bk-icon icon-grag-fill"></i>
                  {{ item }}
                </bk-tag>
              </transition-group>
            </vue-draggable>
            <bk-select
              :ext-cls="`add-sort-btn ${!formData.sort_fields.length && 'not-sort'}`"
              :popover-min-width="240"
              searchable
              @selected="handleAddSortFields"
            >
              <template #trigger>
                <bk-button
                  class="king-button"
                  icon="plus"
                ></bk-button>
              </template>
              <bk-option
                v-for="option in targetFieldSelectList"
                :disabled="getSortDisabledState(option.id)"
                :id="option.id"
                :key="option.id"
                :name="option.name"
              >
              </bk-option>
            </bk-select>
          </div>
        </div>
      </article>
      <bk-button
        style="width: 86px"
        :loading="submitLoading"
        data-test-id="newlogIndexSetBox_button_submit"
        theme="primary"
        @click="submitForm"
      >
        {{ $t('提交') }}
      </bk-button>
      <component
        ref="selectCollectionRef"
        :is="scenarioId === 'es' ? 'SelectEs' : 'SelectCollection'"
        :parent-data="formData"
        :time-index.sync="timeIndex"
        @selected="addCollection"
      />
    </template>
  </div>
</template>

<script>
  import { projectManages } from '@/common/util';
  import AuthContainerPage from '@/components/common/auth-container-page';
  import VueDraggable from 'vuedraggable';
  import { mapGetters, mapState } from 'vuex';

  import * as authorityMap from '../../../../../../common/authority-map';
  import SelectCollection from './select-collection';
  import SelectEs from './select-es';

  export default {
    name: 'IndexSetCreate',
    components: {
      SelectCollection,
      SelectEs,
      AuthContainerPage,
      VueDraggable,
    },
    data() {
      const scenarioId = this.$route.name.split('-')[0];
      return {
        scenarioId,
        isEdit: false, // 编辑索引集 or 新建索引集
        basicLoading: false,
        submitLoading: false,
        authPageInfo: null,
        isSubmit: false,
        clusterList: [], // 集群列表
        timeIndex: null,
        formData: {
          scenario_id: scenarioId, // 采集接入
          index_set_name: '', // 索引集名称
          category_id: '', // 数据分类
          storage_cluster_id: '', // 集群
          indexes: [], // 采集项
          target_fields: [],
          sort_fields: [],
        },
        formRules: {
          index_set_name: [
            {
              required: true,
              trigger: 'blur',
            },
          ],
          category_id: [
            {
              required: true,
              trigger: 'blur',
            },
          ],
          storage_cluster_id: [
            {
              required: true,
              trigger: 'blur',
            },
          ],
        },
        tableLoading: false,
        currentActiveShowID: '',
        currentMatchedTableIds: [], // 匹配到的索引 id，result table id list
        collectionTableData: [],
        targetFieldSelectList: [],
      };
    },
    computed: {
      ...mapState(['spaceUid', 'bkBizId', 'showRouterLeaveTip']),
      ...mapState('collect', ['curIndexSet']),
      ...mapGetters('globals', ['globalsData']),
      authorityMap() {
        return authorityMap;
      },
      collectProject() {
        return projectManages(this.$store.state.topMenu, 'collection-item');
      },
      subTitle() {
        const textMap = {
          log: this.$t('采集项'),
          es: this.$t('索引'),
          bkdata: this.$t('数据源'),
        };
        return textMap[this.scenarioId];
      },
      getTimeFiled() {
        return this.timeIndex?.time_field || '--';
      },
    },
    created() {
      this.checkAuth();
      this.fetchPageData();
      this.getIndexStorage();
    },

    beforeRouteLeave(to, from, next) {
      if (!this.isSubmit && !this.showRouterLeaveTip) {
        this.$bkInfo({
          title: this.$t('是否放弃本次操作？'),
          confirmFn: () => {
            next();
          },
        });
        return;
      }
      next();
    },
    methods: {
      // 检查权限、确认基本信息
      async checkAuth() {
        try {
          this.basicLoading = true;
          const isEdit = this.$route.name.endsWith('edit');
          this.isEdit = isEdit;
          const paramData = isEdit
            ? {
                action_ids: [authorityMap.MANAGE_INDICES_AUTH],
                resources: [
                  {
                    type: 'indices',
                    id: this.$route.params.indexSetId,
                  },
                ],
              }
            : {
                action_ids: [authorityMap.CREATE_INDICES_AUTH],
                resources: [
                  {
                    type: 'space',
                    id: this.spaceUid,
                  },
                ],
              };
          const res = await this.$store.dispatch('checkAndGetData', paramData);
          if (res.isAllowed === false) {
            this.authPageInfo = res.data;
          }
          if (isEdit) {
            await this.fetchIndexSetData();
            const data = this.curIndexSet;
            Object.assign(this.formData, {
              index_set_name: data.index_set_name,
              category_id: data.category_id,
              storage_cluster_id: this.scenarioId === 'log' ? '' : data.storage_cluster_id,
              indexes: data.indexes,
              target_fields: data.target_fields ?? [],
              sort_fields: data.sort_fields ?? [],
            });
            this.timeIndex = {
              time_field: data.time_field,
              time_field_type: data.time_field_type,
              time_field_unit: data.time_field_unit,
            };
            await this.handleChangeShowTableList(data.indexes[0].result_table_id, true);
          }
        } catch (err) {
          console.warn(err);
          this.$nextTick(this.returnIndexList);
        } finally {
          this.basicLoading = false;
        }
      },
      // 索引集详情
      async fetchIndexSetData() {
        const indexSetId = this.$route.params.indexSetId.toString();
        if (!this.curIndexSet.index_set_id || this.curIndexSet.index_set_id.toString() !== indexSetId) {
          const { data: indexSetData } = await this.$http.request('indexSet/info', {
            params: {
              index_set_id: indexSetId,
            },
          });
          this.$store.commit('collect/updateCurIndexSet', indexSetData);
        }
      },
      // 初始化集群列表
      async fetchPageData() {
        try {
          if (this.scenarioId !== 'es') return;
          const clusterRes = await this.$http.request('/source/logList', {
            query: {
              bk_biz_id: this.bkBizId,
              scenario_id: 'es',
            },
          });
          // 有权限的优先展示
          const s1 = [];
          const s2 = [];
          for (const item of clusterRes.data) {
            if (item.permission?.[authorityMap.MANAGE_ES_SOURCE_AUTH]) {
              s1.push(item);
            } else {
              s2.push(item);
            }
          }
          this.clusterList = s1.concat(s2).filter(item => !item.is_platform);
          if (this.$route.query.cluster) {
            const clusterId = this.$route.query.cluster;
            if (this.clusterList.some(item => item.storage_cluster_id === Number(clusterId))) {
              this.formData.storage_cluster_id = Number(clusterId);
            }
          }
        } catch (e) {
          console.warn(e);
        }
      },
      async getIndexStorage() {
        // 索引集列表的集群
        try {
          if (this.scenarioId !== 'log') return;
          const queryData = { bk_biz_id: this.bkBizId };
          const res = await this.$http.request('collect/getStorage', {
            query: queryData,
          });
          if (res.data) {
            // 根据权限排序
            const s1 = [];
            const s2 = [];
            for (const item of res.data) {
              if (item.permission?.manage_es_source) {
                s1.push(item);
              } else {
                s2.push(item);
              }
            }
            this.clusterList = s1.concat(s2);
          }
        } catch (e) {
          console.warn(e);
        }
      },
      // 申请集群权限
      async applyClusterAccess(option) {
        try {
          this.$el.click(); // 因为下拉在loading上面所以需要关闭下拉
          this.basicLoading = true;
          const res = await this.$store.dispatch('getApplyData', {
            action_ids: [authorityMap.MANAGE_ES_SOURCE_AUTH],
            resources: [
              {
                type: 'es_source',
                id: option.storage_cluster_id,
              },
            ],
          });
          window.open(res.data.apply_url);
        } catch (err) {
          console.warn(err);
        } finally {
          this.basicLoading = false;
        }
      },
      // 增加采集项
      openDialog() {
        if (this.scenarioId === 'es' && !this.formData.storage_cluster_id) {
          return this.messageError(this.$t('请选择集群'));
        }
        this.$refs.selectCollectionRef.openDialog();
      },
      addCollection(item) {
        item.scenarioId = this.scenarioId;
        this.formData.indexes.push(item);
        this.handleChangeShowTableList(item.result_table_id, true);
      },
      handleClickTag(resultTableID) {
        if (this.scenarioId === 'es') this.handleChangeShowTableList(resultTableID, false);
      },
      // 删除采集项
      removeCollection(index, closeID) {
        this.formData.indexes.splice(index, 1);
        if (!this.formData.indexes.length) {
          this.timeIndex = null;
          this.currentMatchedTableIds = [];
        }
        if (this.currentActiveShowID === closeID || this.scenarioId !== 'es') {
          this.handleChangeShowTableList(this.formData.indexes[0].result_table_id, true);
        }
      },
      // 新建索引集提交
      async submitForm() {
        try {
          await this.$refs.formRef.validate();
          if (!this.formData.indexes.length) {
            return this.messageError(this.$t('请选择索引'));
          }
          this.submitLoading = true;
          this.formData.indexes.forEach(item => {
            item.scenarioId = this.scenarioId;
          });
          const requestBody = Object.assign(
            {
              view_roles: [], // 兼容后端历史遗留代码
              space_uid: this.spaceUid,
            },
            this.formData,
          );
          if (this.scenarioId === 'es') {
            Object.assign(requestBody, this.timeIndex);
          } else {
            delete requestBody.storage_cluster_id;
          }
          const res = this.isEdit
            ? await this.$http.request('/indexSet/update', {
                params: {
                  index_set_id: this.$route.params.indexSetId,
                },
                data: requestBody,
              })
            : await this.$http.request('/indexSet/create', { data: requestBody });
          this.isSubmit = true;
          this.handleCreatSuccess(res.data);
        } catch (e) {
          console.warn(e);
        } finally {
          this.submitLoading = false;
        }
      },
      handleCreatSuccess({ bkdata_auth_url: authUrl, index_set_id: id }) {
        if (authUrl) {
          let redirectUrl = ''; // 数据平台授权地址
          if (process.env.NODE_ENV === 'development') {
            redirectUrl = `${authUrl}&redirect_url=${window.origin}/static/auth.html`;
          } else {
            let siteUrl = window.SITE_URL;
            if (siteUrl.startsWith('http')) {
              if (!siteUrl.endsWith('/')) siteUrl += '/';
              redirectUrl = `${authUrl}&redirect_url=${siteUrl}bkdata_auth/`;
            } else {
              if (!siteUrl.startsWith('/')) siteUrl = `/${siteUrl}`;
              if (!siteUrl.endsWith('/')) siteUrl += '/';
              redirectUrl = `${authUrl}&redirect_url=${window.origin}${siteUrl}bkdata_auth/`;
            }
          }
          // auth.html 返回索引集管理的路径
          let indexSetPath = '';
          const { href } = this.$router.resolve({
            name: `${this.scenarioId}-index-set-list`,
          });
          let siteUrl = window.SITE_URL;
          if (siteUrl.startsWith('http')) {
            if (!siteUrl.endsWith('/')) siteUrl += '/';
            indexSetPath = siteUrl + href;
          } else {
            if (!siteUrl.startsWith('/')) siteUrl = `/${siteUrl}`;
            if (!siteUrl.endsWith('/')) siteUrl += '/';
            indexSetPath = window.origin + siteUrl + href;
          }
          // auth.html 需要使用的数据
          const urlComponent = `?indexSetId=${id}&ajaxUrl=${window.AJAX_URL_PREFIX}&redirectUrl=${indexSetPath}`;
          redirectUrl += encodeURIComponent(urlComponent);
          if (self !== top) {
            // 当前页面是 iframe
            window.open(redirectUrl);
            this.returnIndexList();
          } else {
            window.location.assign(redirectUrl);
          }
        } else {
          this.messageSuccess(this.isEdit ? this.$t('设置成功') : this.$t('创建成功'));
          this.returnIndexList();
        }
      },
      returnIndexList() {
        const { editName: _, ...rest } = this.$route.query;
        this.$router.push({
          name: this.$route.name.replace(/create|edit/, 'list'),
          query: { ...rest },
        });
      },
      getIndexActive(resultTableId) {
        if (this.scenarioId !== 'es') return '';
        if (resultTableId === this.currentActiveShowID) return 'info';
        return '';
      },
      handleCloseSortFiled(item) {
        const splitIndex = this.formData.sort_fields.findIndex(fItem => fItem === item);
        this.formData.sort_fields.splice(splitIndex, 1);
      },
      async handleChangeShowTableList(resultTableId, isInitTarget = false) {
        this.currentActiveShowID = resultTableId;
        if (this.scenarioId === 'es') {
          this.currentMatchedTableIds = await this.fetchList(resultTableId);
        } else {
          this.collectionTableData = await this.collectList();
        }
        if (isInitTarget) this.initTargetFieldSelectList();
      },
      async fetchList(resultTableId) {
        this.tableLoading = true;
        try {
          const res = await this.$http.request('/resultTables/list', {
            query: {
              scenario_id: this.scenarioId,
              bk_biz_id: this.bkBizId,
              storage_cluster_id: this.formData.storage_cluster_id,
              result_table_id: resultTableId,
            },
          });
          return res.data;
        } catch (e) {
          console.warn(e);
          return [];
        } finally {
          this.tableLoading = false;
        }
      },
      async collectList() {
        this.tableLoading = true;
        try {
          const resultTableID = this.formData.indexes.map(item => item.result_table_id);
          const queryData = resultTableID.map(item => ({
            params: {
              result_table_id: item,
            },
            query: {
              scenario_id: this.scenarioId,
              bk_biz_id: this.bkBizId,
            },
          }));
          const promiseQuery = queryData.map(item =>
            this.$refs.selectCollectionRef.handleCollectionSelected(null, item),
          );
          const res = await Promise.all(promiseQuery);
          const collectionMap = new Map();
          res.forEach(item => {
            item.data.fields.forEach(el => {
              if (!collectionMap.has(el.field_name)) {
                collectionMap.set(el.field_name, el);
              }
            });
          });
          return [...collectionMap.values()];
        } catch (error) {
          console.warn(error);
          return [];
        } finally {
          this.tableLoading = false;
        }
      },
      /**
       * @desc: 初始化字段设置所需的字段
       */
      async initTargetFieldSelectList() {
        const resultTableID = this.formData.indexes.map(item => item.result_table_id);
        const queryData = resultTableID.map(item => ({
          params: {
            result_table_id: item,
          },
          query: {
            scenario_id: this.scenarioId,
            bk_biz_id: this.bkBizId,
            storage_cluster_id: this.scenarioId === 'es' ? this.formData.storage_cluster_id : undefined,
          },
        }));
        let promiseQuery = [];
        if (this.scenarioId === 'es') {
          promiseQuery = queryData.map(item => this.$refs.selectCollectionRef.fetchInfo(item));
        } else {
          promiseQuery = queryData.map(item => this.$refs.selectCollectionRef.handleCollectionSelected(null, item));
        }
        const res = await Promise.all(promiseQuery);
        const { target_fields: targetField, sort_fields: sortFields } = this.formData;
        const targetFieldSet = new Set([...(sortFields ?? []), ...(targetField ?? [])]);
        res.forEach(item => {
          item.data.fields.forEach(el => {
            if (!targetFieldSet.has(el.field_name)) {
              targetFieldSet.add(el.field_name);
            }
          });
        });
        this.targetFieldSelectList = [...targetFieldSet].map(item => ({
          id: item,
          name: item,
        }));
      },
      handleAddSortFields(val) {
        this.formData.sort_fields.push(val);
      },
      getSortDisabledState(id) {
        return this.formData.sort_fields.includes(id);
      },
    },
  };
</script>

<style scoped lang="scss">
  @import '@/scss/mixins/overflow-tips.scss';
  @import '@/scss/mixins/flex.scss';

  .sort-box {
    display: inline-flex;
    align-items: center;

    .add-sort-btn {
      display: inline-block;
      margin-left: 6px;
      border: none;
      box-shadow: none;
    }

    .not-sort {
      margin-left: 0;
    }
  }

  .create-index-container {
    padding: 20px 24px;

    .article {
      padding: 22px 24px;
      margin-bottom: 20px;
      background-color: #fff;
      border: 1px solid #dcdee5;
      border-radius: 3px;

      .title {
        margin: 0 0 10px;
        font-size: 14px;
        font-weight: bold;
        line-height: 20px;
        color: #63656e;
      }

      .title-tips {
        margin-left: 16px;
        font-size: 12px;
        font-weight: normal;

        .icon-exclamation-circle {
          font-size: 16px;
          color: #ea3636;
        }
      }

      .king-form {
        width: 588px;

        :deep(.bk-form-item) {
          padding: 10px 0;
          margin: 0;
        }
      }

      .collection-form {
        display: flex;
        font-size: 14px;
        color: #63656e;

        .collection-label {
          position: relative;
          width: 160px;
          padding: 10px 24px 10px 0;
          font-size: 12px;
          line-height: 32px;
          text-align: right;

          &:after {
            position: absolute;
            top: 12px;
            right: 16px;
            display: inline-block;
            font-size: 12px;
            color: #ea3636;
            content: '*';
          }
        }

        .not-required {
          &:after {
            /* stylelint-disable-next-line declaration-no-important */
            content: '' !important;
          }
        }

        .collection-select {
          width: 428px;
          padding: 10px 0;

          .tag-items {
            height: 32px;
            line-height: 32px;

            .icon-grag-fill {
              display: inline-block;
              cursor: move;
              transform: translateY(-1px);
            }
          }
        }

        .dotted-line {
          border-bottom: 1px dashed #63656e;
        }

        .selected-collection {
          display: flex;
          flex-flow: wrap;
          padding: 10px 0 0;

          :deep(.bk-tag) {
            display: inline-flex;
            align-items: center;
            height: 32px;
            padding: 0 4px 0 10px;
            margin: 0 10px 10px 0;
            line-height: 32px;
            background: #f0f1f5;
            background-color: #f0f1f5;

            .bk-tag-close {
              font-size: 18px;
              color: #63656e;
            }

            &.bk-tag-info {
              /* stylelint-disable-next-line declaration-no-important */
              background: #ebf2ff !important;
            }
          }

          .selected-tag {
            cursor: pointer;
          }
        }

        .time-filed {
          align-items: center;
          padding-top: 0;
          font-size: 12px;
        }
      }
    }

    .king-button {
      &.no-slot {
        padding: 0 5px;
      }
    }
  }
</style>
