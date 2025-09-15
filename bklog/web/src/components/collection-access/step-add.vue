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
  <div class="add-collection-container">
    <bk-alert
      class="king-alert"
      type="info"
      closable
    >
      <template #title>
        <div class="slot-title-container">
          <i18n path="接入前请查看 {0} ，尤其是在日志量大的情况下请务必提前沟通。">
            <a
              class="link"
              @click="handleGotoLink('logCollection')"
            >
              {{ $t('接入指引') }}</a
            >
          </i18n>
        </div>
      </template>
    </bk-alert>
    <bk-form
      ref="validateForm"
      :label-width="labelWidth"
      :model="formData"
      data-test-id="addNewCollectionItem_form_acquisitionConfig"
    >
      <!-- 基础信息 -->
      <div data-test-id="acquisitionConfig_div_baseMessageBox">
        <div class="add-collection-title">{{ $t('基础信息') }}</div>
        <bk-form-item
          ext-cls="en-bk-form"
          :icon-offset="120"
          :label="$t('采集名')"
          :property="'collector_config_name'"
          :required="true"
          :rules="rules.collector_config_name"
        >
          <bk-input
            class="w520"
            v-model="formData.collector_config_name"
            data-test-id="baseMessage_input_fillName"
            maxlength="50"
            show-word-limit
          >
          </bk-input>
        </bk-form-item>
        <bk-form-item
          ext-cls="en-bk-form"
          :icon-offset="120"
          :label="$t('数据名')"
          :property="'collector_config_name_en'"
          :required="true"
          :rules="rules.collector_config_name_en"
        >
          <div class="en-name-box">
            <div>
              <bk-input
                class="w520"
                v-model="formData.collector_config_name_en"
                :disabled="isUpdate && !!formData.collector_config_name_en"
                :placeholder="$t('支持数字、字母、下划线，长短5～50字符')"
                data-test-id="baseMessage_input_fillEnglishName"
                maxlength="50"
                show-word-limit
              >
              </bk-input>
              <span
                v-if="!isTextValid"
                class="text-error"
                >{{ formData.collector_config_name_en }}</span
              >
            </div>
            <span v-bk-tooltips.top="$t('自动转换成正确的数据名格式')">
              <bk-button
                v-if="!isTextValid"
                text
                @click="handleEnConvert"
                >{{ $t('自动转换') }}</bk-button
              >
            </span>
          </div>
          <template #tip>
            <p class="en-name-tips">
              {{ $t('数据名用于索引和数据源') }}
            </p>
          </template>
        </bk-form-item>
        <bk-form-item :label="$t('备注说明')">
          <bk-input
            class="w520"
            v-model="formData.description"
            data-test-id="baseMessage_input_fillDetails"
            maxlength="100"
            type="textarea"
          >
          </bk-input>
        </bk-form-item>
      </div>

      <!-- 源日志信息 -->
      <div data-test-id="acquisitionConfig_div_sourceLogBox">
        <div class="add-collection-title original-title">
          <span>{{ $t('源日志信息') }}</span>
          <div
            class="flex-ac"
            v-show="!isPhysicsEnvironment"
          >
            <span>{{ $t('Yaml模式') }}</span>
            <div
              v-bk-tooltips.top="{ content: $t('请先选择集群'), delay: 500 }"
              :disabled="!!formData.bcs_cluster_id"
            >
              <bk-switcher
                class="ml10"
                v-model="isYaml"
                :disabled="!formData.bcs_cluster_id"
                :pre-check="handelChangeYaml"
                theme="primary"
              >
              </bk-switcher>
            </div>
          </div>
        </div>
        <div
          v-if="!isFinishCreateStep"
          class="add-collection-import"
        >
          <span @click="handleIndexImportClick">{{ $t('索引配置导入') }}</span>
          <IndexImportModal
            v-model="isIndexImportShow"
            @sync-export="handleSyncExport"
          ></IndexImportModal>
        </div>
        <!-- 环境选择 -->
        <bk-form-item
          :label="$t('环境选择')"
          required
        >
          <div class="environment-box">
            <div
              v-for="(fItem, fIndex) of environmentList"
              class="environment-container"
              :key="fIndex"
            >
              <span class="environment-category">{{ fItem.category }}</span>
              <div class="button-box">
                <div
                  v-for="(sItem, index) of fItem.btnList"
                  :class="{
                    'environment-button': true,
                    active: sItem.id === currentEnvironment,
                    disable: sItem.isDisable,
                  }"
                  :key="index"
                  @click="handleSelectEnvironment(sItem.id, sItem.isDisable)"
                >
                  <img :src="sItem.img" />
                  <p>{{ sItem.name }}</p>
                </div>
              </div>
            </div>
          </div>
        </bk-form-item>
        <!-- 数据分类 -->
        <bk-form-item
          :label="$t('数据分类')"
          :property="'category_id'"
          :rules="rules.category_id"
          required
        >
          <bk-select
            style="width: 320px"
            v-model="formData.category_id"
            :disabled="isUpdate"
            data-test-id="sourceLogBox_div_selectDataClassification"
            @selected="chooseDataClass"
          >
            <template>
              <bk-option-group
                v-for="(item, index) in globalsData.category"
                :id="item.id"
                :key="index"
                :name="item.name"
              >
                <bk-option
                  v-for="(option, key) in item.children"
                  :id="option.id"
                  :key="key"
                  :name="`${item.name}-${option.name}`"
                >
                  {{ option.name }}
                </bk-option>
              </bk-option-group>
            </template>
          </bk-select>
        </bk-form-item>

        <bk-form-item
          v-if="!isPhysicsEnvironment"
          class="cluster-select-box"
          :label="$t('集群选择')"
          :property="'bcs_cluster_id'"
          :rules="rules.bcs_cluster_id"
          required
        >
          <div class="cluster-select">
            <bk-select
              v-model="formData.bcs_cluster_id"
              :clearable="false"
              :disabled="isUpdate || isRequestCluster"
              searchable
              @change="handelClusterChange"
            >
              <bk-option
                v-for="(cluItem, cluIndex) of localClusterList"
                :id="cluItem.id"
                :key="cluIndex"
                :name="`${cluItem.name} (${cluItem.id})`"
              >
              </bk-option>
            </bk-select>
            <!-- <span class="tips">说明详情</span> -->
          </div>
        </bk-form-item>

        <!-- 物理环境 日志类型 -->
        <bk-form-item
          v-if="isPhysicsEnvironment"
          :label="$t('日志类型')"
          required
        >
          <div class="bk-button-group log-type">
            <bk-button
              v-for="(item, index) in getCollectorScenario"
              :class="{
                disable: !item.is_active,
                'is-selected': item.id === formData.collector_scenario_id,
              }"
              :data-test-id="`sourceLogBox_button_checkoutType${item.id}`"
              :disabled="isUpdate && isUpdateAndSelectedWinEvent && isWinEventLog"
              :key="index"
              @click="chooseLogType(item)"
              >{{ item.name }}
            </bk-button>
          </div>
        </bk-form-item>
        <!-- 容器环境 日志类型 -->
        <bk-form-item
          v-else-if="!isPhysicsEnvironment && !isYaml"
          :label="$t('日志类型')"
          required
        >
          <div class="bk-button-group log-type">
            <bk-button
              v-for="(item, index) in getCollectorScenario"
              :class="{
                'is-selected': item.id === formData.collector_scenario_id,
              }"
              :data-test-id="`sourceLogBox_buttom_checkoutType${item.id}`"
              :key="index"
              @click="chooseLogType(item)"
              >{{ item.name }}
            </bk-button>
          </div>
        </bk-form-item>

        <!-- 采集目标 -->
        <div
          v-if="isPhysicsEnvironment"
          class="form-div mt"
        >
          <bk-form-item
            ref="formItemTarget"
            class="item-target"
            :label="$t('采集目标')"
            :property="'target_nodes'"
            :rules="rules.nodes"
            required
          >
            <bk-button
              style="font-size: 12px"
              :class="colorRules ? 'rulesColor' : ''"
              :disabled="!formData.category_id"
              :title="$t('新增')"
              data-test-id="sourceLogBox_button_addCollectionTarget"
              icon="plus"
              theme="default"
              @click="showIpSelectorDialog = true"
            >
              {{ $t('选择目标') }}
            </bk-button>
            <input
              style="display: none"
              :value="formData.target_nodes"
              type="text"
            />
          </bk-form-item>
          <div
            v-if="formData.target_nodes.length"
            class="count"
          >
            <i18n :path="collectTargetTarget[formData.target_node_type]">
              <span class="font-blue">{{ formData.target_nodes.length }}</span>
            </i18n>
          </div>
          <template v-if="formData.category_id">
            <!-- 目标选择器 -->
            <log-ip-selector
              :height="670"
              :key="bkBizId"
              :original-value="ipSelectorOriginalValue"
              :show-dialog.sync="showIpSelectorDialog"
              :show-view-diff="isUpdate"
              :value="selectorNodes"
              :panel-list="ipSelectorPanelList"
              mode="dialog"
              allow-host-list-miss-host-id
              @change="handleTargetChange"
            />
          </template>
        </div>
        <!-- 物理环境 配置项 -->
        <config-log-set-item
          v-if="isPhysicsEnvironment"
          ref="formConfigRef"
          :config-data="formData"
          :config-change-length="configChangeLength"
          :current-environment="currentEnvironment"
          :en-label-width="enLabelWidth"
          :is-clone-or-update="isCloneOrUpdate"
          :scenario-id="formData.collector_scenario_id"
          @config-change="val => handelFormChange(val, 'formConfig')"
        >
        </config-log-set-item>

        <yaml-editor
          v-if="isYaml && !isPhysicsEnvironment"
          ref="yamlEditorRef"
          v-model="formData.yaml_config"
          :cluster-id="formData.bcs_cluster_id"
          :yaml-form-data.sync="yamlFormData"
          value-type="base64"
        ></yaml-editor>

        <template v-else>
          <!-- 配置项  容器环境才显示配置项 -->
          <bk-form-item
            v-if="!isPhysicsEnvironment"
            :label="$t('配置项')"
            required
          >
            <ConfigsSelect
              ref="configsSelectRef"
              :form-data.sync="formData"
              :is-node="isNode"
              :config-change-length="configChangeLength"
              :current-environment="currentEnvironment"
              :is-clone-or-update="isCloneOrUpdate"
              :cluster-list="clusterList"
              :is-physics-environment="isPhysicsEnvironment"
              :is-update="isUpdate"
            ></ConfigsSelect>
          </bk-form-item>

          <div v-if="!isPhysicsEnvironment">
            <!-- <div v-show="isConfigConflict" class="conflict-container flex-ac">
                <span class="bk-icon icon-exclamation-circle"></span>
                <span class="conflict-message">
                  <span>{{$t('冲突检查结果')}}</span> :
                  <span>{{conflictMessage}}</span>
                </span>
                <span v-for="item in conflictList" :key="item" class="collection-item">配置{{index}}</span>
              </div> -->
            <div
              v-en-style="'margin-left: 180px; width: 900px;'"
              class="add-config-item"
              @click="handleAddNewContainerConfig"
            >
              <div><span class="bk-icon icon-plus"></span> {{ $t('添加配置项') }}</div>
            </div>
            <bk-form-item :label="$t('附加日志标签')">
              <div
                v-for="(item, index) in formData.extra_labels"
                class="add-log-label form-div"
                :key="index"
              >
                <bk-input
                  v-model.trim="item.key"
                  :class="{ 'extra-error': item.key === '' && isExtraError }"
                  @blur="isExtraError = false"
                ></bk-input>
                <span>=</span>
                <bk-input
                  v-model.trim="item.value"
                  :class="{ 'extra-error': item.value === '' && isExtraError }"
                  @blur="isExtraError = false"
                ></bk-input>
                <div class="ml9">
                  <i
                    :class="['bk-icon icon-plus-circle-shape icons']"
                    @click="handleAddExtraLabel"
                  ></i>
                  <i
                    :class="[
                      'bk-icon icon-minus-circle-shape icons ml9',
                      {
                        disable: formData.extra_labels.length === 1,
                      },
                    ]"
                    @click="handleDeleteExtraLabel(index)"
                  ></i>
                </div>
              </div>
              <bk-checkbox
                class="mt8"
                v-model="formData.add_pod_label"
              >
                {{ $t('自动添加Pod中的{n}', { n: 'label' }) }}
              </bk-checkbox>
              <bk-checkbox
                class="mt8 ml10"
                v-model="formData.add_pod_annotation"
              >
                {{ $t('自动添加Pod中的{n}', { n: 'annotation' }) }}
              </bk-checkbox>
            </bk-form-item>
          </div>
        </template>
      </div>

      <!-- 上报链路配置 -->
      <template v-if="!isCloseDataLink">
        <div class="add-collection-title">{{ $t('链路配置') }}</div>
        <bk-form-item
          :label="$t('上报链路')"
          :rules="rules.linkConfig"
          property="data_link_id"
          required
        >
          <bk-select
            class="w520"
            v-model="formData.data_link_id"
            :clearable="false"
            :disabled="isUpdate"
            data-test-id="acquisitionConfig_div_selectReportLink"
          >
            <bk-option
              v-for="item in linkConfigurationList"
              :id="item.data_link_id"
              :key="item.data_link_id"
              :name="item.link_group_name"
            >
            </bk-option>
          </bk-select>
        </bk-form-item>
      </template>

      <!-- <bk-dialog
          v-model="isShowSubmitErrorDialog"
          theme="primary"
          header-position="left"
          :mask-close="false">
          {{submitErrorMessage}}
        </bk-dialog> -->

      <div class="page-operate">
        <bk-button
          :disabled="!collectProject"
          :loading="isHandle"
          :title="isFinishCreateStep ? $t('保存') : $t('开始采集')"
          data-test-id="acquisitionConfig_div_nextPage"
          theme="primary"
          @click.stop.prevent="startCollect()"
        >
          {{ isFinishCreateStep ? $t('保存') : $t('下一步') }}
        </bk-button>
        <bk-button
          class="ml10"
          :title="$t('取消')"
          data-test-id="acquisitionConfig_div_cancel"
          theme="default"
          @click="cancel"
        >
          {{ $t('取消') }}
        </bk-button>
      </div>
    </bk-form>
  </div>
