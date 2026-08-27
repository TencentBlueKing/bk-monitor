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
import { computed, defineComponent, nextTick, onMounted, shallowRef } from 'vue';

import { Button, InfoBox, Input, Message, Select } from 'bkui-vue';
import { Plus } from 'bkui-vue/lib/icon';
import OverflowTips from 'trace/directive/overflow-tips';
import { useI18n } from 'vue-i18n';

import { useBkciProjectsSelect } from '../../composables/use-bkci-projects-select';
import { useBkciRepositoriesSelect } from '../../composables/use-bkci-repositories-select';
import { useMatchRuleFields } from '../../composables/use-match-rule-fields';
import { SidesliderTypeEnum } from '../../constants';
import { getSourceAnalysisConfigData, setSaveSourceAnalysisConfig } from '../../services/ai-config';
import {
  createSourceAnalysisRule,
  deleteSourceAnalysisRule,
  listSourceAnalysisRules,
  updateSourceAnalysisRule,
} from '../../services/source-analysis-rule';
import AnalysisConfigSideslider from '../analysis-config-sideslider/analysis-config-sideslider';
import AnalysisRuleTable from '../analysis-rule-table/analysis-rule-table';

import type { ConfirmPayload, CreateSourceAnalysisRuleVo, SidesliderType, SourceAnalysisRuleDto } from '../../typings';

import './source-code-analysis.scss';

/**
 * @description 源码 AI 分析
 */
