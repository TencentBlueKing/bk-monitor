<!-- eslint-disable vue/no-deprecated-slot-attribute -->
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
  <bk-dialog
    v-model="showDialog"
    :mask-close="false"
    :show-footer="false"
    :title="$t('新增索引')"
    :width="680"
    header-position="left"
  >
    <div
      class="slot-container"
      v-bkloading="{ isLoading: basicLoading }"
    >
      <bk-form
        ref="formRef"
        :label-width="100"
        :model="formData"
        :rules="formRules"
      >
        <bk-form-item
          :label="$t('索引')"
          property="resultTableId"
          v-if="scenarioId === 'bkdata'"
          required
        >
          <bk-select
            v-model="formData.resultTableId"
            :clearable="false"
            data-test-id="addIndex_select_selectIndex"
            searchable
            @selected="val => handleCollectionSelected(val)"
          >
            <bk-option
              v-for="item in getShowCollectionList"
              class="custom-no-padding-option"
              :disabled="parentData.indexes.some(selectedItem => item.result_table_id === selectedItem.result_table_id)"
              :id="item.result_table_id"
              :key="item.result_table_id"
              :name="`${item.result_table_name_alias}(${item.result_table_id})`"
            >
              <div
                class="option-slot-container"
              >
                {{ item.result_table_name_alias }}
              </div>
            </bk-option>
          </bk-select>
        </bk-form-item>
        <bk-form-item
          v-else
          :label="$t('索引')"
          property="resultTableIds"
          required
        >
          <bk-select
            v-model="formData.resultTableIds"
            :clearable="false"
            multiple
            data-test-id="addIndex_multiple_select_selectIndex"
            searchable
            @selected="(value) => handleLogSelected(value)"
          >
            <bk-option
              v-for="item in getShowCollectionList"
              class="custom-no-padding-option"
              :disabled="parentData.indexes.some(selectedItem => item.result_table_id === selectedItem.result_table_id)"
              :id="item.result_table_id"
              :key="item.result_table_id"
              :name="`${item.result_table_name_alias}(${item.result_table_id})`"
            >
              <div
                v-if="!(item.permission && item.permission[authorityMap.MANAGE_COLLECTION_AUTH])"
                class="option-slot-container no-authority"
                @click.stop
              >
                <span class="text">{{ item.result_table_name_alias }}</span>
                <span
                  class="apply-text"
                  @click="applyCollectorAccess(item)"
                  >{{ $t('申请权限') }}</span
                >
              </div>
              <div
                v-else
                class="option-slot-container"
              >
                {{ item.result_table_name_alias }}
              </div>
            </bk-option>
          </bk-select>
        </bk-form-item>
        <bk-form-item label="">
          <bk-table
            v-bkloading="{ isLoading: tableLoading }"
            :data="tableData"
            max-height="400"
            ext-cls="table-container-collection"
          >
            <bk-table-column
              :label="$t('字段')"
              min-width="240"
              prop="field_name"
            >
              <template #default="props">
                <span
                  class="overflow-tips"
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
                  class="overflow-tips"
                  v-bk-overflow-tips
                  >{{ props.row.field_type }}</span
                >
              </template>
            </bk-table-column>
            <template #empty>
              <div>
                <empty-status empty-type="empty" />
              </div>
            </template>
          </bk-table>
        </bk-form-item>
      </bk-form>
      <div
        class="button-footer"
        slot="footer"
      >
        <bk-button
          class="king-button"
          :loading="confirmLoading"
          data-test-id="addIndex_button_confirm"
          theme="primary"
          @click="handleConfirm"
        >
          {{ $t('添加') }}
        </bk-button>
        <bk-button
          class="king-button"
          @click="handleCancel"
          >{{ $t('取消') }}</bk-button
        >
      </div>
    </div>
  </bk-dialog>
</template>

