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
  <div class="archive-slider-container">
    <bk-sideslider
      :before-close="handleCloseSidebar"
      :is-show="showSlider"
      :quick-close="true"
      :title="isEdit ? $t('编辑归档') : $t('新建归档')"
      :width="676"
      transfer
      @animation-end="updateIsShow"
    >
      <template #content>
        <div
          class="archive-slider-content"
          v-bkloading="{ isLoading: sliderLoading }"
        >
          <bk-form
            v-if="!sliderLoading"
            ref="validateForm"
            class="king-form"
            :label-width="350"
            :model="formData"
            :rules="basicRules"
            data-test-id="addNewArchive_div_formContainer"
            form-type="vertical"
          >
            <bk-form-item
              :label="$t('选择采集项/采集插件')"
              property="instance_id"
              required
            >
              <bk-select
                v-model="formData.instance_id"
                :clearable="false"
                :disabled="isEdit"
                data-test-id="formContainer_select_selectCollector"
                searchable
                @change="handleCollectorChange"
              >
                <bk-option-group
                  v-for="item in collectorList"
                  :id="item.id"
                  :key="item.id"
                  :name="item.name"
                  show-collapse
                >
                  <bk-option
                    v-for="option in item.list"
                    :disabled="!option.permission[authorityMap.MANAGE_COLLECTION_AUTH]"
                    :id="option.id"
                    :key="option.id"
                    :name="option.name"
                  >
                    {{ option.name }}
                  </bk-option>
                </bk-option-group>
              </bk-select>
            </bk-form-item>
            <bk-form-item
              :label="$t('归档仓库')"
              property="target_snapshot_repository_name"
              required
            >
              <bk-select
                v-model="formData.target_snapshot_repository_name"
                :disabled="isEdit || !formData.instance_id"
                data-test-id="formContainer_select_selectStorehouse"
              >
                <bk-option
                  v-for="option in repositoryRenderList"
                  :disabled="!option.permission[authorityMap.MANAGE_ES_SOURCE_AUTH]"
                  :id="option.repository_name"
                  :key="option.repository_name"
                  :name="option.repository_name"
                >
                </bk-option>
              </bk-select>
            </bk-form-item>
            <bk-form-item
              :label="$t('过期时间')"
              property="snapshot_days"
              required
            >
              <bk-select
                style="width: 300px"
                v-model="formData.snapshot_days"
                :clearable="false"
                data-test-id="formContainer_select_selectExpireDate"
              >
                <template #trigger>
                  <div class="bk-select-name">
                    {{ getDaysStr }}
                  </div>
                </template>
                <template v-for="(option, index) in retentionDaysList">
                  <bk-option
                    :id="option.id"
                    :key="index"
                    :name="option.name"
                  ></bk-option>
                </template>
                <template #extension>
                  <div style="padding: 8px 0">
                    <bk-input
                      v-model="customRetentionDay"
                      :placeholder="$t('输入自定义天数，按 Enter 确认')"
                      :show-controls="false"
                      size="small"
                      type="number"
                      @enter="enterCustomDay($event)"
                    ></bk-input>
                  </div>
                </template>
              </bk-select>
            </bk-form-item>
            <bk-form-item style="margin-top: 40px">
              <bk-button
                class="king-button mr10"
                :loading="confirmLoading"
                data-test-id="formContainer_button_handleSubmit"
                theme="primary"
                @click.stop.prevent="handleConfirm"
              >
                {{ $t('提交') }}
              </bk-button>
              <bk-button
                data-test-id="formContainer_button_handleCancel"
                @click="handleCancel"
                >{{ $t('取消') }}</bk-button
              >
            </bk-form-item>
          </bk-form>
        </div>
      </template>
    </bk-sideslider>
  </div>
</template>

