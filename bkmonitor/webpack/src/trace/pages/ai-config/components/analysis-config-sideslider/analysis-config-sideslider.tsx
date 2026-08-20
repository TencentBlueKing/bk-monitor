/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 *
 * Copyright (C) 2017-2025 Tencent.  All rights reserved.
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
import { type PropType, computed, defineComponent, shallowRef, watch } from 'vue';

import {
  RenderAgentCard,
  RenderKnowledgebaseCard,
  RenderResourceDialog,
  RenderSkillCard,
} from '@blueking/ai-ui-sdk/components';
import { Module, ResourceCardType } from '@blueking/ai-ui-sdk/enums';
import { Button, Input, Message, Sideslider, Switcher } from 'bkui-vue';
import { useI18n } from 'vue-i18n';

import { useAiResources } from '../../composables/use-ai-resources';
import { type IResourceDialogConfirmData, useResourceDialog } from '../../composables/use-resource-dialog';
import { useRuleBasicInfo } from '../../composables/use-rule-basic-info';
import { useSourceAnalysisRuleDetail } from '../../composables/use-source-analysis-rule-detail';
import { AiResourceEnum, MODULE_CONFIG, RESOURCE_DIALOG_TITLE_MAP, SidesliderTypeEnum } from '../../constants';
import MatchRule from '../match-rule/match-rule';
import ResourceCollapseList from '../resource-collapse-list/resource-collapse-list';

import type { AiResourceType, ConfirmPayload, SidesliderType, SourceAnalysisRuleDto } from '../../typings';
import type { IAgent, IKnowledgebase } from '@blueking/ai-ui-sdk/types';
import type {
  IFilterField,
  IGetValueFnParams,
  IOptionsInfo,
  IWhereItem,
  TTagValueDisplayFormatter,
} from 'trace/components/retrieval-filter/typing';

import './analysis-config-sideslider.scss';

/** AI SDK API 前缀 */
const AI_UI_SDK_API_PREFIX = '';

/**
 * @description 新增/编辑绑定侧弹窗
 * 用于源码 AI 分析中告警策略与流程实例的绑定关系配置。
 */
