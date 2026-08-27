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

import { Button, Input, Message, Sideslider, Switcher } from 'bkui-vue';
import { useI18n } from 'vue-i18n';

import { useAiResourceSelect } from '../../composables/use-ai-resource-select';
import { useRuleVerification } from '../../composables/use-rule-verification';
import { useSourceAnalysisRuleDetail } from '../../composables/use-source-analysis-rule-detail';
import { AiResourceEnum, ErrorKeyEnum, SidesliderTypeEnum } from '../../constants';
import { getAgents, getKnowledgeBases, getSkills } from '../../services/source-analysis-rule';
import AiResourceSelect from '../ai-resource-select/ai-resource-select';
import MatchRule from '../match-rule/match-rule';

import type { ConfirmPayload, SidesliderType } from '../../typings';
import type {
  IFilterField,
  IGetValueFnParams,
  IOptionsInfo,
  IWhereItem,
  TTagValueDisplayFormatter,
} from 'trace/components/retrieval-filter/typing';

import './analysis-config-sideslider.scss';

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
    /** 当前绑定项目名称 */
    projectName: {
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
    const { t } = useI18n();
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
      setConditions,
      setPriority,
      setEnabled,
    } = useSourceAnalysisRuleDetail();

    const { errors, clearError, validate } = useRuleVerification(detail);

    /** 智能体下拉（单选） */
    const agentSelect = useAiResourceSelect(getAgents);
    /** 知识库下拉（多选） */
    const knowledgeBaseSelect = useAiResourceSelect(getKnowledgeBases);
    /** Skill 下拉（多选） */
    const skillSelect = useAiResourceSelect(getSkills);
    /** 是否编辑态 */
    const isEdit = computed(() => props.type === SidesliderTypeEnum.EDIT);

    /**
     * @description 匹配规则条件变化
     * 更新规则详情中的 conditions，并提取所选告警策略 id 列表：
     * 调用父组件共享的 fetchStrategyDimensions 拉取策略维度候选值。
     */
    const handleMatchRuleConditionsChange = (where: IWhereItem[]) => {
      setConditions(where);
      clearError(ErrorKeyEnum.CONDITIONS);
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

    /**
     * @description 确认提交
     * 准备好提交参数后，连同 Promise 一同抛出 confirm 事件；
     * 父组件执行新增/更新接口后通过 resolve/reject 回传结果，
     * resolve 时自动关闭弹窗，reject 时保留弹窗，两种情况均重置 loading。
     */
    const handleConfirm = () => {
      if (!validate()) return;
      if (confirmLoading.value) return;

      // 准备提交参数：新增态取全量，编辑态取变更字段（conditions/priority/is_enabled 已落在 detail）
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

    watch(
      () => props.show,
      newVal => {
        if (!newVal) {
          resetState();
          // 清空 AI 相关资源下拉的残留状态（列表 / 搜索关键词 / 分页等），避免下次打开时显示旧数据
          agentSelect.reset();
          knowledgeBaseSelect.reset();
          skillSelect.reset();
          return;
        }
        // 规则只保存资源 id，选择器需要全量选项才能把已选 id 回填成名称与所属空间，
        // 因此弹窗一打开就预加载，而不是等下拉展开时才请求。
        agentSelect.ensureLoaded();
        knowledgeBaseSelect.ensureLoaded();
        skillSelect.ensureLoaded();
        if (isEdit.value && props.ruleId) {
          fetchDetail(props.ruleId);
        } else {
          initDetail();
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
                    value={detail.value?.conditions ?? []}
                    onUpdate:value={handleMatchRuleConditionsChange}
                  />
                )}
                {errors.value?.[ErrorKeyEnum.CONDITIONS] && (
                  <div class='form-item-error'>{errors.value[ErrorKeyEnum.CONDITIONS]}</div>
                )}
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
                      modelValue={detail.value?.priority}
                      type='number'
                      onUpdate:modelValue={(val: number | string) => {
                        setPriority(Number(val));
                        clearError(ErrorKeyEnum.PRIORITY);
                      }}
                    />
                  )}
                  {errors.value?.[ErrorKeyEnum.PRIORITY] && (
                    <div class='form-item-error'>{errors.value[ErrorKeyEnum.PRIORITY]}</div>
                  )}
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
                      modelValue={detail.value?.is_enabled}
                      theme='primary'
                      onChange={(val: boolean) => setEnabled(val)}
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
     * @description 渲染流程实例参数区域
     * 智能体（单选）、知识库 / Skill（多选）均以 bkui-vue Select 远程搜索下拉呈现，
     * 选中值经 setResourceIds 写回规则 detail，提交链路保持不变。
     */
    const renderProcessParams = () => {
      return (
        <div class='main-section process-params-section'>
          <div class='main-section-header'>
            <span class='main-section-title'>{t('流程实例参数')}</span>
            <div class='section-header-division' />
            <span class='main-section-subtitle'>
              {t('当前绑定流程')}：{props.projectName ?? '--'}
            </span>
          </div>
          <div class='main-section-content'>
            <div class='form-item'>
              <div class='form-item-label'>
                <span>{t('智能体')}</span>
                <span class='required-star'>*</span>
              </div>
              <div class='form-item-content'>
                {detailLoading.value ? (
                  <div
                    style='height: 32px'
                    class='skeleton-element'
                  />
                ) : (
                  <AiResourceSelect
                    footerText={t('新增智能体')}
                    loading={agentSelect.loading.value}
                    modelValue={detail.value?.agent_id || undefined}
                    multiple={false}
                    options={agentSelect.list.value}
                    onToggle={agentSelect.handleToggle}
                    onUpdate:modelValue={(val: string) => {
                      setResourceIds(AiResourceEnum.AGENT, val);
                      clearError(ErrorKeyEnum.AGENT);
                    }}
                  />
                )}
                {errors.value?.[ErrorKeyEnum.AGENT] && (
                  <div class='form-item-error'>{errors.value[ErrorKeyEnum.AGENT]}</div>
                )}
              </div>
            </div>
            <div class='form-item'>
              <div class='form-item-label'>
                <span>{t('知识库')}</span>
                <span class='required-star'>*</span>
              </div>
              <div class='form-item-content'>
                {detailLoading.value ? (
                  <div
                    style='height: 32px'
                    class='skeleton-element'
                  />
                ) : (
                  <AiResourceSelect
                    footerText={t('新增知识库')}
                    loading={knowledgeBaseSelect.loading.value}
                    modelValue={detail.value?.knowledge_base_ids ?? []}
                    multiple={true}
                    multipleMode='tag'
                    options={knowledgeBaseSelect.list.value}
                    selectedStyle='checkbox'
                    onToggle={knowledgeBaseSelect.handleToggle}
                    onUpdate:modelValue={(val: string[]) => {
                      setResourceIds(AiResourceEnum.KNOWLEDGE_BASE, val);
                      clearError(ErrorKeyEnum.KNOWLEDGE_BASE);
                    }}
                  />
                )}
                {errors.value?.[ErrorKeyEnum.KNOWLEDGE_BASE] && (
                  <div class='form-item-error'>{errors.value[ErrorKeyEnum.KNOWLEDGE_BASE]}</div>
                )}
              </div>
            </div>
            <div class='form-item'>
              <div class='form-item-label'>
                <span>{t('Skill')}</span>
                <span class='required-star'>*</span>
              </div>
              <div class='form-item-content'>
                {detailLoading.value ? (
                  <div
                    style='height: 32px'
                    class='skeleton-element'
                  />
                ) : (
                  <AiResourceSelect
                    footerText={t('新增Skill')}
                    loading={skillSelect.loading.value}
                    modelValue={detail.value?.skill_ids ?? []}
                    multiple={true}
                    multipleMode='tag'
                    options={skillSelect.list.value}
                    selectedStyle='checkbox'
                    onToggle={skillSelect.handleToggle}
                    onUpdate:modelValue={(val: string[]) => {
                      setResourceIds(AiResourceEnum.SKILL, val);
                      clearError(ErrorKeyEnum.SKILL);
                    }}
                  />
                )}
                {errors.value?.[ErrorKeyEnum.SKILL] && (
                  <div class='form-item-error'>{errors.value[ErrorKeyEnum.SKILL]}</div>
                )}
              </div>
            </div>
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

    return {
      handleMatchRuleConditionsChange,
      isEdit,
      renderBasicInfo,
      renderProcessParams,
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
            </div>
          ),
          footer: this.renderFooter,
        }}
      </Sideslider>
    );
  },
});
