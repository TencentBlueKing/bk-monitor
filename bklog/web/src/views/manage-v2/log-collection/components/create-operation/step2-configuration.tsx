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

import { computed, defineComponent, onMounted, ref, nextTick, onBeforeMount } from 'vue';

import LogIpSelector, { toTransformNode, toSelectorNode } from '@/components/log-ip-selector/log-ip-selector';
import useLocale from '@/hooks/use-locale';
import useStore from '@/hooks/use-store';

import { useCollectList } from '../../hook/useCollectList';
import { useOperation } from '../../hook/useOperation';
import {
  showMessage,
  TARGET_TYPES,
  collectTargetTarget,
  LOG_SPECIES_LIST,
  LOG_TYPE_LIST,
  COLLECT_METHOD_LIST,
} from '../../utils';
import BaseInfo from '../business-comp/step2/base-info';
import DeviceMetadata from '../business-comp/step2/device-metadata';
import EventFilter from '../business-comp/step2/event-filter';
import LogFilter from '../business-comp/step2/log-filter';
import MultilineRegDialog from '../business-comp/step2/multiline-reg-dialog';
import InfoTips from '../common-comp/info-tips';
import InputAddGroup from '../common-comp/input-add-group';
import { HOST_COLLECTION_CONFIG, CONTAINER_COLLECTION_CONFIG } from './defaultConfig';
import $http from '@/api';

import './step2-configuration.scss';

type TargetType = (typeof TARGET_TYPES)[keyof typeof TARGET_TYPES];

type TargetValue = {
  host_list?: any[];
  node_list?: any[];
  service_template_list?: any[];
  set_template_list?: any[];
  dynamic_group_list?: any[];
};