</template>

<script>
  import { projectManages, random, deepEqual } from '@/common/util';
  import LogIpSelector, { toTransformNode, toSelectorNode } from '@/components/log-ip-selector/log-ip-selector';
  import ContainerSvg from '@/images/container-icons/Container.svg';
  import LinuxSvg from '@/images/container-icons/Linux.svg';
  import NodeSvg from '@/images/container-icons/Node.svg';
  import StdoutSvg from '@/images/container-icons/Stdout.svg';
  import WindowsSvg from '@/images/container-icons/Windows.svg';
  import { mapGetters } from 'vuex';

  // import ipSelectorDialog from './ip-selector-dialog';
  import configLogSetItem from './components/step-add/config-log-set-item';
  import yamlEditor from './components/step-add/yaml-editor';
  import IndexImportModal from './components/index-import-modal';
  import ConfigsSelect from './components/step-add/configs-select';

  export default {
    components: {
      LogIpSelector,
      // ipSelectorDialog,
      configLogSetItem,
      yamlEditor,
      IndexImportModal,
      ConfigsSelect,
    },
    props: {
      isUpdate: {
        type: Boolean,
        require: true,
      },
      /** 是否是容器步骤 */
      isContainerStep: {
        type: Boolean,
        require: true,
      },
      /** 是否已走过一次完整步骤，编辑状态显示不同的操作按钮 */
      isFinishCreateStep: {
        type: Boolean,
        require: true,
      },
    },
    data() {
      return {
        guideUrl: window.COLLECTOR_GUIDE_URL,
        colorRules: false,
        isItsm: window.FEATURE_TOGGLE.collect_itsm === 'on',
        showRegDialog: false, // 显示段日志调试弹窗
        linkConfigurationList: [], // 链路配置列表
        formData: {
          collector_config_name: '', // 采集项名称
          collector_config_name_en: '', // 采集项数据名称
          category_id: '', // 数据分类
          collector_scenario_id: 'row',
          data_encoding: 'UTF-8', // 日志字符集
          data_link_id: '', // 链路配置
          description: '', // 备注
          target_object_type: 'HOST', // 目前固定为 HOST
          target_node_type: 'TOPO', // 动态 TOPO 静态 INSTANCE 服务模版 SERVICE_TEMPLATE 集群模板 SET_TEMPLATE
          target_nodes: [], // 采集目标
          params: {
            multiline_pattern: '', // 行首正则, char
            multiline_max_lines: '50', // 最多匹配行数, int
            multiline_timeout: '2', // 最大耗时, int
            paths: [{ value: '' }], // 日志路径
            exclude_files: [{ value: '' }], // 日志路径黑名单
            conditions: {
              type: 'none', // 过滤方式类型 match separator
              match_type: 'include', // 过滤方式 可选字段 include, exclude
              match_content: '',
              separator: '|',
              separator_filters: [
                // 分隔符过滤条件
                { fieldindex: '', word: '', op: '=', logic_op: 'and' },
              ],
            },
            winlog_name: [], // windows事件名称
            winlog_level: [], // windows事件等级
            winlog_event_id: [], // windows事件id
            extra_labels: [], // 补充元数据
          },
          environment: 'linux', // 容器环境
          bcs_cluster_id: '', // 集群ID
          add_pod_label: false, // 是否自动添加Pod中的labels
          add_pod_annotation: false, // 是否自动添加Pod中的labels
          extra_labels: [
            // 附加日志标签
            {
              key: '',
              value: '',
            },
          ],
          yaml_config: '', // yaml base64
          yaml_config_enabled: false, // 是否以yaml模式结尾
          configs: [
            // 配置项列表
            {
              namespaces: [],
              noQuestParams: {
                letterIndex: 0,
                scopeSelectShow: {
                  namespace: false,
                  label: true,
                  load: true,
                  containerName: true,
                  annotation: true,
                },
                namespaceStr: '',
                namespacesExclude: '=',
                containerExclude: '=',
              },
              container: {
                workload_type: '',
                workload_name: '',
                container_name: '',
              }, // 容器
              containerNameList: [], // 容器名列表
              labelSelector: [], // 展示用的标签或表达式数组
              label_selector: {
                // 指定标签或表达式
                match_labels: [],
                match_expressions: [],
              },
              match_labels: [],
              match_expressions: [], // config 为空时回填的标签数组
              annotationSelector: [],
              data_encoding: 'UTF-8',
              params: {
                paths: [{ value: '' }], // 日志路径
                exclude_files: [{ value: '' }], // 日志路径黑名单
                conditions: {
                  type: 'none', // 过滤方式类型 none match separator
                  match_type: 'include', // 过滤方式 可选字段 include, exclude
                  match_content: '',
                  separator: '|',
                  separator_filters: [
                    // 分隔符过滤条件
                    { fieldindex: '', word: '', op: '=', logic_op: 'and' },
                  ],
                },
                multiline_pattern: '', // 行首正则, char
                multiline_max_lines: '50', // 最多匹配行数, int
                multiline_timeout: '2', // 最大耗时, int
                winlog_name: [], // windows事件名称
                winlog_level: [], // windows事件等级
                winlog_event_id: [], // windows事件id
              },
            },
          ],
        },
        rules: {
          category_id: [
            // 数据分类
            {
              required: true,
              trigger: 'blur',
            },
          ],
          collector_config_name: [
            // 采集名称
            {
              required: true,
              trigger: 'blur',
            },
            {
              max: 50,
              message: this.$t('不能多于{n}个字符', { n: 50 }),
              trigger: 'blur',
            },
          ],
          collector_config_name_en: [
            // 采集数据名称
            {
              required: true,
              trigger: 'blur',
            },
            {
              validator: this.checkEnNameLength,
              message: this.$t('不能多于{n}个字符', { n: 50 }),
              trigger: 'blur',
            },
            {
              min: 5,
              message: this.$t('不能少于5个字符'),
              trigger: 'blur',
            },
            {
              validator: this.checkEnNameValidator,
              message: this.$t('只支持输入字母，数字，下划线'),
              trigger: 'blur',
            },
            {
              // 检查数据名是否可用
              validator: this.checkEnNameRepeat,
              message: () => this.enNameErrorMessage,
              trigger: 'blur',
            },
          ],
          // 上报链路配置
          linkConfig: [
            {
              required: true,
              trigger: 'blur',
            },
          ],
          nodes: [
            {
              validator: this.checkNodes,
              trigger: 'change',
            },
          ],
          bcs_cluster_id: [
            // 集群
            {
              required: true,
              trigger: 'blur',
            },
          ],
        },
        isTextValid: true,
        isHandle: false,
        isClone: false,
        globals: {},
        localParams: {}, // 缓存的初始数据 用于对比编辑时表单是否有属性更改
        editComparedData: {}, // 编辑保存时 保存不判断基本信息 去除基本信息后的所有值
        showIpSelectorDialog: false,
        collectTargetTarget: {
          // 已(动态)选择 静态主机 节点 服务模板 集群模板
          INSTANCE: '已选择{0}个静态主机',
          TOPO: '已动态选择{0}个节点',
          SERVICE_TEMPLATE: '已选择{0}个服务模板',
          SET_TEMPLATE: '已选择{0}个集群模板',
          DYNAMIC_GROUP: '已选择{0}个动态组',
        },
        configBaseObj: {}, // 新增配置项的基础对象
        isYaml: false, // 是否是yaml模式
        yamlFormData: {}, // yaml请求成功时的表格数据
        currentEnvironment: 'linux', // 当前选中的环境
        environmentList: [
          {
            category: this.$t('物理环境'),
            btnList: [
              { id: 'linux', img: LinuxSvg, name: 'Linux', isDisable: false },
              { id: 'windows', img: WindowsSvg, name: 'Windows', isDisable: false },
            ],
          },
          {
            category: this.$t('容器环境'),
            btnList: [
              { id: 'container_log_config', img: ContainerSvg, name: 'Container', isDisable: false },
              { id: 'node_log_config', img: NodeSvg, name: 'Node', isDisable: false },
              { id: 'std_log_config', img: StdoutSvg, name: this.$t('标准输出'), isDisable: false },
            ],
          },
        ],
        isRequestCluster: false, // 集群列表是否正在请求
        // isConfigConflict: false, // 配置项是否有冲突
        conflictList: [], // 冲突列表
        conflictMessage: '', // 冲突信息
        /** 英文名错误信息 */
        enNameErrorMessage: '',
        clusterList: [], // 集群列表

        allContainer: {
          // 所有容器时指定容器默认传空
          workload_type: '',
          workload_name: '',
          container_name: '',
        },
        publicLetterIndex: 0, // 公共的字母下标
        formTime: null, // form更改防抖timer
        isExtraError: false, // 附加标签是否有出错
        uiconfigToYamlData: {}, // 切换成yaml时当前保存的ui配置
        // ip选择器面板
        ipSelectorPanelList: ['staticTopo', 'dynamicTopo', 'dynamicGroup', 'serviceTemplate', 'setTemplate', 'manualInput'],
        // 编辑态ip选择器初始值
        ipSelectorOriginalValue: null,
        enLabelWidth: 180,
        /** 是否是编状态况并且初始选中的是winevent类型 */
        isUpdateAndSelectedWinEvent: false,
        isIndexImportShow: false,
        configChangeLength: 0,
      };
    },
    computed: {
      ...mapGetters({
        bkBizId: 'bkBizId',
        mySpaceList: 'mySpaceList',
      }),
      ...mapGetters('collect', ['curCollect']),
      ...mapGetters('collect', ['exportCollectObj']),
      ...mapGetters('globals', ['globalsData']),
      collectProject() {
        return projectManages(this.$store.state.topMenu, 'collection-item');
      },
      isCloseDataLink() {
        // 没有可上报的链路时，编辑采集配置链路ID为0或null时，隐藏链路配置框，并且不做空值校验。
        return !this.linkConfigurationList.length || (this.isUpdate && !this.curCollect.data_link_id);
      },
      // 是否打开行首正则功能
      hasMultilineReg() {
        return this.formData.collector_scenario_id === 'section';
      },
      // 是否是wineventlog日志
      isWinEventLog() {
        return this.formData.collector_scenario_id === 'wineventlog';
      },
      // 是否是物理环境
      isPhysicsEnvironment() {
        const isPhysics = ['linux', 'windows'].includes(this.currentEnvironment);
        this.$emit('update:is-physics', isPhysics);
        return isPhysics;
      },
      // 是否是Node环境
      isNode: {
        get() {
          return this.currentEnvironment === 'node_log_config';
        },
        set(newVal) {
          if (newVal) {
            this.formData.configs.forEach(item => {
              item.container = this.allContainer;
              item.namespaces = [];
            });
          }
        },
      },
      // 获取日志类型列表
      getCollectorScenario() {
        try {
          const activeScenario = this.globalsData.collector_scenario.filter(item => item.is_active);
          if (this.currentEnvironment === 'windows') return activeScenario;
          const winIndex = activeScenario.findIndex(item => item.id === 'wineventlog');
          activeScenario.splice(winIndex, 1);
          return activeScenario;
        } catch (error) {
          return [];
        }
      },
      // 是否是编辑或者克隆
      isCloneOrUpdate() {
        return this.isUpdate || this.isClone;
      },
      localClusterList() {
        return this.clusterList.filter(val => (this.isNode ? !val.is_shared : true));
      },
      // ip选择器选中节点
      selectorNodes() {
        return this.getSelectorNodes();
      },
      updateCollectorConfigID() {
        // 若是新增容器日志 返回上一步 则使用curCollect缓存的collector_config_id更新;
        const { collectorId } = this.$route.params;
        return !!collectorId ? Number(collectorId) : Number(this.curCollect.collector_config_id);
      },
      labelWidth() {
        return this.$store.state.isEnLanguage ? this.enLabelWidth : 115;
      },
    },
    watch: {
      currentEnvironment(nVal, oVal) {
        if (oVal === 'windows' && this.isWinEventLog) {
          this.formData.collector_scenario_id = this.globalsData.collector_scenario[0].id;
        }
        if (['std_log_config', 'container_log_config', 'node_log_config'].includes(nVal)) {
          this.formData.environment = 'container';
          this.isNode = nVal === 'node_log_config';
          !this.clusterList.length && this.getBcsClusterList();
          if (nVal === 'node_log_config' && this.getIsSharedCluster()) {
            // 选中node环境时 如果存在已选的共享集群 则清空
            this.formData.bcs_cluster_id = '';
          }
          return;
        }
        this.formData.environment = nVal;
      },
      'formData.bcs_cluster_id'(nVal, oVal) {
        if (!nVal && !oVal) return;
        this.$nextTick(() => {
          this.$refs?.configsSelectRef?.getNameSpaceList(nVal, oVal === '');
        });
      },
      'formData.extra_labels.length'() {
        this.isExtraError = false;
      },
      yamlFormData: {
        deep: true,
        handler(val) {
          if (val?.configs.length) {
            this.currentEnvironment = val.configs[0].collector_type;
          }
        },
      },
    },
    created() {
      this.isClone = this.$route.query?.type === 'clone';
      this.$store.commit('updateState', { 'showRouterLeaveTip': false});
      this.configBaseObj = structuredClone(this.formData.configs[0]); // 生成配置项的基础对象
      this.getLinkData();
      // 克隆与编辑均进行数据回填
      if (this.isUpdate || this.isClone) {
        const cloneCollect = structuredClone(this.curCollect);
        this.initFromData(cloneCollect);
        if (!this.isPhysicsEnvironment) {
          const initFormData = this.initContainerFormData(cloneCollect);
          Object.assign(this.formData, initFormData);
        }
        if (this.isUpdate && this.isWinEventLog) {
          this.isUpdateAndSelectedWinEvent = true;
        }
        // 克隆采集项的时候 清空以下回显或者重新赋值 保留其余初始数据
        if (this.isClone) {
          // 若是容器环境 克隆时 初始化物理环境的值
          this.formData.params = this.configBaseObj.params;
          this.formData.data_encoding = 'UTF-8';
          this.formData.collector_config_name = `${this.formData.collector_config_name}_clone`;
          this.formData.collector_config_name_en = '';
          this.formData.target_nodes = [];
        } else {
          // 编辑且非克隆则禁用另一边的环境按钮
          this.initBtnListDisable();
        }
        this.$nextTick(() => {
          this.configChangeLength += 1;
          if (!this.isClone) {
            // 克隆时不缓存初始数据
            // 编辑采集项时缓存初始数据 用于对比提交时是否发生变化 未修改则不重新提交 update 接口
            this.localParams = this.handleParams();
            const { description, collector_config_name, ...otherVal } = this.localParams;
            this.editComparedData = otherVal;
          }
        });
      }
    },
    methods: {
      handleIndexImportClick() {
        this.isIndexImportShow = true;
      },
      async getLinkData() {
        try {
          this.tableLoading = true;
          const res = await this.$http.request('linkConfiguration/getLinkList', {
            query: {
              bk_biz_id: this.$store.state.bkBizId,
            },
          });
          this.linkConfigurationList = res.data.filter(item => item.is_active);
          if (this.linkConfigurationList.length && !this.isCloneOrUpdate) {
            this.formData.data_link_id = this.linkConfigurationList[0].data_link_id;
          }
        } catch (e) {
          console.warn(e);
        } finally {
          this.tableLoading = false;
        }
      },
      /**
       * @desc: 初始化容器的编辑的form表单值
       * @param { Object } formData 基础表单
       * @param { Boolean } isYamlData 是否是yaml解析出的表单数据
       * @returns { Object } 返回初始化后的Form表单
       */
      initContainerFormData(formData, initType = 'all', isYamlData = false) {
        const curFormData = structuredClone(formData);
        if (!curFormData.extra_labels.length && initType !== 'collect') {
          curFormData.extra_labels = [
            {
              key: '',
              value: '',
            },
          ];
        }
        const filterConfigs = curFormData.configs.map((item, index) => {
          const { params: configParams, ...otherCollect } = this.configBaseObj;
          if (initType === 'collect') {
            item.params = configParams;
          } else if (initType === 'params') {
            item = {
              ...otherCollect,
              params: item.params,
            };
          }
          const {
            workload_name,
            workload_type,
            container_name: containerName,
            container_name_exclude: containerNameExclude,
            match_expressions,
            match_labels,
            match_annotations: matchAnnotations,
            data_encoding,
            params,
            namespaces: itemNamespace,
            namespaces_exclude: itemNamespacesExclude,
            container: yamlContainer,
            label_selector: yamlSelector,
            annotation_selector: yamlAnnoSelector,
            collector_type,
          } = item;
          const showNameSpace = itemNamespacesExclude?.length ? itemNamespacesExclude : itemNamespace;
          const namespaces = item.any_namespace ? ['*'] : showNameSpace;
          const container = {
            workload_type,
            workload_name,
            container_name: containerName,
            container_name_exclude: containerNameExclude,
          };

          let labelSelector = [];
          let annotationSelector = [];
          let containerNameList = this.getContainerNameList(containerName || containerNameExclude);
          if (isYamlData) {
            Object.assign(container, yamlContainer);
            labelSelector = this.getLabelSelectorArray(yamlSelector);
            annotationSelector = this.getLabelSelectorArray(yamlAnnoSelector);
            const { container_name: yamlContainerName, container_name_exclude: yamlContainerNameExclude } =
              yamlContainer;
            containerNameList = this.getContainerNameList(yamlContainerName || yamlContainerNameExclude);
            params.paths = params.paths.length ? params.paths.map(item => ({ value: item })) : [{ value: '' }];
            params.exclude_files = params.exclude_files.length
              ? params.exclude_files.map(item => ({ value: item }))
              : [{ value: '' }];
          } else {
            labelSelector = this.getLabelSelectorArray({
              match_expressions,
              match_labels,
            });
            annotationSelector = this.getLabelSelectorArray({
              match_annotations: matchAnnotations || [],
            });
            if (!params.conditions?.separator_filters) {
              params.conditions.separator_filters = [{ fieldindex: '', word: '', op: '=', logic_op: 'and' }];
            }
          }
          const containerExclude = !!containerNameExclude ? '!=' : '=';
          const namespacesExclude = itemNamespacesExclude?.length ? '!=' : '=';
          const namespaceStr = this.getNameSpaceStr(namespaces);
          return {
            namespaces,
            noQuestParams: {
              letterIndex: index, // 配置项字母下标
              scopeSelectShow: {
                namespace: !Boolean(namespaces.length),
                label: !Boolean(labelSelector.length),
                load: !(Boolean(container.workload_type) || Boolean(container.workload_name)),
                containerName: !Boolean(containerNameList.length),
                annotation: !Boolean(annotationSelector.length),
              },
              namespaceStr,
              containerExclude,
              namespacesExclude,
            },
            data_encoding,
            container,
            labelSelector,
            annotationSelector,
            containerNameList,
            params,
            collector_type,
          };
        });
        curFormData.configs = filterConfigs;
        return curFormData;
      },
      /** 获取label页面所需的数组 */
      getLabelSelectorArray(selector) {
        return Object.entries(selector).reduce((pre, [labelKey, labelVal]) => {
          pre.push(...labelVal.map(item => ({ ...item, id: random(10), type: labelKey })));
          return pre;
        }, []);
      },
      /**
       * @desc: 初始化物理环境编辑的的form表单值
       * @param { Object } formData 基础表单
       * @returns { Object } 返回初始化后的Form表单
       */
      getInitFormData(formData) {
        const curFormData = structuredClone(formData);
        // win_event类型不需要初始化分隔符的过滤条件
        if (!curFormData.params.conditions?.separator_filters && curFormData.collector_scenario_id !== 'wineventlog') {
          curFormData.params.conditions.separator_filters = [{ fieldindex: '', word: '', op: '=', logic_op: 'and' }];
        }
        return curFormData;
      },
      getContainerNameList(containerName = '') {
        const splitList = containerName.split(',');
        if (splitList.length === 1 && splitList[0] === '') return [];
        return splitList;
      },
      /** 导航切换提交函数 */
      stepSubmitFun(callback) {
        this.startCollect(callback);
      },
      // 开始采集
      async startCollect(callback) {
        const isCanSubmit = await this.submitDataValidate();
        if (!isCanSubmit) {
          callback?.(false);
          return;
        }
        const params = this.handleParams();
        // console.log(params);
        // return
        if (deepEqual(this.localParams, params)) {
          this.isHandle = false;
          if (this.isFinishCreateStep) {
            // 保存的情况下, 没有任何改变, 回退到列表
            if (callback) {
              callback(true);
              return;
            }
            this.cancel();
          } else {
            // 未修改表单 直接跳转下一步
            this.$emit('step-change');
          }
          return;
        }
        this.$refs.validateForm.validate().then(
          () => {
            this.isCloseDataLink && delete params.data_link_id;
            this.isPhysicsEnvironment
              ? this.setCollection(params, callback)
              : this.setContainerCollection(params, callback);
          },
          () => {
            callback?.(false);
          },
        );
      },
      /**
       * @desc: 提交表格时验证是否通过
       * @return { Boolean } 是否可以提交
       */
      async submitDataValidate() {
        try {
          // 基础信息表格验证
          await this.$refs.validateForm.validate();
        } catch (error) {}
        // win日志类型验证
        if (this.$refs.formConfigRef?.winCannotPass && this.isWinEventLog) return false;
        // 物理环境验证
        if (this.isPhysicsEnvironment) {
          return (
            (await this.$refs.formConfigRef.logFilterValidate()) &&
            (await this.$refs.formConfigRef.extraLabelsValidate())
          );
        }
        // 容器环境并且打开yaml模式时进行yaml语法检测
        if (this.isYaml && !this.isPhysicsEnvironment) {
          if (!this.$refs.yamlEditorRef.getSubmitState || this.formData.yaml_config === '') {
            let message = this.$refs.yamlEditorRef.isHaveCannotSubmitWaring
              ? this.$t('yaml缺少必要的字段')
              : this.$t('yaml语法出错');
            this.formData.yaml_config === '' && (message = this.$t('yaml不能为空'));
            this.$bkMessage({ theme: 'error', message });
            return false;
          }
          return true;
        }
        // 容器环境时 进行配置项检查
        if (!this.isPhysicsEnvironment) {
          let containerConfigValidate = true;
          const configList = this.$refs.configsSelectRef.$refs.containerConfigRef;
          // 标准输出环境下配置项里过滤内容是否有分隔符过滤 有则进行配置项form校验
          const isCheckConfigItem = !(
            this.currentEnvironment === 'std_log_config' && this.formData.collector_scenario_id === 'row'
          );
          // 检查配置项中是否有分隔符过滤
          const isHaveSeparator = configList.some(item => item.subFormData.params.conditions.type === 'separator');
          if (isCheckConfigItem || isHaveSeparator) {
            // 判断config列表里是否有需要校验的dom元素。
            for (const key in configList) {
              if (containerConfigValidate) containerConfigValidate = await configList[Number(key)].logFilterValidate();
            }
          }
          // 附加日志标签是否只单独填写了一边
          this.isExtraError = this.formData.extra_labels.some(item => {
            const extraFillLength = Object.values(item).reduce((pre, cur) => {
              cur === '' && (pre += 1);
              return pre;
            }, 0);
            return extraFillLength === 1;
          });
          if (!containerConfigValidate || this.isExtraError) return false;
          if (this.getIsSharedCluster() && this.formData.configs.some(conf => !conf.namespaces.length)) {
            // 容器环境下选择了共享集群 但NameSpace为空
            this.$bkMessage({ theme: 'error', message: this.$t('配置项命名空间不能为空') });
            return false;
          }
        }
        return true;
      },
      // 新增/修改采集
      setCollection(params, callback) {
        this.isHandle = true;
        const urlParams = {};
        let requestUrl;
        if (this.isUpdate) {
          urlParams.collector_config_id = this.updateCollectorConfigID;
          requestUrl = 'collect/updateCollection';
        } else {
          requestUrl = 'collect/addCollection';
        }
        const updateData = { params: urlParams, data: params };
        this.$http
          .request(requestUrl, updateData)
          .then(res => {
            if (res.code === 0) {
              this.$store.commit(
                `collect/${this.isUpdate ? 'updateCurCollect' : 'setCurCollect'}`,
                Object.assign({}, this.formData, params, res.data),
              );
              this.$emit('update:is-update', true);
              this.setDetail(res.data.collector_config_id);
              // 物理环境编辑情况
              if (this.isFinishCreateStep) {
                if (callback) {
                  callback(true);
                  return;
                }
                this.cancel();
              } else {
                // 新增情况直接下一步
                this.$emit('step-change');
              }
            }
          })
          .catch(() => callback?.(false))
          .finally(() => {
            this.isHandle = false;
          });
      },
      // 容器日志新增/修改采集
      setContainerCollection(params, callback) {
        this.isHandle = true;
        this.$emit('update:container-loading', true);
        const urlParams = {};
        let requestUrl;
        if (this.isUpdate) {
          urlParams.collector_config_id = this.updateCollectorConfigID;
          requestUrl = 'container/update';
        } else {
          requestUrl = 'container/create';
        }
        const data = Object.assign(params, this.isYaml ? this.yamlFormData : {}, { yaml_config_enabled: this.isYaml });
        const updateData = { params: urlParams, data };
        this.$http
          .request(requestUrl, updateData)
          .then(res => {
            if (res.code === 0) {
              this.$store.commit(
                `collect/${this.isUpdate ? 'updateCurCollect' : 'setCurCollect'}`,
                Object.assign({}, this.formData, params, res.data),
              );
              this.$emit('update:is-update', true);
              this.setDetail(res.data.collector_config_id);
              // 容器环境没有下发步骤 直接回到列表或者下一步
              if (this.isFinishCreateStep) {
                if (callback) {
                  callback(true);
                  return;
                }
                this.cancel();
              } else {
                this.$emit('update:container-loading', false);
                this.$emit('step-change');
              }
            }
          })
          .catch(error => {
            console.warn(error);
            callback?.(false);
            // this.isShowSubmitErrorDialog = true;
            // this.submitErrorMessage = error.message;
          })
          .finally(() => {
            this.isHandle = false;
            this.$emit('update:container-loading', false);
          });
      },
      /**
       * @desc: 获取提交参数
       * @returns {Object} 返回提交参数数据
       */
      handleParams() {
        const formData = structuredClone(this.formData);
        const {
          collector_config_name,
          collector_config_name_en,
          category_id,
          collector_scenario_id,
          description,
          target_object_type,
          target_node_type,
          target_nodes,
          data_encoding,
          data_link_id,
          params,
          environment,
          bcs_cluster_id,
          add_pod_label,
          add_pod_annotation,
          extra_labels: extraLabels,
          configs,
          yaml_config,
        } = formData;
        const containerFromData = {}; // 容器环境From数据
        const physicsFromData = {}; // 物理环境From数据
        const publicFromData = {
          // 通用From数据
          collector_config_name,
          collector_config_name_en,
          collector_scenario_id,
          description,
          environment,
          data_link_id,
          category_id,
        };
        // 容器环境
        if (!this.isPhysicsEnvironment) {
          Object.assign(containerFromData, publicFromData, {
            bcs_cluster_id,
            add_pod_label,
            add_pod_annotation,
            extra_labels: extraLabels,
            configs,
            yaml_config,
            yaml_config_enabled: this.isYaml,
          });
          containerFromData.configs.forEach((item, index) => {
            const containerKey =
              item.noQuestParams.containerExclude === '!=' ? 'container_name_exclude' : 'container_name';
            const namespacesKey = item.noQuestParams.namespacesExclude === '!=' ? 'namespaces_exclude' : 'namespaces';
            JSON.stringify(item.namespaces) === '["*"]' && (item.namespaces = []);
            const { namespace, load, containerName } = this.getScopeSelectShow(index);
            item.collector_type = this.currentEnvironment;
            if (namespace || this.isNode) item.namespaces = [];
            if (load || this.isNode) {
              item.container.workload_type = '';
              item.container.workload_name = '';
            }
            const cloneNamespaces = structuredClone(item.namespaces);
            delete item.namespaces;
            item[namespacesKey] = cloneNamespaces;
            item.label_selector = this.getSelectorQueryParams(item.labelSelector, {
              match_labels: [],
              match_expressions: [],
            });
            item.annotation_selector = this.getSelectorQueryParams(item.annotationSelector, { match_annotations: [] });

            item.container = {
              workload_type: item.container.workload_type,
              workload_name: item.container.workload_name,
              [containerKey]: item.containerNameList.join(','),
            };
            if (containerName || this.isNode) item.container[containerKey] = '';

            delete item.noQuestParams;
            delete item.labelSelector;
            delete item.containerNameList;
            delete item.annotationSelector;
            // 若为标准输出 则直接清空日志路径
            if (item.collector_type === 'std_log_config') {
              item.params.paths = [];
              item.params.exclude_files = [];
            }
            item.params = this.filterParams(item.params);
          });
          containerFromData.extra_labels = extraLabels.filter(item => !(item.key === '' && item.value === ''));
          return Object.assign(containerFromData, {
            // 容器环境更新
            bk_biz_id: this.bkBizId,
          });
        }
        const physicsParams = this.filterParams(params);
        // 物理环境
        Object.assign(physicsFromData, publicFromData, {
          target_node_type,
          target_object_type,
          target_nodes,
          data_encoding,
          params: physicsParams,
        });
        if (this.isUpdate) {
          // 物理环境编辑
          physicsFromData.collector_config_id = this.updateCollectorConfigID;
          delete physicsFromData.category_id;
          return Object.assign(physicsFromData, {
            bk_biz_id: this.bkBizId,
          });
        } // 物理环境新增
        return Object.assign(physicsFromData, {
          bk_biz_id: this.bkBizId,
        });
      },
      /**
       * @desc: 对表单的params传参参数进行处理
       * @param { Object } passParams
       */
      filterParams(passParams) {
        let params = structuredClone(passParams);
        if (!this.isWinEventLog) {
          if (!this.hasMultilineReg) {
            // 行首正则未开启
            delete params.multiline_pattern;
            delete params.multiline_max_lines;
            delete params.multiline_timeout;
          }
          const { separator, separator_filters, type } = params.conditions;
          params.conditions = { type };
          if (type !== 'none') {
            Object.assign(params.conditions, { separator, separator_filters });
          }
          params.paths = params.paths.map(item => (typeof item === 'object' ? item.value : item)) || [];
          params.exclude_files =
            params.exclude_files?.map(item => (typeof item === 'object' ? item.value : item)).filter(Boolean) || [];
        } else {
          params = this.$refs.formConfigRef.getWinParamsData;
        }
        return params;
      },
      // 选择日志类型
      chooseLogType(item) {
        if (item?.is_active) this.formData.collector_scenario_id = item.id;
      },
      // 选择数据分类
      chooseDataClass() {
        // console.log(val)
        /**
         * 以下为预留逻辑
         */
        // 当父类为services时，仅能选取动态类型目标；其他父类型目标为静态类型时，切换为serveices时需要做清空判断操作
        // if (['services', 'module'].includes(val)) {
        //     if (this.formData.target_object_type === 'SERVICE') {
        //         this.formData.target_nodes = []
        //     }
        //     this.formData.target_object_type = 'SERVICE'
        // } else {
        //     this.formData.target_object_type = 'HOST'
        // }
      },
      // 取消操作
      cancel() {
        // 保存, 回退到列表
        if (this.isFinishCreateStep) {
          this.$emit('change-submit', true);
        }
        let routeName;
        const { backRoute, ...reset } = this.$route.query;
        if (backRoute) {
          routeName = backRoute;
        } else {
          routeName = 'collection-item';
        }
        this.$router.push({
          name: routeName,
          query: {
            ...reset,
            spaceUid: this.$store.state.spaceUid,
          },
        });
      },
      // 采集目标选择内容变更
      targetChange(params) {
        // bk_biz_id, target_object_type, target_node_type, target_nodes
        // this.formData.target_object_type = params.target_object_type
        this.formData.target_node_type = params.target_node_type;
        this.formData.target_nodes = params.target_nodes;
        this.showIpSelectorDialog = false;
        // 触发 bk-form 的表单验证
        this.$refs.formItemTarget.validate('change');
      },
      // 采集目标选择内容变更
      handleTargetChange(value) {
        const {
          host_list: hostList,
          node_list: nodeList,
          service_template_list: serviceTemplateList,
          set_template_list: setTemplateList,
          dynamic_group_list: dynamicGroupList,
        } = value;
        let type = '';
        let nodes = [];
        if (nodeList?.length) {
          type = 'TOPO';
          nodes = nodeList;
        }
        if (hostList?.length) {
          type = 'INSTANCE';
          nodes = hostList;
        }
        if (serviceTemplateList?.length) {
          type = 'SERVICE_TEMPLATE';
          nodes = serviceTemplateList;
        }
        if (setTemplateList?.length) {
          type = 'SET_TEMPLATE';
          nodes = setTemplateList;
        }
        if (dynamicGroupList?.length) {
          type = 'DYNAMIC_GROUP';
          nodes = dynamicGroupList;
        }
        if (!type) return;

        this.formData.target_node_type = type;
        this.formData.target_nodes = toTransformNode(nodes, type);
        // 触发 bk-form 的表单验证
        this.$refs.formItemTarget.validate('change');
      },
      checkNodes() {
        this.colorRules = !this.formData.target_nodes?.length;
        return this.formData.target_nodes.length;
      },
      // 新增的时候更新详情
      setDetail(id) {
        this.$http
          .request('collect/details', {
            params: { collector_config_id: id },
          })
          .then(res => {
            if (res.data) {
              this.$store.commit('collect/setCurCollect', res.data);
            }
          });
      },
      async checkEnNameRepeat(val) {
        if (this.isUpdate) return true;
        const result = await this.getEnNameIsRepeat(val);
        return result;
      },
      // 检测数据名称是否可用
      async getEnNameIsRepeat(val) {
        try {
          const res = await this.$http.request('collect/getPreCheck', {
            params: { collector_config_name_en: val, bk_biz_id: this.$store.state.bkBizId },
          });
          if (res.data) {
            this.enNameErrorMessage = res.data.message;
            return res.data.allowed;
          }
        } catch (error) {
          return false;
        }
      },
      /**
       * @desc: 环境选择
       * @param { String } name 环境名称
       * @param { Boolean } isDisable 是否禁用
       */
      handleSelectEnvironment(name, isDisable) {
        if (this.isUpdate && isDisable) return;
        this.currentEnvironment = name;
        if (!['linux', 'windows'].includes(this.currentEnvironment)) {
          this.formData.configs.forEach(item => (item.labelSelector = [])); // 切换环境清空label
        }
        if (name === 'windows' && this.isUpdateAndSelectedWinEvent) {
          this.formData.collector_scenario_id = 'wineventlog';
        }
      },
      handleAddExtraLabel() {
        this.formData.extra_labels.push({ key: '', value: '' });
      },
      handleDeleteExtraLabel(index) {
        this.formData.extra_labels.length > 1 && this.formData.extra_labels.splice(index, 1);
      },
      handleAddNewContainerConfig() {
        // 添加配置项
        const newContainerConfig = structuredClone(this.configBaseObj);
        this.publicLetterIndex += 1;
        newContainerConfig.noQuestParams.letterIndex = this.publicLetterIndex;
        this.formData.configs.push(newContainerConfig);
      },
      // 当前所选集群是否共享集群
      getIsSharedCluster() {
        return this.clusterList?.find(cluster => cluster.id === this.formData.bcs_cluster_id)?.is_shared ?? false;
      },
      /**
       * @desc: 获取bcs集群列表
       */
      getBcsClusterList() {
        if (this.isRequestCluster) return;
        this.isRequestCluster = true;
        const query = { bk_biz_id: this.bkBizId };
        this.$http
          .request('container/getBcsList', { query })
          .then(res => {
            if (res.code === 0) {
              this.clusterList = res.data;
            }
          })
          .catch(err => {
            console.warn(err);
          })
          .finally(() => {
            this.isRequestCluster = false;
          });
      },
      /**
       * @desc: 切换ui模式或yaml模式
       * @param { Boolean } val
       */
      handelChangeYaml(val) {
        return new Promise((resolve, reject) => {
          if (val) {
            const { add_pod_label, add_pod_annotation, extra_labels, configs } = this.handleParams();
            const data = { add_pod_label, add_pod_annotation, extra_labels, configs };
            // 传入处理后的参数 请求ui配置转yaml的数据
            this.$http
              .request('container/containerConfigsToYaml', { data })
              .then(res => {
                this.formData.yaml_config = res.data;
                // 保存进入yaml模式之前的ui配置参数
                Object.assign(this.uiconfigToYamlData, {
                  add_pod_label: this.formData.add_pod_label,
                  add_pod_annotation: this.formData.add_pod_annotation,
                  extra_labels: this.formData.extra_labels,
                  configs: this.formData.configs,
                });
                resolve(true);
              })
              .catch(err => {
                console.warn(err);
                reject(false);
              });
          } else {
            try {
              // 若有报错 则回填进入yaml模式之前的ui配置参数
              if (!this.$refs.yamlEditorRef.getSubmitState) {
                Object.assign(this.formData, this.uiconfigToYamlData);
              } else {
                // 无报错 回填yamlData的参数
                const assignData = this.initContainerFormData(this.yamlFormData, 'all', true);
                Object.assign(this.formData, assignData);
              }
              resolve(true);
            } catch (error) {
              resolve(false);
            }
          }
        });
      },
      /**
       * @desc: 编进进入时判断当前环境 禁用另一边环境选择
       */
      initBtnListDisable() {
        const operateIndex = ['linux', 'windows'].includes(this.currentEnvironment) ? 1 : 0;
        this.environmentList[operateIndex].btnList.forEach(item => (item.isDisable = true));
      },
      handelClusterChange() {
        // 切换集群清空 namespaces
        this.formData.configs = this.formData.configs.map(conf => {
          return {
            ...conf,
            namespaces: [],
          };
        });
      },
      checkEnNameValidator(val) {
        this.isTextValid = new RegExp(/^[A-Za-z0-9_]+$/).test(val);
        return this.isTextValid;
      },
      checkEnNameLength(val) {
        // 编辑时，不需要验证采集项英文名
        if (this.isUpdate) return true;
        // 判断字符串长度是否大于50
        return val.length <= 50;
      },
      handleEnConvert() {
        const str = this.formData.collector_config_name_en;
        const convertStr = str.split('').reduce((pre, cur) => {
          if (cur === '-') cur = '_'; // 中划线转化成下划线
          if (!/\w/.test(cur)) cur = ''; // 不符合的值去掉
          return (pre += cur);
        }, '');
        this.formData.collector_config_name_en = convertStr;
        this.$refs.validateForm
          .validate()
          .then(() => {
            this.isTextValid = true;
          })
          .catch(() => {
            if (convertStr.length < 5) this.isTextValid = true;
          });
      },
      getSelectorNodes() {
        const { target_node_type: type, target_nodes: nodes } = this.formData;
        const targetList = toSelectorNode(nodes, type);
        return {
          host_list: type === 'INSTANCE' ? targetList : [],
          node_list: type === 'TOPO' ? targetList : [],
          service_template_list: type === 'SERVICE_TEMPLATE' ? targetList : [],
          set_template_list: type === 'SET_TEMPLATE' ? targetList : [],
          dynamic_group_list: type === 'DYNAMIC_GROUP' ? targetList : [],
        };
      },
      // 获取config里添加范围的列表
      getScopeSelectShow(conIndex) {
        return this.formData.configs[conIndex].noQuestParams.scopeSelectShow;
      },
      getNameSpaceStr(namespaces) {
        return namespaces.length === 1 && namespaces[0] === '*' ? '' : namespaces.join(',');
      },
      /**
       * @desc: 展示用的标签格式转化成存储或传参的标签格式
       * @param {Object} labelSelector 主页展示用的label_selector
       * @returns {Object} 返回传参的数据
       */
      getSelectorQueryParams(selector, basePre) {
        return selector.reduce((pre, cur) => {
          if (!pre[cur.type]) pre[cur.type] = [];
          pre[cur.type].push({
            key: cur.key,
            operator: cur.operator,
            value: cur.value,
          });
          return pre;
        }, basePre);
      },
      /** 判断除基本信息外是否有更改过值 */
      isUpdateIssuedShowValue() {
        const params = this.handleParams();
        const { description, collector_config_name, ...otherVal } = params;
        return !deepEqual(this.editComparedData, otherVal);
      },
      /** 判断是否有改值 */
      getIsUpdateSubmitValue() {
        const params = this.handleParams();
        return !deepEqual(this.localParams, params);
      },
      /**
       * @desc: 用户操作合并form数据
       * @param { Object } val 操作后返回值对象
       * @param { String } operator 配置项还是form本身
       * @param { Number } index 配置项下标
       */
      handelFormChange(val, operator) {
        const setTime = operator === 'dialogChange' ? 10 : 500;
        clearTimeout(this.formTime);
        this.formTime = setTimeout(() => {
          Object.assign(this.formData, val);
        }, setTime);
      },
      handleSyncExport() {
        const syncType = this.exportCollectObj.syncType;
        const collect = this.exportCollectObj.collect;
        const everyExport = ['source_log_info', 'acquisition_target'];
        const { collector_config_name, collector_config_name_en, description, target_nodes: formNodes } = this.formData;
        const baseMessage = {
          collector_config_name,
          collector_config_name_en,
          description,
        };
        let collectConfig = {};
        this.initFromData(collect);
        if (everyExport.every(item => syncType.includes(item))) {
          if (!this.isPhysicsEnvironment) {
            Object.assign(collectConfig, this.initContainerFormData(collect));
          }
        } else {
          if (syncType.includes('source_log_info')) {
            if (this.isPhysicsEnvironment) {
              this.formData.target_nodes = formNodes;
            } else {
              Object.assign(collectConfig, this.initContainerFormData(collect, 'params'));
            }
          }
          if (syncType.includes('acquisition_target')) {
            if (this.isPhysicsEnvironment) {
              this.formData.target_nodes = collect.target_nodes;
            } else {
              Object.assign(collectConfig, this.initContainerFormData(collect, 'collect'));
            }
          }
        }
        // 切换不同环境时需要的初始化的内容
        if (this.isPhysicsEnvironment) {
          // IP 选择器预览结果回填
          collectConfig.configs = [this.configBaseObj];
        } else {
          Object.assign(collectConfig, {
            target_object_type: 'HOST',
            target_node_type: 'TOPO',
            target_nodes: [],
            target: [],
          });
        }
        Object.assign(this.formData, collectConfig, baseMessage);
        this.$nextTick(() => {
          this.configChangeLength += 1;
        });
      },
      initFromData(curCollect) {
        if (curCollect.environment === 'container') {
          this.isYaml = curCollect.yaml_config_enabled;
          // yaml模式可能会有多种容器环境 选择第一项配置里的环境作为展示
          if (curCollect.configs[0]) {
            // 如果采集项不为空 则回显
            this.currentEnvironment = curCollect.configs[0].collector_type;
            this.publicLetterIndex = curCollect.configs.length - 1;
          } else {
            // 为空 重新赋值 标准输出
            this.currentEnvironment = 'std_log_config';
            this.publicLetterIndex = 0;
            curCollect.configs = [this.configBaseObj];
          }
        } else {
          // 物理环境
          this.currentEnvironment = curCollect.environment;
          this.formData = this.getInitFormData(curCollect);
          Object.assign(this.formData, curCollect);
          if (this.formData.target_nodes?.length) {
            // IP 选择器预览结果回填
            this.ipSelectorOriginalValue = this.getSelectorNodes();
          }
          if (!this.formData.collector_config_name_en) {
            // 兼容旧数据数据名称为空
            this.formData.collector_config_name_en = this.formData.table_id || '';
          }
        }
      },
    },
  };
