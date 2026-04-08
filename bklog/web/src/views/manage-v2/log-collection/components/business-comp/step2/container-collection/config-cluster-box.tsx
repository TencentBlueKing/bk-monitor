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

import { defineComponent, ref, watch, computed, onBeforeUnmount, onMounted, nextTick, type PropType } from 'vue';

import useLocale from '@/hooks/use-locale';
import useStore from '@/hooks/use-store';
import tippy, { type Instance, type SingleTarget } from 'tippy.js';

import InfoTips from '../../../common-comp/info-tips';
import ConfigLogSetEditItem from './config-log-set-edit-item';
import ConfigViewDialog from './config-view-dialog';
import WorkloadSelection from './workload-selection';
import $http from '@/api';
import type { IContainerConfigItem, IClusterItem } from '../../../../type';
import './config-cluster-box.scss';

/**
 * 选择项类型定义
 */
type ISelectItem = {
  id: string;
  name: string;
};

/**
 * 容器配置类型定义
 */
type IContainerConfig = {
  workload_type?: string;
  workload_name?: string;
  container_name?: string;
};

/**
 * 配置范围类型
 */
type ScopeType = 'namespace' | 'label' | 'annotation' | 'load' | 'containerName';

/**
 * 操作符类型
 */
type OperatorType = '=' | '!=';

/**
 * ConfigClusterBox 组件
 * 用于配置容器/节点的采集范围，支持多种选择方式：
 * - 按命名空间选择
 * - 按标签选择
 * - 按注解选择
 * - 按工作负载选择
 * - 直接指定容器名称
 */
