/*
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
 */

import { computed, defineComponent, onMounted, ref, onBeforeMount } from 'vue';

import LogIpSelector, { toTransformNode, toSelectorNode } from '@/components/log-ip-selector/log-ip-selector'; // 日志IP选择器组件
import useLocale from '@/hooks/use-locale';
import useStore from '@/hooks/use-store';
import { useRoute } from 'vue-router/composables';

import { useCollectList } from '../../hook/useCollectList'; // 收集列表相关功能
import { useOperation } from '../../hook/useOperation'; // 操作相关功能
import {
  showMessage,
  TARGET_TYPES,
  collectTargetTarget,
  LOG_SPECIES_LIST,
  LOG_TYPE_LIST,
  COLLECT_METHOD_LIST,
  getLabelSelectorArray,
  getContainerNameList,
} from '../../utils'; // 工具函数

import BaseInfo from '../business-comp/step2/base-info';

import type { IFormData, IValueItem, IContainerConfigItem } from '../../type'; // 基础信息组件
import DeviceMetadata from '../business-comp/step2/device-metadata'; // 设备元数据组件
import EventFilter from '../business-comp/step2/event-filter'; // 事件过滤器组件
import LogFilter from '../business-comp/step2/log-filter'; // 日志过滤器组件
import MultilineRegDialog from '../business-comp/step2/multiline-reg-dialog'; // 多行正则对话框组件
import InfoTips from '../common-comp/info-tips'; // 信息提示组件
import InputAddGroup from '../common-comp/input-add-group'; // 输入框组组件
import AppendLogTags from '../business-comp/step2/container-collection/append-log-tags'; // 附加日志标签组件
import ConfigurationItemList from '../business-comp/step2/container-collection/configuration-item-list'; // 配置项组件
import { HOST_COLLECTION_CONFIG, CONTAINER_COLLECTION_CONFIG } from './defaultConfig'; // 默认配置
import IndexConfigImportDialog from '../business-comp/step2/index-config-import-dialog';
import $http from '@/api'; // API请求封装

import './step2-configuration.scss'; // 样式文件

/**
 * 目标类型定义
 */
type TargetType = (typeof TARGET_TYPES)[keyof typeof TARGET_TYPES];

/**
 * 目标值类型定义
 */
type TargetValue = {
  host_list?: any[]; // 主机列表
  node_list?: any[]; // 节点列表
  service_template_list?: any[]; // 服务模板列表
  set_template_list?: any[]; // 集群模板列表
  dynamic_group_list?: any[]; // 动态分组列表
};

/**
 * 目标选择结果类型定义
 */
type TargetSelectionResult = {
  // 目标类型
  type: TargetType;
  nodes: any[];
};

