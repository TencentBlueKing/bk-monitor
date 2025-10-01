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

import { computed, defineComponent, onMounted, ref } from 'vue';

import LogIpSelector, { toTransformNode, toSelectorNode } from '@/components/log-ip-selector/log-ip-selector';
import useLocale from '@/hooks/use-locale';
import useStore from '@/hooks/use-store';

import { useCollectList } from '../../hook/useCollectList';
import { useOperation } from '../../hook/useOperation';
import { showMessage } from '../../utils';
import BaseInfo from '../business-comp/step2/base-info';
import DeviceMetadata from '../business-comp/step2/device-metadata';
import EventFilter from '../business-comp/step2/event-filter';
import LogFilter from '../business-comp/step2/log-filter';
import MultilineRegDialog from '../business-comp/step2/multiline-reg-dialog';
import InfoTips from '../common-comp/info-tips';
import InputAddGroup from '../common-comp/input-add-group';
import $http from '@/api';

import './step2-configuration.scss';

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
    const logTypeList = [
      { text: t('行日志'), value: 'row' },
      { text: t('段日志'), value: 'section' },
    ];
    const baseInfoRef = ref();
    const showMultilineRegDialog = ref(false);
    const paths = ref<string[]>(['']);
    const blacklist = ref<string[]>(['']);
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
    const environment = computed(() => (props.scenarioId === 'wineventlog' ? 'windows' : 'linux'));
    const formData = ref({
      collector_config_name: '',
      collector_config_name_en: '',
      target_node_type: 'INSTANCE',
      data_link_id: '',
      params: {
        winlog_name: selectLogSpeciesList.value,
      },
      bk_biz_id: bkBizId.value,
      description: '',
      target_nodes: [],
      collector_scenario_id: props.scenarioId,
      environment: environment.value,
      target_object_type: 'HOST',
      data_encoding: 'UTF-8',
    });
    /**
     * 上报链路列表
     */
    const linkConfigurationList = ref([]);
    const linkListLoading = ref(false);
    const isCloneOrUpdate = ref(false);
    const otherSpeciesList = ref([]);
    const otherRules = ref(false);
    const loadingSave = ref(false);
    // 获取全局数据
    // const globalsData = computed(() => store.getters['globals/globalsData']);
    const collectTargetTarget = {
      // 已(动态)选择 静态主机 节点 服务模板 集群模板
      INSTANCE: '已选择{0}个静态主机',
      TOPO: '已动态选择{0}个节点',
      SERVICE_TEMPLATE: '已选择{0}个服务模板',
      SET_TEMPLATE: '已选择{0}个集群模板',
      DYNAMIC_GROUP: '已选择{0}个动态组',
    };
    const logSpeciesList = [
      {
        id: 'Application',
        name: t('应用程序(Application)'),
      },
      {
        id: 'Security',
        name: t('安全(Security)'),
      },
      {
        id: 'System',
        name: t('系统(System)'),
      },
      {
        id: 'Other',
        name: t('其他'),
      },
    ];
    const metadataList = ref([
      {
        key: 'value',
        value: '2',
        duplicateKey: false,
      },
    ]);
    const eventSettingList = ref([{ type: 'winlog_event_id', list: [], isCorrect: true }]);

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
    };
    /**
     * 修改采集路径
     */
    const handleUpdateUrl = (data: string[]) => {
      paths.value = data;
    };
    /**
     * 修改路径黑名单
     */
    const handleUpdateBlacklist = (data: string[]) => {
      blacklist.value = data;
    };
    /**
     * 修改设备元数据
     * @param data
     */
    const handleMetadataList = data => {
      metadataList.value = data;
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
    const handleCancelMultilineReg = () => {
      showMultilineRegDialog.value = false;
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

    onMounted(() => {
      getLinkData();
    });

    /**
     * 基本信息
     */
    const renderBaseInfo = () => (
      <BaseInfo
        ref={baseInfoRef}
        data={formData.value}
        on-change={data => {
          formData.value = { ...formData.value, ...data };
        }}
      />
    );
    /**
     * 行首正则
     */
    const renderSegment = () => (
      <div class='line-rule'>
        <div class='label-title text-left'>{t('行首正则')}</div>
        <div class='rule-reg'>
          <bk-input class='reg-input' />
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
            <bk-input>
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
            <bk-input class='time-box'>
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
    const renderLogFilter = () => <LogFilter />;
    /**
     * 设备元数据
     */
    const renderDeviceMetadata = () => (
      <DeviceMetadata
        valueList={metadataList.value}
        on-update={handleMetadataList}
      />
    );
    /**
     * 源日志信息
     */
    const renderSourceLogInfo = () => (
      <div class='source-log-info'>
        {props.scenarioId !== 'wineventlog' && (
          <div class='label-form-box'>
            <span class='label-title'>{t('日志类型')}</span>
            <div class='form-box'>
              <div class='bk-button-group'>
                {logTypeList.map(item => (
                  <bk-button
                    key={item.value}
                    class={{ 'is-selected': logType.value === item.value }}
                    on-Click={() => handleLogType(item)}
                  >
                    {item.text}
                  </bk-button>
                ))}
              </div>
              {logType.value === 'section' && renderSegment()}
            </div>
          </div>
        )}
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
                  {logSpeciesList.map(item => (
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
                    // on-blur={handleLogTypeOther}
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
        {props.scenarioId !== 'wineventlog' && (
          <div>
            <div class='label-form-box'>
              <span class='label-title'>{t('采集路径')}</span>
              <div class='form-box'>
                <InfoTips tips={t('日志文件的绝对路径，可使用 通配符')} />
                <div class='form-box-url'>
                  <InputAddGroup
                    valueList={paths.value}
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
                      valueList={blacklist.value}
                      on-update={handleUpdateBlacklist}
                    />
                  )}
                </div>
              </div>
            </div>
            <div class='label-form-box'>
              <span class='label-title'>{t('字符集')}</span>
              <bk-select class='form-box' />
            </div>
            <div class='label-form-box'>
              <span class='label-title'>{t('采集范围')}</span>
              <bk-radio-group class='form-box'>
                <bk-radio class='mr-24'>{t('仅采集下发后的日志')}</bk-radio>
                <bk-radio>{t('采集全量日志')}</bk-radio>
              </bk-radio-group>
            </div>
            <div class='label-form-box large-width'>
              <span class='label-title'>{t('日志过滤')}</span>
              <div class='form-box mt-5'>
                <bk-switcher
                  size='large'
                  theme='primary'
                />
                <InfoTips
                  class='ml-12'
                  tips={t('过滤器支持采集时过滤不符合的日志内容，请保证采集器已升级到最新版本')}
                />
                {renderLogFilter()}
              </div>
            </div>
            <div class='label-form-box'>
              <span class='label-title'>{t('设备元数据')}</span>
              <div class='form-box mt-5'>
                <bk-switcher
                  size='large'
                  theme='primary'
                />
                <InfoTips
                  class='ml-12'
                  tips={t('该设置可以将采集设备的元数据信息补充至日志中')}
                />
                {renderDeviceMetadata()}
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
     * @param value
     * @returns
     */
    const handleConfirm = value => {
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
      if (!type) {
        return;
      }

      formData.value.target_node_type = type;
      formData.value.target_nodes = toTransformNode(nodes, type);
      console.log('formData.value', formData.value);
      // 触发 bk-form 的表单验证
      // this.$refs.formItemTarget.validate('change');
    };

    // 新增/修改采集
    const setCollection = () => {
      console.log('params', formData.value);
      loadingSave.value = true;
      const { index_set_name, ...rest } = formData.value;
      rest.collector_config_name = index_set_name;
      $http
        .request('collect/addCollection', {
          data: rest,
        })
        .then(res => {
          store.commit(`collect/${isUpdate.value ? 'updateCurCollect' : 'setCurCollect'}`, {
            ...formData.value,
            ...rest,
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
      setCollection();
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
        <MultilineRegDialog
          showDialog={showMultilineRegDialog.value}
          on-cancel={handleCancelMultilineReg}
        />
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