export default defineComponent({
  name: 'ConfigClusterBox',
  props: {
    /** 是否为节点模式 */
    isNode: {
      type: Boolean,
      default: false,
    },
    /** 配置项数据 */
    config: {
      type: Object as PropType<IContainerConfigItem>,
      default: () => ({}),
    },
    /** BCS 集群 ID */
    bcsClusterId: {
      type: String,
      default: '',
    },
    /** 是否为更新模式 */
    isUpdate: {
      type: Boolean,
      default: false,
    },
    /** 场景 ID */
    scenarioId: {
      type: String,
      default: '',
    },
    /** 集群列表 */
    clusterList: {
      type: Array as PropType<IClusterItem[]>,
      default: () => [],
    },
  },

  emits: ['change'],

  setup(props, { emit }) {
    const { t } = useLocale();
    const store = useStore();

    // ==================== Refs 定义 ====================
    /** Tippy 菜单面板引用 */
    const menuPanelRef = ref<HTMLElement>();
    /** 添加范围按钮引用 */
    const rootRef = ref<HTMLElement>();
    /** 是否悬停在添加按钮上 */
    const isHover = ref(false);
    /** Tippy 实例 */
    let tippyInstance: Instance | null = null;
    /** 业务 ID */
    const bkBizId = computed(() => store.getters.bkBizId);
    /** 选择集群提示配置 */
    const chooseClusterTips = ref({
      content: t('请先选择集群'),
      placement: 'top' as const,
    });
    /** 是否正在请求集群列表 */
    const isRequestCluster = ref(false);
    /** 集群列表 */
    const clusterList = ref<IClusterItem[]>([]);
    /** 是否正在请求命名空间接口 */
    const nameSpaceRequest = ref(false);
    /** 操作符选择列表 */
    const operatorSelectList = ref<ISelectItem[]>([
      { id: '=', name: '=' },
      { id: '!=', name: '!=' },
    ]);
    /** 命名空间选择列表 */
    const nameSpacesSelectList = ref<ISelectItem[]>([]);
    /** 配置范围名称映射 */
    const scopeNameList = ref<Record<ScopeType, string>>({
      namespace: t('按命名空间选择'),
      label: t('按标签选择'),
      annotation: t('按annotation选择'),
      load: t('按工作负载选择'),
      containerName: t('直接指定{n}', { n: 'Container' }),
    });
    /** 控制配置预览弹窗显示隐藏 */
    const isShowConfigView = ref(false);

    // ==================== 工具函数 ====================
    /**
     * 确保容器配置对象存在
     * @param config - 配置项对象
     * @returns 确保存在的容器配置对象
     */
    const ensureContainerConfig = (
      config: IContainerConfigItem,
    ): IContainerConfig & {
      workload_type: string;
      workload_name: string;
      container_name: string;
    } => {
      if (!config.container) {
        config.container = {
          workload_type: '',
          workload_name: '',
          container_name: '',
        };
      }
      // 确保所有字段都有默认值
      return {
        workload_type: config.container.workload_type || '',
        workload_name: config.container.workload_name || '',
        container_name: config.container.container_name || '',
      };
    };

    /**
     * 获取配置范围名称
     * @param scope - 范围类型
     * @returns 范围名称
     */
    const getScopeName = (scope: ScopeType): string => {
      return scopeNameList.value[scope] || scope;
    };

    /**
     * 检查是否显示容器提示信息
     * 当命名空间或容器的排除操作符为 '!=' 时显示提示
     * @param configItem - 配置项
     * @returns 是否显示提示
     */
    const isShowContainerTips = (configItem: IContainerConfigItem): boolean => {
      const noQuestParams = configItem.noQuestParams;
      if (!noQuestParams) return false;
      const { containerExclude, namespacesExclude } = noQuestParams;
      return [containerExclude, namespacesExclude].includes('!=' as OperatorType);
    };
    /**
     * 视图查询参数计算属性
     * 用于配置预览功能，格式化配置数据为查询参数
     */
    const viewQueryParams = computed(() => {
      const type = props.isNode ? 'node' : 'pod';
      const config = props.config as IContainerConfigItem;
      const { namespaces, annotation_selector, label_selector, container } = config;

      /**
       * 格式化匹配表达式的值
       * 对于 'In' 和 'NotIn' 操作符，将值用括号包裹
       * @param item - 匹配表达式项
       * @returns 格式化后的值
       */
      const formatValue = (item: { operator?: string; value?: string }): string => {
        if (!item.value) return '';
        return ['NotIn', 'In'].includes(item.operator || '') ? `(${item.value})` : item.value;
      };

      // 处理注解选择器
      const matchAnnotations = (annotation_selector?.match_annotations || []).map(item => ({
        ...item,
        value: formatValue(item),
      }));

      // 处理标签选择器：合并 match_labels 和 match_expressions
      const labelMatchExpressions = label_selector?.match_labels
        ? [...(label_selector.match_expressions || []), ...label_selector.match_labels]
        : label_selector?.match_expressions || [];

      const matchExpressions = labelMatchExpressions.map(item => ({
        ...item,
        value: formatValue(item),
      }));

      return {
        bcs_cluster_id: props.bcsClusterId,
        bk_biz_id: bkBizId.value,
        namespaces: namespaces || [],
        label_selector: {
          match_expressions: matchExpressions,
        },
        annotation_selector: {
          match_annotations: matchAnnotations,
        },
        container: container || {},
        type,
      };
    });

    /**
     * 初始化添加范围按钮的 Tippy 弹出层
     * 在 DOM 更新后调用，确保元素已渲染
     */
    const initActionPop = (): void => {
      // 先销毁旧的实例，避免重复创建
      if (tippyInstance) {
        tippyInstance.hide();
        tippyInstance.destroy();
        tippyInstance = null;
      }

      // 检查必要条件：元素存在且按钮应该显示
      if (!rootRef.value || !isShowAddScopeButton.value) {
        return;
      }

      tippyInstance = tippy(rootRef.value as SingleTarget, {
        content: menuPanelRef.value as any,
        trigger: 'click',
        placement: 'bottom-start',
        theme: 'light cluster-menu-list-popover',
        interactive: true,
        hideOnClick: true,
        arrow: false,
        offset: [0, 1],
        appendTo: () => document.body,
        onShow: () => {
          isHover.value = true;
        },
        onHide: () => {
          isHover.value = false;
        },
      });
    };

    /**
     * 获取配置范围的显示状态
     * @returns 配置范围显示状态对象
     */
    const getScopeSelectShow = computed(() => {
      const config = props.config as IContainerConfigItem;
      return (
        config.noQuestParams?.scopeSelectShow || {
          namespace: true,
          label: true,
          load: true,
          containerName: true,
          annotation: true,
        }
      );
    });

    /**
     * 获取 BCS 集群列表
     * 防止重复请求，使用 isRequestCluster 标志位
     */
    const getBcsClusterList = async (): Promise<void> => {
      if (isRequestCluster.value) {
        return;
      }
      isRequestCluster.value = true;
      const query = { bk_biz_id: bkBizId.value };
      try {
        const res = await $http.request('container/getBcsList', { query });
        if (res.code === 0) {
          clusterList.value = res.data || [];
        }
      } catch (err) {
        console.error('获取 BCS 集群列表失败:', err);
      } finally {
        isRequestCluster.value = false;
      }
    };

    /**
     * 判断当前所选集群是否为共享集群
     * @returns 是否为共享集群
     */
    const getIsSharedCluster = (): boolean => {
      return clusterList.value?.find(cluster => cluster.id === props.bcsClusterId)?.is_shared ?? false;
    };

    /**
     * 获取命名空间列表
     * @param clusterID - 集群 ID
     * @param isFirstUpdateSelect - 是否为首次更新选择（用于详情页数据回显）
     */
    const getNameSpaceList = async (clusterID: string, isFirstUpdateSelect = false): Promise<void> => {
      // 参数校验和防重复请求
      if (!clusterID || props.isUpdate || nameSpaceRequest.value) {
        return;
      }

      const query = { bcs_cluster_id: clusterID, bk_biz_id: bkBizId.value };
      nameSpaceRequest.value = true;

      try {
        const res = (await $http.request('container/getNameSpace', { query })) as { code: number; data: ISelectItem[] };

        if (isFirstUpdateSelect) {
          // 首次切换集群时，合并现有命名空间和接口返回的命名空间，用于详情页数据回显
          const config = props.config as IContainerConfigItem;
          const namespaceList: string[] = [...(config.namespaces || [])];
          const resIDList = (res.data || []).map((item: ISelectItem) => item.id);
          const setList = new Set([...namespaceList, ...resIDList]);
          setList.delete('*'); // 移除通配符，后续会重新添加

          const allList = [...setList].map(item => ({ id: item, name: item }));
          nameSpacesSelectList.value = [...allList];
        } else {
          nameSpacesSelectList.value = res.data || [];
        }

        // 如果不是共享集群，添加"所有"选项
        if (!getIsSharedCluster()) {
          nameSpacesSelectList.value.unshift({ name: t('所有'), id: '*' });
        }
      } catch (err) {
        console.log('获取命名空间列表失败:', err);
        nameSpacesSelectList.value = [];
      } finally {
        nameSpaceRequest.value = false;
      }
    };

    /**
     * 获取命名空间的字符串表示
     * 如果只有一个 '*' 选项，返回空字符串
     * @param namespaces - 命名空间数组
     * @returns 命名空间字符串
     */
    const getNameSpaceStr = (namespaces: string[]): string => {
      if (!namespaces || namespaces.length === 0) return '';
      return namespaces.length === 1 && namespaces[0] === '*' ? '' : namespaces.join(',');
    };

    /**
     * 处理命名空间选择变化
     * 处理逻辑：
     * 1. 如果最后选择了"所有"(*)，则只保留"所有"
     * 2. 如果选择了多个且包含"所有"，则移除"所有"
     * 3. 其他情况直接更新
     * @param option - 选中的命名空间数组
     */
    const handleNameSpaceSelect = (option: string[]): void => {
      const config = { ...props.config } as IContainerConfigItem;
      if (!config.namespaces) {
        config.namespaces = [];
      }

      if (option.at(-1) === '*') {
        // 如果最后选择了"所有"，则只保留"所有"
        config.namespaces = ['*'];
      } else if (option.length > 1 && option.includes('*')) {
        // 如果选择了多个且包含"所有"，则移除"所有"
        const allIndex = option.indexOf('*');
        const newNamespaces = [...option];
        newNamespaces.splice(allIndex, 1);
        config.namespaces = newNamespaces;
      } else {
        // 其他情况直接更新
        config.namespaces = option;
      }

      // 确保 noQuestParams 存在
      if (!config.noQuestParams) {
        config.noQuestParams = {
          scopeSelectShow: {},
          namespaceStr: '',
        };
      }
      // 更新命名空间字符串表示
      config.noQuestParams.namespaceStr = getNameSpaceStr(config.namespaces);
      emit('change', config);
    };

    /**
     * 检查是否显示指定的配置范围项
     * 节点环境下只显示标签和注释，其他环境下根据 scopeSelectShow 判断
     * @param scope - 范围类型
     * @returns 是否显示
     */
    const isShowScopeItem = (scope: ScopeType): boolean => {
      // 节点环境下只显示标签和注释
      if (props.isNode) {
        return ['label', 'annotation'].includes(scope);
      }
      const config = props.config as IContainerConfigItem;
      const scopeSelectShow = config.noQuestParams?.scopeSelectShow;
      if (!scopeSelectShow) return false;
      return !scopeSelectShow[scope];
    };

    /**
     * 检查是否显示添加范围按钮
     * 节点环境下不显示，其他环境下检查是否有可添加的范围
     * @returns 是否显示添加按钮
     */
    const isShowAddScopeButton = computed((): boolean => {
      // 节点环境下不显示添加范围按钮
      if (props.isNode) {
        return false;
      }
      // 检查是否有可添加的范围（scopeSelectShow 中为 true 的项）
      return Object.values(getScopeSelectShow.value).some(Boolean);
    });

    /**
     * 获取要显示的命名空间选择列表
     * 排除模式下不显示"所有"选项
     * @returns 命名空间选择列表
     */
    const showNameSpacesSelectList = (): ISelectItem[] => {
      const config = props.config as IContainerConfigItem;
      const operate = config.noQuestParams?.namespacesExclude;

      if (!nameSpacesSelectList.value.length) {
        return [];
      }

      // 排除模式下不显示"所有"选项
      if (operate === '!=' && nameSpacesSelectList.value.some(item => item.id === '*')) {
        // 如果当前选择的是"所有"，需要重置为空
        const namespaces = config.namespaces || [];
        if (namespaces.length === 1 && namespaces[0] === '*') {
          const newConfigs = { ...props.config } as IContainerConfigItem;
          newConfigs.namespaces = [];
          // 注意：这里不触发 emit，因为只是获取列表，不改变配置
        }
        return nameSpacesSelectList.value.slice(1);
      }
      return nameSpacesSelectList.value;
    };

    /**
     * 添加新的配置范围
     * @param scope - 范围类型
     */
    const handleAddNewScope = (scope: ScopeType): void => {
      tippyInstance?.hide();
      const newConfigs = { ...props.config };
      if (!newConfigs.noQuestParams) {
        newConfigs.noQuestParams = {
          scopeSelectShow: {},
        };
      }
      if (!newConfigs.noQuestParams.scopeSelectShow) {
        newConfigs.noQuestParams.scopeSelectShow = {};
      }
      newConfigs.noQuestParams.scopeSelectShow[scope] = false;
      emit('change', newConfigs);
    };

    // ==================== Watch 监听 ====================
    /**
     * 监听集群 ID 变化
     * 当集群 ID 变化时，重新获取命名空间列表，并初始化 Tippy
     */
    watch(
      () => props.bcsClusterId,
      (newVal: string) => {
        if (newVal) {
          getNameSpaceList(newVal, true);
          // 非节点模式下，等待 DOM 更新后初始化 Tippy
          if (!props.isNode) {
            nextTick(() => {
              if (isShowAddScopeButton.value && rootRef.value) {
                initActionPop();
              }
            });
          }
        }
      },
    );

    /**
     * 监听场景 ID 变化
     * 当场景 ID 不是 'container_stdout' 时，获取 BCS 集群列表
     */
    watch(
      () => props.scenarioId,
      (val: string) => {
        if (val && val !== 'container_stdout') {
          getBcsClusterList();
        }
      },
      { immediate: true },
    );

    /**
     * 监听节点模式变化
     * 当 isNode 变化时，销毁旧的 Tippy 实例，并在非节点模式下重新初始化
     */
    watch(
      () => props.isNode,
      () => {
        // 先销毁旧实例
        if (tippyInstance) {
          tippyInstance.hide();
          tippyInstance.destroy();
          tippyInstance = null;
        }
        // 等待 DOM 更新后再初始化（如果按钮显示的话）
        if (!props.isNode) {
          nextTick(() => {
            if (isShowAddScopeButton.value && rootRef.value) {
              initActionPop();
            }
          });
        }
      },
    );

    /**
     * 删除配置参数项
     * 根据不同的范围类型，重置对应的配置值，并更新显示状态
     * @param scope - 范围类型
     */
    const handleDeleteConfigParamsItem = (scope: ScopeType): void => {
      const config = { ...props.config } as IContainerConfigItem;

      // 确保 noQuestParams 存在
      if (!config.noQuestParams) {
        config.noQuestParams = {
          scopeSelectShow: {},
        };
      }
      if (!config.noQuestParams.scopeSelectShow) {
        config.noQuestParams.scopeSelectShow = {};
      }

      // 根据不同类型重置对应的值
      switch (scope) {
        case 'namespace':
          config.namespaces = [];
          break;
        case 'load':
          // 确保 container 对象存在后重置工作负载相关字段
          ensureContainerConfig(config);
          if (config.container) {
            config.container.workload_type = '';
            config.container.workload_name = '';
          }
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

      // 对于非节点环境的 label 类型，更新显示状态
      if (scope !== 'label' || !props.isNode) {
        config.noQuestParams.scopeSelectShow[scope] = true;
      }
      emit('change', config);
    };

    /**
     * 处理容器名称输入失去焦点事件
     * 当用户在输入框中输入后失去焦点时，将输入值添加到容器名称列表中
     * @param inputStr - 输入的字符串
     * @param list - 当前的标签列表
     */
    const handleContainerNameBlur = (inputStr: string, list: string[]): void => {
      if (!inputStr) {
        return;
      }

      const config = { ...props.config } as IContainerConfigItem;
      const currentList = config.containerNameList || [];

      // 确保输入值被添加且去重
      if (list.length > 0) {
        // 合并现有列表和新列表，去重
        config.containerNameList = [...new Set([...currentList, ...list])];
      } else {
        // 如果列表为空，直接添加输入值
        config.containerNameList = [...new Set([...currentList, inputStr])];
      }

      emit('change', config);
    };

    // ==================== 生命周期 ====================
    /**
     * 组件挂载后初始化 Tippy
     * 等待 DOM 更新完成后再初始化，确保元素已渲染
     */
    onMounted(() => {
      nextTick(() => {
        if (!props.isNode && isShowAddScopeButton.value && rootRef.value) {
          initActionPop();
        }
      });
    });

    /**
     * 组件卸载前清理 Tippy 实例
     * 防止内存泄漏
     */
    onBeforeUnmount(() => {
      if (tippyInstance) {
        tippyInstance.hide();
        tippyInstance.destroy();
        tippyInstance = null;
      }
    });

    // ==================== 渲染函数 ====================
    /**
     * 渲染命名空间配置项
     * @returns JSX 元素
     */
    const renderNamespaceItem = () => {
      const config = props.config as IContainerConfigItem;
      return (
        <div class='config-item hover-light'>
          <div class='config-item-title flex-ac'>
            <span>{t('按命名空间选择')}</span>
            <span
              class='bk-icon icon-delete'
              on-Click={() => handleDeleteConfigParamsItem('namespace')}
            />
          </div>
          <div
            class='operator-box'
            v-bk-tooltips={{ ...chooseClusterTips.value, disabled: !!props.bcsClusterId }}
          >
            <bk-select
              class='operate-select'
              clearable={false}
              disabled={props.isNode || !props.bcsClusterId || nameSpaceRequest.value}
              placeholder=' '
              popoverWidth={100}
              value={config.noQuestParams.namespacesExclude}
              on-change={val => {
                config.noQuestParams.namespacesExclude = val;
                emit('change', config);
              }}
            >
              {operatorSelectList.value.map(oItem => (
                <bk-option
                  id={oItem.id}
                  key={oItem.id}
                  name={oItem.name}
                />
              ))}
            </bk-select>
            <bk-select
              class='space-select'
              disabled={props.isNode || !props.bcsClusterId || nameSpaceRequest.value}
              value={config.namespaces}
              displayTag
              multiple
              searchable
              loading={nameSpaceRequest.value}
              on-selected={option => {
                config.namespaces = option;
                handleNameSpaceSelect(option);
              }}
            >
              {showNameSpacesSelectList().map(oItem => (
                <bk-option
                  id={oItem.id}
                  key={oItem.id}
                  name={oItem.name}
                />
              ))}
            </bk-select>
          </div>
        </div>
      );
    };

    /**
     * 渲染工作负载配置项
     * @returns JSX 元素
     */
    const renderWorkloadItem = () => {
      const config = { ...props.config } as IContainerConfigItem;
      // 确保 container 对象存在
      ensureContainerConfig(config);
      return (
        <div class='config-item hover-light'>
          <div class='config-item-title flex-ac'>
            <span>{t('按工作负载选择')}</span>
            <span
              class='bk-icon icon-delete'
              on-Click={() => handleDeleteConfigParamsItem('load')}
            />
          </div>
          <WorkloadSelection
            bcsClusterId={props.bcsClusterId}
            conItem={config}
            container={config.container}
            on-update={val => {
              config.container = val;
              emit('change', config);
            }}
          />
        </div>
      );
    };

    /**
     * 渲染容器名称配置项
     * @returns JSX 元素
     */
    const renderContainerNameItem = () => {
      const config = { ...props.config } as IContainerConfigItem;
      // 确保 container 对象存在
      ensureContainerConfig(config);
      return (
        <div class='config-item hover-light'>
          <div class='config-item-title flex-ac'>
            <span>{t('直接指定{n}', { n: 'Container' })}</span>
            <span
              class='bk-icon icon-delete'
              on-Click={() => handleDeleteConfigParamsItem('containerName')}
            />
          </div>
          <div class='operator-box'>
            <bk-select
              class='operate-select'
              clearable={false}
              placeholder=' '
              popoverWidth={100}
              value={config.noQuestParams.containerExclude}
              on-change={val => {
                config.noQuestParams.containerExclude = val;
                emit('change', config);
              }}
            >
              {operatorSelectList.value.map(oItem => (
                <bk-option
                  id={oItem.id}
                  key={oItem.id}
                  name={oItem.name}
                />
              ))}
            </bk-select>
            <bk-tag-input
              extCls='container-input'
              value={(config.container.container_name || '').split(',').filter(Boolean)}
              allowCreate
              freePaste
              hasDeleteIcon
              on-Blur={(inputStr: string, list: string[]) => handleContainerNameBlur(inputStr, list)}
              on-change={(val: string[]) => {
                ensureContainerConfig(config);
                if (config.container) {
                  config.container.container_name = val.join(',');
                }
                emit('change', config);
              }}
            />
          </div>
        </div>
      );
    };

    return () => (
      <div class='config-cluster-box-main'>
        {/* 容器提示信息 */}
        {isShowContainerTips(props.config) && (
          <bk-alert
            class='container-alert'
            showIcon={false}
            type='info'
          >
            <template slot='title'>
              <i class='bk-icon icon-info' />
              <span>{t('采集范围排除能力依赖采集器 bk-log-collector >= 0.3.2，请保证采集器已升级到最新版本')}</span>
            </template>
          </bk-alert>
        )}
        {/* 配置标题和预览按钮 */}
        <div class='config-cluster-title justify-bt'>
          <span class='title-box'>
            <span class='title'>{t('选择 {n} 范围', { n: props.isNode ? 'Node' : 'Container' })}</span>
            <InfoTips tips={t('所有选择范围可相互叠加并作用')} />
          </span>
          <span
            class={['preview', !props.bcsClusterId && 'disable'].join(' ')}
            v-bk-tooltips={{ ...chooseClusterTips.value, disabled: !!props.bcsClusterId }}
            on-Click={() => {
              isShowConfigView.value = true;
            }}
          >
            <span class='bk-icon icon-eye' />
            <span>{t('预览')}</span>
          </span>
        </div>

        <div class='config-params-box'>
          {/* 命名空间配置项 */}
          {isShowScopeItem('namespace') && renderNamespaceItem()}

          {/* 标签配置项 */}
          {isShowScopeItem('label') && (
            <ConfigLogSetEditItem
              bcsClusterId={props.bcsClusterId}
              clusterList={props.clusterList}
              config={props.config as any}
              editType='label_selector'
              isNode={props.isNode}
              on-change={config => {
                emit('change', { ...props.config, ...config });
              }}
              on-delete-config-params-item={type => handleDeleteConfigParamsItem(type as ScopeType)}
            />
          )}

          {/* 注释配置项 */}
          {isShowScopeItem('annotation') && (
            <ConfigLogSetEditItem
              bcsClusterId={props.bcsClusterId}
              clusterList={props.clusterList}
              config={props.config as IContainerConfigItem}
              editType='annotation_selector'
              isNode={props.isNode}
              on-change={config => {
                emit('change', { ...props.config, ...config });
              }}
              on-delete-config-params-item={type => handleDeleteConfigParamsItem(type as ScopeType)}
            />
          )}

          {/* 工作负载配置项 */}
          {isShowScopeItem('load') && renderWorkloadItem()}

          {/* 容器名称配置项 */}
          {isShowScopeItem('containerName') && renderContainerNameItem()}
        </div>
        {/* 添加范围 */}
        <div
          class='add-btn-box'
          style={{ display: isShowAddScopeButton.value ? 'block' : 'none' }}
          v-bk-tooltips={{ ...chooseClusterTips.value, disabled: !!props.bcsClusterId }}
        >
          <div
            ref={rootRef}
            class={{
              'add-btns': true,
              hover: isHover.value,
              'is-disabled': !props.bcsClusterId,
            }}
          >
            <i class='bk-icon icon-plus-line icons' />
            {t('添加范围')}
          </div>
        </div>
        <ConfigViewDialog
          isShowDialog={isShowConfigView.value}
          viewQueryParams={viewQueryParams.value}
          on-cancel={() => {
            isShowConfigView.value = false;
          }}
        />
        <div style='display: none'>
          <div ref={menuPanelRef}>
            <ul class='menu-popover-dropdown-list'>
              {Object.entries(getScopeSelectShow.value).map(
                ([scopeStr, isShowScope]) =>
                  isShowScope && (
                    <li
                      key={scopeStr}
                      class='menu-dropdown-list-item'
                      on-Click={() => handleAddNewScope(scopeStr as ScopeType)}
                    >
                      {getScopeName(scopeStr as ScopeType)}
                    </li>
                  ),
              )}
            </ul>
          </div>
        </div>
      </div>
    );
  },
});