export default defineComponent({
  name: 'StepConfiguration',
  props: {
    scenarioId: {
      type: String,
      default: '',
    },
    isEdit: {
      type: Boolean,
      default: false,
    },
    /**
     * 是否为clone模式
     */
    isClone: {
      type: Boolean,
      default: false,
    },
  },

  emits: ['next', 'prev', 'cancel'],

  setup(props, { emit }) {
    const { t } = useLocale();
    const store = useStore();
    const route = useRoute();
    const { bkBizId } = useCollectList();
    const { cardRender } = useOperation();
    const baseInfoRef = ref();
    const showMultilineRegDialog = ref(false);
    const isBlacklist = ref(false);
    const logType = ref('row');
    const showSelectDialog = ref(false);
    const selectorNodes = ref({ host_list: [] });
    const ipSelectorOriginalValue = ref(null);
    const collectorType = ref('container_log_config');
    const configurationItemListRef = ref();
    const loading = ref(false);
    const isIndexConfigImport = ref(false);
    /**
     * 是否修改了内容
     */
    const isConfigChange = ref(false);

    const baseConditions = {
      type: 'none',
      match_type: 'include',
      match_content: '',
      separator: '|',
      separator_filters: [{ fieldindex: '', word: '', op: '=', logic_op: 'and' }],
    };
    /**
     * 行首正则是否为空
     */
    const isSegmentError = ref(false);

    /**
     * 日志种类
     */
    const selectLogSpeciesList = ref(['Application', 'Security', 'System', 'Other']);
    const ipSelectorPanelList = [
      'staticTopo',
      'dynamicTopo',
      'dynamicGroup',
      'serviceTemplate',
      'setTemplate',
      'manualInput',
    ];

    const typeMap: { [key: string]: string } = {
      INSTANCE: 'host_list',
      TOPO: 'node_list',
      SERVICE_TEMPLATE: 'service_template_list',
      SET_TEMPLATE: 'set_template_list',
      DYNAMIC_GROUP: 'dynamic_group_list',
    };

    /**
     * 上报链路列表
     */
    const linkConfigurationList = ref([]);
    const linkListLoading = ref(false);
    const otherSpeciesList = ref([]);
    const loadingSave = ref(false);

    /**
     * 相关校验
     */
    /**
     * 选择目标是否为空
     */
    const isTargetNodesEmpty = ref(false);
    const pathRef = ref(); // 日志路径ref
    const excludeFilesRef = ref(); // 黑名单路径ref
    const logFilterRef = ref(); // 日志过滤器ref
    /**
     * 集群列表
     */
    const clusterList = ref([]);
    // 集群列表是否正在请求
    const isRequestCluster = ref(false);
    /**
     * 不展示日志路径的类型
     */
    const hideLogFilterKeys = ['winevent', 'container_stdout', 'container_file'];
    /**
     * 需要展示集群列表的类型
     */
    const showClusterListKeys = ['container_stdout', 'container_file'];

    const eventSettingList = ref([{ type: 'winlog_event_id', list: [], isCorrect: true }]);
    const isClone = computed(() => route.query.type === 'clone');
    // 获取全局数据
    const globalsData = computed(() => store.getters['globals/globalsData']);
    const environment = computed(() => {
      if (showClusterListKeys.includes(props.scenarioId)) {
        return 'container';
      }
      return props.scenarioId === 'winevent' ? 'windows' : 'linux';
    });
    // 是否是编辑或者克隆
    const isCloneOrUpdate = computed(() => props.isEdit || isClone.value);
    /**
     * 是否为编辑
     */
    const isUpdate = computed(() => route.name === 'collectEdit' && props.isEdit);
    /**
     * 是否为采集主机日志
     */
    const isHostLog = computed(() => props.scenarioId === 'linux');
    /**
     * 是否为段日志
     */
    const isSectionLog = computed(() => logType.value === 'section' && isHostLog.value);

    const currentIndexSetId = computed(() => route.query.indexSetId);

    /**
     * 通用配置
     */
    const baseFormData = computed(() => {
      return {
        target_node_type: 'INSTANCE',
        data_link_id: '',
        collector_config_name: '',
        collector_config_name_en: '',
        bk_biz_id: bkBizId.value,
        description: '',
        target_nodes: [],
        category_id: props.scenarioId,
        collector_scenario_id: 'row',
        environment: environment.value,
        target_object_type: 'HOST',
        data_encoding: 'UTF-8',
        parent_index_set_ids: [],
        tail_files: true,
        params: {
          conditions: {
            type: 'none',
          },
        },
      };
    });
    const formData = ref<IFormData>({
      ...baseFormData.value,
    });

    /**
     * 根据类型初始化数据
     */
    const initFromData = () => {
      /**
       * windows events log 日志
       */
      if (props.scenarioId === 'winevent') {
        formData.value = {
          ...formData.value,
          collector_scenario_id: 'winevent',
          params: {
            ...formData.value.params,
            winlog_name: selectLogSpeciesList.value,
          },
        };
      }
      /**
       * 主机日志
       */
      if (isHostLog.value) {
        formData.value = {
          ...formData.value,
          ...HOST_COLLECTION_CONFIG,
        };
      }
      /**
       * 文件采集
       */
      if (props.scenarioId === 'container_file') {
        formData.value = {
          ...formData.value,
          ...CONTAINER_COLLECTION_CONFIG,
        };
      }
      /**
       * 标准输出
       */
      if (props.scenarioId === 'container_stdout') {
        formData.value = {
          ...formData.value,
          ...CONTAINER_COLLECTION_CONFIG,
        };
      }
      /**
       * 在新增的时候，如果列表选中了某个索引集，则进入页面默认选中该索引集
       */
      if (!isCloneOrUpdate.value && Number(currentIndexSetId.value)) {
        formData.value = {
          ...formData.value,
          parent_index_set_ids: [Number(currentIndexSetId.value)],
        };
      }
    };

    /**
     * @desc: 获取bcs集群列表
     */
    const getBcsClusterList = () => {
      if (isRequestCluster.value) {
        return;
      }
      isRequestCluster.value = true;
      const query = { bk_biz_id: bkBizId.value };
      $http
        .request('container/getBcsList', { query })
        .then(res => {
          if (res.code === 0) {
            clusterList.value = res.data;
            formData.value.bcs_cluster_id = clusterList.value[0]?.cluster_id || '';
          }
        })
        .catch(err => {
          console.log(err);
        })
        .finally(() => {
          isRequestCluster.value = false;
        });
    };
    /**
     * 获取链路列表
     */
    const getLinkData = async () => {
      try {
        linkListLoading.value = true;
        const res = await $http.request('linkConfiguration/getLinkList', {
          query: {
            bk_biz_id: bkBizId.value,
          },
        });
        linkConfigurationList.value = res.data.filter(item => item.is_active);
        if (linkConfigurationList.value.length && !isCloneOrUpdate.value) {
          formData.value.data_link_id = linkConfigurationList.value[0].data_link_id;
        }
      } catch (e) {
        console.log(e);
      } finally {
        linkListLoading.value = false;
      }
    };

    const handleBlacklist = () => {
      isBlacklist.value = !isBlacklist.value;
      formData.value.params.exclude_files = isBlacklist.value ? [''] : [];
    };

    /**
     * 修改日志类型
     * @param item
     */
    const handleLogType = (item: { value: string }) => {
      isConfigChange.value = true;
      logType.value = item.value;
      formData.value.collector_scenario_id = item.value;
    };
    /**
     * 修改日志路径
     */
    const handleUpdateUrl = (data: { value: string }[]) => {
      isConfigChange.value = true;
      formData.value.params.paths = data;
    };
    /**
     * 修改路径黑名单
     */
    const handleUpdateBlacklist = (data: { value: string }[] | string[]) => {
      isConfigChange.value = true;
      // 将对象数组转换为字符串数组，以匹配 exclude_files 的格式
      formData.value.params.exclude_files = data.map(item => (typeof item === 'string' ? item : item.value));
    };
    /**
     * 修改设备元数据
     * @param data
     */
    const handleMetadataList = (data: IValueItem[]) => {
      isConfigChange.value = true;
      formData.value.extra_labels = data;
    };
    /**
     * 显示行首正则调试弹窗
     */
    const handleDebugReg = () => {
      showMultilineRegDialog.value = true;
    };
    /**
     * 关闭行首正则调试弹窗
     */
    const handleCancelMultilineReg = (val: boolean) => {
      showMultilineRegDialog.value = val;
    };
    /**
     * 修改过滤内容
     * @param data
     */
    const handleFilterChange = data => {
      isConfigChange.value = true;
      eventSettingList.value = data;
      (data || []).map(item => {
        formData.value.params[item.type] = item.list;
      });
    };
    /**
     * 修改日志种类 - 其他 输入框内容
     * @param val
     */
    const handleLogTypeOther = (val: string[]) => {
      isConfigChange.value = true;
      otherSpeciesList.value = val;
      formData.value.params.winlog_name = [...selectLogSpeciesList.value, ...val];
    };

    onBeforeMount(() => {
      initFromData();
    });

    onMounted(() => {
      getLinkData();

      /**
     采集和标准输出的情况下，获取集群列表
       */
      if (showClusterListKeys.includes(props.scenarioId)) {
        getBcsClusterList();
      }
      /**
       * 编辑/克隆状态下去拉取详情接口
       */
      if (props.isEdit || props.isClone) {
        setDetail();
      }
    });
    /**
     * 将字符串数组转换为输入框组件的值格式
     * @param items - 字符串数组
     * @returns 转换后的值数组，如果为空则返回包含空字符串的数组
     */
    const transformStringArrayToInputValue = (items?: string[]): Array<{ value: string }> => {
      return items?.map(item => ({ value: item })) || [{ value: '' }];
    };

    /**
     * 处理 Windows 事件日志的配置数据
     * @param params - 参数对象
     */
    const handleWindowsEventLogConfig = (params: any) => {
      const { paths, exclude_files, winlog_match_op, winlog_name, ...restParams } = params;

      // 构建事件设置列表，排除已处理的字段
      eventSettingList.value = Object.keys(restParams).map(key => ({
        type: key,
        list: restParams[key],
        isCorrect: true,
      }));

      // 过滤出自定义的日志种类（不在预定义列表中的）
      otherSpeciesList.value = winlog_name.filter(item => LOG_SPECIES_LIST.findIndex(i => i.id === item) === -1);

      // 如果没有自定义种类，从选择列表中移除 'Other' 选项
      if (otherSpeciesList.value.length === 0) {
        selectLogSpeciesList.value = selectLogSpeciesList.value.filter(item => item !== 'Other');
      }
    };

    /**
     * 处理容器采集的单个配置项
     * @param configItem - 配置项数据
     * @returns 处理后的配置项
     */
    const transformContainerConfigItem = (configItem: any) => {
      const {
        namespaces,
        container_name,
        match_expressions,
        match_labels,
        workload_name,
        workload_type,
        container_name_exclude,
        match_annotations,
        namespaces_exclude,
        params: itemParams,
      } = configItem;

      // 转换路径和排除文件格式
      const paths = transformStringArrayToInputValue(itemParams.paths);
      const excludeFiles = transformStringArrayToInputValue(itemParams.exclude_files);

      // 构建标签选择器和注解选择器
      const labelSelector = getLabelSelectorArray({
        match_expressions,
        match_labels,
      });
      const annotationSelector = getLabelSelectorArray({
        match_annotations: match_annotations || [],
      });

      // 确定容器和命名空间的排除操作符
      const containerExclude = container_name_exclude ? '!=' : '=';
      const namespacesExclude = namespaces_exclude?.length ? '!=' : '=';
      const containerNameList = getContainerNameList(container_name || container_name_exclude);

      // 处理命名空间字符串（如果是 '*' 则返回空字符串）
      const namespaceStr = namespaces.length === 1 && namespaces[0] === '*' ? '' : namespaces.join(',');

      // 构建范围选择显示配置
      const noQuestParams = {
        scopeSelectShow: {
          namespace: !namespaces.length,
          label: !labelSelector.length,
          load: !(Boolean(workload_type) || Boolean(workload_name)),
          containerName: !containerNameList.length,
          annotation: !annotationSelector.length,
        },
        namespaceStr,
        containerExclude,
        namespacesExclude,
      };

      return {
        ...configItem,
        noQuestParams,
        label_selector: {
          match_labels,
          match_expressions,
        },
        annotation_selector: {
          match_annotations,
        },
        container: {
          workload_type,
          workload_name,
          container_name,
        },
        params: {
          ...itemParams,
          paths,
          exclude_files: excludeFiles,
        },
      };
    };

    /**
     * 处理容器采集的配置列表
     * @param configs - 配置列表
     * @param collectorScenarioId - 采集场景ID
     */
    const handleContainerCollectionConfig = (configs: any[], collectorScenarioId: string) => {
      logType.value = collectorScenarioId;
      collectorType.value = configs[0]?.collector_type;

      // 转换所有配置项
      const transformedConfigs = (configs || []).map(transformContainerConfigItem);
      formData.value.configs = transformedConfigs;
    };

    /**
     * 初始化基础表单数据
     * @param detailData - 详情数据
     */
    const initializeBaseFormData = (detailData: IFormData) => {
      const { collector_config_name, params } = detailData;

      // 转换路径和排除文件格式
      const paths = transformStringArrayToInputValue(params.paths);
      const excludeFiles = transformStringArrayToInputValue(params.exclude_files);

      formData.value = {
        ...formData.value,
        ...detailData,
        params: {
          ...params,
          paths,
          exclude_files: excludeFiles,
        },
        index_set_name: collector_config_name,
      };
      /**
       * 克隆的时候数据处理
       */
      if (props.isClone) {
        const { collector_config_name } = formData.value;
        const cloneName = `${collector_config_name}_clone`;
        formData.value = {
          ...formData.value,
          collector_config_name: cloneName,
          index_set_name: cloneName,
          collector_config_name_en: '',
        };
      }
    };
    /**
     * 初始化回填采集目标
     * @param nodes
     * @param type
     */
    const initSelectorNodes = (nodes, type) => {
      const targetList = toSelectorNode(nodes, type);
      const result = {};
      Object.keys(typeMap).forEach((key: string) => {
        result[typeMap[key]] = type === key ? targetList : [];
      });
      selectorNodes.value = result;
    };

    const initConfig = (data: IFormData) => {
      const { configs, collector_scenario_id, params, target_node_type: type, target_nodes: nodes } = data;
      /**
       * 初始化采集目标
       */
      if (props.scenarioId === 'winevent' || props.scenarioId === 'linux') {
        initSelectorNodes(nodes, type);
      }

      // 根据场景类型处理特定配置
      if (props.scenarioId === 'winevent') {
        // Windows 事件日志特殊处理
        handleWindowsEventLogConfig(params);
      } else if (showClusterListKeys.includes(props.scenarioId)) {
        // 容器采集（文件采集和标准输出）特殊处理
        handleContainerCollectionConfig(configs, collector_scenario_id);
      }
    };

    /**
     * 编辑时初始化详情数据
     * 根据不同的场景类型处理相应的配置数据
     */
    const setDetail = async () => {
      loading.value = true;
      const collectorConfigId = props.isEdit ? route.params.collectorId : route.query.collectorId;
      try {
        const res = await $http.request('collect/details', {
          params: { collector_config_id: collectorConfigId },
        });

        if (!res.data) {
          return;
        }

        // 初始化基础表单数据
        initializeBaseFormData(res.data);
        initConfig(res.data);
        // 更新 store 中的当前采集配置
        store.commit('collect/setCurCollect', res.data);
        setTimeout(() => {
          isConfigChange.value = false;
        }, 2000);
      } catch (err) {
        console.log('获取采集配置详情失败:', err);
      } finally {
        loading.value = false;
      }
    };

    /**
     * 基本信息
     */
    const renderBaseInfo = () => (
      <BaseInfo
        ref={baseInfoRef}
        data={formData.value}
        isEdit={isUpdate.value}
        on-change={data => {
          const { index_set_name } = data;
          isConfigChange.value = true;
          formData.value = { ...formData.value, ...data, collector_config_name: index_set_name };
        }}
      />
    );
    /**
     * 行首正则
     */
    const renderSegment = data => (
      <div class='line-rule'>
        <div class='label-title text-left'>{t('行首正则')}</div>
        <div class='rule-reg'>
          <bk-input
            class={{
              'reg-input': true,
              'is-error': isSegmentError.value,
            }}
            value={data.multiline_pattern}
            on-input={val => {
              isConfigChange.value = true;
              data.multiline_pattern = val;
            }}
          />
          <span
            class='form-link debug'
            on-Click={handleDebugReg}
          >
            {t('调试')}
          </span>
        </div>
        <div class='line-rule-box'>
          <div class='line-rule-box-item'>
            <div class='label-title no-require text-left'>{t('最多匹配')}</div>
            <bk-input
              value={data.multiline_max_lines}
              on-input={val => {
                isConfigChange.value = true;
                data.multiline_max_lines = val;
              }}
            >
              <div
                class='group-text'
                slot='append'
              >
                {t('行')}
              </div>
            </bk-input>
          </div>
          <div class='line-rule-box-right'>
            <div class='label-title no-require text-left'>{t('最大耗时')}</div>
            <bk-input
              class='time-box'
              value={data.multiline_timeout}
              on-input={val => {
                isConfigChange.value = true;
                data.multiline_timeout = val;
              }}
            >
              <div
                class='group-text'
                slot='append'
              >
                {t('秒')}
              </div>
            </bk-input>
            <InfoTips tips={t('建议配置 1s, 配置过长时间可能会导致日志积压')} />
          </div>
        </div>
      </div>
    );
    /**
     * 日志过滤
     */
    const renderLogFilter = () => {
      // 确保 params 和 conditions 存在
      if (!formData.value.params) {
        formData.value.params = {
          conditions: baseConditions,
        };
      }
      if (!formData.value.params.conditions) {
        formData.value.params.conditions = baseConditions;
      }
      return (
        <LogFilter
          ref={logFilterRef}
          conditions={formData.value.params.conditions}
          isCloneOrUpdate={isCloneOrUpdate.value}
          on-conditions-change={val => {
            isConfigChange.value = true;
            formData.value.params.conditions = val;
          }}
        />
      );
    };
    /**
     * 设备元数据
     */
    const renderDeviceMetadata = () => (
      <DeviceMetadata
        metadata={formData.value.extra_labels}
        // metadata={formData.value.params.extra_labels}
        on-extra-labels-change={handleMetadataList}
      />
    );
    /**
     * 源日志信息
     */
    const renderSourceLogInfo = () => (
      <div class='source-log-info'>
        {props.scenarioId === 'container_file' && (
          <div class='label-form-box'>
            <span class='label-title'>{t('采集方式')}</span>
            {COLLECT_METHOD_LIST.map(item => (
              <span
                key={item.id}
                class={{
                  'collect-method-item': true,
                  active: collectorType.value === item.id,
                }}
                on-click={() => {
                  isConfigChange.value = true;
                  collectorType.value = item.id;
                  formData.value.configs?.map(config => {
                    config.collector_type = item.id;
                    config.noQuestParams.scopeSelectShow.namespace = false;
                    return config;
                  });
                }}
              >
                <i class={`bklog-icon bklog-${item.icon} method-item-icon`} />
                {item.name}
              </span>
            ))}
          </div>
        )}
        {showClusterListKeys.includes(props.scenarioId) && (
          <div class='label-form-box'>
            <span class='label-title'>{t('集群选择')}</span>
            <bk-select
              class='form-box'
              clearable={false}
              loading={linkListLoading.value}
              disabled={isUpdate.value}
              value={formData.value.bcs_cluster_id}
              on-selected={val => {
                isConfigChange.value = true;
                formData.value.bcs_cluster_id = val;
              }}
            >
              {clusterList.value.map(item => (
                <bk-option
                  id={item.id}
                  key={item.id}
                  name={`${item.name} (${item.id})`}
                />
              ))}
            </bk-select>
          </div>
        )}
        {props.scenarioId !== 'winevent' && (
          <div class='label-form-box'>
            <span class='label-title'>{t('日志类型')}</span>
            <div class='form-box'>
              <div class='bk-button-group'>
                {LOG_TYPE_LIST.map(item => (
                  <bk-button
                    key={item.value}
                    class={{ 'is-selected': logType.value === item.value }}
                    on-Click={() => handleLogType(item)}
                  >
                    {item.text}
                  </bk-button>
                ))}
              </div>
              {isSectionLog.value && renderSegment(formData.value.params)}
            </div>
          </div>
        )}
        {!showClusterListKeys.includes(props.scenarioId) && (
          <div class='label-form-box'>
            <span class='label-title'>{t('采集目标')}</span>
            <div class='form-box'>
              <bk-button
                class={{
                  'target-btn': true,
                  error: isTargetNodesEmpty.value,
                }}
                icon='plus'
                on-Click={() => {
                  showSelectDialog.value = true;
                }}
              >
                {t('选择目标')}
              </bk-button>
              {formData.value.target_nodes.length > 0 && (
                <span class='count-box'>
                  <i18n path={collectTargetTarget[formData.value.target_node_type]}>
                    <span class='font-blue'>{formData.value.target_nodes.length}</span>
                  </i18n>
                </span>
              )}
            </div>
          </div>
        )}
        {props.scenarioId === 'winevent' && (
          <div class='label-form-box'>
            <span class='label-title'>{t('日志种类')}</span>
            <div class='form-box'>
              <bk-checkbox-group
                class='log-type-box'
                value={selectLogSpeciesList.value}
                on-change={(val: string[]) => {
                  isConfigChange.value = true;
                  selectLogSpeciesList.value = val;
                  formData.value.params.winlog_name = val;
                }}
              >
                <div class='species-item'>
                  {LOG_SPECIES_LIST.map(item => (
                    <bk-checkbox
                      key={item.id}
                      class={{
                        other: item.id === 'Other',
                      }}
                      disabled={selectLogSpeciesList.value.length === 1 && selectLogSpeciesList.value[0] === item.id}
                      value={item.id}
                    >
                      {item.name}
                    </bk-checkbox>
                  ))}
                  <bk-tag-input
                    allow-auto-match={true}
                    allow-create={true}
                    has-delete-icon={true}
                    value={otherSpeciesList.value}
                    free-paste
                    on-change={handleLogTypeOther}
                  />
                </div>
              </bk-checkbox-group>
            </div>
          </div>
        )}
        {props.scenarioId === 'winevent' && (
          <div class='label-form-box'>
            <span
              class='label-title no-require'
              v-bk-tooltips={t('为减少传输和存储成本，可以过滤掉部分内容,更复杂的可在“清洗”功能中完成')}
            >
              {t('过滤内容')}
            </span>
            <div class='form-box'>
              <EventFilter
                data={eventSettingList.value}
                on-change={handleFilterChange}
              />
            </div>
          </div>
        )}
        {!hideLogFilterKeys.includes(props.scenarioId) && (
          <div>
            <div class='label-form-box'>
              <span class='label-title'>{t('日志路径')}</span>
              <div class='form-box'>
                <InfoTips tips={t('日志文件的绝对路径，可使用 通配符')} />
                <div class='form-box-url'>
                  <InputAddGroup
                    ref={pathRef}
                    valueList={formData.value?.params?.paths}
                    on-update={handleUpdateUrl}
                  />
                </div>
                <div>
                  <span
                    class='form-link'
                    on-click={handleBlacklist}
                  >
                    <i class={`bklog-icon link-icon bklog-${isBlacklist.value ? 'collapse' : 'expand'}-small`} />
                    {t('路径黑名单')}
                  </span>
                  <InfoTips tips={t('可通过正则语法排除符合条件的匹配项 。如：匹配任意字符：.*')} />
                  {isBlacklist.value && (
                    <InputAddGroup
                      ref={excludeFilesRef}
                      valueList={formData.value.params.exclude_files}
                      on-update={handleUpdateBlacklist}
                    />
                  )}
                </div>
              </div>
            </div>
            <div class='label-form-box'>
              <span class='label-title'>{t('字符集')}</span>
              <bk-select
                class='form-box'
                clearable={false}
                value={formData.value.data_encoding}
                searchable
                on-selected={(val: string) => {
                  isConfigChange.value = true;
                  formData.value.data_encoding = val;
                }}
              >
                {globalsData.value.data_encoding.map(option => (
                  <bk-option
                    id={option.id}
                    key={option.id}
                    name={option.name}
                  />
                ))}
              </bk-select>
            </div>
            <div class='label-form-box'>
              <span class='label-title'>{t('采集范围')}</span>
              <bk-radio-group
                class='form-box'
                value={formData.value.tail_files}
                on-change={val => {
                  isConfigChange.value = true;
                  formData.value.tail_files = val;
                }}
              >
                <bk-radio
                  class='mr-24'
                  value={true}
                >
                  {t('仅采集下发后的日志')}
                </bk-radio>
                <bk-radio value={false}>{t('采集全量日志')}</bk-radio>
              </bk-radio-group>
            </div>
            <div class='label-form-box large-width'>
              <span class='label-title no-require'>{t('日志过滤')}</span>
              <div class='form-box'>{renderLogFilter()}</div>
            </div>
            <div class='label-form-box'>
              <span class='label-title no-require'>{t('设备元数据')}</span>
              <div class='form-box mt-5'>{renderDeviceMetadata()}</div>
            </div>
          </div>
        )}
        {showClusterListKeys.includes(props.scenarioId) && (
          <div>
            <div class='label-form-box large-width'>
              <span class='label-title'>{t('配置项')}</span>
              <div class='form-box mt-5'>
                <ConfigurationItemList
                  ref={configurationItemListRef}
                  bcsClusterId={formData.value.bcs_cluster_id}
                  clusterList={clusterList.value}
                  collectorType={collectorType.value}
                  data={formData.value.configs}
                  logType={logType.value}
                  on-change={(data: IContainerConfigItem[]) => {
                    isConfigChange.value = true;
                    formData.value.configs = data;
                  }}
                />
              </div>
            </div>
            <div class='label-form-box'>
              <span class='label-title no-require'>{t('附加日志标签')}</span>
              <div class='form-box mt-5'>
                <AppendLogTags
                  config={formData.value}
                  on-change={(data: IFormData) => {
                    isConfigChange.value = true;
                    formData.value = { ...formData.value, ...data };
                  }}
                />
              </div>
            </div>
          </div>
        )}
      </div>
    );
    /** 链路配置 */
    const renderLinkConfig = () => (
      <div class='link-config label-form-box'>
        <span class='label-title'>{t('上报链路')}</span>
        <bk-select
          class='form-box'
          clearable={false}
          disabled={isUpdate.value}
          loading={linkListLoading.value}
          value={formData.value.data_link_id}
          on-selected={val => {
            isConfigChange.value = true;
            formData.value.data_link_id = val;
          }}
        >
          {linkConfigurationList.value.map(item => (
            <bk-option
              id={item.data_link_id}
              key={item.data_link_id}
              name={item.link_group_name}
            />
          ))}
        </bk-select>
      </div>
    );
    const cardConfig = [
      {
        title: t('基础信息'),
        key: 'baseInfo',
        renderFn: renderBaseInfo,
      },
      {
        title: t('源日志信息'),
        key: 'sourceLogInfo',
        renderFn: renderSourceLogInfo,
        subTitle: () => {
          if (!props.isEdit) {
            return (
              <span
                class='config-import'
                on-click={() => {
                  isIndexConfigImport.value = true;
                }}
              >
                {t('索引配置导入')}
                <i class='bklog-icon bklog-import-daoru config-import-icon' />
              </span>
            );
          }
        },
      },
      {
        title: t('链路配置'),
        key: 'linkConfiguration',
        renderFn: renderLinkConfig,
      },
    ];

    /**
     * 选择采集目标
     * @param value - 目标选择值，包含多种类型的节点列表
     * @returns void
     */
    const handleConfirm = (value: TargetValue): void => {
      const selection = extractTargetSelection(value);

      if (!selection) {
        return;
      }

      updateFormDataWithSelection(selection);
      isTargetNodesEmpty.value = formData.value.target_nodes.length === 0;
    };

    /**
     * 从目标值中提取类型和节点数据
     * @param value - 目标选择值
     * @returns 目标选择结果或null（如果没有有效数据）
     */
    const extractTargetSelection = (value: TargetValue): TargetSelectionResult | null => {
      const {
        host_list: hostList = [],
        node_list: nodeList = [],
        service_template_list: serviceTemplateList = [],
        set_template_list: setTemplateList = [],
        dynamic_group_list: dynamicGroupList = [],
      } = value;

      /**
       * 按优先级顺序检查目标类型
       */
      const targetChecks: Array<[TargetType, any[]]> = [
        [TARGET_TYPES.TOPO, nodeList],
        [TARGET_TYPES.INSTANCE, hostList],
        [TARGET_TYPES.SERVICE_TEMPLATE, serviceTemplateList],
        [TARGET_TYPES.SET_TEMPLATE, setTemplateList],
        [TARGET_TYPES.DYNAMIC_GROUP, dynamicGroupList],
      ];

      for (const [type, nodes] of targetChecks) {
        if (nodes?.length > 0) {
          return { type, nodes };
        }
      }

      return null;
    };

    /**
     * 使用选择结果更新表单数据
     * @param selection - 目标选择结果
     */
    const updateFormDataWithSelection = (selection: TargetSelectionResult): void => {
      const { type, nodes } = selection;
      formData.value.target_node_type = type;
      formData.value.target_nodes = toTransformNode(nodes, type);
    };

    /**
     * 提取路径值的函数
     * @param params
     * @returns
     */
    const extractPaths = params => {
      return params?.paths ? params.paths.map(item => item.value) : [];
    };

    // 处理winevent场景的请求数据
    const handleWineventlogRequestData = (baseParam, newParams, dataEncoding) => {
      const { paths, exclude_files, winlog_match_op, ...rect } = newParams;
      return {
        ...baseParam,
        params: rect,
        data_encoding: dataEncoding,
      };
    };

    /**
     * 检查 extra_labels 是否所有值都为空
     * @param extraLabels - 标签数组
     * @returns 如果所有值都为空则返回 true
     */
    const isEmptyExtraLabels = (extraLabels: { key: string; value: string }[]): boolean => {
      if (!extraLabels || !Array.isArray(extraLabels) || extraLabels.length === 0) {
        return true;
      }
      // 检查所有项的 key 和 value 是否都为空
      return extraLabels.every(item => {
        const key = item?.key || '';
        const value = item?.value || '';
        return !key.trim() && !value.trim();
      });
    };

    /**
     * 处理主机采集的请求数据
     * @param requestData
     * @param extraLabels
     * @returns
     */
    const handleHostLogRequestData = (requestData, extraLabels, dataEncoding) => {
      requestData.params.extra_labels = isEmptyExtraLabels(extraLabels) ? [] : extraLabels;
      requestData.data_encoding = dataEncoding;
      return requestData;
    };

    /**
     * 处理容器采集的请求数据
     * @param requestData
     * @param configs
     * @param addPodAnnotation
     * @param addPodLabel
     * @param extra_labels
     * @param bcsClusterId
     * @returns
     */
    const handleContainerRequestData = (
      requestData,
      configs,
      addPodAnnotation,
      addPodLabel,
      extraLabels,
      bcsClusterId,
    ) => {
      const { params, ...rect } = requestData;
      // const { data_encoding, params, target_object_type, target_node_type, target_nodes, ...rect } = requestData;
      const newConfig = (configs || []).map(item => {
        const { data_encoding, container, params, collector_type, namespaces, label_selector, annotation_selector } =
          item;
        return {
          data_encoding,
          container,
          params: {
            ...params,
            exclude_files: params.exclude_files.map(item => item.value),
            paths: extractPaths(params),
          },
          collector_type,
          namespaces,
          label_selector,
          annotation_selector,
        };
      });
      // 如果 extra_labels 所有值都为空，则设置为空数组
      const finalExtraLabels = isEmptyExtraLabels(extraLabels) ? [] : extraLabels;
      return {
        ...rect,
        configs: newConfig,
        add_pod_annotation: addPodAnnotation,
        add_pod_label: addPodLabel,
        extra_labels: finalExtraLabels,
        bcs_cluster_id: bcsClusterId,
      };
    };
    /**
     * 新增/修改配置
     */
    const setCollection = () => {
      loadingSave.value = true;
      const {
        params,
        extra_labels,
        collector_config_name,
        collector_config_name_en,
        collector_scenario_id,
        description,
        data_link_id,
        target_node_type,
        target_nodes,
        environment,
        target_object_type,
        data_encoding,
        configs,
        parent_index_set_ids,
        add_pod_annotation,
        add_pod_label,
        bcs_cluster_id,
      } = formData.value;

      const baseParam = {
        collector_config_name,
        collector_config_name_en,
        collector_scenario_id,
        description,
        data_link_id,
        target_node_type,
        target_nodes,
        environment,
        target_object_type,
        parent_index_set_ids,
        bk_biz_id: bkBizId.value,
      };
      const newParams = {
        ...params,
        paths: extractPaths(params),
      };
      const urlParams = {};
      let requestUrl = 'collect/addCollection';
      if (isUpdate.value) {
        urlParams.collector_config_id = route.params.collectorId;
        requestUrl = 'collect/updateCollection';
      }

      let requestData = { ...baseParam, params: newParams };

      // 当为 winevent 时，过滤空值和空对象
      if (props.scenarioId === 'winevent') {
        requestData = handleWineventlogRequestData(baseParam, newParams, data_encoding);
      }
      /**
       * 主机采集的时候
       */
      if (isHostLog.value) {
        requestData = handleHostLogRequestData(requestData, extra_labels, data_encoding);
      }
      /**
       * 容器采集的时候
       */
      if (showClusterListKeys.includes(props.scenarioId)) {
        requestData = handleContainerRequestData(
          requestData,
          configs,
          add_pod_annotation,
          add_pod_label,
          extra_labels,
          bcs_cluster_id,
        );
      }
      if (requestData.params.conditions.type === 'none') {
        requestData.params.conditions = {
          type: 'none',
        };
      }
      $http
        .request(requestUrl, {
          params: urlParams,
          data: requestData,
        })
        .then(res => {
          if (!res?.result) {
            return;
          }
          const newConfig = {
            ...formData.value,
            ...res.data,
          };
          store.commit(`collect/${isUpdate.value ? 'updateCurCollect' : 'setCurCollect'}`, newConfig);
          res.result && showMessage(t('保存成功'));
          emit('next', newConfig);
        })
        .catch(err => {
          console.log('保存采集配置出错:', err);
        })
        .finally(() => {
          loadingSave.value = false;
        });
    };
    /**
     * 保存配置
     */
    const handleSubmitSave = () => {
      if (!showClusterListKeys.includes(props.scenarioId)) {
        isTargetNodesEmpty.value = formData.value.target_nodes.length === 0;
      }
      /**
       * 日志路径校验
       */
      let isErr = true;
      /**
       * 日志过滤器校验
       */
      let isLogFilterErr = true;
      if (isHostLog.value) {
        isErr = pathRef.value.validate();

        isLogFilterErr = logFilterRef.value.validateInputs();
      }

      /**
       * 行首正则是否为空
       */
      isSegmentError.value = isSectionLog.value && !formData.value.params?.multiline_pattern;
      /**
       * 当为文件采集和标准输出时，配置项校验
       */
      let isConfigError = true;
      if (showClusterListKeys.includes(props.scenarioId)) {
        isConfigError = configurationItemListRef.value.validate();
      }
      loadingSave.value = true;
      /**
       * 是否为容器采集并且配置项校验通过
       */
      baseInfoRef.value
        .validate()
        .then(() => {
          /**
           * 判断用户是否有修改行为，如果没有则直接跳转到下一步
           */
          if (!isConfigChange.value) {
            emit('next', formData.value);
            return;
          }
          if (props.scenarioId === 'winevent') {
            setCollection();
            return;
          }
          if (!isTargetNodesEmpty.value && isErr && isLogFilterErr && !isSegmentError.value && isConfigError) {
            setCollection();
          }
        })
        .catch(() => {
          loadingSave.value = false;
        });
    };
    return () => (
      <div
        class='operation-step2-configuration'
        v-bkloading={{ isLoading: loading.value }}
      >
        {cardRender(cardConfig)}
        <LogIpSelector
          key={bkBizId.value}
          height={670}
          mode='dialog'
          original-value={ipSelectorOriginalValue.value}
          panel-list={ipSelectorPanelList}
          show-dialog={showSelectDialog.value}
          show-view-diff={isUpdate.value}
          value={selectorNodes.value}
          allow-host-list-miss-host-id
          {...{
            on: {
              'update:show-dialog': (val: boolean) => {
                showSelectDialog.value = val;
              },
              change: handleConfirm,
            },
          }}
        />
        {props.scenarioId !== 'winevent' && (
          <MultilineRegDialog
            oldPattern={formData.value.params?.multiline_pattern}
            showDialog={showMultilineRegDialog.value}
            on-cancel={handleCancelMultilineReg}
            on-update={(val: string) => {
              formData.value.params.multiline_pattern = val;
            }}
          />
        )}
        <div class='classify-btns-fixed'>
          {!isCloneOrUpdate.value && (
            <bk-button
              class='mr-8'
              on-click={() => {
                emit('prev');
              }}
            >
              {t('上一步')}
            </bk-button>
          )}
          <bk-button
            class='width-88 mr-8'
            loading={loadingSave.value}
            theme='primary'
            on-click={handleSubmitSave}
          >
            {t('下一步')}
          </bk-button>
          <bk-button
            on-click={() => {
              emit('cancel');
            }}
          >
            {t('取消')}
          </bk-button>
        </div>
        {/* 索引配置导入对话框组件 */}
        <IndexConfigImportDialog
          showDialog={isIndexConfigImport.value}
          scenarioId={props.scenarioId}
          on-cancel={(val: boolean) => {
            isIndexConfigImport.value = val;
          }}
          on-update={(data: IFormData) => {
            formData.value = {
              ...formData.value,
              ...data,
            };
            initConfig(formData.value);
          }}
        />
      </div>
    );
  },
});