<script>
  import SidebarDiffMixin from '@/mixins/sidebar-diff-mixin';
  import { mapGetters } from 'vuex';

  import * as authorityMap from '../../../../../common/authority-map';

  export default {
    mixins: [SidebarDiffMixin],
    props: {
      showSlider: {
        type: Boolean,
        default: false,
      },
      editArchive: {
        type: Object,
        default: null,
      },
    },
    data() {
      return {
        confirmLoading: false,
        sliderLoading: false,
        customRetentionDay: '', // 自定义过期天数
        collectorList: [
          { id: 'collector_config', name: this.$t('采集项'), list: [] }, // 采集项
          { id: 'collector_plugin', name: this.$t('采集插件'), list: [] }, // 采集插件
        ], // 采集项列表
        repositoryOriginList: [], // 仓库列表
        // repositoryRenderList: [], // 根据采集项关联的仓库列表
        retentionDaysList: [], // 过期天数列表
        formData: {
          snapshot_days: '',
          instance_id: '',
          target_snapshot_repository_name: '',
        },
        collectorType: 'collector_config',
        basicRules: {},
        requiredRules: {
          required: true,
          trigger: 'blur',
        },
      };
    },
    computed: {
      ...mapGetters({
        bkBizId: 'bkBizId',
        globalsData: 'globals/globalsData',
      }),
      authorityMap() {
        return authorityMap;
      },
      isEdit() {
        return this.editArchive !== null;
      },
      repositoryRenderList() {
        let list = [];
        const collectorId = this.formData.instance_id;
        if (collectorId && this.collectorList.length && this.repositoryOriginList.length) {
          const targetList = this.collectorList.find(item => item.id === this.collectorType)?.list || [];
          const curCollector = targetList.find(collect => collect.id === collectorId);
          const clusterId = curCollector.storage_cluster_id;
          list = this.repositoryOriginList.filter(item => item.cluster_id === clusterId);
        }

        return list;
      },
      getDaysStr() {
        if (String(this.formData.snapshot_days) === '0') {
          return this.$t('永久');
        }
        return !!this.formData.snapshot_days ? this.formData.snapshot_days + this.$t('天') : '';
      },
    },
    watch: {
      async showSlider(val) {
        if (val) {
          this.sliderLoading = this.isEdit;
          await this.getCollectorList();
          await this.getRepoList();
          this.updateDaysList();

          if (this.isEdit) {
            const {
              instance_id: instanceId,
              target_snapshot_repository_name,
              snapshot_days,
              instance_type: instanceType,
            } = this.editArchive;
            Object.assign(this.formData, {
              instance_id: instanceId,
              target_snapshot_repository_name,
              snapshot_days,
            });
            this.collectorType = instanceType;
          }
          this.initSidebarFormData();
        } else {
          // 清空表单数据
          this.formData = {
            snapshot_days: '',
            instance_id: '',
            target_snapshot_repository_name: '',
          };
        }
      },
    },
    created() {
      this.basicRules = {
        instance_id: [this.requiredRules],
        target_snapshot_repository_name: [this.requiredRules],
        snapshot_days: [this.requiredRules],
      };
    },
    methods: {
      // 获取采集项列表
      getCollectorList() {
        const query = {
          bk_biz_id: this.bkBizId,
          have_data_id: 1,
        };
        this.$http.request('collect/getAllCollectors', { query }).then(res => {
          this.collectorList[0].list =
            res.data.map(item => {
              return {
                id: item.collector_config_id,
                name: item.collector_config_name,
                ...item,
              };
            }) || [];
        });
        this.$http.request('collect/getCollectorPlugins', { query }).then(res => {
          this.collectorList[1].list =
            res.data.map(item => {
              return {
                id: item.collector_plugin_id,
                name: item.collector_plugin_name,
                ...item,
              };
            }) || [];
        });
      },
      // 获取归档仓库列表
      getRepoList() {
        this.$http
          .request('archive/getRepositoryList', {
            query: {
              bk_biz_id: this.bkBizId,
            },
          })
          .then(res => {
            const { data } = res;
            this.repositoryOriginList = data || [];
          })
          .finally(() => {
            this.sliderLoading = false;
          });
      },
      handleCollectorChange(value) {
        this.collectorType = this.collectorList.find(item => item.list.some(val => val.id === value))?.id || '';
        this.formData.target_snapshot_repository_name = '';
      },
      updateIsShow() {
        this.$emit('hidden');
        this.$emit('update:show-slider', false);
      },
      handleCancel() {
        this.$emit('update:show-slider', false);
      },
      updateDaysList() {
        const retentionDaysList = [...this.globalsData.storage_duration_time].filter(item => {
          return item.id;
        });
        retentionDaysList.push({
          default: false,
          id: '0',
          name: this.$t('永久'),
        });
        this.retentionDaysList = retentionDaysList;
      },
      // 输入自定义过期天数
      enterCustomDay(val) {
        const numberVal = parseInt(val.trim(), 10);
        const stringVal = numberVal.toString();
        if (numberVal) {
          if (!this.retentionDaysList.some(item => item.id === stringVal)) {
            this.retentionDaysList.push({
              id: stringVal,
              name: stringVal + this.$t('天'),
            });
          }
          this.formData.snapshot_days = stringVal;
          this.customRetentionDay = '';
          document.body.click();
        } else {
          this.customRetentionDay = '';
          this.messageError(this.$t('请输入有效数值'));
        }
      },
      // 采集项列表点击申请采集项目管理权限
      async applyProjectAccess(item) {
        this.$el.click(); // 手动关闭下拉
        try {
          this.$bkLoading();
          const res = await this.$store.dispatch('getApplyData', {
            action_ids: [authorityMap.MANAGE_COLLECTION_AUTH],
            resources: [
              {
                type: 'collection',
                id: item.collector_config_id,
              },
            ],
          });
          window.open(res.data.apply_url);
        } catch (err) {
          console.warn(err);
        } finally {
          this.$bkLoading.hide();
        }
      },
      async handleConfirm() {
        try {
          await this.$refs.validateForm.validate();
          let url = '/archive/createArchive';
          const params = {};
          let paramsData = {
            ...this.formData,
            instance_type: this.collectorType,
            bk_biz_id: this.bkBizId,
          };

          if (this.isEdit) {
            url = '/archive/editArchive';
            const { snapshot_days } = this.formData;
            const { archive_config_id } = this.editArchive;
            paramsData = {
              snapshot_days,
            };

            params.archive_config_id = archive_config_id;
          }

          this.confirmLoading = true;
          await this.$http.request(url, {
            data: paramsData,
            params,
          });
          this.$bkMessage({
            theme: 'success',
            message: this.$t('保存成功'),
            delay: 1500,
          });
          this.$emit('updated');
        } catch (e) {
          console.warn(e);
        } finally {
          this.confirmLoading = false;
        }
      },
    },
  };
</script>

<style lang="scss" scoped>
  .archive-slider-content {
    height: calc(100vh - 60px);
    min-height: 394px;

    .king-form {
      padding: 10px 0 36px 36px;

      .bk-form-item {
        margin-top: 18px;
      }

      .bk-select {
        width: 300px;
      }
    }
  }
</style>
