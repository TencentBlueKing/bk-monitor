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
import { defineComponent, onMounted, shallowRef, watch } from 'vue';

import { Button, InfoBox, Input, Select } from 'bkui-vue';
import { Plus } from 'bkui-vue/lib/icon';
import { debounce } from 'lodash';
import OverflowTips from 'trace/directive/overflow-tips';
import { useI18n } from 'vue-i18n';

import { useBkciProjectsSelect } from '../../composables/use-bkci-projects-select';
import { useBkciRepositoriesSelect } from '../../composables/use-bkci-repositories-select';
import {
  deleteSourceAnalysisRuleApi,
  getListSourceAnalysisRules,
  getSourceAnalysisConfigData,
  setSaveSourceAnalysisConfig,
} from '../../services/ai-config';
import AnalysisConfigSideslider from '../analysis-config-sideslider/analysis-config-sideslider';
import AnalysisRuleTable from '../analysis-rule-table/analysis-rule-table';

import type { TSourceAnalysisRule } from '../../typings';

import './source-code-analysis.scss';

/**
 * @description 源码 AI 分析
 */
export default defineComponent({
  name: 'SourceCodeAnalysis',
  directives: {
    OverflowTips,
  },
  setup() {
    const { t } = useI18n();
    /** 蓝盾项目 id */
    const bkciProjectId = shallowRef('');
    /** 源码仓库别名 */
    const repositoryAlias = shallowRef('');
    /** 蓝盾项目下拉选择 */
    const projectsSelect = useBkciProjectsSelect();
    /** 源码仓库下拉选择（依赖蓝盾项目） */
    const repositoriesSelect = useBkciRepositoriesSelect({ bkciProjectId });
    /** 源码分析规则列表（当前为 mock 数据，后续接入真实接口） */
    const sourceAnalysisRules = shallowRef<TSourceAnalysisRule[]>([]);

    /** 规则搜索关键字 */
    const searchValue = shallowRef('');

    /** 新增绑定侧弹窗显隐状态 */
    const showBindModal = shallowRef(false);

    /** 蓝盾项目必填校验错误提示 */
    const projectErrMsg = shallowRef('');
    /** 源码仓库必填校验错误提示 */
    const repositoryErrMsg = shallowRef('');
    /** 初始化加载配置 loading（用于两个选择器位置骨架屏占位） */
    const configLoading = shallowRef(false);
    /** 规则列表加载中 */
    const rulesLoading = shallowRef(false);

    /**
     * @description 打开新增绑定侧弹窗
     */
    const handleOpenBindModal = () => {
      showBindModal.value = true;
    };

    /**
     * @description 提交绑定
     */
    const handleBindConfirm = () => {
      // TODO: 提交绑定逻辑
      showBindModal.value = false;
    };

    /**
     * @description 保存配置，校验必填项
     */
    const handleSaveConfig = async () => {
      projectErrMsg.value = bkciProjectId.value ? '' : t('必填项');
      repositoryErrMsg.value = repositoryAlias.value ? '' : t('必填项');
      if (!bkciProjectId.value || !repositoryAlias.value) return;
      await setSaveSourceAnalysisConfig({
        bkci_project_id: bkciProjectId.value,
        repository_alias: repositoryAlias.value,
      });
    };

    /**
     * @description 初始化加载：查询已保存的源码分析配置并回填到两个选择器
     */
    const handleInitConfig = async () => {
      configLoading.value = true;
      try {
        const data = await getSourceAnalysisConfigData().catch(() => null);
        if (data?.bkci_project_id) {
          bkciProjectId.value = data.bkci_project_id;
          // 已配置蓝盾项目，加载其下的源码仓库列表，保证选中值能正常展示
          repositoriesSelect.fetchData();
        }
        repositoryAlias.value = data?.repository_alias || '';
        // 加载蓝盾项目列表，保证已选项目能匹配到对应名称
        projectsSelect.fetchData();
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
        const rules = await getListSourceAnalysisRules().catch(() => []);
        sourceAnalysisRules.value = rules ?? [];
      } finally {
        rulesLoading.value = false;
      }
    };
    handleFetchRules();

    /**
     * @description 清空规则搜索关键字
     */
    const handleClearSearch = () => {
      searchValue.value = '';
    };

    /** 搜索输入防抖处理（300ms），避免频繁触发接口请求 */
    const handleProjectsSearchDebounce = debounce(projectsSelect.handleSearch, 300);
    const handleRepositoriesSearchDebounce = debounce(repositoriesSelect.handleSearch, 300);

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

    /** 规则局部更新（启停等）：将更新后的规则回写到列表对应项 */
    const handleTableUpdateRule = (rule: TSourceAnalysisRule) => {
      sourceAnalysisRules.value = sourceAnalysisRules.value.map(item => (item.id === rule.id ? rule : item));
    };

    /** 编辑规则：打开编辑弹窗（待接入编辑能力） */
    const handleEditRule = (rule: TSourceAnalysisRule) => {
      console.log(rule);
    };
    /** 删除规则：二次确认后调用删除接口并同步移除列表项（默认策略不可删除） */
    const handleDeleteRule = (rule: TSourceAnalysisRule) => {
      InfoBox({
        title: t('确定删除此规则'),
        beforeClose: action => {
          console.log(action);
          if (action === 'confirm') {
            return new Promise(resolve => {
              deleteSourceAnalysisRuleApi(rule.id)
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

    /** 蓝盾项目切换/清空时，同步清空已选的源码仓库 */
    watch(
      () => bkciProjectId.value,
      () => {
        repositoryAlias.value = '';
      }
    );

    onMounted(() => {
      handleInitConfig();
    });

    return {
      t,
      showBindModal,
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
      projectsScrollLoading: projectsSelect.scrollLoading,
      handleProjectsToggle,
      handleProjectsSearch: handleProjectsSearchDebounce,
      handleProjectsScrollEnd: projectsSelect.handleScrollEnd,
      /** 源码仓库下拉 */
      bkciRepositories: repositoriesSelect.list,
      repositoriesLoading: repositoriesSelect.loading,
      repositoriesScrollLoading: repositoriesSelect.scrollLoading,
      handleRepositoriesToggle,
      handleRepositoriesSearch: handleRepositoriesSearchDebounce,
      handleRepositoriesScrollEnd: repositoriesSelect.handleScrollEnd,
      handleOpenBindModal,
      handleBindConfirm,
      handleSaveConfig,
      handleClearSearch,
      handleTableUpdateRule,
      handleEditRule,
      handleDeleteRule,
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
            {/* {params.err ? <div class='err-msg'>{params.err}</div> : null} */}
          </div>
        </div>
      );
    };
    return (
      <div class='ai-config-source-code-analysis'>
        {cardItem(
          {
            icon: () => <span class='icon-monitor icon-APM' />,
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
                        filterOption={() => true}
                        loading={this.projectsLoading}
                        modelValue={this.bkciProjectId}
                        multiple={false}
                        noDataText={this.projectsLoading ? this.t('加载中...') : this.t('无数据')}
                        scrollLoading={this.projectsScrollLoading}
                        filterable
                        onScroll-end={this.handleProjectsScrollEnd}
                        onSearch-change={this.handleProjectsSearch}
                        onToggle={this.handleProjectsToggle}
                        onUpdate:modelValue={val => {
                          this.bkciProjectId = val;
                        }}
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
                        filterOption={() => true}
                        loading={this.repositoriesLoading}
                        modelValue={this.repositoryAlias}
                        multiple={false}
                        noDataText={this.repositoriesLoading ? this.t('加载中...') : this.t('无数据')}
                        scrollLoading={this.repositoriesScrollLoading}
                        filterable
                        onScroll-end={this.handleRepositoriesScrollEnd}
                        onSearch-change={this.handleRepositoriesSearch}
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
                    onClick={this.handleOpenBindModal}
                  >
                    <Plus style='font-size: 20px; margin-right: 4px;' />
                    {this.t('新增绑定配置')}
                  </Button>
                  <Input
                    style='width: 342px;'
                    modelValue={this.searchValue}
                    type='search'
                    onUpdate:modelValue={val => {
                      this.searchValue = val;
                    }}
                  />
                </span>

                <AnalysisRuleTable
                  data={this.sourceAnalysisRules}
                  loading={this.rulesLoading}
                  searchValue={this.searchValue}
                  onClearSearch={this.handleClearSearch}
                  onDeleteRule={this.handleDeleteRule}
                  onEditRule={this.handleEditRule}
                  onUpdateRule={this.handleTableUpdateRule}
                />
                <AnalysisConfigSideslider
                  v-model:show={this.showBindModal}
                  processName='IEG - 登陆服务'
                  onConfirm={this.handleBindConfirm}
                />
              </div>
            ),
          },
          '2'
        )}
        <Button
          theme='primary'
          onClick={this.handleSaveConfig}
        >
          {this.t('保存配置')}
        </Button>
      </div>
    );
  },
});