export default defineComponent({
  name: 'AnalysisConfigSideslider',
  props: {
    /** 是否展示抽屉 */
    show: {
      type: Boolean,
      default: false,
    },
    /** 当前绑定流程名称 */
    processName: {
      type: String,
      default: '',
    },
    /** 操作类型：新增 / 编辑 */
    type: {
      type: String as PropType<SidesliderType>,
      default: SidesliderTypeEnum.ADD,
    },
    /** 当前规则 id，编辑态必传 */
    ruleId: {
      type: Number,
    },
    /** 匹配规则字段列表（由父组件共享） */
    matchRuleFields: {
      type: Array as PropType<IFilterField[]>,
      default: () => [],
    },
    /** 匹配规则字段加载状态（由父组件共享） */
    matchRuleFieldsLoading: {
      type: Boolean,
      default: false,
    },
    /** 匹配规则候选值获取函数（由父组件共享） */
    getMatchRuleValueFn: {
      type: Function as PropType<(params: IGetValueFnParams) => Promise<IOptionsInfo>>,
      default: () => Promise.resolve({ count: 0, list: [] }),
    },
    /** 已选条件 tag 的 value 显示格式化函数（由父组件共享） */
    tagValueDisplayFormatter: {
      type: Function as PropType<TTagValueDisplayFormatter>,
      default: (val: boolean | number | string) => `${val}`,
    },
    /** 拉取策略维度候选值（由父组件共享，hook 提供，无 loading） */
    fetchStrategyDimensions: {
      type: Function as PropType<(strategyIds: (number | string)[]) => void>,
      default: () => {},
    },
  },
  emits: {
    /** 抽屉显隐更新（v-model:show） */
    'update:show': (_v: boolean) => true,
    /** 确认提交，抛出提交参数与 Promise；父组件执行接口后 resolve/reject 控制 confirmLoading 与关闭 */
    confirm: (_payload: ConfirmPayload) => true,
  },
  setup(props, { emit }) {
    // TODO: 接入真实空间 / 用户 / 接口前缀配置
    const dialogEnv = {
      spaceId: '',
      memberUrl: '',
      spaces: [],
    };
    const { t } = useI18n();
    const {
      conditions,
      priority,
      isEnabled,
      errors,
      getFormData: getBasicInfoFormData,
      setFormData: setBasicInfoFormData,
      reset: resetBasicInfo,
      handleConditionsChange,
      handlePriorityChange,
      handleEnabledChange,
      validate: validateBasicInfo,
    } = useRuleBasicInfo();

    /**
     * @description 匹配规则条件变化
     * 更新表单状态，并提取所选告警策略 id 列表：
     * 抛出 strategy-change 事件，同时调用父组件共享的 fetchStrategyDimensions 拉取策略维度候选值。
     */
    const handleMatchRuleConditionsChange = (where: IWhereItem[]) => {
      handleConditionsChange(where);
      const strategyIds: (number | string)[] = [];
      for (const item of where || []) {
        if (item.key === 'alert.strategy_id') {
          for (const value of item.value) {
            strategyIds.push(value as number | string);
          }
        }
      }
      props.fetchStrategyDimensions?.(strategyIds);
    };

    /** 提交 confirmLoading */
    const confirmLoading = shallowRef(false);

    const {
      detail,
      loading: detailLoading,
      fetchDetail,
      initDetail,
      resetState,
      getCreateParams,
      getChangedFields,
      setResourceIds,
      clearResourceIds,
      removeResourceId,
    } = useSourceAnalysisRuleDetail();

    const { agents, skills, knowledgebases, getResourceByType, fetchAllResources, resetAllResources } =
      useAiResources();

    const { dialogIsShow, dialogModule, dialogMultiple, handleOpenResourceDialog, handleCloseResourceDialog } =
      useResourceDialog();

    /** 是否编辑态 */
    const isEdit = computed(() => props.type === SidesliderTypeEnum.EDIT);

    /**
     * @description 弹窗确认：按当前模块从确认数据中提取资源值，写回规则并同步已选资源详情后关闭弹窗
     * @param {IResourceDialogConfirmData} data 弹窗回传的已选资源
     */
    const handleDialogConfirm = (data: IResourceDialogConfirmData) => {
      const config = MODULE_CONFIG[dialogModule.value];
      if (config) {
        const items = data[config.field];
        const value = config.single ? (items[0] ? String(items[0].id) : '') : items.map(item => String(item.id));
        setResourceIds(config.resource, value as SourceAnalysisRuleDto[AiResourceType]);
        getResourceByType(config.resource).setResources(items);
      }
      handleCloseResourceDialog();
    };

    /**
     * @description 删除资源：同步移除规则中的资源 ID 与已选资源详情
     */
    const handleRemoveResource = (resourceType: AiResourceType, resourceId: string) => {
      removeResourceId(resourceType, resourceId);
      getResourceByType(resourceType).removeResource(resourceId);
    };

    /**
     * @description 清空资源：同步清空规则中的资源 ID 与已选资源详情
     */
    const handleClearResources = (resourceType: AiResourceType) => {
      clearResourceIds(resourceType);
      getResourceByType(resourceType).clearResources();
    };

    /**
     * @description 确认提交
     * 准备好提交参数后，连同 Promise 一同抛出 confirm 事件；
     * 父组件执行新增/更新接口后通过 resolve/reject 回传结果，
     * resolve 时自动关闭弹窗，reject 时保留弹窗，两种情况均重置 loading。
     */
    const handleConfirm = () => {
      if (!validateBasicInfo()) return;
      if (confirmLoading.value) return;

      // 准备提交参数：新增态取全量，编辑态取变更字段
      const baseInfoParams = getBasicInfoFormData();
      const params = isEdit.value ? getChangedFields(baseInfoParams) : getCreateParams(baseInfoParams);
      if (!params) return;
      if (isEdit.value && !Object.keys(params).length) {
        Message({ theme: 'warning', message: t('数据未变更') });
        return;
      }

      confirmLoading.value = true;

      // 创建 Promise 供父组件回传提交结果
      let resolveFn: () => void = () => {};
      let rejectFn: (err?: unknown) => void = () => {};
      const promise = new Promise<void>((res, rej) => {
        resolveFn = res;
        rejectFn = rej;
      });

      // 副作用链：Promise 完成后控制 confirmLoading 与弹窗显隐
      promise.finally(() => {
        confirmLoading.value = false;
      });

      emit('confirm', { params, promise, resolve: resolveFn, reject: rejectFn });
    };

    watch(
      () => props.show,
      newVal => {
        if (!newVal) {
          handleCloseResourceDialog();
          resetState();
          resetBasicInfo();
          resetAllResources();
          return;
        }
        if (isEdit.value && props.ruleId) {
          fetchDetail(props.ruleId, detail => {
            setBasicInfoFormData(detail);
            fetchAllResources(detail);
          });
        } else {
          resetAllResources();
          initDetail(detail => {
            setBasicInfoFormData(detail);
          });
        }
      },
      { immediate: true }
    );

    /**
     * @description 渲染基础信息区域
     */
    const renderBasicInfo = () => {
      return (
        <div class='main-section'>
          <div class='main-section-header'>
            <div class='main-section-title'>{t('基础信息')}</div>
          </div>
          <div class='main-section-content'>
            <div class='form-item'>
              <div class='form-item-label'>
                <span>{t('告警策略匹配规则')}</span>
                <span class='required-star'>*</span>
              </div>
              <div class='form-item-content'>
                {props.matchRuleFieldsLoading || detailLoading.value ? (
                  <div
                    style='height: 48px'
                    class='skeleton-element'
                  />
                ) : (
                  <MatchRule
                    fields={props.matchRuleFields}
                    getValueFn={props.getMatchRuleValueFn}
                    readonly={!!detail.value?.is_default}
                    tagValueDisplayFormatter={props.tagValueDisplayFormatter}
                    value={conditions.value}
                    onUpdate:value={handleMatchRuleConditionsChange}
                  />
                )}
                {errors.value?.conditions && <div class='form-item-error'>{errors.value.conditions}</div>}
              </div>
            </div>
            <div class='form-items mt-24'>
              <div class='form-item'>
                <div class='form-item-label'>
                  <span>{t('优先级')}</span>
                  <span class='required-star'>*</span>
                  <span class='form-item-label-tip'>
                    <span class='icon-monitor icon-hint' />
                    {t('数值越高，优先级越高，最大值为10000')}
                  </span>
                </div>
                <div class='form-item-content'>
                  {detailLoading.value ? (
                    <div
                      style='width: 340px;height: 32px'
                      class='skeleton-element'
                    />
                  ) : (
                    <Input
                      style='width: 340px'
                      disabled={!!detail.value?.is_default}
                      modelValue={priority.value}
                      type='number'
                      onUpdate:modelValue={handlePriorityChange}
                    />
                  )}
                  {errors.value?.priority && <div class='form-item-error'>{errors.value.priority}</div>}
                </div>
              </div>
              <div class='form-item'>
                <div class='form-item-label'>
                  <span>{t('状态')}</span>
                  <span class='required-star'>*</span>
                </div>
                <div class='form-item-content'>
                  {detailLoading.value ? (
                    <div
                      style='width: 38px;height: 20px'
                      class='skeleton-element mt-6'
                    />
                  ) : (
                    <Switcher
                      class='mt-6'
                      modelValue={isEnabled.value}
                      theme='primary'
                      onChange={handleEnabledChange}
                    />
                  )}
                </div>
              </div>
            </div>
          </div>
        </div>
      );
    };

    /**
     * @description 渲染智能体折叠面板
     */
    const renderAgentPanel = () => {
      return (
        <ResourceCollapseList
          count={agents.value.length}
          emptyText={t('暂无关联智能体')}
          headerTip={t('可绑定本空间有使用权限的智能体')}
          title={t('智能体')}
          onAdd={() => handleOpenResourceDialog(Module.Agent)}
          onClear={() => {
            handleClearResources(AiResourceEnum.AGENT);
          }}
        >
          {agents.value.map(agent => (
            <RenderAgentCard
              key={agent.id}
              class='agent-card'
              agent={agent}
              apiPrefix={AI_UI_SDK_API_PREFIX}
              isShowOperation={true}
              showDeleteTips={false}
              type={ResourceCardType.Info}
              onDelete={(agent: IAgent) => {
                handleRemoveResource(AiResourceEnum.AGENT, String(agent.id));
              }}
            />
          ))}
        </ResourceCollapseList>
      );
    };

    /**
     * @description 渲染 Skill 折叠面板
     */
    const renderSkillPanel = () => {
      return (
        <ResourceCollapseList
          count={skills.value.length}
          emptyText={t('暂无关联Skill')}
          headerTip={t('可绑定本空间有使用权限的 Skill')}
          title={t('Skill')}
          onAdd={() => handleOpenResourceDialog(Module.Skill)}
          onClear={() => {
            handleClearResources(AiResourceEnum.SKILL);
          }}
        >
          {skills.value.map(item => (
            <RenderSkillCard
              key={item.id}
              class='skill-card'
              apiPrefix={AI_UI_SDK_API_PREFIX}
              isShowOperation={true}
              showDeleteTips={false}
              skill={item}
              type={ResourceCardType.Info}
              onDelete={() => handleRemoveResource(AiResourceEnum.SKILL, String(item.id))}
            />
          ))}
        </ResourceCollapseList>
      );
    };

    /**
     * @description 渲染知识库折叠面板
     */
    const renderKnowledgeBasePanel = () => {
      return (
        <ResourceCollapseList
          count={knowledgebases.value.length}
          emptyText={t('暂无关联知识库')}
          headerTip={t('可绑定本空间有使用权限的知识库')}
          title={t('知识库')}
          onAdd={() => handleOpenResourceDialog(Module.Knowledgebase)}
          onClear={() => {
            handleClearResources(AiResourceEnum.KNOWLEDGE_BASE);
          }}
        >
          {knowledgebases.value.map(item => (
            <RenderKnowledgebaseCard
              key={item.id}
              class='knowledgebase-card'
              apiPrefix={AI_UI_SDK_API_PREFIX}
              isShowOperation={true}
              knowledgebase={item}
              showDeleteTips={false}
              type={ResourceCardType.Info}
              onDelete={(knowledgebase: IKnowledgebase) => {
                handleRemoveResource(AiResourceEnum.KNOWLEDGE_BASE, String(knowledgebase.id));
              }}
            />
          ))}
        </ResourceCollapseList>
      );
    };

    /**
     * @description 渲染流程实例参数区域
     * 折叠面板复用 trace-explore 的 chart-collapse 组件（经 resource-collapse-list 封装）。
     */
    const renderProcessParams = () => {
      return (
        <div class='main-section process-params-section'>
          <div class='main-section-header'>
            <span class='main-section-title'>{t('流程实例参数')}</span>
            <div class='section-header-division' />
            <span class='main-section-subtitle'>
              {t('当前绑定流程')}：{props.processName ?? '--'}
            </span>
          </div>
          <div class='main-section-content'>
            {renderAgentPanel()}
            {renderKnowledgeBasePanel()}
            {renderSkillPanel()}
          </div>
        </div>
      );
    };

    /**
     * @description 渲染底部操作栏
     */
    const renderFooter = () => {
      return (
        <div class='analysis-config-sideslider-footer'>
          <Button
            loading={confirmLoading.value}
            theme='primary'
            onClick={handleConfirm}
          >
            {t('确定')}
          </Button>
          <Button
            disabled={confirmLoading.value}
            onClick={() => {
              emit('update:show', false);
            }}
          >
            {t('取消')}
          </Button>
        </div>
      );
    };

    /**
     * @description 渲染资源选择弹窗
     */
    const renderResourceDialog = () => {
      return (
        <RenderResourceDialog
          agents={agents.value}
          apiPrefix={AI_UI_SDK_API_PREFIX}
          isShow={dialogIsShow.value}
          knowledgebases={knowledgebases.value}
          memberUrl={dialogEnv.memberUrl}
          module={dialogModule.value}
          multiple={dialogMultiple.value}
          skills={skills.value}
          spaceId={dialogEnv.spaceId}
          spaces={dialogEnv.spaces}
          title={RESOURCE_DIALOG_TITLE_MAP[dialogModule.value]}
          username={window.username}
          onConfirm={handleDialogConfirm}
          onUpdate:isShow={(v: boolean) => {
            dialogIsShow.value = v;
          }}
        />
      );
    };

    return {
      conditions,
      priority,
      isEnabled,
      errors,
      handleMatchRuleConditionsChange,
      handlePriorityChange,
      handleEnabledChange,
      isEdit,
      renderBasicInfo,
      renderProcessParams,
      renderResourceDialog,
      renderFooter,
    };
  },
  render() {
    return (
      <Sideslider
        width={960}
        extCls='analysis-config-sideslider'
        isShow={this.show}
        renderDirective='if'
        quickClose
        onUpdate:isShow={(v: boolean) => this.$emit('update:show', v)}
      >
        {{
          header: () => (
            <span class='analysis-config-sideslider-header-title'>
              {this.isEdit ? this.$t('编辑绑定') : this.$t('新增绑定')}
            </span>
          ),
          default: () => (
            <div class='analysis-config-sideslider-main'>
              {this.renderBasicInfo()}
              {this.renderProcessParams()}
              {this.renderResourceDialog()}
            </div>
          ),
          footer: this.renderFooter,
        }}
      </Sideslider>
    );
  },
});
