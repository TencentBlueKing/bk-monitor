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
  <div>
    <div
      v-for="(conItem, conIndex) of formData.configs"
      v-en-style="'width: 900px;'"
      class="config-box"
      v-bkloading="{ isLoading: nameSpaceRequest, zIndex: 10 }"
      :key="conIndex"
    >
      <div class="config-title">
        <span>{{ getFromCharCode(conItem.noQuestParams.letterIndex) }}</span>
        <span
          v-if="formData.configs.length > 1"
          class="bk-icon icon-delete"
          @click="handleDeleteConfig(conIndex, conItem.noQuestParams.letterIndex)"
        ></span>
      </div>

      <div class="config-container">
        <div class="config-cluster-box">
          <bk-alert
            v-if="isShowContainerTips(conItem)"
            :show-icon="false"
            type="info"
          >
            <template #title>
              <div>
                <i class="bk-icon icon-info"></i>
                <span>
                  {{ $t('采集范围排除能力依赖采集器 bk-log-collector >= 0.3.2，请保证采集器已升级到最新版本') }}
                </span>
              </div>
            </template>
          </bk-alert>
          <div class="config-cluster-title justify-bt">
            <div>
              <span class="title">{{ $t('选择{n}范围', { n: isNode ? 'Node' : 'Container' }) }}</span>
              <span>
                <span class="bk-icon icon-info-circle"></span>
                <span>{{ $t('所有选择范围可相互叠加并作用') }}</span>
              </span>
            </div>
            <div
              v-bk-tooltips.top="{ content: $t('请先选择集群'), delay: 500 }"
              :class="['preview', !formData.bcs_cluster_id && 'disable']"
              :disabled="!!formData.bcs_cluster_id"
              @click="handelShowDialog(conIndex, 'view')"
            >
              <span class="bk-icon icon-eye"></span>
              <span>{{ $t('预览') }}</span>
            </div>
          </div>
          <div
            v-if="isShowScopeItem(conIndex, 'namespace')"
            class="config-item hover-light"
          >
            <div class="config-item-title flex-ac">
              <span>{{ $t('按命名空间选择') }}</span>
              <span
                class="bk-icon icon-delete"
                @click="handleDeleteConfigParamsItem(conIndex, 'namespace')"
              >
              </span>
            </div>
            <div
              class="operator-box"
              v-bk-tooltips.top="{ content: $t('请先选择集群'), delay: 500 }"
              :disabled="!!formData.bcs_cluster_id"
            >
              <bk-select
                class="operate-select"
                v-model="conItem.noQuestParams.namespacesExclude"
                :clearable="false"
                :disabled="isNode || !formData.bcs_cluster_id || nameSpaceRequest"
                :popover-width="100"
                placeholder=" "
              >
                <bk-option
                  v-for="oItem in operatorSelectList"
                  :id="oItem.id"
                  :key="oItem.id"
                  :name="oItem.name"
                ></bk-option>
              </bk-select>
              <bk-select
                v-model="conItem.namespaces"
                :disabled="isNode || !formData.bcs_cluster_id || nameSpaceRequest"
                display-tag
                multiple
                searchable
                @selected="option => handleNameSpaceSelect(option, conIndex)"
              >
                <bk-option
                  v-for="oItem in showNameSpacesSelectList(conIndex)"
                  :id="oItem.id"
                  :key="oItem.id"
                  :name="oItem.name"
                ></bk-option>
              </bk-select>
            </div>
          </div>
          <template v-if="isShowScopeItem(conIndex, 'label')">
            <ConfigLogSetEditItem
              :edit-type="'label'"
              :config="conItem"
              :is-node="isNode"
              @config-change="v => handleConfigChange(conIndex, v)"
              @show-dialog="handelShowDialog(conIndex, 'label')"
              @delete-config-params-item="type => handleDeleteConfigParamsItem(conIndex, type)"
            />
          </template>
          <template v-if="isShowScopeItem(conIndex, 'annotation')">
            <ConfigLogSetEditItem
              :edit-type="'annotation'"
              :config="conItem"
              :is-node="isNode"
              @config-change="v => handleConfigChange(conIndex, v)"
              @delete-config-params-item="type => handleDeleteConfigParamsItem(conIndex, type)"
            />
          </template>
          <div
            v-if="isShowScopeItem(conIndex, 'load')"
            class="config-item hover-light"
          >
            <div class="config-item-title flex-ac">
              <span>{{ $t('按工作负载选择') }}</span>
              <span
                class="bk-icon icon-delete"
                @click="handleDeleteConfigParamsItem(conIndex, 'load')"
              >
              </span>
            </div>
            <container-target-item
              :bcs-cluster-id="formData.bcs_cluster_id"
              :con-item="conItem"
              :container.sync="conItem.container"
              :type-list="typeList"
            />
          </div>

          <div
            v-if="isShowScopeItem(conIndex, 'containerName')"
            class="config-item hover-light"
          >
            <div class="config-item-title flex-ac">
              <span>{{ $t('直接指定{n}', { n: 'Container' }) }}</span>
              <span
                class="bk-icon icon-delete"
                @click="handleDeleteConfigParamsItem(conIndex, 'containerName')"
              >
              </span>
            </div>
            <div class="operator-box">
              <bk-select
                class="operate-select"
                v-model="conItem.noQuestParams.containerExclude"
                :clearable="false"
                :popover-width="100"
                placeholder=" "
              >
                <bk-option
                  v-for="oItem in operatorSelectList"
                  :id="oItem.id"
                  :key="oItem.id"
                  :name="oItem.name"
                ></bk-option>
              </bk-select>
              <bk-tag-input
                ext-cls="container-input"
                v-model="conItem.containerNameList"
                allow-create
                free-paste
                has-delete-icon
                @blur="(inputStr, list) => handleContainerNameBlur(inputStr, list, conIndex)"
              >
              </bk-tag-input>
            </div>
          </div>

          <bk-dropdown-menu
            v-if="isShowAddScopeButton(conIndex)"
            style="margin-left: 12px"
            :disabled="!formData.bcs_cluster_id"
          >
            <template #dropdown-trigger>
              <div>
                <div
                  v-bk-tooltips.top="{ content: $t('请先选择集群'), delay: 500 }"
                  :disabled="!!formData.bcs_cluster_id"
                >
                  <bk-button
                    :disabled="!formData.bcs_cluster_id"
                    icon="plus"
                    size="small"
                    theme="primary"
                    outline
                  >
                    {{ $t('添加范围') }}
                  </bk-button>
                </div>
              </div>
            </template>
            <template #dropdown-content>
              <ul class="bk-dropdown-list">
                <li
                  v-for="(isShowScope, scopeStr) in conItem.noQuestParams.scopeSelectShow"
                  v-show="isShowScopeButton(conIndex, scopeStr)"
                  :key="`${scopeStr}`"
                  @click="handleAddNewScope(conIndex, scopeStr)"
                >
                  <a href="javascript:;">{{ getScopeName(scopeStr) }}</a>
                </li>
              </ul>
            </template>
          </bk-dropdown-menu>
        </div>

        <div
          class="hight-setting"
          data-test-id="acquisitionConfig_div_contentFiltering"
        >
          <!-- 容器环境 配置项 -->
          <config-log-set-item
            ref="containerConfigRef"
            :config-data="conItem"
            :config-length="formData.configs.length"
            :config-change-length="configChangeLength"
            :current-environment="currentEnvironment"
            :is-clone-or-update="isCloneOrUpdate"
            :scenario-id="formData.collector_scenario_id"
            show-type="vertical"
            @config-change="val => handelFormChange(val, 'containerConfig', conIndex)"
          >
          </config-log-set-item>
        </div>
      </div>
    </div>
    <config-view-dialog
      :is-node="isNode"
      :is-show-dialog.sync="isShowViewDialog"
      :view-query-params="viewQueryParams"
    />
    <label-target-dialog
      :cluster-list="clusterList"
      :is-show-dialog.sync="isShowLabelTargetDialog"
      :label-params="currentSelector"
      @config-label-change="val => handelFormChange(val, 'dialogChange')"
    />
  </div>