type TargetSelectionResult = {
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
  },

  emits: ['next', 'prev', 'cancel'],

  setup(props, { emit }) {
    const { t } = useLocale();
    const store = useStore();
    const { bkBizId, spaceUid, goListPage } = useCollectList();
    const { cardRender } = useOperation();
    const baseInfoRef = ref();
    const showMultilineRegDialog = ref(false);
    const isBlacklist = ref(false);
    const logType = ref('row');
    const showSelectDialog = ref(false);
    const selectorNodes = ref({ host_list: [] });
    const ipSelectorOriginalValue = ref(null);

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
    const isUpdate = ref(false);

    /**
     * 上报链路列表
     */
    const linkConfigurationList = ref([]);
    const linkListLoading = ref(false);
    const isClone = ref(false);
    const otherSpeciesList = ref([]);
    const otherRules = ref(false);
    const loadingSave = ref(false);
    /**
     * 集群列表
     */
    const clusterList = ref([]);
    // 集群列表是否正在请求
    const isRequestCluster = ref(false);
    /**
     * 不展示日志路径的类型
     */
    const hideLogFilterKeys = ['wineventlog', 'std_log_config', 'file_log_config'];
    /**
     * 需要展示集群列表的类型
     */
    const showClusterListKeys = ['std_log_config', 'file_log_config'];

    const eventSettingList = ref([{ type: 'winlog_event_id', list: [], isCorrect: true }]);
    // 获取全局数据
    const globalsData = computed(() => store.getters['globals/globalsData']);
    const environment = computed(() => (props.scenarioId === 'wineventlog' ? 'windows' : 'linux'));
    // 是否是编辑或者克隆
    const isCloneOrUpdate = computed(() => isUpdate.value || isClone.value);

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
      };
    });
    const formData = ref({
      ...baseFormData.value,
    });

    /**
     * 根据类型初始化数据
     */
    const initFromData = () => {
      /**
       * windows events log 日志
       */
      if (props.scenarioId === 'wineventlog') {
        formData.value = {
          ...formData.value,
          params: {
            winlog_name: selectLogSpeciesList.value,
          },
        };
      }
      /**
       * 主机日志
       */
      if (props.scenarioId === 'host_log') {
        formData.value = {
          ...formData.value,
          ...HOST_COLLECTION_CONFIG,
        };
      }
      /**
       * 文件采集
       */
      if (props.scenarioId === 'file_log_config') {
        formData.value = {
          ...formData.value,
          ...CONTAINER_COLLECTION_CONFIG,
          config: {
            collector_type: 'container_log_config',
          },
        };
      }
      /**
       * 标准输出
       */
      if (props.scenarioId === 'std_log_config') {
        formData.value = {
          ...formData.value,
          ...CONTAINER_COLLECTION_CONFIG,
        };
      }
      console.log('formData.value', formData.value);
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
          console.warn(err);
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
        console.warn(e);
      } finally {
        linkListLoading.value = false;
      }
    };

    const handleBlacklist = () => {
      isBlacklist.value = !isBlacklist.value;
    };

    /**
     * 修改日志类型
     * @param item
     */
    const handleLogType = item => {
      logType.value = item.value;
      formData.value.collector_scenario_id = item.value;
    };
    /**
     * 修改日志路径
     */
    const handleUpdateUrl = (data: { value: string }[]) => {
      formData.value.params.paths = data;
    };
    /**
     * 修改路径黑名单
     */
    const handleUpdateBlacklist = (data: { value: string }[]) => {
      formData.value.params.exclude_files = data;
    };
    /**
     * 修改设备元数据
     * @param data
     */
    const handleMetadataList = data => {
      formData.value.params.extra_labels = data;
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
    const handleCancelMultilineReg = val => {
      showMultilineRegDialog.value = val;
    };
    /**
     * 修改过滤内容
     * @param data
     */
    const handleFilterChange = data => {
      eventSettingList.value = data;
      (data || []).map(item => {
        formData.value.params[item.type] = item.list;
      });
    };
    /**
     * 修改日志种类 - 其他 输入框内容
     * @param val
     */
    const handleLogTypeOther = val => {
      otherSpeciesList.value = val;
      formData.value.params.winlog_name = [...selectLogSpeciesList.value, ...val];
    };

    onBeforeMount(() => {
      initFromData();
    });

    onMounted(() => {
      getLinkData();
      /**
       * 文件采集和标准输出的情况下，获取集群列表
       */
      if (showClusterListKeys.includes(props.scenarioId)) {
        getBcsClusterList();
      }
    });

    /**
     * 基本信息
     */
    const renderBaseInfo = () => (
      <BaseInfo
        ref={baseInfoRef}
        data={formData.value}
        on-change={data => {
          const { index_set_name, ...rest } = data;
          rest.collector_config_name = index_set_name;
          formData.value = { ...formData.value, ...rest };
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
            class='reg-input'
            value={data.multiline_pattern}
            on-input={val => {
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
    const renderLogFilter = () => (
      <LogFilter
        conditions={formData.value.params.conditions}
        isCloneOrUpdate={isCloneOrUpdate.value}
        on-conditions-change={val => {
          formData.value.params.conditions = val;
        }}
      />
    );
    /**
     * 设备元数据
     */
    const renderDeviceMetadata = () => (
      <DeviceMetadata
        metadata={formData.value.params.extra_labels}
        on-extra-labels-change={handleMetadataList}
      />
    );
    /**
     * 源日志信息
     */
    const renderSourceLogInfo = () => (
      <div class='source-log-info'>
        {props.scenarioId === 'file_log_config' && (
          <div class='label-form-box'>
            <span class='label-title'>{t('采集方式')}</span>
            {COLLECT_METHOD_LIST.map(item => (
              <span
                key={item.id}
                class={{
                  'collect-method-item': true,
                  active: formData.value.config.collector_type === item.id,
                }}
                on-click={() => {
                  formData.value.config.collector_type = item.id;
                }}
              >
                <img
                  src={item.img}
                  class='img-box'
                />
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
              value={formData.value.bcs_cluster_id}
              on-selected={val => {
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
        {props.scenarioId !== 'wineventlog' && (
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
              {logType.value === 'section' && renderSegment(formData.value.params)}
            </div>
          </div>
        )}
        {!showClusterListKeys.includes(props.scenarioId) && (
          <div class='label-form-box'>
            <span class='label-title'>{t('采集目标')}</span>
            <div class='form-box'>
              <bk-button
                class='target-btn'
                icon='plus'
                onClick={() => {
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
        {props.scenarioId === 'wineventlog' && (
          <div class='label-form-box'>
            <span class='label-title'>{t('日志种类')}</span>
            <div class='form-box'>
              <bk-checkbox-group
                class='log-type-box'
                value={selectLogSpeciesList.value}
                on-change={val => {
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
        {props.scenarioId === 'wineventlog' && (
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
                value={formData.value.data_encoding}
                searchable
                on-selected={val => {
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
              <bk-radio-group class='form-box'>
                <bk-radio class='mr-24'>{t('仅采集下发后的日志')}</bk-radio>
                <bk-radio>{t('采集全量日志')}</bk-radio>
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
            <div class='label-form-box'>
              <span class='label-title'>{t('配置项')}</span>
              <div class='form-box mt-5'>1</div>
            </div>
            <div class='label-form-box'>
              <span class='label-title no-require'>{t('附加日志标签')}</span>
              <div class='form-box mt-5'>
                <div class='checkbox-group'>
                  <bk-checkbox> {t('自动添加 Pod 中的 label')}</bk-checkbox>
                  <bk-checkbox> {t('自动添加 Pod 中的 annotation')}</bk-checkbox>
                </div>
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
          loading={linkListLoading.value}
          value={formData.value.data_link_id}
          on-selected={val => {
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
      triggerFormValidation();
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

      // 按优先级顺序检查目标类型
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
     * 触发表单验证
     */
    const triggerFormValidation = (): void => {
      // 触发 bk-form 的表单验证
      nextTick(() => {
        // formRef.value?.validateField('target_nodes');
      });
    };

    // 新增/修改采集
    const setCollection = () => {
      console.log('params', formData.value);
      loadingSave.value = true;
      $http
        .request('collect/addCollection', {
          data: formData.value,
        })
        .then(res => {
          store.commit(`collect/${isUpdate.value ? 'updateCurCollect' : 'setCurCollect'}`, {
            ...formData.value,
            ...res.data,
          });
          res.result && showMessage(t('保存成功'));
          emit('next', res.data);
        })
        .finally(() => {
          loadingSave.value = false;
        });
    };
    /**
     * 保存配置
     */
    const handleSubmitSave = () => {
      // emit('next');
      // setCollection();
      console.log('下一步', formData.value);
    };
    return () => (
      <div class='operation-step2-configuration'>
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
        {props.scenarioId !== 'wineventlog' && (
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
          <bk-button
            class='mr-8'
            on-click={() => {
              emit('prev');
            }}
          >
            {t('上一步')}
          </bk-button>
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
      </div>
    );
  },
});