</script>

<style lang="scss">
  @import '@/scss/mixins/flex.scss';

  /* stylelint-disable no-descending-specificity */
  .add-collection-container {
    min-width: 950px;
    max-height: 100%;
    padding: 0 42px 42px;
    overflow: auto;

    .en-bk-form {
      width: 710px;

      .en-name-box {
        align-items: center;

        @include flex-justify(space-between);
      }

      .text-error {
        position: absolute;
        top: 6px;
        left: 12px;
        display: inline-block;
        font-size: 12px;
        color: transparent;

        /* stylelint-disable-next-line declaration-no-important */
        text-decoration: red wavy underline !important;
        pointer-events: none;
      }
    }

    .bk-form-content {
      line-height: 20px;
    }

    .king-alert {
      margin: 24px 0 -18px;

      .link {
        color: #3a84ff;
        cursor: pointer;
      }
    }

    .add-collection-title {
      width: 100%;
      padding-top: 36px;
      padding-bottom: 10px;
      margin-bottom: 20px;
      font-size: 14px;
      font-weight: 600;
      color: #63656e;
      border-bottom: 1px solid #dcdee5;
    }

    .add-collection-import {
      padding: 12px 24px;
      font-size: 16px;

      span {
        padding: 12px;
        font-weight: 800;
        color: #3a84ff;
        cursor: pointer;
      }
    }

    .original-title {
      @include flex-justify(flex-start);

      > div {
        margin-left: 40px;
        font-weight: 500;
      }
    }

    .tips,
    .en-name-tips {
      padding-top: 4px;
      font-size: 12px;
      color: #aeb0b7;
    }

    .en-name-tips {
      margin-top: 8px;
      margin-left: 0;
      line-height: 12px;
    }

    .hight-setting {
      width: 100%;
      min-height: 60px;

      .icons-downs {
        display: inline-block;
        width: 9px;
        height: 5px;
        margin-top: -3px;
        margin-right: 6px;
        vertical-align: middle;
        background: url('../../images/icons/triangle.png');
        background-size: 100% 100%;
      }

      .icon-left {
        transform: rotate(-90deg);
      }

      .log-paths {
        .bk-form-control {
          width: 460px;
        }
      }
    }

    .bk-label {
      color: #90929a;
    }

    .w520 {
      &.bk-form-control {
        width: 520px;
      }

      &.bk-select {
        width: 520px;
      }
    }

    .multiline-log-container {
      margin-top: 4px;

      .row-container {
        display: flex;
        align-items: center;

        &.second {
          // padding-left: 115px;
          margin-top: 10px;
          font-size: 12px;
          color: #63656e;

          .bk-form-item {
            /* stylelint-disable-next-line declaration-no-important */
            margin: 0 !important;

            .bk-form-content {
              /* stylelint-disable-next-line declaration-no-important */
              margin: 0 !important;

              .bk-form-control {
                width: 64px;
                margin: 0 6px;
              }
            }
          }
        }

        .king-button {
          margin-bottom: 4px;
        }
      }
    }

    .form-div {
      display: flex;

      .form-inline-div {
        .bk-form-content {
          display: flex;
        }
      }

      .prefix {
        margin-right: 8px;
        font-size: 14px;
        line-height: 32px;
        color: #858790;
      }

      .count {
        margin-left: 8px;
        font-size: 12px;
        line-height: 32px;
        color: #7a7c85;
      }

      .font-blue {
        font-weight: bold;
        color: #4e99ff;
      }

      .font-gray {
        color: #858790;
      }

      .icons {
        font-size: 21px;
        line-height: 32px;
        color: #c4c6cb;
        vertical-align: middle;
        cursor: pointer;
      }

      .disable {
        color: #dcdee5;
        cursor: not-allowed;
      }

      .item-target {
        &.is-error .bk-form-content {
          padding-right: 30px;
        }
      }
    }

    .win-filter {
      margin-top: 8px;

      .select-div {
        width: 129px;
        margin-right: 8px;
      }

      .tag-input {
        width: 320px;
      }
    }

    .log-type {
      height: 32px;
      border-radius: 2px;

      .bk-button {
        min-width: 106px;
        font-size: 12px;

        span {
          padding: 0 1px;
        }
      }

      .disable {
        color: #dcdee5;
        cursor: not-allowed;
        border-color: #dcdee5;
      }
    }

    .species-item {
      margin-bottom: -30px;

      .bk-form-checkbox {
        display: flex;
        align-items: center;
        width: 320px;
        height: 30px;
      }

      .bk-tag-selector {
        width: 320px;
        transform: translate3d(66px, -30px, 0);
      }
    }

    .ml {
      margin-left: -115px;
    }

    .mt {
      margin-top: 20px;
    }

    .ml9 {
      margin-left: 8px;
    }

    .ml10 {
      margin-left: 10px;
    }

    .ml115 {
      margin-left: 115px;
    }

    .mt8 {
      margin-top: 8px;
    }

    .is-selected {
      /* stylelint-disable-next-line declaration-no-important */
      z-index: 2 !important;
    }

    .rulesColor {
      /* stylelint-disable-next-line declaration-no-important */
      border-color: #ff5656 !important;
    }

    .tagRulesColor {
      .bk-tag-input {
        /* stylelint-disable-next-line declaration-no-important */
        border-color: #ff5656 !important;
      }
    }

    .win-content {
      position: relative;
      left: 118px;
      width: 76%;
      padding-bottom: 20px;

      > span {
        position: absolute;
        top: 6px;
        left: -76px;
        font-size: 12px;
        color: #90929a;
      }

      &.en-span span {
        left: -112px;
      }

      .filter-select {
        margin-top: 11px;
      }

      .bk-select {
        width: 184px;
        height: 32px;
        margin: 0 8px 12px 0;
      }
    }

    .icon-close-circle {
      display: inline-block;
      font-size: 14px;
      transform: rotateZ(45deg);
    }

    .environment-box {
      display: flex;
      align-items: center;
      margin-bottom: 30px;

      .environment-container {
        height: 68px;
        margin-right: 8px;

        .environment-category {
          display: inline-block;
          margin: 6px 0;
          font-size: 12px;
          font-weight: 400;
          color: #63656e;
        }

        .button-box {
          display: flex;

          .environment-button {
            display: flex;
            align-items: center;
            width: 120px;
            height: 40px;
            margin-right: 16px;
            font-size: 12px;
            color: #313238;
            cursor: pointer;
            user-select: none;
            border: 1px solid #dcdee5;
            border-radius: 2px;

            img {
              padding: 0 8px 0 4px;
            }

            &.disable {
              cursor: no-drop;
              background: #fafbfd;
            }

            &.active {
              background: #e1ecff;
              border: 1px solid #3a84ff;
            }
          }
        }

        &:not(:first-child) {
          position: relative;
          margin-left: 24px;

          &::before {
            position: absolute;
            top: 36px;
            left: -24px;
            width: 1px;
            height: 32px;
            content: ' ';
            background-color: #dcdee5;
          }
        }
      }
    }

    .cluster-select-box {
      margin-top: 20px;

      .bk-select {
        width: 382px;
      }

      .tips {
        font-size: 12px;
        color: #979ba5;
      }
    }

    .add-config-item {
      justify-content: center;
      width: 730px;
      height: 42px;
      margin: 0 0 14px 115px;
      font-size: 12px;
      cursor: pointer;
      background: #fafbfd;
      border: 1px dashed #dcdee5;

      @include flex-align();

      > div {
        color: #63656e;

        @include flex-center;
      }

      .icon-plus {
        font-size: 22px;
        color: #989ca7;
      }
    }

    .extra-error {
      .bk-form-input {
        border-color: #ff5656;
      }
    }

    .add-log-label {
      display: flex;
      align-items: center;

      &:not(:first-child) {
        margin-top: 20px;
      }

      span {
        margin: 0 7px;
        color: #ff9c01;
      }

      .bk-form-control {
        width: 240px;
      }
    }

    .page-operate {
      margin-top: 36px;
    }

    .justify-bt {
      align-items: center;

      @include flex-justify(space-between);
    }

    .flex-ac {
      @include flex-align();
    }
  }
</style>
