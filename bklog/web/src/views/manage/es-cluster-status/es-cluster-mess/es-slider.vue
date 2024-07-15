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
    class="es-access-slider-container"
    data-test-id="addNewEsAccess_div_esAccessFromBox"
  >
    <bk-sideslider
      :before-close="handleCloseSidebar"
      :is-show="showSlider"
      :quick-close="true"
      :title="isEdit ? $t('编辑集群') : $t('新建集群')"
      :width="640"
      transfer
      @animation-end="updateIsShow"
    >
      <template #content>
        <div
          class="king-slider-content"
          v-bkloading="{ isLoading: sliderLoading }"
        >
          <bk-form
            v-if="!sliderLoading"
            ref="validateForm"
            class="king-form"
            :label-width="170"
            :model="basicFormData"
            :rules="basicRules"
            form-type="vertical"
          >
            <div class="add-collection-title">{{ $t('基础信息') }}</div>
            <bk-form-item
              :label="$t('数据源名称')"
              property="cluster_name"
              required
            >
              <bk-input
                v-model="basicFormData.cluster_name"
                :readonly="isEdit"
                data-test-id="esAccessFromBox_input_fillName"
                maxlength="50"
              ></bk-input>
            </bk-form-item>
            <!-- 来源 es地址 -->
            <div class="form-item-container">
              <bk-form-item
                :label="$t('来源')"
                property="source_type"
                required
              >
                <div class="source-item">
                  <bk-select
                    style="width: 154px; margin-right: 10px"
                    v-model="basicFormData.source_type"
                    @change="handleChangeSource"
                  >
                    <bk-option
                      v-for="option in globalsData.es_source_type"
                      :id="option.id"
                      :key="option.id"
                      :name="option.name"
                    >
                    </bk-option>
                  </bk-select>
                </div>
              </bk-form-item>
              <bk-form-item
                class="es-address"
                :label="$t('ES地址')"
                property="domain_name"
                required
              >
                <bk-input
                  class="address-input"
                  v-model="basicFormData.domain_name"
                  :readonly="isEdit"
                  data-test-id="esAccessFromBox_input_fillDomainName"
                ></bk-input>
              </bk-form-item>
            </div>
            <!-- 端口  协议 -->
            <div class="form-item-container">
              <bk-form-item
                :label="$t('端口')"
                property="port"
                required
              >
                <bk-input
                  v-model="basicFormData.port"
                  :max="65535"
                  :min="0"
                  :readonly="isEdit"
                  :show-controls="false"
                  data-test-id="esAccessFromBox_input_fillPort"
                  type="number"
                >
                </bk-input>
              </bk-form-item>
              <bk-form-item
                :label="$t('协议')"
                required
              >
                <bk-select
                  v-model="basicFormData.schema"
                  :clearable="false"
                  data-test-id="esAccessFromBox_select_selectProtocol"
                >
                  <bk-option
                    id="http"
                    name="http"
                  ></bk-option>
                  <bk-option
                    id="https"
                    name="https"
                  ></bk-option>
                </bk-select>
              </bk-form-item>
            </div>
            <!-- 用户名 密码 -->
            <div class="form-item-container">
              <bk-form-item :label="$t('用户名')">
                <bk-input
                  v-model="basicFormData.auth_info.username"
                  data-test-id="esAccessFromBox_input_fillUsername"
                ></bk-input>
              </bk-form-item>
              <bk-form-item :label="$t('密码')">
                <bk-input
                  v-model="basicFormData.auth_info.password"
                  data-test-id="esAccessFromBox_input_fillPassword"
                  type="password"
                ></bk-input>
              </bk-form-item>
            </div>
            <!-- 连通性测试 -->
            <bk-form-item label="">
              <div class="test-container">
                <bk-button
                  :loading="connectLoading"
                  data-test-id="esAccessFromBox_button_connectivityTest"
                  theme="primary"
                  type="button"
                  @click="handleTestConnect"
                >
                  {{ $t('连通性测试') }}
                </bk-button>
                <div
                  v-if="connectResult === 'success'"
                  class="success-text"
                >
                  <i class="bk-icon icon-check-circle-shape"></i>{{ $t('连通成功！') }}
                </div>
                <div
                  v-else-if="connectResult === 'failed'"
                  class="error-text"
                >
                  <i class="bk-icon icon-close-circle-shape"></i>{{ $t('连通失败！') }}
                </div>
              </div>
            </bk-form-item>
            <bk-form-item
              v-if="connectResult === 'failed' && connectFailedMessage"
              label=""
            >
              <div class="connect-message">{{ connectFailedMessage }}</div>
            </bk-form-item>

            <bk-form-item v-if="connectResult === 'success'">
              <div
                class="es-cluster-management button-text"
                @click="isShowManagement = !isShowManagement"
              >
                <span>{{ $t('ES集群管理') }}</span>
                <span :class="['bk-icon icon-angle-double-down', isShowManagement && 'is-show']"></span>
              </div>
            </bk-form-item>

            <div v-if="isShowManagement && connectResult === 'success'">
              <!-- 可见范围 -->
              <bk-form-item
                style="margin-top: 4px"
                :label="$t('可见范围')"
              >
                <bk-radio-group v-model="formData.visible_config.visible_type">
                  <bk-radio
                    v-for="item of visibleScopeSelectList"
                    class="scope-radio"
                    :key="item.id"
                    :value="item.id"
                  >
                    {{ item.name }}
                  </bk-radio>
                </bk-radio-group>
                <bk-select
                  v-model="visibleBkBiz"
                  v-show="!scopeValueType"
                  :list="mySpaceList"
                  :virtual-scroll-render="virtualscrollSpaceList"
                  display-key="space_full_code_name"
                  id-key="bk_biz_id"
                  display-tag
                  enable-virtual-scroll
                  multiple
                  searchable
                  @toggle="handleToggleVisible"
                >
                  <template #trigger>
                    <div class="visible-scope-box">
                      <div class="selected-tag">
                        <bk-tag
                          v-for="(tag, index) in visibleList"
                          v-bk-tooltips="inUseProjectPopover(tag.is_use)"
                          :class="`tag-icon ${tag.is_use ? 'is-active' : 'is-normal'}`"
                          :closable="!tag.is_use"
                          :key="tag.id"
                          @close="handleDeleteTag(index)"
                        >
                          {{ tag.name }}
                        </bk-tag>
                      </div>
                      <span
                        v-if="!visibleList.length"
                        class="please-select"
                        >{{ $t('请选择') }}</span
                      >
                      <span :class="['bk-icon', 'icon-angle-down', !visibleIsToggle ? '' : 'icon-rotate']"></span>
                    </div>
                  </template>
                </bk-select>
                <bk-search-select
                  ref="searchSelectRef"
                  v-model="bkBizLabelsList"
                  v-show="isBizAttr"
                  :data="bizParentList"
                  :popover-zindex="2500"
                  :remote-method="handleRemoteMethod"
                  :show-condition="false"
                  :show-popover-tag-change="false"
                  clearable
                  @input-change="handleInputChange"
                  @input-click-outside="handleClickOutside"
                  @menu-child-select="handleChildMenuSelect"
                  @menu-select="handleMenuSelect"
                >
                </bk-search-select>
              </bk-form-item>
              <!-- 过期时间 -->
              <bk-form-item
                :label="$t('过期时间')"
                required
              >
                <div class="flex-space">
                  <div class="flex-space-item">
                    <div class="space-item-label">{{ $t('默认') }}</div>
                    <bk-select
                      v-model="formData.setup_config.retention_days_default"
                      :clearable="false"
                      data-test-id="storageBox_select_selectExpiration"
                    >
                      <template #trigger>
                        <div class="bk-select-name">
                          {{ formData.setup_config.retention_days_default + $t('天') }}
                        </div>
                      </template>
                      <template>
                        <bk-option
                          v-for="(option, index) in retentionDaysList"
                          :disabled="option.disabled"
                          :id="option.id"
                          :key="index"
                          :name="option.name"
                        >
                        </bk-option>
                      </template>
                      <template #extension>
                        <div style="padding: 8px 0">
                          <bk-input
                            v-model="customRetentionDay"
                            :placeholder="$t('输入自定义天数，按 Enter 确认')"
                            :show-controls="false"
                            size="small"
                            type="number"
                            @enter="enterCustomDay($event, 'retention')"
                          ></bk-input>
                        </div>
                      </template>
                    </bk-select>
                  </div>
                  <div class="flex-space-item">
                    <div class="space-item-label">{{ $t('最大') }}</div>
                    <bk-select
                      v-model="formData.setup_config.retention_days_max"
                      :clearable="false"
                      data-test-id="storageBox_select_selectExpiration"
                    >
                      <template #trigger>
                        <div class="bk-select-name">
                          {{ formData.setup_config.retention_days_max + $t('天') }}
                        </div>
                      </template>
                      <template>
                        <bk-option
                          v-for="(option, index) in maxDaysList"
                          :disabled="option.disabled"
                          :id="option.id"
                          :key="index"
                          :name="option.name"
                        >
                        </bk-option>
                      </template>
                      <template #extension>
                        <div style="padding: 8px 0">
                          <bk-input
                            v-model="customMaxDay"
                            :placeholder="$t('输入自定义天数，按 Enter 确认')"
                            :show-controls="false"
                            size="small"
                            type="number"
                            @enter="enterCustomDay($event, 'max')"
                          ></bk-input>
                        </div>
                      </template>
                    </bk-select>
                  </div>
                </div>
              </bk-form-item>
              <!-- 副本数 -->
              <bk-form-item
                :label="$t('副本数')"
                required
              >
                <div class="flex-space">
                  <div class="flex-space-item">
                    <div class="space-item-label">{{ $t('默认') }}</div>
                    <bk-input
                      v-model="formData.setup_config.number_of_replicas_default"
                      :max="Number(formData.setup_config.number_of_replicas_max)"
                      :min="0"
                      type="number"
                    >
                    </bk-input>
                  </div>
                  <div class="flex-space-item">
                    <div class="space-item-label">{{ $t('最大') }}</div>
                    <bk-input
                      v-model="formData.setup_config.number_of_replicas_max"
                      :min="Number(formData.setup_config.number_of_replicas_default)"
                      type="number"
                    >
                    </bk-input>
                  </div>
                </div>
              </bk-form-item>
              <!-- 分片数 -->
              <bk-form-item
                :label="$t('分片数')"
                required
              >
                <div class="flex-space">
                  <div class="flex-space-item">
                    <div class="space-item-label">{{ $t('默认') }}</div>
                    <bk-input
                      v-model="formData.setup_config.es_shards_default"
                      :max="Number(formData.setup_config.es_shards_max)"
                      :min="1"
                      type="number"
                    >
                    </bk-input>
                  </div>
                  <div class="flex-space-item">
                    <div class="space-item-label">{{ $t('最大') }}</div>
                    <bk-input
                      v-model="formData.setup_config.es_shards_max"
                      :min="Number(formData.setup_config.es_shards_default)"
                      type="number"
                    >
                    </bk-input>
                  </div>
                </div>
              </bk-form-item>
              <!-- 冷热数据 -->
              <bk-form-item
                v-if="connectResult === 'success'"
                :label="$t('冷热数据')"
              >
                <div class="form-flex-container">
                  <bk-switcher
                    v-model="formData.enable_hot_warm"
                    :disabled="isDisableHotSetting"
                    size="large"
                    theme="primary"
                  ></bk-switcher>
                  <template v-if="isDisableHotSetting && !connectLoading">
                    <span class="bk-icon icon-info"></span>
                    <span style="font-size: 12px">{{ $t('没有获取到正确的标签，') }}</span>
                    <a
                      class="button-text"
                      :href="configDocUrl"
                      target="_blank"
                      >{{ $t('查看具体的配置方法') }}</a
                    >
                  </template>
                </div>
              </bk-form-item>
              <!-- 冷热数据标签 -->
              <div
                v-if="formData.enable_hot_warm"
                class="form-item-container"
              >
                <div class="bk-form-item">
                  <div class="form-item-label">
                    <p>{{ $t('热数据标签') }}</p>
                    <div
                      v-if="formData.hot_attr_name && formData.hot_attr_value"
                      class="button-text"
                      @click="handleViewInstanceList('hot')"
                    >
                      <span class="bk-icon icon-eye"></span>{{ $t('查看实例列表') }}
                    </div>
                  </div>
                  <bk-select
                    v-model="selectedHotId"
                    @change="handleHotSelected"
                  >
                    <template>
                      <bk-option
                        v-for="option in hotColdAttrSet"
                        :disabled="option.isSelected"
                        :id="option.computedId"
                        :key="option.computedId"
                        :name="`${option.computedName}(${option.computedCounts})`"
                      >
                      </bk-option>
                    </template>
                  </bk-select>
                </div>
                <div
                  v-if="formData.enable_hot_warm"
                  class="bk-form-item"
                >
                  <div class="form-item-label">
                    <p>{{ $t('冷数据标签') }}</p>
                    <div
                      v-if="formData.warm_attr_name && formData.warm_attr_value"
                      class="button-text"
                      @click="handleViewInstanceList('cold')"
                    >
                      <span class="bk-icon icon-eye"></span>{{ $t('查看实例列表') }}
                    </div>
                  </div>
                  <bk-select
                    v-model="selectedColdId"
                    @change="handleColdSelected"
                  >
                    <template>
                      <bk-option
                        v-for="option in hotColdAttrSet"
                        :disabled="option.isSelected"
                        :id="option.computedId"
                        :key="option.computedId"
                        :name="`${option.computedName}(${option.computedCounts})`"
                      >
                      </bk-option>
                    </template>
                  </bk-select>
                </div>
              </div>
              <!-- 日志归档 容量评估 -->
              <div class="form-item-container">
                <bk-form-item :label="$t('日志归档')">
                  <div class="document-container">
                    <bk-switcher
                      v-model="formData.enable_archive"
                      size="large"
                      theme="primary"
                    ></bk-switcher>
                    <div
                      v-if="archiveDocUrl"
                      class="check-document button-text"
                      @click="handleGotoLink('logArchive')"
                    >
                      <span class="bk-icon icon-text-file"></span>
                      <a>{{ $t('查看说明文档') }}</a>
                    </div>
                  </div>
                </bk-form-item>
                <bk-form-item
                  v-if="isItsm"
                  :label="$t('容量评估')"
                >
                  <bk-switcher
                    v-model="formData.enable_assessment"
                    size="large"
                    theme="primary"
                  ></bk-switcher>
                </bk-form-item>
              </div>
              <!-- 集群负责人 -->
              <bk-form-item
                :desc="$t('集群负责人可以用于容量审核等')"
                :label="$t('集群负责人')"
                required
              >
                <div class="principal">
                  <bk-user-selector
                    :api="userApi"
                    :class="isAdminError && 'is-error'"
                    :empty-text="$t('无匹配人员')"
                    :placeholder="$t('请选择集群负责人')"
                    :value="formData.admin"
                    @blur="handleBlur"
                    @change="handleChangePrincipal"
                  >
                  </bk-user-selector>
                </div>
              </bk-form-item>
              <!-- 集群说明 -->
              <bk-form-item
                class="illustrate"
                :label="$t('说明')"
              >
                <bk-input
                  v-model="formData.description"
                  :maxlength="100"
                  :rows="3"
                  type="textarea"
                >
                </bk-input>
              </bk-form-item>
            </div>
          </bk-form>

          <div class="submit-container">
            <bk-button
              class="king-button mr10"
              :disabled="isDisableClickSubmit"
              :loading="confirmLoading"
              data-test-id="esAccessFromBox_button_confirm"
              theme="primary"
              @click.stop.prevent="handleConfirm"
            >
              {{ $t('提交') }}
            </bk-button>
            <bk-button
              data-test-id="esAccessFromBox_button_cancel"
              @click="handleCancel"
              >{{ $t('取消') }}</bk-button
            >
          </div>
        </div>
      </template>
    </bk-sideslider>
    <!-- 查看实例列表弹窗 -->
    <es-dialog
      v-model="showInstanceDialog"
      :form-data="formData"
      :list="hotColdOriginList"
      :type="viewInstanceType"
    />
  </div>
