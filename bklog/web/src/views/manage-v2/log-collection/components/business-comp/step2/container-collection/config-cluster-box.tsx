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

import { defineComponent, ref, watch, computed, onBeforeUnmount, onMounted } from 'vue';

import useLocale from '@/hooks/use-locale';
import useStore from '@/hooks/use-store';
import tippy, { type Instance, type SingleTarget } from 'tippy.js';

import InfoTips from '../../../common-comp/info-tips';
import ConfigLogSetEditItem from './config-log-set-edit-item';
import ConfigViewDialog from './config-view-dialog';
import WorkloadSelection from './workload-selection';
import $http from '@/api'; // API请求封装
import './config-cluster-box.scss';

// 操作符选择项类型定义
type ISelectItem = {
  id: string;
  name: string;
};

export default defineComponent({
  name: 'ConfigClusterBox',
  props: {
    isNode: {
      type: Boolean,
      default: false,
    },
    config: {
      type: Object,
      default: () => ({}),
    },
    bcsClusterId: {
      type: String,
      default: '',
    },
    isUpdate: {
      type: Boolean,
      default: false,
    },
    scenarioId: {
      type: String,
      default: '',
    },
    clusterList: {
      type: Array,
      default: () => [],
    },
  },

  emits: ['change'],

  setup(props, { emit }) {
    const { t } = useLocale();
    const store = useStore();
    const menuPanelRef = ref();
    const rootRef = ref();
    const isHover = ref(false);
    let tippyInstance: Instance | null = null;
    const bkBizId = computed(() => store.getters.bkBizId);
    const chooseClusterTips = ref({
      content: t('请先选择集群'),
      placement: 'top',
    });

    // const cacheConfig = ref({ ...props.config });
    const isRequestCluster = ref(false); // 集群列表是否正在请求
    // 集群列表
    const clusterList = ref([]);
    // 状态管理
    const nameSpaceRequest = ref(false); // 是否正在请求namespace接口
    const operatorSelectList = ref<ISelectItem[]>([
      { id: '=', name: '=' },
      { id: '!=', name: '!=' },
    ]);
    const nameSpacesSelectList = ref<ISelectItem[]>([]); // namespace 列表

    const scopeNameList = ref({
      namespace: t('按命名空间选择'),
      label: t('按标签选择'),
      annotation: t('按annotation选择'),
      load: t('按工作负载选择'),
      containerName: t('直接指定{n}', { n: 'Container' }),
    });
    /**
     * @desc: 控制配置预览弹窗显示隐藏
     */
    const isShowConfigView = ref(false);

    // 获取配置范围名称
    const getScopeName = (scope: string) => {
      return scopeNameList.value[scope];
    };
    // 检查是否显示容器提示
    const isShowContainerTips = configItem => {
      const { containerExclude, namespacesExclude } = configItem.noQuestParams;
      return [containerExclude, namespacesExclude].includes('!=');
    };
    const viewQueryParams = computed(() => {
      const type = props.isNode ? 'node' : 'pod';
      const { namespaces, annotation_selector, label_selector, container } = props.config;

      // 提取格式化value的函数
      const formatValue = item => {
        return ['NotIn', 'In'].includes(item.operator) ? `(${item.value})` : item.value;
      };

      const matchAnnotations = annotation_selector.match_annotations.map(item => {
        return {
          ...item,
          value: formatValue(item),
        };
      });

      // 简化label_selector的处理
      const labelMatchExpressions = label_selector.match_labels
        ? [...label_selector.match_expressions, ...label_selector.match_labels]
        : label_selector.match_expressions;

      const matchExpressions = labelMatchExpressions.map(item => {
        return {
          ...item,
          value: formatValue(item),
        };
      });

      return {
        bcs_cluster_id: props.bcsClusterId,
        bk_biz_id: bkBizId.value,
        namespaces,
        label_selector: {
          match_expressions: matchExpressions,
        },
        annotation_selector: {
          match_annotations: matchAnnotations,
        },
        container,
        type,
      };
    });

    const initActionPop = () => {
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

    // 获取配置范围的显示状态
    const getScopeSelectShow = () => {
      return props.config.noQuestParams.scopeSelectShow;
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
          }
        })
        .catch(err => {
          console.log(err);
        })
        .finally(() => {
          isRequestCluster.value = false;
        });
    };

    // 判断当前所选集群是否为共享集群
    const getIsSharedCluster = () => {
      return clusterList.value?.find(cluster => cluster.id === props.bcsClusterId)?.is_shared ?? false;
    };

    // 获取命名空间列表
    const getNameSpaceList = async (clusterID: string, isFirstUpdateSelect = false) => {
      if (!clusterID || props.isUpdate || nameSpaceRequest.value) {
        return;
      }

      const query = { bcs_cluster_id: clusterID, bk_biz_id: bkBizId.value };
      nameSpaceRequest.value = true;

      // try {
      const res = await $http.request('container/getNameSpace', { query });

      if (isFirstUpdateSelect) {
        // 第一次切换集群，处理详情页namespace数据回显
        const namespaceList: string[] = [];
        namespaceList.push(...props.config.namespaces);

        const resIDList = res.data.map((item: ISelectItem) => item.id);
        const setList = new Set([...namespaceList, ...resIDList]);
        setList.delete('*');

        const allList = [...setList].map(item => ({ id: item, name: item }));
        nameSpacesSelectList.value = [...allList];
      } else {
        nameSpacesSelectList.value = [...res.data];
      }

      // 如果不是共享集群，添加"所有"选项
      if (!getIsSharedCluster()) {
        nameSpacesSelectList.value.unshift({ name: t('所有'), id: '*' });
      }
      nameSpaceRequest.value = false;
      // } catch (err) {
      //   console.warn(err);
      // } finally {
      //   nameSpaceRequest.value = false;
      // }
    };

    // 获取命名空间的字符串表示
    const getNameSpaceStr = (namespaces: string[]) => {
      return namespaces.length === 1 && namespaces[0] === '*' ? '' : namespaces.join(',');
    };

    // 处理命名空间选择变化
    const handleNameSpaceSelect = (option: string[]) => {
      const config = { ...props.config };

      if (option.at(-1) === '*') {
        // 如果最后选择了"所有"，则只保留"所有"
        config.namespaces = ['*'];
      } else if (option.length > 1 && option.includes('*')) {
        // 如果选择了多个且包含"所有"，则移除"所有"
        const allIndex = option.findIndex(item => item === '*');
        config.namespaces.splice(allIndex, 1);
      } else {
        // 其他情况直接更新
        config.namespaces = option;
      }

      // 更新命名空间字符串表示
      config.noQuestParams.namespaceStr = getNameSpaceStr(config.namespaces);
      emit('change', config);
    };

    // 检查是否显示指定的配置范围项
    const isShowScopeItem = (scope: string) => {
      // 节点环境下只显示标签和注释
      if (props.isNode) {
        return ['label', 'annotation'].includes(scope);
      }
      return !props.config.noQuestParams.scopeSelectShow[scope];
    };

    // 检查是否显示添加范围按钮
    const isShowAddScopeButton = () => {
      // 节点环境下不显示添加范围按钮
      if (props.isNode) {
        return false;
      }

      // 检查是否有可添加的范围
      return Object.values(getScopeSelectShow()).some(Boolean);
    };

    // 获取要显示的命名空间选择列表
    const showNameSpacesSelectList = () => {
      const config = props.config;
      const operate = config.noQuestParams.namespacesExclude;

      if (!nameSpacesSelectList.value.length) {
        return [];
      }

      // 排除模式下不显示"所有"选项
      if (operate === '!=' && nameSpacesSelectList.value.some(item => item.id === '*')) {
        if (config.namespaces.length === 1 && config.namespaces[0] === '*') {
          // 重置"所有"选择
          const newConfigs = { ...props.config };
          newConfigs.namespaces = [];
          // emit('update:formData', { ...props.config, configs: newConfigs });
        }
        return nameSpacesSelectList.value.slice(1);
      }

      return nameSpacesSelectList.value;
    };

    // 添加新的配置范围
    const handleAddNewScope = (scope: string) => {
      tippyInstance?.hide();
      const newConfigs = { ...props.config };
      newConfigs.noQuestParams.scopeSelectShow[scope] = false;
      emit('change', newConfigs);
    };

    // 监听集群ID变化，重新获取命名空间列表
    watch(
      () => props.bcsClusterId,
      newVal => {
        getNameSpaceList(newVal, true);
        !!newVal && initActionPop();
      },
      // { immediate: true },
    );

    watch(
      () => props.scenarioId,
      val => {
        val !== 'std_log_config' && getBcsClusterList();
      },
      { immediate: true },
    );

    // 删除配置参数项
    const handleDeleteConfigParamsItem = (scope: string) => {
      const config = { ...props.config };

      // 根据不同类型重置对应的值
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

      // 对于非节点环境的label类型，更新显示状态
      if (scope !== 'label' || !props.isNode) {
        config.noQuestParams.scopeSelectShow[scope] = true;
      }

      emit('change', config);
    };

    // 处理容器名称输入失去焦点事件
    const handleContainerNameBlur = (inputStr: string, list: string[]) => {
      if (!inputStr) {
        return;
      }

      const config = { ...props.config };

      // 确保输入值被添加且去重
      config.containerNameList = list.length ? [...new Set([...config.containerNameList, inputStr])] : [inputStr];

      emit('change', config);
    };

    onMounted(() => {
      setTimeout(() => {
        initActionPop();
      });
    });

    onBeforeUnmount(() => {
      tippyInstance?.hide();
      tippyInstance?.destroy();
    });

    // 渲染命名空间配置项
    const renderNamespaceItem = () => {
      const config = props.config;
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

    // 渲染工作负载配置项
    const renderWorkloadItem = () => {
      const config = { ...props.config };
      return (
        <div>
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
        </div>
      );
    };

    // 渲染容器名称配置项
    const renderContainerNameItem = () => {
      const config = { ...props.config };
      return (
        <div>
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
                value={(config.container.container_name || []).split(',')}
                allowCreate
                freePaste
                hasDeleteIcon
                on-Blur={(inputStr: string, list: string[]) => handleContainerNameBlur(inputStr, list)}
                on-change={val => {
                  config.container.container_name = val.join(',');
                  emit('change', config);
                }}
              />
            </div>
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
            // on-Click={() => handelShowDialog(conIndex, 'view')}
            on-Click={() => {
              isShowConfigView.value = true;
            }}
          >
            <span class='bk-icon icon-eye' />
            <span>{t('预览')}</span>
          </span>
        </div>

        {/* 命名空间配置项 */}
        {isShowScopeItem('namespace') && renderNamespaceItem()}

        {/* 标签配置项 */}
        {isShowScopeItem('label') && (
          <ConfigLogSetEditItem
            bcsClusterId={props.bcsClusterId}
            clusterList={props.clusterList}
            config={props.config}
            editType='label_selector'
            isNode={props.isNode}
            on-change={config => {
              emit('change', { ...props.config, ...config });
            }}
            on-delete-config-params-item={type => handleDeleteConfigParamsItem(type)}
          />
        )}

        {/* 注释配置项 */}
        {isShowScopeItem('annotation') && (
          <ConfigLogSetEditItem
            bcsClusterId={props.bcsClusterId}
            clusterList={props.clusterList}
            config={props.config}
            editType='annotation_selector'
            isNode={props.isNode}
            on-change={config => {
              emit('change', { ...props.config, ...config });
            }}
            on-delete-config-params-item={type => handleDeleteConfigParamsItem(type)}
          />
        )}

        {/* 工作负载配置项 */}
        {isShowScopeItem('load') && renderWorkloadItem()}

        {/* 容器名称配置项 */}
        {isShowScopeItem('containerName') && renderContainerNameItem()}
        {/* 添加范围 */}
        {isShowAddScopeButton() && (
          <div
            class='add-btn-box'
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
        )}
        <ConfigViewDialog
          isNode={props.isNode}
          isShowDialog={isShowConfigView.value}
          viewQueryParams={viewQueryParams.value}
          on-cancel={() => {
            isShowConfigView.value = false;
          }}
        />
        <div style='display: none'>
          <div ref={menuPanelRef}>
            <ul class='menu-popover-dropdown-list'>
              {Object.entries(getScopeSelectShow()).map(
                ([scopeStr, isShowScope]) =>
                  isShowScope && (
                    <li
                      key={scopeStr}
                      class='menu-dropdown-list-item'
                      on-Click={() => handleAddNewScope(scopeStr)}
                    >
                      {getScopeName(scopeStr)}
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