<script>
  import EmptyStatus from '@/components/empty-status';
  import { mapState } from 'vuex';
  import * as authorityMap from '../../../../../../common/authority-map';

  export default {
    components: {
      EmptyStatus,
    },
    props: {
      parentData: {
        type: Object,
        required: true,
      },
    },
    data() {
      const scenarioId = this.$route.name.split('-')[0];
      return {
        scenarioId,
        showDialog: false,
        basicLoading: false,
        tableLoading: false,
        confirmLoading: false,
        collectionList: [], // log bkdata 下拉列表
        tableData: [], // log bkdata 表格
        formData: {
          resultTableId: '',
          resultTableIds: [],
        },
        formRules: {
          resultTableId: [
            {
              required: true,
              trigger: 'blur',
            },
          ],
          resultTableIds: [
            {
              required: true,
              trigger: 'blur',
            },
          ],
        },
        searchData:[],// log 多选时搜索结果
      };
    },
    computed: {
      ...mapState(['spaceUid', 'bkBizId']),
      authorityMap() {
        return authorityMap;
      },
      getShowCollectionList() {
        if (this.parentData.storage_cluster_id && this.scenarioId === 'log') {
          return this.collectionList.filter(item => item.storage_cluster_id === this.parentData.storage_cluster_id);
        }
        return this.collectionList;
      },
    },
    mounted() {
      this.fetchCollectionList();
    },
    methods: {
      openDialog() {
        this.showDialog = true;
        this.emptyType = 'empty';
        Object.assign(this, {
          basicLoading: false,
          tableLoading: false,
          confirmLoading: false,
          tableData: [], // log bkdata 表格
          formData: {
            resultTableId: '',
            resultTableIds: [],
          },
        });
      },
      // 获取下拉列表
      async fetchCollectionList() {
        try {
          this.basicLoading = true;
          const res = await this.$http.request('/resultTables/list', {
            query: {
              scenario_id: this.scenarioId,
              bk_biz_id: this.bkBizId,
            },
          });
          this.collectionList = res.data.map(item => {
            // 后端要传这个值，虽然不太合理
            item.bk_biz_id = this.bkBizId;
            return item;
          });
        } catch (e) {
          console.warn(e);
        } finally {
          this.basicLoading = false;
        }
      },
      // 选择采集项
      async handleCollectionSelected(id, foreignParams) {
        try {
          this.tableLoading = true;
          const res = await this.$http.request(
            '/resultTables/info',
            !!foreignParams
              ? foreignParams
              : {
                  params: {
                    result_table_id: id,
                  },
                  query: {
                    scenario_id: this.scenarioId,
                    bk_biz_id: this.bkBizId,
                  },
                },
          );
          if (foreignParams) return res;
          this.tableData = res.data.fields;
          this.tableLoading = false;
        } catch (e) {
          console.warn(e);
        }
      },
      // 选择采集项获取字段列表
      async handleMultipleSelected(id) {
        try {
          const res = await this.$http.request(
            '/resultTables/info',
            {
              params: {
                result_table_id: id,
              },
              query: {
                scenario_id: this.scenarioId,
                bk_biz_id: this.bkBizId,
              },
            },
          );
           return res.data?.fields || [];
        } catch (e) {
          console.warn(e);
          return [];
        }
      },
      async handleLogSelected(value){
        const existingIds = new Set(this.searchData.map(item => item.id));
        this.searchData = this.searchData.filter(item => value.includes(item.id));
        const newEntriesPromises = value
          .filter(id => !existingIds.has(id)) 
          .map(async id => {
            try {
              const data = await this.handleMultipleSelected(id);
              return { id, data };
            } catch (error) {
              console.error(`Error fetching data for id ${id}:`, error);
              return null; 
            }
          });
        const newEntries = await Promise.all(newEntriesPromises);
        this.searchData.push(...newEntries.filter(entry => entry !== null));
        const collectionMap = new Map();
        this.searchData.forEach(item => {
          item.data.forEach(el => {
            if (!collectionMap.has(el.field_name)) {
              collectionMap.set(el.field_name, el);
            }
          });
        });
        this.tableData = [...collectionMap.values()];
      },
      // 采集项-申请权限
      async applyCollectorAccess(option) {
        try {
          this.$el.click(); // 因为下拉在loading上面所以需要关闭下拉
          this.basicLoading = true;
          const res = await this.$store.dispatch('getApplyData', {
            action_ids: [authorityMap.MANAGE_COLLECTION_AUTH],
            resources: [
              {
                type: 'collection',
                id: option.collector_config_id,
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
      // 确认添加
      async handleConfirm() {
        try {
          await this.$refs.formRef.validate();
          this.confirmLoading = true;
          if(this.scenarioId === 'log') {
            this.formData.resultTableIds.forEach(resultTableId => {
              this.$emit(
              'selected',
              this.collectionList.find(item => item.result_table_id === resultTableId),
            );
            });
          }else{
            const data = {
              scenario_id: this.scenarioId,
              basic_indices: this.parentData.indexes.map(item => ({
                index: item.result_table_id,
              })),
              append_index: {
                index: this.formData.resultTableId,
              },
            };
            await this.$http.request('/resultTables/adapt', { data });
            this.$emit(
              'selected',
              this.collectionList.find(item => item.result_table_id === this.formData.resultTableId),
            );
          }
          this.showDialog = false;
        } catch (e) {
          console.warn(e);
        } finally {
          this.confirmLoading = false;
        }
      },
      handleCancel() {
        this.showDialog = false;
      },
    },
  };
</script>

<style scoped lang="scss">
  @import '@/scss/mixins/overflow-tips.scss';

  .slot-container {
    min-height: 363px;
    padding-right: 40px;

    :deep(.bk-form) {
      .bk-label {
        text-align: left;
      }
    }
  }

  .button-footer {
    margin-top: 20px;
    text-align: right;

    .king-button {
      width: 86px;

      &:first-child {
        margin-right: 8px;
      }
    }
  }

  .overflow-tips {
    @include overflow-tips;
  }

  .table-container-collection{
    :deep(.bk-table-body-wrapper){
      overflow-x: hidden;
    }
  }
</style>
