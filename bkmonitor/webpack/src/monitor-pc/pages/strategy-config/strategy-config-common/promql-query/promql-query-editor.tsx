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
import { markRaw } from 'vue';

import { Component, Prop } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import AIWhaleIcon from '../../../../components/ai-whale-icon/ai-whale-icon';
import { PromqlQueryController } from './controller';
import {
  type PromqlQuery,
  type PromqlSourceData,
  getSourceQueries,
  isExistingMultiPromql,
  isMultiPromqlBiz,
} from './model';

import './promql-query-editor.scss';

/** 覆盖 promql-editor 默认代码样式，对齐设计稿字号 12px / 行高 22px。 */
const EDITOR_OPTIONS = { fontSize: 12, lineHeight: 22 };

interface Events {
  onBlur: boolean;
  onExecute: boolean;
  onExpressionBlur: string;
  onExpressionChange: string;
  onQueriesChange: PromqlQuery[];
  onStepChange: number;
}

interface Props {
  expression: string;
  loading?: boolean;
  readonly?: boolean;
  sourceData: PromqlSourceData;
}

@Component({
  components: {
    PromqlMonacoEditor: () =>
      import(/* webpackChunkName: 'PromqlMonacoEditor' */ '../../../../components/promql-editor/promql-editor'),
  },
})
export default class PromqlQueryEditor extends tsc<Props, Events> {
  @Prop({ required: true, type: Object }) sourceData: PromqlSourceData;
  @Prop({ default: '', type: String }) expression: string;
  @Prop({ default: false, type: Boolean }) readonly: boolean;
  @Prop({ default: false, type: Boolean }) loading: boolean;

  private controller = markRaw(new PromqlQueryController());
  validationShown = false;
  addedAlias = '';

  get queries() {
    return getSourceQueries(this.sourceData);
  }

  /** 当前业务是否允许配置多 PromQL。 */
  get allowMulti() {
    return isMultiPromqlBiz(this.$store?.getters?.bizId);
  }

  /** 非多 PromQL 业务下，已有多查询或非别名表达式只读。 */
  get multiLocked() {
    return !this.allowMulti && isExistingMultiPromql(this.sourceData, this.expression);
  }

  get effectiveExpression() {
    return this.controller.effectiveExpression(this.sourceData, this.expression);
  }

  /** 被表达式引用的查询不能直接删除，需先从表达式中去掉该别名。 */
  isReferenced(alias: string) {
    return this.controller.analyzeExpression(this.effectiveExpression).aliases.includes(alias);
  }

  /** 删除按钮禁用原因；仅剩一条查询时表达式必然兜底引用它，故先判条数再判依赖。 */
  deleteDisabledTip(alias: string) {
    if (this.queries.length <= 1) return this.$t('至少需要有 1 条查询，不能删除');
    if (this.isReferenced(alias)) return this.$t('存在表达式依赖，不能删除');
    return '';
  }

  get isReadonly() {
    return this.readonly || this.sourceData.legacyMultiQuery || this.multiLocked;
  }

  /** immediate 错误无需等待提交校验即可展示，其余错误在失焦或执行后才提示。 */
  get validationError() {
    const error = this.controller.validate(this.sourceData, this.expression, { allowMulti: this.allowMulti });
    return this.validationShown || error?.immediate ? error : null;
  }

  get hint() {
    if (this.validationError) {
      return this.$t(this.validationError.message, this.validationError.params || {});
    }
    if (!this.allowMulti) return '';
    if (this.queries.some(query => query.alias === this.addedAlias)) {
      return this.$t('新增查询 {alias}；填写后可在表达式中引用，原表达式保持不变。', { alias: this.addedAlias });
    }
    return this.queries.length === 1
      ? this.$t('单查询默认使用 {alias} 的结果；可继续添加查询并设置表达式。', { alias: this.queries[0].alias })
      : this.$t('已添加 {count} 条查询，可继续添加；表达式可引用所需查询的别名。', { count: this.queries.length });
  }

  validate() {
    this.validationShown = true;
    return !this.validationError;
  }