export default defineComponent({
  name: 'SourceCodeAnalysis',
  directives: {
    OverflowTips,
  },
  setup(_props) {
    const { t } = useI18n();
    /** 蓝盾项目 id */
    const bkciProjectId = shallowRef('');
    /** 源码仓库别名 */
    const repositoryAlias = shallowRef('');
    /**
     * 初始化完成后保存的初始快照，用于判断用户是否已修改
     * 仅需关注 bkciProjectId 与 repositoryAlias 两个表单字段
     */
    const initialBkciProjectId = shallowRef<null | string>(null);
    const initialRepositoryAlias = shallowRef<null | string>(null);
    /** 蓝盾项目下拉选择 */
    const projectsSelect = useBkciProjectsSelect();
    /** 源码仓库下拉选择（依赖蓝盾项目） */
    const repositoriesSelect = useBkciRepositoriesSelect({ bkciProjectId });
    /** 源码分析规则列表（当前为 mock 数据，后续接入真实接口） */
    const sourceAnalysisRules = shallowRef<SourceAnalysisRuleDto[]>([]);

    /** 规则搜索关键字 */
    const searchValue = shallowRef('');

    /** 新增绑定侧弹窗显隐状态 */
    const showBindModal = shallowRef(false);
    /** 侧弹窗操作类型：新增 / 编辑 */
    const sidesliderType = shallowRef<SidesliderType>(SidesliderTypeEnum.ADD);
    /** 编辑态当前规则 id */
    const editRuleId = shallowRef<number>();

    /** 蓝盾项目必填校验错误提示 */
    const projectErrMsg = shallowRef('');
    /** 源码仓库必填校验错误提示 */
    const repositoryErrMsg = shallowRef('');
    /** 初始化加载配置 loading（用于两个选择器位置骨架屏占位） */
    const configLoading = shallowRef(false);
    /** 规则列表加载中 */
    const rulesLoading = shallowRef(false);
    const saveLoading = shallowRef(false);

    /** 匹配规则字段与候选值（与侧弹窗共享） */
    const {
      fields: matchRuleFields,
      fetchAllData: fetchMatchRuleFields,
      fetchStrategyDimensions: fetchMatchRuleStrategyDimensions,
      getValueFn: getMatchRuleValueFn,
      loading: matchRuleFieldsLoading,
      tagValueDisplayFormatter: getMatchRuleTagValueDisplayFormatter,
    } = useMatchRuleFields();

    /**
     * @description 统一控制侧弹窗显隐，并在关闭时重置操作类型与规则 id
     * @param show 是否展示
     * @param config 打开时携带的操作类型与规则 id（关闭时无需传）
     * @param config.type 侧弹窗操作类型，缺省时默认为新增
     * @param config.ruleId 编辑态下当前规则 id，新增态不传
     */
    const handleRuleSliderChange = (
      show: boolean,
      config?: {
        ruleId?: number;
        type?: SidesliderType;
      }
    ) => {
      sidesliderType.value = config?.type ?? SidesliderTypeEnum.ADD;
      editRuleId.value = config?.ruleId;
      showBindModal.value = show;
    };

    /**
     * @description 提交绑定
     * 侧弹窗准备好参数后抛出，父组件按 新增/编辑 态执行接口，
     * 成功后 resolve 并关闭弹窗，失败 reject 保留弹窗。
     * @param payload 侧弹窗抛出的提交载荷
     * @param payload.params 新增/编辑规则接口所需参数
     * @param payload.resolve 提交成功回调，通知侧弹窗关闭 loading
     * @param payload.reject 提交失败回调，通知侧弹窗保留并恢复按钮态
     */
    const handleBindConfirm = async (payload: ConfirmPayload) => {
      const isEditMode = sidesliderType.value === SidesliderTypeEnum.EDIT;
      try {
        if (isEditMode && editRuleId.value) {
          await updateSourceAnalysisRule(editRuleId.value, payload.params as Partial<CreateSourceAnalysisRuleVo>);
          Message({ theme: 'success', message: t('编辑成功') });
        } else {
          await createSourceAnalysisRule(payload.params as CreateSourceAnalysisRuleVo);
          Message({ theme: 'success', message: t('新增成功') });
        }
        payload.resolve();
        handleRuleSliderChange(false);
        handleFetchRules();
      } catch {
        payload.reject();
        Message({ theme: 'error', message: isEditMode ? t('编辑失败') : t('新增失败') });
      }
    };

    /**
     * @description 保存配置，校验必填项
     */
    const handleSaveConfig = async () => {
      projectErrMsg.value = bkciProjectId.value ? '' : t('必填项');
      repositoryErrMsg.value = repositoryAlias.value ? '' : t('必填项');
      if (!bkciProjectId.value || !repositoryAlias.value || saveLoading.value) return false;
      saveLoading.value = true;
      const success = await setSaveSourceAnalysisConfig({
        bkci_project_id: bkciProjectId.value,
        repository_alias: repositoryAlias.value,
      })
        .then(() => true)
        .catch(() => false);
      saveLoading.value = false;
      if (success) {
        Message({ theme: 'success', message: t('保存成功') });
        // 保存成功后更新初始快照，使 isEdited 归位为未编辑状态
        initialBkciProjectId.value = `${bkciProjectId.value}`;
        initialRepositoryAlias.value = `${repositoryAlias.value}`;
      }
      return success;
    };

    /**
     * @description 初始化加载：查询已保存的源码分析配置并回填到两个选择器
     */
    const handleInitConfig = async () => {
      configLoading.value = true;
      try {
        const data = await getSourceAnalysisConfigData().catch(() => null);
        bkciProjectId.value = data?.bkci_project_id || '';
        repositoryAlias.value = data?.repository_alias || '';
        // 初始化加载完成后记录初始快照，作为是否编辑过的基线
        initialBkciProjectId.value = `${bkciProjectId.value}`;
        initialRepositoryAlias.value = `${repositoryAlias.value}`;
        // 已保存的配置只有项目 id 与仓库别名，先加载全量选项才能把它们展示成可读名称；
        // 仓库列表要等项目变更的 watch 清空后再拉，避免刚写入的数据被清掉。
        projectsSelect.fetchData();
        if (bkciProjectId.value) {
          nextTick(() => repositoriesSelect.fetchData());
        }
      } finally {
        configLoading.value = false;
      }
    };

    /**
     * @description 获取源码分析规则列表
     */
    const handleFetchRules = async () => {
      rulesLoading.value = true;
      try {
        const rules = await listSourceAnalysisRules().catch(() => []);
        sourceAnalysisRules.value = rules ?? [];
      } finally {
        rulesLoading.value = false;
      }
    };

    /**
     * @description 清空规则搜索关键字
     */
    const handleClearSearch = () => {
      searchValue.value = '';
    };

    /**
     * @description 蓝盾项目下拉展开/收起：展开时清空该校验错误
     */
    const handleProjectsToggle = (val: boolean) => {
      if (val) {
        projectErrMsg.value = '';
      }
      projectsSelect.handleToggle(val);
    };

    /**
     * @description 源码仓库下拉展开/收起：展开时清空该校验错误
     */
    const handleRepositoriesToggle = (val: boolean) => {
      if (val) {
        repositoryErrMsg.value = '';
      }
      repositoriesSelect.handleToggle(val);
    };

    /**
     * 当前表单是否相对初始快照被修改：仅判断 bkciProjectId / repositoryAlias
     * 初始快照在 handleInitConfig 完成后写入，初始化前视作未编辑
     */
    const isEdited = computed(() => {
      if (initialBkciProjectId.value === null || initialRepositoryAlias.value === null) return false;
      return (
        `${bkciProjectId.value}` !== `${initialBkciProjectId.value}` ||
        `${repositoryAlias.value}` !== `${initialRepositoryAlias.value}`
      );
    });

    /** 规则局部更新（启停等）：将更新后的规则回写到列表对应项 */
    const handleTableUpdateRule = (rule: SourceAnalysisRuleDto) => {
      sourceAnalysisRules.value = sourceAnalysisRules.value.map(item => (item.id === rule.id ? rule : item));
    };

    /** 删除规则：二次确认后调用删除接口并同步移除列表项（默认策略不可删除） */
    const handleDeleteRule = (rule: SourceAnalysisRuleDto) => {
      InfoBox({
        title: t('确定删除此规则'),
        beforeClose: action => {
          console.log(action);
          if (action === 'confirm') {
            return new Promise(resolve => {
              deleteSourceAnalysisRule(rule.id)
                .then(() => {
                  resolve(true);
                  sourceAnalysisRules.value = sourceAnalysisRules.value.filter(item => item.id !== rule.id);
                })
                .catch(() => {
                  resolve(false);
                });
            });
          }
          return true;
        },
      });
    };

    const handleChangeBkciProjectId = val => {
      bkciProjectId.value = val;
      repositoryAlias.value = '';
    };

    onMounted(() => {
      handleInitConfig();
      handleFetchRules();
      fetchMatchRuleFields();
    });

    return {
      t,
      showBindModal,
      sidesliderType,
      editRuleId,
      sourceAnalysisRules,
      searchValue,
      bkciProjectId,
      repositoryAlias,
      projectErrMsg,
      repositoryErrMsg,
      configLoading,
      rulesLoading,
      /** 蓝盾项目下拉 */
      bkciProjects: projectsSelect.list,
      projectsLoading: projectsSelect.loading,
      handleProjectsToggle,
      /** 源码仓库下拉 */
      bkciRepositories: repositoriesSelect.list,
      repositoriesLoading: repositoriesSelect.loading,
      handleRepositoriesToggle,
      handleRuleSliderChange,
      handleBindConfirm,
      handleSaveConfig,
      handleClearSearch,
      handleTableUpdateRule,
      handleDeleteRule,
      matchRuleFields,
      getMatchRuleValueFn,
      matchRuleFieldsLoading,
      getMatchRuleTagValueDisplayFormatter,
      fetchMatchRuleStrategyDimensions,
      saveLoading,
      handleChangeBkciProjectId,
      save: handleSaveConfig,
      isEdited,
    };
  },
  render() {
    type TCardItem = {
      content: () => JSX.Element;
      description: (() => JSX.Element) | string;
      icon: (() => JSX.Element) | string;
      title: (() => JSX.Element) | string;
    };
    const cardItem = (params: TCardItem, key: string) => {
      const title = typeof params.title === 'function' ? params.title() : params.title;
      const description = typeof params.description === 'function' ? params.description() : params.description;
      const icon = typeof params.icon === 'function' ? params.icon() : params.icon;
      return (
        <div
          key={key}
          class='card-item-wrap'
        >
          <div class='top-wrap'>
            <div class='icon-wrap'>{icon}</div>
            <div class='title-wrap'>
              <div class='title'>{title}</div>
              <div class='description'>{description}</div>
            </div>
          </div>
          <div class='bottom-wrap'>{params.content()}</div>
        </div>
      );
    };
    /**
     * @description 渲染表单项（label + content）
     * @param params.label 表单项标签文案
     * @param params.key 表单项唯一 key
     * @param params.content 表单项内容渲染函数
     */
    const formItem = (params: { content: () => JSX.Element; err?: string; key: string; label: string }) => {
      return (
        <div
          key={params.key}
          class='form-item'
        >
          <div class='label'>
            <span>{params.label}</span>
          </div>
          <div class={['content', { 'has-err': !!params.err }]}>
            {params.content()}
            {params.err ? <div class='err-msg'>{params.err}</div> : null}
          </div>
        </div>
      );
    };
    return (
      <div class='ai-config-source-code-analysis'>
        {cardItem(
          {
            icon: () => <span class='icon-monitor icon-storehouse' />,
            title: this.t('源码仓库关联'),
            description: this.t('关联后，告警中心的 AI 分析可基于蓝盾构建与 Git 变更进行'),
            content: () => (
              <div class='form-items'>
                {formItem({
                  label: this.t('蓝盾项目'),
                  content: () =>
                    this.configLoading ? (
                      <div class='select-loading-skeleton'>
                        <div class='skeleton-element' />
                      </div>
                    ) : (
                      <Select
                        popoverOptions={{
                          extCls: 'ai-config-source-code-analysis-popover',
                        }}
                        customContent={this.projectsLoading}
                        loading={this.projectsLoading}
                        modelValue={this.bkciProjectId}
                        multiple={false}
                        noDataText={this.projectsLoading ? this.t('加载中...') : this.t('无数据')}
                        filterable
                        onToggle={this.handleProjectsToggle}
                        onUpdate:modelValue={val => this.handleChangeBkciProjectId(val)}
                      >
                        {/* 首次加载/搜索时显示骨架屏占位，避免下拉面板空白闪烁 */}
                        {this.projectsLoading ? (
                          <div style='padding: 0 8px;'>
                            {new Array(4).fill(null).map((_item, index) => (
                              <div
                                key={index}
                                style='height: 24px; margin: 4px 0;'
                                class='skeleton-element'
                              />
                            ))}
                          </div>
                        ) : (
                          this.bkciProjects.map(item => (
                            <Select.Option
                              id={item.id}
                              key={item.id}
                              name={item.name}
                            >
                              <span
                                class='source-select-item'
                                v-overflow-tips
                              >
                                {item.name}
                              </span>
                            </Select.Option>
                          ))
                        )}
                      </Select>
                    ),
                  err: this.projectErrMsg,
                  key: '1',
                })}
                {formItem({
                  label: this.t('源码仓库'),
                  content: () =>
                    this.configLoading ? (
                      <div class='select-loading-skeleton'>
                        <div class='skeleton-element' />
                      </div>
                    ) : (
                      <Select
                        v-bk-tooltips={{
                          placement: 'top',
                          content: this.t('请先选择蓝盾项目'),
                          disabled: !!this.bkciProjectId,
                        }}
                        popoverOptions={{
                          extCls: 'ai-config-source-code-analysis-popover',
                        }}
                        customContent={this.repositoriesLoading}
                        disabled={!this.bkciProjectId}
                        loading={this.repositoriesLoading}
                        modelValue={this.repositoryAlias}
                        multiple={false}
                        noDataText={this.repositoriesLoading ? this.t('加载中...') : this.t('无数据')}
                        filterable
                        onToggle={this.handleRepositoriesToggle}
                        onUpdate:modelValue={val => {
                          this.repositoryAlias = val;
                        }}
                      >
                        {/* 首次加载/搜索时显示骨架屏占位，避免下拉面板空白闪烁 */}
                        {this.repositoriesLoading ? (
                          <div style='padding: 0 8px;'>
                            {new Array(4).fill(null).map((_item, index) => (
                              <div
                                key={index}
                                style='height: 24px; margin: 4px 0;'
                                class='skeleton-element'
                              />
                            ))}
                          </div>
                        ) : (
                          this.bkciRepositories.map(item => (
                            <Select.Option
                              id={item.id}
                              key={item.id}
                              name={item.name}
                            >
                              <span
                                class='source-select-item'
                                v-overflow-tips
                              >
                                {item.name}
                              </span>
                            </Select.Option>
                          ))
                        )}
                      </Select>
                    ),
                  err: this.repositoryErrMsg,
                  key: '2',
                })}
              </div>
            ),
          },
          '1'
        )}
        {cardItem(
          {
            icon: () => <span class='icon-monitor icon-mc-guanlian' />,
            title: this.t('策略关联分析流程'),
            description: this.t('不同的策略，可以配置不同的流程实例参数（知识库、skill、告警组）'),
            content: () => (
              <div class='analysis-rules-wrap'>
                <span class='analysis-rules-wrap-header'>
                  <Button
                    outline={true}
                    theme='primary'
                    onClick={() => this.handleRuleSliderChange(true)}
                  >
                    <Plus style='font-size: 20px; margin-right: 4px;' />
                    {this.t('新增绑定配置')}
                  </Button>
                  <Input
                    style='width: 342px;'
                    modelValue={this.searchValue}
                    placeholder={this.t('搜索')}
                    type='search'
                    onUpdate:modelValue={val => {
                      this.searchValue = val;
                    }}
                  />
                </span>

                <AnalysisRuleTable
                  data={this.sourceAnalysisRules}
                  loading={this.rulesLoading}
                  matchRuleFields={this.matchRuleFields}
                  matchRuleFieldsLoading={this.matchRuleFieldsLoading}
                  searchValue={this.searchValue}
                  tagValueDisplayFormatter={this.getMatchRuleTagValueDisplayFormatter}
                  onClearSearch={this.handleClearSearch}
                  onDeleteRule={this.handleDeleteRule}
                  onEditRule={(rule: SourceAnalysisRuleDto) =>
                    this.handleRuleSliderChange(true, { type: SidesliderTypeEnum.EDIT, ruleId: rule.id })
                  }
                  onUpdateRule={this.handleTableUpdateRule}
                />
                <AnalysisConfigSideslider
                  fetchStrategyDimensions={this.fetchMatchRuleStrategyDimensions}
                  getMatchRuleValueFn={this.getMatchRuleValueFn}
                  matchRuleFields={this.matchRuleFields}
                  matchRuleFieldsLoading={this.matchRuleFieldsLoading}
                  projectName='IEG - 登陆服务'
                  ruleId={this.editRuleId}
                  show={this.showBindModal}
                  tagValueDisplayFormatter={this.getMatchRuleTagValueDisplayFormatter}
                  type={this.sidesliderType}
                  onConfirm={this.handleBindConfirm}
                  onUpdate:show={this.handleRuleSliderChange}
                />
              </div>
            ),
          },
          '2'
        )}
        <Button
          loading={this.saveLoading}
          theme='primary'
          onClick={this.handleSaveConfig}
        >
          {this.t('保存配置')}
        </Button>
      </div>
    );
  },
});