</template>
<script>
  import containerTargetItem from './container-target-item';
  import configLogSetItem from './config-log-set-item';
  import labelTargetDialog from './label-target-dialog';
  import configViewDialog from './config-view-dialog';
  import ConfigLogSetEditItem from './config-log-set-edit-item';
  import { mapGetters } from 'vuex';

  export default {
    components: {
      containerTargetItem,
      configLogSetItem,
      labelTargetDialog,
      configViewDialog,
      ConfigLogSetEditItem,
    },
    props: {
      formData: {
        type: Object,
        required: true,
      },
      isNode: {
        type: Boolean,
        required: true,
      },
      configChangeLength: {
        type: Number,
        required: true,
      },
      currentEnvironment: {
        type: String,
        required: true,
      },
      isCloneOrUpdate: {
        type: Boolean,
        required: true,
      },
      clusterList: {
        type: Array,
        required: true,
      },
      isPhysicsEnvironment: {
        type: Boolean,
        required: true,
      },
      isUpdate: {
        type: Boolean,
        required: true,
      },
    },
    data() {
      return {
        nameSpaceRequest: false, // 是否正在请求namespace接口
        operatorSelectList: [
          {
            id: '=',
            name: '=',
          },
          {
            id: '!=',
            name: '!=',
          },
        ],
        isShowViewDialog: false, // 是否展预览dialog
        isShowLabelTargetDialog: false, // 是否展示指定标签dialog
        nameSpacesSelectList: [], // namespace 列表
        scopeNameList: {
          namespace: this.$t('按命名空间选择'),
          label: this.$t('按标签选择'),
          annotation: this.$t('按annotation选择'),
          load: this.$t('按工作负载选择'),
          containerName: this.$t('直接指定{n}', { n: 'Container' }),
        },
        viewQueryParams: {}, // 预览弹窗传参
        currentSelector: {}, // 当前操作的配置项指定标签值
        currentSetIndex: 0, // 当前操作的配置项的下标
        typeList: [],
      };
    },
    computed: {
      ...mapGetters({
        bkBizId: 'bkBizId',
      }),
    },
    mounted() {
      // 容器环境
      this.getNameSpaceList(this.formData.bcs_cluster_id);
      !this.typeList.length && this.getWorkLoadTypeList();
    },
    methods: {
      isShowContainerTips(configItem) {
        const { containerExclude, namespacesExclude } = configItem.noQuestParams;
        return [containerExclude, namespacesExclude].includes('!=');
      },
      getFromCharCode(index) {
        return String.fromCharCode(index + 65);
      },
      getNameSpaceList(clusterID, isFirstUpdateSelect = false) {
        if (!clusterID || (this.isPhysicsEnvironment && this.isUpdate) || this.nameSpaceRequest) return;
        const query = { bcs_cluster_id: clusterID, bk_biz_id: this.bkBizId };
        this.nameSpaceRequest = true;
        this.$http
          .request('container/getNameSpace', { query })
          .then(res => {
            // 判断是否是第一次切换集群 如果是 则进行详情页namespace数据回显
            if (isFirstUpdateSelect) {
              const namespaceList = [];
              this.formData.configs.forEach(configItem => {
                namespaceList.push(...configItem.namespaces);
              });
              const resIDList = res.data.map(item => item.id);
              const setList = new Set([...namespaceList, ...resIDList]);
              setList.delete('*');
              const allList = [...setList].map(item => ({ id: item, name: item }));
              this.nameSpacesSelectList = [...allList];
              if (!this.getIsSharedCluster()) {
                this.nameSpacesSelectList.unshift({ name: this.$t('所有'), id: '*' });
              }
              return;
            }
            this.nameSpacesSelectList = [...res.data];
            if (!this.getIsSharedCluster()) {
              this.nameSpacesSelectList.unshift({ name: this.$t('所有'), id: '*' });
            }
          })
          .catch(err => {
            console.warn(err);
          })
          .finally(() => {
            this.nameSpaceRequest = false;
          });
      },
      /**
       * @desc: 配置项点击所有容器
       * @param { Number } index 下标
       * @param { Boolean } state 状态
       */
      getWorkLoadTypeList() {
        this.$http
          .request('container/getWorkLoadType')
          .then(res => {
            if (res.code === 0) this.typeList = res.data.map(item => ({ id: item, name: item }));
          })
          .catch(err => {
            console.warn(err);
          });
      },
      // 当前所选集群是否共享集群
      getIsSharedCluster() {
        return this.clusterList?.find(cluster => cluster.id === this.formData.bcs_cluster_id)?.is_shared ?? false;
      },
      handleDeleteConfig(index, letterIndex) {
        // 删除配置项
        this.$bkInfo({
          subTitle: this.$t('确定要删除配置项{n}？', { n: this.getFromCharCode(letterIndex) }),
          type: 'warning',
          confirmFn: () => {
            this.formData.configs.splice(index, 1);
          },
        });
      },
      // 点击删除icon 隐藏对应范围模块 初始化对应的值
      handleDeleteConfigParamsItem(conIndex, scope) {
        const config = this.formData.configs[conIndex];
        switch (scope) {
          case 'namespace':
            config.namespaces = [];
            break;
          case 'load':
            config.container.workload_type = '';
            config.container.workload_name = '';
            break;
          case 'label':
            config.labelSelector = [];
            break;
          case 'annotation':
            config.annotationSelector = [];
            break;
          case 'containerName':
            config.containerNameList = [];
            break;
          default:
            break;
        }
        if (scope === 'label' && this.isNode) return;
        this.getScopeSelectShow(conIndex)[scope] = true;
      },
      handleConfigChange(index, val) {
        Object.assign(this.formData.configs[index], val);
      },
      // 点击添加范围的列表 显示对应模块
      handleAddNewScope(conIndex, scope) {
        this.getScopeSelectShow(conIndex)[scope] = false;
      },
      // 是否显示对应模块的列表的按钮
      isShowScopeButton(conIndex, scope) {
        // 当前环境为node时， 除了label列表全部不显示
        return this.getScopeSelectShow(conIndex)[scope];
      },
      getScopeName(conItem) {
        return this.scopeNameList[conItem];
      },
      /**
       * @desc: 指定操作弹窗
       * @param { Number } index 下标
       * @param { String } dialogType 标签或预览
       */
      handelShowDialog(index, dialogType = 'label') {
        if (!this.formData.bcs_cluster_id) return;
        this.currentSetIndex = index;
        const type = this.isNode ? 'node' : 'pod';
        const config = this.formData.configs[index];
        const containerKey =
          config.noQuestParams.containerExclude === '!=' ? 'container_name_exclude' : 'container_name';
        const namespacesKey = config.noQuestParams.namespacesExclude === '!=' ? 'namespaces_exclude' : 'namespaces';
        if (dialogType === 'label') {
          this.currentSelector = {
            bk_biz_id: this.bkBizId,
            bcs_cluster_id: this.formData.bcs_cluster_id,
            type,
            namespaceStr: config.noQuestParams.namespaceStr,
            labelSelector: config.labelSelector,
          };
        } else if (dialogType === 'view') {
          const { workload_type: workloadType, workload_name: workloadName } = config.container;
          const namespaces = config.namespaces.length === 1 && config.namespaces[0] === '*' ? [] : config.namespaces;
          this.viewQueryParams = {
            bk_biz_id: this.bkBizId,
            bcs_cluster_id: this.formData.bcs_cluster_id,
            type,
            [namespacesKey]: namespaces,
            label_selector: this.getLabelSelectorQueryParams(config.labelSelector, {
              match_labels: [],
              match_expressions: [],
            }),
            annotation_selector: this.getLabelSelectorQueryParams(config.annotationSelector, {
              match_annotations: [],
            }),
            container: {
              workload_type: workloadType,
              workload_name: workloadName,
              [containerKey]: config.containerNameList.join(','),
            },
          };
        }
        dialogType === 'label' ? (this.isShowLabelTargetDialog = true) : (this.isShowViewDialog = true);
      },
      /**
       * @desc: 展示用的标签格式转化成存储或传参的标签格式
       * @param {Object} labelSelector 主页展示用的label_selector
       * @returns {Object} 返回传参用的label_selector
       */
      getLabelSelectorQueryParams(labelSelector, preParams) {
        return labelSelector.reduce((pre, cur) => {
          const value = ['NotIn', 'In'].includes(cur.operator) ? `(${cur.value})` : cur.value;
          pre[cur.type].push({
            key: cur.key,
            operator: cur.operator,
            value,
          });
          return pre;
        }, preParams);
      },
      // 是否展示对应操作范围模块
      isShowScopeItem(conIndex, scope) {
        if (this.isNode) return ['label', 'annotation'].includes(scope); // 当前环境为node时 若是标签模块则直接显示 其余均不显示
        return !this.getScopeSelectShow(conIndex)[scope];
      },
      // 获取config里添加范围的列表
      getScopeSelectShow(conIndex) {
        return this.formData.configs[conIndex].noQuestParams.scopeSelectShow;
      },
      handleNameSpaceSelect(option, index) {
        const config = this.formData.configs[index];
        if (option[option.length - 1] === '*') {
          // 如果最后一步选择所有，则清空数组填所有
          const nameSpacesLength = config.namespaces.length;
          config.namespaces.splice(0, nameSpacesLength, '*');
          config.noQuestParams.namespaceStr = this.getNameSpaceStr(config.namespaces);
          return;
        }
        if (option.length > 1 && option.includes('*')) {
          // 如果选中其他的值 包含所有则去掉所有选项
          const allIndex = option.findIndex(item => item === '*');
          config.namespaces.splice(allIndex, 1);
        }
        config.noQuestParams.namespaceStr = this.getNameSpaceStr(config.namespaces);
      },
      getNameSpaceStr(namespaces) {
        return namespaces.length === 1 && namespaces[0] === '*' ? '' : namespaces.join(',');
      },
      showNameSpacesSelectList(conIndex) {
        const config = this.formData.configs[conIndex];
        const operate = config.noQuestParams.namespacesExclude;
        if (!this.nameSpacesSelectList.length) return [];
        if (operate === '!=' && this.nameSpacesSelectList.some(item => item.id === '*')) {
          if (config.namespaces.length === 1 && config.namespaces[0] === '*') config.namespaces = [];
          return this.nameSpacesSelectList.slice(1);
        }
        return this.nameSpacesSelectList;
      },
      handleContainerNameBlur(input, list, conIndex) {
        if (!input) return;
        const config = this.formData.configs[conIndex];
        config.containerNameList = !list.length ? [input] : [...new Set([...config.containerNameList, input])];
      },
      // 是否展示添加范围的按钮
      isShowAddScopeButton(conIndex) {
        // 当前为node环境时 隐藏按钮直接显示操作范围模块
        if (this.isNode) return false;
        return Object.values(this.getScopeSelectShow(conIndex)).some(Boolean);
      },
      /**
       * @desc: 用户操作合并form数据
       * @param { Object } val 操作后返回值对象
       * @param { String } operator 配置项还是form本身
       * @param { Number } index 配置项下标
       */
      handelFormChange(val, operator, index) {
        const setIndex = index ? index : this.currentSetIndex;
        const setTime = operator === 'dialogChange' ? 10 : 500;
        clearTimeout(this.formTime);
        this.formTime = setTimeout(() => {
          switch (operator) {
            case 'dialogChange':
            case 'containerConfig':
              Object.assign(this.formData.configs[setIndex], val);
              break;
          }
        }, setTime);
      },
    },
  };
