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
    class="repository-slider-container"
    data-test-id="archive_div_addNewStorehouse"
  >
    <bk-sideslider
      :before-close="handleCloseSidebar"
      :is-show="showSlider"
      :quick-close="true"
      :title="isEdit ? $t('编辑归档仓库') : $t('新建归档仓库')"
      :width="676"
      transfer
      @animation-end="updateIsShow"
    >
      <template #content>
        <div
          class="repository-slider-content"
          v-bkloading="{ isLoading: sliderLoading }"
        >
          <bk-form
            v-if="!sliderLoading"
            ref="validateForm"
            class="king-form"
            :label-width="150"
            :model="formData"
            :rules="basicRules"
            form-type="vertical"
          >
            <h3 class="form-title">{{ $t('基础信息') }}</h3>
            <bk-form-item
              ext-cls="es-cluster-item"
              :label="$t('ES集群')"
              :rules="basicRules.cluster_id"
              property="cluster_id"
              required
            >
              <bk-select
                v-model="formData.cluster_id"
                data-test-id="addNewStorehouse_select_selectEsCluster"
                searchable
                @change="handleChangeCluster"
              >
                <bk-option
                  v-for="option in esClusterList"
                  :id="option.storage_cluster_id"
                  :key="option.storage_cluster_id"
                  :name="option.storage_cluster_name"
                >
                  <div
                    v-if="!(option.permission && option.permission[authorityMap.MANAGE_ES_SOURCE_AUTH])"
                    class="option-slot-container no-authority"
                    @click.stop
                  >
                    <span class="text">
                      <span>{{ option.storage_cluster_name }}</span>
                    </span>
                    <span
                      class="apply-text"
                      @click="applyProjectAccess(option)"
                      >{{ $t('申请权限') }}</span
                    >
                  </div>
                  <div
                    v-else
                    class="option-slot-container"
                    v-bk-overflow-tips
                  >
                    <span>{{ option.storage_cluster_name }}</span>
                  </div>
                </bk-option>
              </bk-select>
              <p
                v-if="esClusterSource"
                class="es-source"
              >
                <span>{{ $t('来源') }}：</span>
                <span>{{ esClusterSource }}</span>
              </p>
            </bk-form-item>
            <h3 class="form-title">{{ $t('配置') }}</h3>
            <bk-form-item
              ext-cls="repository-item"
              :label="$t('类型')"
              required
            >
              <div
                v-for="card in repository"
                :class="{ 'repository-card': true, 'is-active': formData.es_config.type === card.id }"
                :data-test-id="`addNewStorehouse_div_${card.id}`"
                :key="card.name"
                @click="changeRepository(card)"
              >
                <span class="repository-name">{{ card.name }}</span>
                <img
                  class="card-image"
                  :src="card.image"
                />
              </div>
            </bk-form-item>
            <bk-alert type="info">
              <template #title>
                <div class="repository-alert">
                  <div v-if="formData.es_config.type === 'hdfs'">
                    <p>
                      {{ $t('1. 用户需要在hdfs设置的kerberos中创建给es使用的principal, 然后导出对应的keytab文件') }}
                    </p>
                    <p>{{ $t('2. 将keytab放es每个节点对应的目录中去') }}</p>
                  </div>
                  <div v-if="formData.es_config.type === 'fs'">
                    <p>{{ $t('本地目录配置说明') }}</p>
                  </div>
                  <div v-if="formData.es_config.type === 'cos'">
                    <p>{{ $t('COS的自动创建和关联，只能用于腾讯云') }}</p>
                  </div>
                </div>
              </template>
            </bk-alert>
            <bk-form-item
              :label="$t('仓库名称')"
              property="snapshot_repository_name"
              required
            >
              <bk-input
                v-model="formData.snapshot_repository_name"
                :placeholder="$t('只能输入英文、数字或者下划线')"
                data-test-id="addNewStorehouse_input_repoName"
              >
              </bk-input>
            </bk-form-item>
            <!-- HDFS -->
            <div
              v-if="formData.es_config.type === 'hdfs'"
              key="hdfs"
            >
              <bk-form-item
                :label="$t('归档目录')"
                :property="formData.hdfsFormData.path"
                :rules="basicRules.path"
                required
              >
                <bk-input
                  v-model="formData.hdfsFormData.path"
                  data-test-id="addNewStorehouse_input_archiveCatalog"
                ></bk-input>
              </bk-form-item>
              <bk-form-item
                :label="$t('HDFS地址')"
                :property="formData.hdfsFormData.uri"
                :rules="basicRules.uri"
                required
              >
                <bk-input
                  v-model="formData.hdfsFormData.uri"
                  data-test-id="addNewStorehouse_input_HDFSurl"
                >
                  <!-- <template slot="prepend">
                  <div class="group-text">hdfs://</div>
                </template> -->
                </bk-input>
              </bk-form-item>
              <bk-form-item
                :property="formData.hdfsFormData.security.principal"
                :rules="basicRules.principal"
                label="Principal"
                required
              >
                <div class="principal-item">
                  <bk-switcher
                    v-model="formData.hdfsFormData.isSecurity"
                    size="large"
                    theme="primary"
                  >
                  </bk-switcher>
                  <bk-input
                    v-model="formData.hdfsFormData.security.principal"
                    data-test-id="addNewStorehouse_input_principal"
                  ></bk-input>
                </div>
              </bk-form-item>
            </div>
            <!-- FS -->
            <div
              v-if="formData.es_config.type === 'fs'"
              key="fs"
            >
              <bk-form-item
                :label="$t('归档目录')"
                :property="formData.fsFormData.location"
                :rules="basicRules.location"
                data-test-id="addNewStorehouse_input_archiveCatalog"
                required
              >
                <bk-input v-model="formData.fsFormData.location"></bk-input>
              </bk-form-item>
            </div>
            <!-- COS -->
            <div
              v-if="formData.es_config.type === 'cos'"
              key="cos"
            >
              <bk-form-item
                :label="$t('归档目录')"
                :property="formData.cosFormData.base_path"
                :rules="basicRules.base_path"
                required
              >
                <bk-input
                  v-model="formData.cosFormData.base_path"
                  data-test-id="addNewStorehouse_input_archiveCatalog"
                ></bk-input>
              </bk-form-item>
              <bk-form-item
                :label="$t('区域')"
                :property="formData.cosFormData.region"
                :rules="basicRules.region"
                required
              >
                <bk-input
                  v-model="formData.cosFormData.region"
                  data-test-id="addNewStorehouse_input_region"
                ></bk-input>
              </bk-form-item>
              <bk-form-item
                :property="formData.cosFormData.access_key_id"
                :rules="basicRules.access_key_id"
                label="Secretld"
                required
              >
                <bk-input
                  v-model="formData.cosFormData.access_key_id"
                  data-test-id="addNewStorehouse_input_Secretld"
                ></bk-input>
              </bk-form-item>
              <bk-form-item
                :property="formData.cosFormData.access_key_secret"
                :rules="basicRules.access_key_secret"
                label="SecretKey"
                required
              >
                <bk-input
                  v-model="formData.cosFormData.access_key_secret"
                  data-test-id="addNewStorehouse_input_SecretKey"
                  type="password"
                ></bk-input>
              </bk-form-item>
              <bk-form-item
                :property="formData.cosFormData.app_id"
                :rules="basicRules.app_id"
                label="APPID"
                required
              >
                <bk-input
                  v-model="formData.cosFormData.app_id"
                  data-test-id="addNewStorehouse_input_APPID"
                ></bk-input>
              </bk-form-item>
              <bk-form-item
                :label="$t('Bucket名字')"
                :property="formData.cosFormData.bucket"
                :rules="basicRules.bucket"
                required
              >
                <bk-input
                  v-model="formData.cosFormData.bucket"
                  data-test-id="addNewStorehouse_input_BucketName"
                ></bk-input>
              </bk-form-item>
            </div>
            <bk-form-item style="margin-top: 40px">
              <bk-button
                class="king-button mr10"
                :loading="confirmLoading"
                data-test-id="addNewStorehouse_button_submit"
                theme="primary"
                @click.stop.prevent="handleConfirm"
              >
                {{ $t('提交') }}
              </bk-button>
              <bk-button
                data-test-id="addNewStorehouse_button_cancel"
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

  import * as authorityMap from '../../../../common/authority-map';

  const cosConfigForm = () => {
    return {
      app_id: '',
      access_key_id: '',
      access_key_secret: '',
      bucket: '',
      region: '',
      compress: true,
    };
  };

  const hdfsConfigForm = () => {
    return {
      uri: '',
      path: '',
      isSecurity: false,
      compress: true,
      security: {
        principal: '',
      },
    };
  };

  const fsConfigForm = () => {
    return {
      location: '',
    };
  };

  export default {
    mixins: [SidebarDiffMixin],
    props: {
      showSlider: {
        type: Boolean,
        default: false,
      },
      editClusterId: {
        type: Number,
        default: null,
      },
    },
    data() {
      return {
        confirmLoading: false,
        sliderLoading: false,
        esClusterSource: '',
        esClusterList: [],
        repository: [
          { id: 'hdfs', name: 'HDFS', image: require('@/images/hdfs.png') },
          { id: 'fs', name: this.$t('共享目录'), image: require('@/images/fs.png') },
          { id: 'cos', name: 'COS', image: require('@/images/cos.png') },
        ],
        formData: {
          cluster_id: '',
          snapshot_repository_name: '',
          es_config: {
            type: 'hdfs',
          },
          cosFormData: cosConfigForm(),
          hdfsFormData: hdfsConfigForm(),
          fsFormData: fsConfigForm(),
        },
        requiredRules: {
          required: true,
          trigger: 'blur',
        },
        basicRules: {},
      };
    },
    computed: {
      ...mapGetters({
        bkBizId: 'bkBizId',
      }),
      authorityMap() {
        return authorityMap;
      },
      isEdit() {
        return this.editClusterId !== null;
      },
    },
    watch: {
      showSlider(val) {
        if (val) {
          this.getEsClusterList();
          if (this.isEdit) {
          } else {
            //
          }
          this.initSidebarFormData();
        } else {
          // 清空表单数据
          this.formData = {
            cluster_id: '',
            snapshot_repository_name: '',
            es_config: {
              type: 'hdfs',
            },
            cosFormData: cosConfigForm(),
            hdfsFormData: hdfsConfigForm(),
            fsFormData: fsConfigForm(),
          };
        }
      },
    },
    created() {
      this.basicRules = {
        cluster_id: [this.requiredRules],
        snapshot_repository_name: [
          {
            regex: /^[A-Za-z0-9_]+$/,
            trigger: 'blur',
          },
        ],
        path: [this.requiredRules],
        uri: [this.requiredRules],
        principal: [
          {
            validator: () => {
              const { isSecurity, security } = this.formData.hdfsFormData;
              if (isSecurity && security.principal.trim() === '') {
                return false;
              }
              return true;
            },
            trigger: 'blur',
          },
        ],
        location: [this.requiredRules],
        base_path: [this.requiredRules],
        region: [this.requiredRules],
        access_key_id: [this.requiredRules],
        access_key_secret: [this.requiredRules],
        app_id: [this.requiredRules],
        bucket: [this.requiredRules],
      };
    },
    methods: {
      async getEsClusterList() {
        const res = await this.$http.request('/source/getEsList', {
          query: {
            bk_biz_id: this.bkBizId,
            enable_archive: 1,
          },
        });
        if (res.data) {
          this.esClusterList = res.data;
          // this.esClusterList = res.data.filter(item => !item.cluster_config.is_default_cluster);
        }
      },
      handleChangeCluster(value) {
        const curCluster = this.esClusterList.find(cluster => cluster.cluster_config.cluster_id === value);
        this.esClusterSource = curCluster.source_name || '';
      },
      updateIsShow() {
        this.$emit('hidden');
        this.$emit('update:show-slider', false);
      },
      handleCancel() {
        this.$emit('update:show-slider', false);
      },
      changeRepository(card) {
        if (this.formData.es_config.type !== card.id) {
          this.$refs.validateForm.clearError();
          this.formData.es_config.type = card.id;
        }
      },
      async handleConfirm() {
        try {
          await this.$refs.validateForm.validate();
          const url = '/archive/createRepository';
          const {
            cluster_id,
            snapshot_repository_name: snapshotRepositoryName,
            es_config: esConfig,
            hdfsFormData,
            fsFormData,
            cosFormData,
          } = this.formData;
          const paramsData = {
            cluster_id,
            snapshot_repository_name: snapshotRepositoryName,
            alias: snapshotRepositoryName,
            es_config: {
              type: esConfig.type,
            },
            bk_biz_id: this.bkBizId,
          };
          if (esConfig.type === 'hdfs') {
            const { uri, path, isSecurity, security, compress } = hdfsFormData;
            const principal = isSecurity ? security.principal : undefined;
            paramsData.es_config.settings = {
              uri,
              path,
              compress,
              'security.principal': principal,
            };
          }
          if (esConfig.type === 'fs') {
            paramsData.es_config.settings = { ...fsFormData };
          }
          if (esConfig.type === 'cos') {
            paramsData.es_config.settings = { ...cosFormData };
          }

          this.confirmLoading = true;
          await this.$http.request(url, {
            data: paramsData,
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
      // es集群管理权限申请
      async applyProjectAccess(option) {
        this.$el.click(); // 手动关闭下拉
        try {
          this.$bkLoading();
          const res = await this.$store.dispatch('getApplyData', {
            action_ids: [authorityMap.MANAGE_ES_SOURCE_AUTH],
            resources: [
              {
                type: 'es_source',
                id: option.cluster_config.cluster_id,
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
    },
  };
</script>

<style lang="scss">
  .repository-slider-content {
    min-height: 394px;

    .bk-form.bk-form-vertical {
      padding: 0 0 26px 36px;

      .bk-form-content {
        width: 500px;
      }

      .bk-form-item {
        padding-left: 34px;
        margin-top: 12px;
      }

      .bk-alert {
        width: 500px;
        margin: 10px 0 12px 34px;
      }

      .bk-select,
      .bk-date-picker {
        width: 300px;
      }

      .es-cluster-item {
        display: flex;
        margin-top: 16px;

        .bk-label {
          /* stylelint-disable-next-line declaration-no-important */
          width: auto !important;
        }

        .bk-form-content {
          display: flex;
        }

        .bk-select {
          width: 240px;
        }

        .es-source {
          margin-left: 10px;
          font-size: 14px;
          color: #63656e;
        }
      }

      .repository-item {
        display: inline-block;
      }

      .repository-card {
        position: relative;
        float: left;
        width: 158px;
        height: 76px;
        padding: 12px;
        margin-right: 12px;
        font-size: 14px;
        color: #63656e;
        cursor: pointer;
        background: #f5f7fa;
        border: 1px solid #f5f7fa;
        border-radius: 2px;

        &:last-child {
          margin-right: 0;
        }

        &.is-active {
          color: #3a84ff;
          background: #e1ecff;
          border: 1px solid #a3c5fd;
        }
      }

      .card-image {
        position: absolute;
        right: 20px;
        bottom: 10px;
      }
    }

    .form-title {
      padding: 0 0 8px 10px;
      margin: 24px 40px 0 0;
      font-size: 14px;
      font-weight: 600;
      line-height: 20px;
      color: #63656e;
      border-bottom: 1px solid #dcdee5;
    }

    .repository-alert {
      padding-right: 10px;
    }

    .principal-item {
      display: flex;
      align-items: center;

      .bk-switcher {
        margin-right: 16px;
      }

      .bk-form-control {
        flex: 1;
      }
    }
  }

  .option-slot-container {
    min-height: 32px;
    padding: 8px 0;
    line-height: 14px;

    &.no-authority {
      display: flex;
      align-items: center;
      justify-content: space-between;
      color: #c4c6cc;
      cursor: not-allowed;

      .text {
        width: calc(100% - 56px);
      }

      .apply-text {
        display: none;
        flex-shrink: 0;
        color: #3a84ff;
        cursor: pointer;
      }

      &:hover .apply-text {
        display: flex;
      }
    }
  }
</style>
