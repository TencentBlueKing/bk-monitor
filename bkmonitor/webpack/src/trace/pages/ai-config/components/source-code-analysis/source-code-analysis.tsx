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
import { defineComponent, shallowRef } from 'vue';

import { Button, Input, Select } from 'bkui-vue';
import { Plus } from 'bkui-vue/lib/icon';
import { useI18n } from 'vue-i18n';

import AnalysisConfigSideslider from '../analysis-config-sideslider/analysis-config-sideslider';
import AnalysisRuleTable from '../analysis-rule-table/analysis-rule-table';

import type { TBkciProjectsResult, TBkciRepositoriesResult, TSourceAnalysisRule } from '../../typings';

import './source-code-analysis.scss';

/**
 * @description 源码 AI 分析
 */
export default defineComponent({
  name: 'SourceCodeAnalysis',
  setup() {
    const { t } = useI18n();
    /** 蓝盾项目列表 */
    const bkciProjects = shallowRef<TBkciProjectsResult['list']>([]);
    /** 源码仓库列表 */
    const bkciRepositories = shallowRef<TBkciRepositoriesResult['list']>([]);
    /** 源码分析规则列表（当前为 mock 数据，后续接入真实接口） */
    const sourceAnalysisRules = shallowRef<TSourceAnalysisRule[]>([
      {
        id: 1024,
        bk_biz_id: 2,
        priority: 100,
        is_enabled: true,
        is_default: false,
        conditions: [
          {
            field: 'alert.strategy_id',
            value: ['12345'],
            method: 'eq',
            condition: 'and',
          },
        ],
        bkci_project_id: 'bkm-source-ai',
        repository_alias: 'login-service',
        agent_id: 'agent-source-code',
        skill_ids: ['skill-log-query'],
        knowledge_base_ids: ['kb-bkm-runbook'],
        created_by: 'zhangsan',
        created_at: 1785380400,
        updated_by: 'zhangsan',
        updated_at: 1785380400,
      },
    ]);

    /** 规则搜索关键字 */
    const searchValue = shallowRef('');

    /** 新增绑定侧弹窗显隐状态 */
    const showBindModal = shallowRef(false);

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

    return {
      t,
      showBindModal,
      bkciProjects,
      bkciRepositories,
      sourceAnalysisRules,
      searchValue,
      handleOpenBindModal,
      handleBindConfirm,
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
    const formItem = (params: { content: () => JSX.Element; key: string; label: string }) => {
      return (
        <div
          key={params.key}
          class='form-item'
        >
          <div class='label'>
            <span>{params.label}</span>
          </div>
          <div class='content'>{params.content()}</div>
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
                  content: () => (
                    <Select>
                      {this.bkciProjects.map(item => (
                        <Select.Option
                          id={item.id}
                          key={item.id}
                          name={item.name}
                        />
                      ))}
                    </Select>
                  ),
                  key: '1',
                })}
                {formItem({
                  label: this.t('源码仓库'),
                  content: () => (
                    <Select>
                      {this.bkciProjects.map(item => (
                        <Select.Option
                          id={item.id}
                          key={item.id}
                          name={item.name}
                        />
                      ))}
                    </Select>
                  ),
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

                <AnalysisRuleTable data={this.sourceAnalysisRules} />
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
      </div>
    );
  },
});