  handleQueryChange(alias: string, promql: string) {
    if (this.isReadonly) return;
    this.$emit(
      'queriesChange',
      this.queries.map(query => {
        if (query.alias !== alias || query.promql === promql) return query;
        if (alias === this.addedAlias) this.addedAlias = '';
        const updatedQuery = { ...query, promql };
        // metric_id 由后端按 PromQL 生成，编辑后不能继续使用旧值。
        delete updatedQuery.metric_id;
        return updatedQuery;
      })
    );
  }

  handleAdd() {
    if (this.isReadonly || !this.allowMulti) return;
    const alias = this.controller.nextAlias(this.queries);
    if (!alias) return;
    this.validationShown = false;
    this.$emit('queriesChange', [...this.queries, { alias, promql: '' }]);
    this.addedAlias = alias;
  }

  handleDelete(alias: string) {
    if (this.isReadonly || this.queries.length <= 1 || this.isReferenced(alias)) return;
    this.$emit(
      'queriesChange',
      this.queries.filter(query => query.alias !== alias)
    );
    this.addedAlias = '';
    this.validationShown = true;
  }

  async handleBlur() {
    await this.$nextTick();
    this.$emit('blur', !this.validate());
  }

  render() {
    return (
      <div class='strategy-promql-query-editor'>
        {this.sourceData.legacyMultiQuery && (
          <div class='legacy-query-hint'>
            {this.$t('历史多 PromQL 查询配置仅可查看；其他策略设置可正常保存。查询请通过 API 或 as-code 修改。')}
          </div>
        )}
        {this.multiLocked && !this.sourceData.legacyMultiQuery && (
          <div class='legacy-query-hint'>{this.$t('当前业务不支持配置多 PromQL，已有查询和表达式仅可查看。')}</div>
        )}
        {!this.loading &&
          this.queries.map(query => (
            <div
              key={query.alias}
              class='source-query'
            >
              <div class='source-query-title'>
                <span>
                  {query.alias}
                  {'  PromQL'}
                </span>
                {this.allowMulti && !this.isReadonly && (
                  <span
                    class='source-query-delete'
                    v-bk-tooltips={{
                      content: this.deleteDisabledTip(query.alias),
                      disabled: !this.deleteDisabledTip(query.alias),
                    }}
                  >
                    <bk-button
                      disabled={this.queries.length <= 1 || this.isReferenced(query.alias)}
                      text
                      onClick={() => this.handleDelete(query.alias)}
                    >
                      {this.$t('删除')}
                    </bk-button>
                  </span>
                )}
              </div>
              <promql-monaco-editor
                executeQuery={() => this.$emit('execute', !this.validate())}
                isError={this.validationError?.aliases?.includes(query.alias)}
                minHeight={80}
                options={EDITOR_OPTIONS}
                readonly={this.isReadonly}
                value={query.promql}
                onBlur={this.handleBlur}
                onChange={(value: string) => this.handleQueryChange(query.alias, value)}
              />
            </div>
          ))}
        {(this.allowMulti || this.multiLocked) && (
          <div class='source-expression-row'>
            <span class='source-expression-label'>{this.$t('表达式')}</span>
            <bk-input
              class='source-expression-input'
              behavior='simplicity'
              readonly={this.isReadonly}
              value={this.effectiveExpression}
              onBlur={() => {
                this.validate();
                this.$emit('expressionBlur', this.effectiveExpression);
              }}
              onChange={(value: string) => this.$emit('expressionChange', value)}
              onEnter={() => this.$emit('execute', !this.validate())}
            />
            {this.allowMulti && !this.isReadonly && (
              <bk-button
                class='source-add-query'
                disabled={!this.controller.nextAlias(this.queries)}
                onClick={this.handleAdd}
              >
                {this.$t('添加查询')}
              </bk-button>
            )}
          </div>
        )}
        {!this.isReadonly && !!this.hint && (
          <div class={['source-expression-hint', { 'is-error': !!this.validationError }]}>{this.hint}</div>
        )}
        <bk-input
          class='source-step-input'
          disabled={this.isReadonly}
          min={10}
          precision={0}
          type='number'
          value={this.sourceData.step}
          onChange={(value: number) => this.$emit('stepChange', value)}
        >
          <div
            class='source-step-label'
            slot='prepend'
          >
            <span>Step</span>
            <AIWhaleIcon
              content='Step'
              tip={this.$t('数据步长').toString()}
              type='explanation'
            />
          </div>
        </bk-input>
      </div>
    );
  }
}