</script>
<style lang="scss" scoped>
  @import '@/scss/mixins/flex.scss';

  .config-box {
    width: 730px;
    margin-bottom: 20px;
    font-size: 14px;
    background: #fff;
    border: 1px solid #dcdee5;
    border-radius: 2px;

    .config-title {
      display: flex;
      align-items: center;
      justify-content: space-between;
      height: 31px;
      padding: 0 16px;
      background: #f0f1f5;
      border-radius: 1px 1px 0 0;

      .icon-delete {
        font-size: 16px;
        color: #ea3636;
        cursor: pointer;
      }
    }

    .config-container {
      padding: 16px 24px;
      color: #63656e;
      background: #fafbfd;

      .config-cluster-box {
        padding: 8px 12px 16px;
        font-size: 12px;
        background: #fff;
        border: 1px solid #eaebf0;
        border-radius: 2px;

        .config-cluster-title {
          padding: 8px 12px;

          .title {
            margin-right: 14px;
            font-weight: 700;
          }

          .bk-icon {
            font-size: 14px;
          }

          .disable {
            /* stylelint-disable-next-line declaration-no-important */
            color: #63656e !important;

            /* stylelint-disable-next-line declaration-no-important */
            cursor: no-drop !important;
          }

          .preview {
            color: #3a84ff;
            cursor: pointer;
          }
        }
      }

      .tips-btn {
        color: #3a84ff;
        cursor: pointer;
      }

      .config-item-title {
        padding-bottom: 8px;

        :last-child {
          margin-left: 8px;
          cursor: pointer;
        }

        .icon-delete {
          display: none;
          font-size: 14px;
          color: #ea3636;
          cursor: pointer;
        }
      }

      .operator-box {
        width: 100%;

        @include flex-center();

        > :nth-child(2) {
          position: relative;
          left: -1px;
          flex: 1;
          border-radius: 0 2px 2px 0;
        }

        .operate-select {
          width: 30px;
          border-radius: 2px 0 0 2px;

          :deep(.bk-select-angle) {
            display: none;
          }
        }

        .is-focus {
          position: relative;
          z-index: 999;
        }
      }

      .config-item {
        padding: 8px 12px;
        margin-bottom: 12px;
        font-size: 12px;
        border-radius: 2px;

        .select-label {
          margin-top: 4px;
          color: #3a84ff;

          .manually {
            margin-right: 15px;
            cursor: pointer;
          }

          .select {
            position: relative;
            margin-left: 15px;
            cursor: pointer;

            &::before {
              position: absolute;
              top: 4px;
              left: -14px;
              display: inline-block;
              width: 1px;
              height: 14px;
              content: ' ';
              background: #eaebf0;
            }
          }
        }

        &.hover-light:hover {
          background: #f5f7fa;
        }

        &:hover .icon-delete {
          display: inline-block;
        }
      }

      .container-input {
        .input {
          max-width: none;
        }

        .bk-tag-input {
          border-radius: 0 2px 2px 0;
        }
      }

      .container-btn-container {
        position: relative;
        align-items: center;

        .span-box {
          margin-right: 24px;

          &:not(:first-child) {
            position: relative;
            margin-right: 0;

            &::before {
              position: absolute;
              top: 3px;
              left: -11px;
              width: 1px;
              height: 16px;
              content: ' ';
              background-color: #dcdee5;
            }
          }
        }

        .container-btn {
          color: #3a84ff;
          cursor: pointer;

          &.disable {
            color: #c4c6cc;
            cursor: not-allowed;
          }

          &.cluster-not-select {
            cursor: not-allowed;
          }
        }
      }

      .filter-content {
        margin-top: 24px;
        color: #979ba5;

        > span {
          margin-bottom: 0;
          color: #63656e;
        }
      }

      .bk-select {
        background: #fff;
      }

      .filter-select {
        margin-top: 11px;

        .bk-select {
          width: 184px;
          height: 32px;
        }
      }

      .bk-label {
        color: #63656e;
      }
    }
  }

  .conflict-container {
    width: 730px;
    height: 32px;
    padding: 0 11px;
    margin: 12px 0 14px 115px;
    font-size: 12px;
    background: #fff4e2;
    border: 1px solid #ffdfac;
    border-radius: 2px;

    .icon-exclamation-circle {
      font-size: 16px;
      color: #ff9c01;
    }

    .conflict-message {
      margin: 0 16px 0 9px;
      color: #63656e;
    }

    .collection-item {
      margin-left: 24px;
      color: #3a84ff;
    }
  }
</style>
