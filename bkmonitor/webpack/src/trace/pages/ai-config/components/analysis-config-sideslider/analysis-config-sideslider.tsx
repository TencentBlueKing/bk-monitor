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
import { useMatchRuleFields } from '../../composables/use-match-rule-fields';
import { useResourceDialog } from '../../composables/use-resource-dialog';
import { useRuleBasicInfo } from '../../composables/use-rule-basic-info';
import { useSourceAnalysisRuleDetail } from '../../composables/use-source-analysis-rule-detail';
import { AiResourceEnum, RESOURCE_DIALOG_TITLE_MAP, SidesliderTypeEnum } from '../../constants';
import MatchRule from '../match-rule/match-rule';
import ResourceCollapseList from '../resource-collapse-list/resource-collapse-list';

import type { ConfirmPayload, SidesliderType } from '../../typings';
import type { IAgent, IKnowledgebase, ISkill } from '@blueking/ai-ui-sdk/types';

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
  },
  emits: {
    /** 抽屉显隐更新（v-model:show） */
    'update:show': (_v: boolean) => true,
    /** 确认提交，抛出提交参数与 Promise；父组件执行接口后 resolve/reject 控制 confirmLoading 与关闭 */
    confirm: (_payload: ConfirmPayload) => true,
  },
  setup(props, { emit }) {
    const { t } = useI18n();
    const {
      conditions,
      priority,
      isEnabled,
      errors,
      handleConditionsChange,
      handlePriorityChange,
      handleEnabledChange,
      validate,
    } = useRuleBasicInfo();
    const { fields: matchRuleFields, fetchFields: fetchMatchRuleFields } = useMatchRuleFields();

    watch(
      () => props.show,
      () => {
        if (props.show) {
          fetchMatchRuleFields();
        }
      }
    );
    /** 提交 confirmLoading */
    const confirmLoading = shallowRef(false);

    const {
      detail,
      fetchDetail,
      initDetail,
      resetState,
      getCreateParams,
      getChangedFields,
      handleAddResource,
      handleClearResources,
      handleRemoveResource,
    } = useSourceAnalysisRuleDetail();

    const { agents, skills, knowledgebases, fetchResources } = useAiResources();

    const {
      dialogIsShow,
      dialogModule,
      dialogMultiple,
      handleOpenResourceDialog,
      handleCloseResourceDialog,
      handleDialogConfirm,
    } = useResourceDialog({
      addResource: handleAddResource,
    });

    /** 是否编辑态 */
    const isEdit = computed(() => props.type === SidesliderTypeEnum.EDIT);
    /** 根据当前规则中的资源 id 在全量资源池中匹配完整数据 */
    const selectedAgent = computed<IAgent[]>(() => {
      const rule = detail.value;
      if (!rule?.agent_id) return [];
      const agent = agents.value.find(item => String(item.id) === rule.agent_id);
      return agent ? [agent] : [];
    });
    const selectedSkills = computed<ISkill[]>(() => {
      const rule = detail.value;
      if (!rule?.skill_ids?.length) return [];
      return skills.value.filter(item => rule.skill_ids.includes(String(item.id)));
    });
    const selectedKnowledgebases = computed<IKnowledgebase[]>(() => {
      const rule = detail.value;
      if (!rule?.knowledge_base_ids?.length) return [];
      return knowledgebases.value.filter(item => rule.knowledge_base_ids.includes(String(item.id)));
    });

    // TODO: 接入真实空间 / 用户 / 接口前缀配置
    const dialogEnv = {
      spaceId: '',
      memberUrl: '',
      spaces: [],
    };

    /**
     * @description 提交前校验必填字段不为空
     * @returns {boolean} 校验是否通过
     */
    const validateFields = (): boolean => {
      const data = detail.value;
      const rules: Array<{ message: string; valid: boolean }> = [
        { valid: !!data, message: t('数据未就绪，请稍后重试') },
        { valid: data?.priority != null, message: t('优先级不能为空') },
        { valid: !!data?.conditions?.length, message: t('匹配条件不能为空') },
      ];
      const failed = rules.find(rule => !rule.valid);
      if (failed) {
        Message({ theme: 'error', message: failed.message });
        return false;
      }
      return true;
    };

    /**
     * @description 确认提交
     * 准备好提交参数后，连同 Promise 一同抛出 confirm 事件；
     * 父组件执行新增/更新接口后通过 resolve/reject 回传结果，
     * resolve 时自动关闭弹窗，reject 时保留弹窗，两种情况均重置 loading。
     */
    const handleConfirm = () => {
      if (!validate()) return;
      if (confirmLoading.value) return;
      if (!validateFields()) return;

      // 准备提交参数：新增态取全量，编辑态取变更字段
      const params = isEdit.value ? getChangedFields() : getCreateParams();
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
                <MatchRule
                  fields={matchRuleFields.value}
                  value={conditions.value}
                  onUpdate:value={handleConditionsChange}
                />
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
                  <Input
                    style='width: 340px'
                    modelValue={priority.value}
                    type='number'
                    onUpdate:modelValue={handlePriorityChange}
                  />
                  {errors.value?.priority && <div class='form-item-error'>{errors.value.priority}</div>}
                </div>
              </div>
              <div class='form-item'>
                <div class='form-item-label'>
                  <span>{t('状态')}</span>
                  <span class='required-star'>*</span>
                </div>
                <div class='form-item-content'>
                  <Switcher
                    class='mt-6'
                    modelValue={isEnabled.value}
                    onChange={handleEnabledChange}
                  />
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
          count={detail.value?.agent_id ? 1 : 0}
          emptyText={t('暂无关联智能体')}
          headerTip={t('可绑定本空间有使用权限的智能体')}
          title={t('智能体')}
          onAdd={() => handleOpenResourceDialog(Module.Agent)}
          onClear={() => {
            handleClearResources(AiResourceEnum.AGENT);
          }}
        >
          {selectedAgent.value.map(agent => (
            <RenderAgentCard
              key={agent.id}
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
          count={selectedSkills.value.length}
          emptyText={t('暂无关联Skill')}
          headerTip={t('可绑定本空间有使用权限的 Skill')}
          title={t('Skill')}
          onAdd={() => handleOpenResourceDialog(Module.Skill)}
          onClear={() => {
            handleClearResources(AiResourceEnum.SKILL);
          }}
        >
          {selectedSkills.value.map(item => (
            <RenderSkillCard
              key={item.id}
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
          count={selectedKnowledgebases.value.length}
          emptyText={t('暂无关联知识库')}
          headerTip={t('可绑定本空间有使用权限的知识库')}
          title={t('知识库')}
          onAdd={() => handleOpenResourceDialog(Module.Knowledgebase)}
          onClear={() => {
            handleClearResources(AiResourceEnum.KNOWLEDGE_BASE);
          }}
        >
          {selectedKnowledgebases.value.map(item => (
            <RenderKnowledgebaseCard
              key={item.id}
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
          agents={selectedAgent.value}
          apiPrefix={AI_UI_SDK_API_PREFIX}
          isShow={dialogIsShow.value}
          knowledgebases={selectedKnowledgebases.value}
          memberUrl={dialogEnv.memberUrl}
          module={dialogModule.value}
          multiple={dialogMultiple.value}
          skills={selectedSkills.value}
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

    watch(
      () => props.show,
      newVal => {
        if (!newVal) {
          handleCloseResourceDialog();
          resetState();
          return;
        }
        fetchResources();
        if (isEdit.value && props.ruleId) {
          fetchDetail(props.ruleId);
        } else {
          initDetail();
        }
      },
      { immediate: true }
    );

    return {
      conditions,
      priority,
      isEnabled,
      errors,
      handleConditionsChange,
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