</template>

<script>
  import SidebarDiffMixin from '@/mixins/sidebar-diff-mixin';
  import SpaceSelectorMixin from '@/mixins/space-selector-mixin';
  import BkUserSelector from '@blueking/user-selector';
  import { mapState, mapGetters } from 'vuex';

  import EsDialog from './es-dialog';

  export default {
    components: {
      EsDialog,
      BkUserSelector,
    },
    mixins: [SidebarDiffMixin, SpaceSelectorMixin],
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
        configDocUrl: window.BK_HOT_WARM_CONFIG_URL,
        archiveDocUrl: window.BK_ARCHIVE_DOC_URL, // 日志归档跳转链接
        isItsm: window.FEATURE_TOGGLE.collect_itsm === 'on', // 容量评估全局参数
        confirmLoading: false,
        sliderLoading: false,
        formData: {
          cluster_name: '', // 集群名
          source_type: '', // 来源
          source_name: '',
          domain_name: '', // 地址
          port: '', // 端口
          schema: 'http', // 协议
          auth_info: {
            username: '', // 用户名
            password: '', // 密码
          },
          enable_hot_warm: false, // 是否开启冷热数据
          hot_attr_name: '', // 热节点属性名称
          hot_attr_value: '', // 热节点属性值
          warm_attr_name: '', // 冷节点属性名称
          warm_attr_value: '', // 冷节点属性值
          setup_config: {
            // 过期时间 副本数
            retention_days_max: 14,
            retention_days_default: 7,
            number_of_replicas_max: 3,
            number_of_replicas_default: 1,
            es_shards_default: 1,
            es_shards_max: 3,
          },
          admin: [], // 负责人名单
          description: '', // 集群说明
          enable_archive: false, // 日志存档开关
          enable_assessment: false, // 容量评估开关
          visible_config: {
            // 可见范围配置
            visible_type: 'current_biz', // 可见范围单选项
            bk_biz_labels: {}, // 按照业务属性选择
            visible_bk_biz: [], // 多个业务
          },
        },
        basicFormData: {
          cluster_name: '', // 集群名
          source_type: '', // 来源
          source_name: '',
          domain_name: '', // 地址
          port: '', // 端口
          schema: 'http', // 协议
          auth_info: {
            username: '', // 用户名
            password: '', // 密码
          },
        },
        basicRules: {
          source_type: [
            {
              required: true,
              trigger: 'blur',
            },
          ],
          cluster_name: [
            {
              required: true,
              trigger: 'blur',
            },
          ],
          domain_name: [
            {
              required: true,
              trigger: 'blur',
            },
          ],
          port: [
            {
              required: true,
              trigger: 'blur',
            },
          ],
        },

        connectLoading: false,
        connectResult: '', // success failed
        connectFailedMessage: '',

        hotColdOriginList: [], // 新增编辑时的冷热数据
        hotColdAttrSet: [], // 相同 attr value 的集合
        selectedHotId: '', // 热 attr:value
        selectedColdId: '', // 冷 attr:value
        showInstanceDialog: false, // 查看实例列表
        viewInstanceType: '', // hot、cold 查看热数据/冷数据实例列表
        visibleScopeSelectList: [
          // 可见范围单选列表
          { id: 'current_biz', name: this.$t('当前空间可见') },
          { id: 'multi_biz', name: this.$t('多空间选择') },
          { id: 'all_biz', name: this.$t('全平台') },
          { id: 'biz_attr', name: this.$t('按照空间属性选择') },
        ],
        visibleBkBiz: [], // 下拉框选中的值列表
        visibleList: [], // 多业务选择下拉框
        cacheVisibleList: [], // 缓存多业务选择下拉框
        bkBizLabelsList: [], // 按照业务属性选择列表
        cacheBkBizLabelsList: [], // 缓存按照业务属性选择
        bizParentList: [], // 按照业务属性父级列表
        bizChildrenList: {}, // 业务属性选择子级键值对象
        visibleIsToggle: false, // 多业务选择icon方向
        userApi: window.BK_LOGIN_URL, // 负责人api
        isShowManagement: false, // 是否展示集群管理
        retentionDaysList: [], // 默认过期时间列表
        maxDaysList: [], // 最大过期时间列表
        customRetentionDay: '', // 默认过期时间输入框
        customMaxDay: '', // 最大过期时间输入框
        isAdminError: false, // 集群负责人是否为空
        bizSelectID: '', // 选中的当前按照业务属性选择
        bizInputStr: '', // 按照业务属性选择输入值
        isFirstShow: true, // 是否是第一次渲染
      };
    },
    computed: {
      ...mapState({
        mySpaceList: state => state.mySpaceList,
        userMeta: state => state.userMeta,
      }),
      ...mapGetters({
        bkBizId: 'bkBizId',
        globalsData: 'globals/globalsData',
      }),
      isEdit() {
        return this.editClusterId !== null;
      },
      // 冷热设置不对，禁用提交
      invalidHotSetting() {
        return this.formData.enable_hot_warm && !(this.formData.hot_attr_value && this.formData.warm_attr_value);
      },
      isRulesCheckSubmit() {
        return !this.formData.admin.length;
      },
      // 标签数量不足，禁止开启冷热设置
      isDisableHotSetting() {
        return this.hotColdAttrSet.length < 2;
      },
      sourceNameCheck() {
        const { source_type, source_name } = this.formData;

        if (source_type === 'other' && source_name.trim() === '') return true;
        return false;
      },
      // 可见范围单选判断，禁用下拉框
      scopeValueType() {
        return this.formData.visible_config.visible_type !== 'multi_biz';
      },
      isBizAttr() {
        return this.formData.visible_config.visible_type === 'biz_attr';
      },
      // 提交按钮是否禁用
      isDisableClickSubmit() {
        return this.connectResult !== 'success' || this.invalidHotSetting || this.isRulesCheckSubmit;
      },
      // 侧边栏需要对比的formData
      _watchFormData_({ formData, basicFormData }) {
        return { formData, basicFormData };
      },
    },
    watch: {
      showSlider(val) {
        if (val) {
          if (this.isEdit) {
            this.isShowManagement = true;
            this.editDataSource();
          } else {
            // 集群负责人默认本人
            this.formData.admin = [this.userMeta.username];
            this.initSidebarFormData();
          }
          this.updateDaysList();
          this.getBizPropertyId();
        } else {
          // 清空表单数据
          this.formData = {
            cluster_name: '', // 集群名
            source_type: '',
            source_name: '',
            domain_name: '', // 地址
            port: '', // 端口
            schema: 'http', // 协议
            auth_info: {
              username: '', // 用户名
              password: '', // 密码
            },
            enable_hot_warm: false, // 是否开启冷热数据
            hot_attr_name: '', // 热节点属性名称
            hot_attr_value: '', // 热节点属性值
            warm_attr_name: '', // 冷节点属性名称
            warm_attr_value: '', // 冷节点属性值
            setup_config: {
              retention_days_max: 14,
              retention_days_default: 7,
              number_of_replicas_max: 3,
              number_of_replicas_default: 1,
              es_shards_default: 1,
              es_shards_max: 3,
            },
            admin: [],
            description: '',
            enable_archive: false,
            enable_assessment: false,
            visible_config: {
              visible_type: 'current_biz',
              visible_bk_biz: [],
              bk_biz_labels: {},
            },
          };
          this.visibleBkBiz = [];
          this.visibleList = [];
          this.cacheVisibleList = [];
          this.bkBizLabelsList = [];
          this.cacheBkBizLabelsList = [];
          // 清空连通测试结果
          this.connectResult = '';
          this.connectFailedMessage = '';
          this.isShowManagement = false;
          this.isFirstShow = true;
        }
      },
      basicFormData: {
        handler() {
          if (!this.isFirstShow) {
            this.connectResult = '';
          }
          this.isFirstShow = false;
        },
        deep: true,
      },
      'formData.setup_config.retention_days_default': {
        handler() {
          this.daySelectAddToDisable();
        },
      },
      'formData.setup_config.retention_days_max': {
        handler() {
          this.daySelectAddToDisable();
        },
      },
      // 切换可见范围时 恢复缓存或清空业务选择
      'formData.visible_config.visible_type': {
        handler(val) {
          if (val !== 'multi_biz') {
            this.visibleList = [];
          } else {
            this.visibleList = JSON.parse(JSON.stringify(this.cacheVisibleList));
          }
          if (val !== 'biz_attr') {
            this.bkBizLabelsList = [];
          } else {
            this.bkBizLabelsList = JSON.parse(JSON.stringify(this.cacheBkBizLabelsList));
          }
        },
      },
      visibleList(val) {
        this.visibleBkBiz = val.map(item => item.id);
      },
    },
    methods: {
      updateIsShow() {
        this.$emit('hidden');
        this.$emit('update:show-slider', false);
      },
      inUseProjectPopover(isUse) {
        return {
          theme: 'light',
          content: this.$t('该业务已有采集使用，无法取消可见'),
          disabled: !isUse,
        };
      },
      handleDeleteTag(index) {
        this.visibleList.splice(index, 1);
      },
      handleChangeSource(data) {
        if (data !== 'other') {
          this.formData.source_name = '';
        }
      },
      handleToggleVisible(data) {
        this.visibleIsToggle = data;
        if (!data) {
          this.visibleList.splice(0, this.visibleList.length);
          this.visibleBkBiz.forEach(val => {
            if (!this.visibleList.some(item => String(item.id) === val)) {
              const target = this.mySpaceList.find(project => project.bk_biz_id === val);
              this.visibleList.push({
                id: val,
                name: target.space_full_code_name,
                is_use: false,
              });
            }
          });
        }
      },
      // 编辑 es 源，回填数据
      async editDataSource() {
        try {
          this.sliderLoading = true;
          const res = await this.$http.request('/source/info', {
            params: {
              cluster_id: this.editClusterId,
              bk_biz_id: this.bkBizId,
            },
          });
          this.basicFormData = {
            cluster_name: res.data.cluster_config.cluster_name, // 集群名
            source_type: res.data.cluster_config.custom_option?.source_type || '', // 来源
            source_name:
              res.data.cluster_config.custom_option?.source_type === 'other'
                ? res.data.cluster_config.custom_option?.source_name
                : '',
            domain_name: res.data.cluster_config.domain_name, // 地址
            port: res.data.cluster_config.port, // 端口
            schema: res.data.cluster_config.schema, // 协议
            auth_info: {
              username: res.data.auth_info.username, // 用户名
              password: res.data.auth_info.password || '******', // 密码
            },
          };
          this.formData = {
            enable_hot_warm: res.data.cluster_config.enable_hot_warm, // 是否开启冷热数据
            hot_attr_name: res.data.cluster_config.custom_option?.hot_warm_config?.hot_attr_name || '', // 热节点属性名称
            hot_attr_value: res.data.cluster_config.custom_option?.hot_warm_config?.hot_attr_value || '', // 热节点属性值
            warm_attr_name: res.data.cluster_config.custom_option?.hot_warm_config?.warm_attr_name || '', // 冷节点属性名称
            warm_attr_value: res.data.cluster_config.custom_option?.hot_warm_config?.warm_attr_value || '', // 冷节点属性值
            setup_config: res.data.cluster_config.custom_option?.setup_config || {},
            admin: res.data.cluster_config.custom_option?.admin || [],
            description: res.data.cluster_config.custom_option?.description || '',
            enable_archive: res.data.cluster_config.custom_option?.enable_archive || false,
            enable_assessment: res.data.cluster_config.custom_option?.enable_assessment || false,
            visible_config: res.data.cluster_config.custom_option?.visible_config || {},
          };
          Object.assign(this.formData, this.basicFormData);
          this.initSidebarFormData();
          (res.data.cluster_config.custom_option.visible_config?.visible_bk_biz ?? []).forEach(val => {
            const target = this.mySpaceList.find(project => project.bk_biz_id === String(val.bk_biz_id));
            if (target) {
              target.is_use = val.is_use;
              const targetObj = {
                id: String(val.bk_biz_id),
                name: target.space_full_code_name,
                is_use: val.is_use,
              };
              this.visibleList.push(targetObj);
              this.cacheVisibleList.push(targetObj);
            }
          });

          this.bkBizLabelsList = Object.entries(
            res.data.cluster_config.custom_option.visible_config?.bk_biz_labels || {},
          ).reduce((pre, cur) => {
            const propertyName = this.bizParentList.find(item => item.id === cur[0]);
            const obj = {
              name: `${propertyName.name}`,
              id: cur[0],
              values: cur[1].map(item => ({ id: item, name: item })),
            };
            pre.push(obj);
            return pre;
          }, []);
          this.cacheBkBizLabelsList = JSON.parse(JSON.stringify(this.bkBizLabelsList));
          this.$nextTick(() => {
            // 编辑的时候直接联通测试 通过则展开ES集群管理
            this.handleTestConnect();
          });
        } catch (e) {
          console.warn(e);
        } finally {
          this.sliderLoading = false;
        }
      },

      // 连通性测试
      async handleTestConnect() {
        try {
          await this.$refs.validateForm.validate();
          const postData = {
            bk_biz_id: this.bkBizId,
            cluster_name: this.basicFormData.cluster_name, // 集群名
            domain_name: this.basicFormData.domain_name, // 地址
            port: this.basicFormData.port, // 端口
            schema: this.basicFormData.schema, // 协议
            es_auth_info: {
              username: this.basicFormData.auth_info.username,
              password: this.basicFormData.auth_info.password,
            },
          };
          if (this.isEdit) {
            postData.cluster_id = this.editClusterId;
          }
          if (postData.es_auth_info.password === '******') {
            postData.es_auth_info.password = '';
          }
          this.connectLoading = true;
          await this.$http.request('/source/connectivityDetect', { data: postData }, { catchIsShowMessage: false });
          this.connectResult = 'success';
          // 连通性测试通过之后获取冷热数据
          const attrsRes = await this.$http.request('/source/getNodeAttrs', { data: postData });
          this.hotColdOriginList = attrsRes.data;
        } catch (e) {
          console.warn(e);
          this.connectResult = 'failed';
          this.connectFailedMessage = e.message;
          this.hotColdOriginList = [];
        } finally {
          this.connectLoading = false;
          this.dealWithHotColdData();
        }
      },
      dealWithHotColdData() {
        const hotColdAttrSet = [];
        this.hotColdOriginList.forEach(item => {
          const newItem = { ...item };
          newItem.computedId = `${item.attr}:${item.value}`;
          newItem.computedName = `${item.attr}:${item.value}`;
          newItem.computedCounts = 1;
          newItem.isSelected = false;
          const existItem = hotColdAttrSet.find(item => item.computedId === newItem.computedId);
          if (existItem) {
            existItem.computedCounts += 1;
          } else {
            hotColdAttrSet.push(newItem);
          }
        });
        this.hotColdAttrSet = hotColdAttrSet;
        this.selectedHotId = this.formData.hot_attr_name
          ? `${this.formData.hot_attr_name}:${this.formData.hot_attr_value}`
          : '';
        this.selectedColdId = this.formData.warm_attr_name
          ? `${this.formData.warm_attr_name}:${this.formData.warm_attr_value}`
          : '';
      },
      handleHotSelected(value) {
        const item = this.hotColdAttrSet.find(item => item.computedId === value);
        this.formData.hot_attr_name = item?.attr || '';
        this.formData.hot_attr_value = item?.value || '';
        this.computeIsSelected();
      },
      handleColdSelected(value) {
        const item = this.hotColdAttrSet.find(item => item.computedId === value);
        this.formData.warm_attr_name = item?.attr || '';
        this.formData.warm_attr_value = item?.value || '';
        this.computeIsSelected();
      },
      computeIsSelected() {
        for (const item of this.hotColdAttrSet) {
          item.isSelected = this.selectedColdId === item.computedId || this.selectedHotId === item.computedId;
        }
      },
      handleViewInstanceList(type) {
        this.viewInstanceType = type;
        this.showInstanceDialog = true;
      },

      // 确认提交新增或编辑
      async handleConfirm() {
        const isCanSubmit = this.checkSelectItem();
        if (!isCanSubmit) return;
        try {
          await this.$refs.validateForm.validate();
          let url = '/source/create';
          const paramsData = {
            bk_biz_id: this.bkBizId,
          };
          Object.assign(this.formData, this.basicFormData);
          const postData = JSON.parse(JSON.stringify(this.formData));
          postData.bk_biz_id = this.bkBizId;
          if (!postData.enable_hot_warm) {
            delete postData.hot_attr_name;
            delete postData.hot_attr_value;
            delete postData.warm_attr_name;
            delete postData.warm_attr_value;
          }
          for (const key in postData.setup_config) {
            postData.setup_config[key] = Number(postData.setup_config[key]);
          }
          if (postData.source_type !== 'other') {
            delete postData.source_name;
          }
          if (this.visibleList.length) {
            postData.visible_config.visible_bk_biz = this.visibleList.map(item => item.id);
          } else {
            postData.visible_config.visible_bk_biz = [];
          }
          if (this.bkBizLabelsList.length) {
            postData.visible_config.bk_biz_labels = this.filterBzID();
          } else {
            postData.visible_config.bk_biz_labels = {};
          }
          if (this.isEdit) {
            url = '/source/update';
            paramsData.cluster_id = this.editClusterId;
            if (postData.auth_info.password === '******') {
              postData.auth_info.password = '';
            }
          }
          this.confirmLoading = true;
          await this.$http.request(url, {
            data: postData,
            params: paramsData,
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
      handleCancel() {
        this.$emit('update:show-slider', false);
      },
      updateDaysList() {
        const retentionDaysList = [...this.globalsData.storage_duration_time].filter(item => {
          return item.id;
        });
        this.retentionDaysList = retentionDaysList;
        this.maxDaysList = JSON.parse(JSON.stringify(retentionDaysList));
        this.daySelectAddToDisable();
      },
      /**
       * @desc: 判断过期时间输入的值
       * @param { String } val 输入的值
       * @param { type } type 默认或最大
       */
      enterCustomDay(val, type) {
        const numberVal = parseInt(val.trim(), 10);
        const stringVal = numberVal.toString();
        const isRetention = type === 'retention';
        if (numberVal) {
          const isExceed = isRetention
            ? this.formData.setup_config.retention_days_max < numberVal
            : this.formData.setup_config.retention_days_default > numberVal;
          if (isExceed) {
            this.messageError(this.$t('默认天数不能大于最大天数'));
            return;
          }
          if (isRetention) {
            if (!this.retentionDaysList.some(item => item.id === stringVal)) {
              this.retentionDaysList.push({
                id: stringVal,
                name: stringVal + this.$t('天'),
              });
            }
            this.formData.setup_config.retention_days_default = stringVal;
            this.customRetentionDay = '';
          } else {
            if (!this.maxDaysList.some(item => item.id === stringVal)) {
              this.maxDaysList.push({
                id: stringVal,
                name: stringVal + this.$t('天'),
              });
            }
            this.formData.setup_config.retention_days_max = stringVal;
            this.customMaxDay = '';
          }
          document.body.click();
        } else {
          isRetention ? (this.customRetentionDay = '') : (this.customMaxDay = '');
          this.messageError(this.$t('请输入有效数值'));
        }
      },
      /**
       * @desc: 更新过期时间列表里禁止选中的情况
       */
      daySelectAddToDisable() {
        const { retention_days_default: defaultDays, retention_days_max: maxDays } = this.formData.setup_config;
        this.retentionDaysList.forEach(el => (el.disabled = Number(maxDays) < Number(el.id)));
        this.maxDaysList.forEach(el => (el.disabled = Number(defaultDays) > Number(el.id)));
      },
      handleChangePrincipal(val) {
        // 集群负责人为空时报错警告
        const realVal = val.filter(item => item !== undefined);
        this.isAdminError = !realVal.length;
        this.formData.admin = realVal;
      },
      handleBlur() {
        this.isAdminError = !this.formData.admin.length;
      },
      getBizPropertyId() {
        // 因搜索框如果直接搜索子级元素则返回值不带父级元素 传参需要父级元素则分开展示
        this.$http.request('/source/getProperty').then(res => {
          // 父级键名
          this.bizParentList = res.data.map(item => {
            return {
              name: item.biz_property_name,
              id: item.biz_property_id,
              multiable: true,
              remote: true,
            };
          });
          // 生成子级数组
          res.data.forEach(item => {
            this.bizChildrenList[item.biz_property_id] = item.biz_property_value.map(item => {
              return {
                id: item,
                name: item,
              };
            });
          });
        });
      },
      handleRemoteMethod() {
        return new Promise(resolve => {
          setTimeout(() => {
            // 空值返回全部，搜索返回部分
            if (!!this.bizInputStr) {
              resolve(this.bizChildrenList[this.bizSelectID].filter(item => item.name.includes(this.bizInputStr)));
            } else {
              resolve(this.bizChildrenList[this.bizSelectID]);
            }
          }, 1000);
        });
      },
      handleMenuSelect(item) {
        // 赋值当前选择的ItemID
        this.bizSelectID = item.id;
        // 父选项选中后搜索设置为空
        this.bizInputStr = '';
      },
      handleChildMenuSelect() {
        // 子选项选中后搜索设置为空
        this.bizInputStr = '';
      },
      handleClickOutside() {
        // searchSelect组件若没有点击确认则清除输入框和选中的值
        if (!this.$refs.searchSelectRef.input.focus) {
          this.$refs.searchSelectRef.input.value = '';
          this.$refs.searchSelectRef.menu.active = -1;
          this.$refs.searchSelectRef.menu.id = null;
          this.$refs.searchSelectRef.updateInput();
          this.$refs.searchSelectRef.clearInput();
          this.$refs.searchSelectRef.menu.checked = {};
          this.$refs.searchSelectRef.menuChildInstance && (this.$refs.searchSelectRef.menuChildInstance.checked = {});
          this.$refs.searchSelectRef.menuInstance = null;
        }
      },
      handleInputChange($event) {
        // 按照业务属性选择赋值
        this.bizInputStr = $event.data;
      },
      /**
       * @desc: 过滤和去重按照业务属性选择
       */
      filterBzID() {
        const parentSet = new Set();
        const list = {};
        this.bkBizLabelsList.forEach(item => {
          // 若当前元素父级未重复则生成新键名并赋值
          if (!parentSet.has(item.id)) {
            parentSet.add(item.id);
            list[item.id] = [];
            const valuesList = item.values.map(item => item.id);
            list[item.id] = list[item.id].concat(valuesList);
          } else {
            // 若当前元素父级重复则去重过滤
            const valuesList = item.values.map(item => item.id);
            const concatList = valuesList.concat(list[item.id]);
            const childSet = new Set([...concatList]);
            list[item.id] = [...childSet];
          }
        });
        return list;
      },
      handleOpenDocument() {
        window.open(this.archiveDocUrl, '_blank');
      },
      checkSelectItem() {
        let messageType;
        const { visible_type: visibleType } = this.formData.visible_config;
        visibleType === 'multi_biz' &&
          !this.visibleList.length &&
          (messageType = this.$t('可见类型为业务属性时，业务标签不能为空'));
        visibleType === 'biz_attr' &&
          !this.bkBizLabelsList.length &&
          (messageType = this.$t('可见类型为多业务时，可见业务范围不能为空'));
        if (!!messageType) {
          this.$bkMessage({
            theme: 'error',
            message: messageType,
          });
          return false;
        }
        return true;
      },
    },
  };
</script>

<style lang="scss" scoped>
  @import '@/scss/mixins/flex.scss';
  @import '@/scss/mixins/scroller.scss';

  .king-slider-content {
    min-height: 394px;
    overflow-y: auto;

    .add-collection-title {
      width: 100%;
      padding-top: 18px;
      font-size: 14px;
      font-weight: 600;
      color: #63656e;
    }

    .king-form {
      padding: 16px 36px 36px;

      .form-flex-container {
        display: flex;
        align-items: center;
        // height: 32px;
        font-size: 12px;
        color: #63656e;

        .icon-info {
          margin: 0 8px 0 24px;
          font-size: 14px;
          color: #3a84ff;
        }
      }

      .bk-form-item {
        margin-top: 18px;
      }

      .source-item {
        display: flex;
      }

      .selected-tag {
        max-width: 94%;

        .bk-tag {
          position: relative;
          padding-left: 18px;
          margin-left: 10px;
        }

        .tag-icon::before {
          position: absolute;
          top: 9px;
          left: 8px;
          width: 4px;
          height: 4px;
          content: '';
          border-radius: 50%;
        }

        .is-active::before {
          background-color: #45e35f;
        }

        .is-normal::before {
          background-color: #699df4;
        }
      }

      .source-name-input.is-error {
        color: #f56c6c;
        background-color: #ffeded;
        border-color: #fde2e2;
        transition: all 0.2s;

        &:hover {
          color: #fff;
          background: #fbb8ac;
          transition: all 0.2s;
        }
      }

      .form-item-container {
        @include flex-justify(space-between);

        .bk-form-item {
          position: relative;
          width: 48%;
        }

        .es-address {
          width: 108%;
        }

        .form-item-label {
          margin-bottom: 8px;
          font-size: 14px;
          color: #63656e;

          @include flex-align;
        }

        .button-text {
          font-size: 12px;

          .icon-eye {
            margin: 0 6px 0 8px;
          }
        }

        .document-container {
          transform: translateY(2px);

          @include flex-align;

          .check-document {
            margin: 0 6px 0 20px;
            font-size: 12px;
          }

          .icon-text-file {
            display: inline-block;
            transform: rotateX(180deg) translateY(2px);
          }
        }
      }

      .es-cluster-management {
        display: flex;
        align-items: center;
        font-size: 14px;

        .icon-angle-double-down {
          font-size: 24px;

          &.is-show {
            transform: rotateZ(180deg);
          }
        }
      }

      .scope-radio {
        &:not(:last-child) {
          margin: 0 26px 14px 0;
        }
      }

      .visible-scope-box {
        position: relative;
        display: flex;
        min-height: 30px;

        .please-select {
          margin-left: 10px;
          color: #c3cdd7;
        }

        .icon-angle-down {
          position: absolute;
          top: 4px;
          right: 0;
          font-size: 20px;
          transition: all 0.3s;
          transform: rotateZ(0deg);
        }

        .icon-rotate {
          transform: rotateZ(-180deg);
        }
      }

      .principal .user-selector {
        width: 100%;
      }

      :deep(.is-error .user-selector-container) {
        border-color: #ff5656;
      }
    }
  }

  .king-slider-footer {
    display: flex;
    align-items: center;
    justify-content: flex-end;
    width: 100%;
    height: 100%;
    padding-right: 36px;
    background-color: #fff;
    border-top: 1px solid #dcdee5;

    .king-button {
      min-width: 86px;
    }
  }

  .submit-container {
    position: fixed;
    bottom: 0;
    width: 100%;
    padding: 8px 0 8px 20px;
    background: #fafbfd;
    border-top: 1px solid #dcdee5;
  }

  .illustrate {
    margin-bottom: 80px;
  }

  :deep(.bk-form-textarea) {
    @include scroller;
  }

  .test-container {
    display: flex;
    align-items: center;
    margin-top: 10px;
    font-size: 14px;
    color: #63656e;

    .success-text .bk-icon {
      margin: 0 6px 0 10px;
      color: rgb(45, 203, 86);
    }

    .error-text .bk-icon {
      margin: 0 6px 0 10px;
      color: rgb(234, 54, 54);
    }
  }

  .connect-message {
    font-size: 14px;
    line-height: 18px;
    color: #63656e;
  }

  .flex-space {
    display: flex;

    @include flex-justify(space-between);

    .flex-space-item {
      width: 48%;

      @include flex-justify(space-between);

      .bk-select,
      .bk-form-control {
        flex: 1;
      }

      :deep(.bk-form-input) {
        height: 34px;
      }
    }

    .space-item-label {
      min-width: 48px;
      padding: 0 4px;
      font-size: 12px;
      color: #63656e;
      background: #fafbfd;
      border: 1px solid #c4c6cc;
      border-radius: 2px 0 0 2px;
      transform: translateX(1px);

      @include flex-center;
    }
  }
</style>

<style lang="scss">
  @import '@/scss/space-tag-option';
</style>
