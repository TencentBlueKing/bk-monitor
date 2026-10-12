import { markRaw } from 'vue';
import { Component, Prop } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import AIWhaleIcon from '../../../../components/ai-whale-icon/ai-whale-icon';
import { PromqlQueryController } from './controller';
import { getSourceQueries, type PromqlQuery, type PromqlSourceData } from './model';

import './promql-query-editor.scss';

interface Props {
  sourceData: PromqlSourceData;
  expression: string;
  readonly?: boolean;
  loading?: boolean;
}

interface Events {
  onQueriesChange: PromqlQuery[];
  onExpressionChange: string;
  onExpressionBlur: string;
  onStepChange: number;
  onExecute: boolean;
  onBlur: boolean;
}

@Component({
  components: {
    PromqlMonacoEditor: () => import(/* webpackChunkName: 'PromqlMonacoEditor' */ '../../../../components/promql-editor/promql-editor'),
  },
})
export default class PromqlQueryEditor extends tsc<Props, Events> {
  @Prop({ required: true, type: Object }) sourceData: PromqlSourceData;
  @Prop({ default: '', type: String }) expression: string;
  @Prop({ default: false, type: Boolean }) readonly: boolean;
  @Prop({ default: false, type: Boolean }) loading: boolean;

  private controller = markRaw(new PromqlQueryController());
  validationShown = false;
  deletingAlias = '';
  deletedAlias = '';

  get queries() {
    return getSourceQueries(this.sourceData);
  }

  get effectiveExpression() {
    return this.expression || (this.queries.length === 1 ? this.queries[0].alias : '');
  }

  get isReadonly() {
    return this.readonly || this.sourceData.legacyMultiQuery;
  }

  get validationError() {
    return this.validationShown ? this.controller.validate(this.sourceData, this.effectiveExpression) : null;
  }

  get hint() {
    if (this.validationError) {
      if (this.deletedAlias && this.controller.analyzeExpression(this.effectiveExpression).aliases.includes(this.deletedAlias)) {
        return this.$t('查询 {alias} 已删除，表达式仍引用它。请修改表达式后再查询或提交。', { alias: this.deletedAlias });
      }
      return this.$t(this.validationError.message, this.validationError.params || {});
    }
    return this.queries.length === 1
      ? this.$t('单查询默认使用 {alias} 的结果；可继续添加查询并设置表达式。', { alias: this.queries[0].alias })
      : this.$t('已添加 {count} 条查询，可继续添加；表达式需引用全部查询的别名。', { count: this.queries.length });
  }

  validate() {
    this.validationShown = true;
    return !this.validationError;
  }

  handleQueryChange(alias: string, promql: string) {
    if (this.isReadonly) return;
    this.$emit('queriesChange', this.queries.map(query => {
      if (query.alias !== alias || query.promql === promql) return query;
      const updatedQuery = { ...query, promql };
      // metric_id 由后端按 PromQL 生成，编辑后不能继续使用旧值。
      delete updatedQuery.metric_id;
      return updatedQuery;
    }));
  }

  handleAdd() {
    if (this.isReadonly) return;
    const alias = this.controller.nextAlias(this.queries);
    if (!alias) return;
    this.validationShown = false;
    this.$emit('queriesChange', [...this.queries, { alias, promql: '' }]);
  }

  handleDelete(alias: string) {
    if (this.isReadonly || this.queries.length <= 1) return;
    if (this.controller.analyzeExpression(this.effectiveExpression).aliases.includes(alias)) {
      this.deletingAlias = alias;
      return;
    }
    this.removeQuery(alias);
  }

  removeQuery(alias: string) {
    if (this.isReadonly || this.queries.length <= 1) return;
    this.$emit('queriesChange', this.queries.filter(query => query.alias !== alias));
    this.deletedAlias = alias;
    this.deletingAlias = '';
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
        {!this.loading && this.queries.map(query => (
          <div key={query.alias} class='source-query'>
            <div class='source-query-title'>
              <span>{query.alias}{'  PromQL'}</span>
              {!this.isReadonly && (
                <bk-button text disabled={this.queries.length <= 1} onClick={() => this.handleDelete(query.alias)}>
                  {this.$t('删除')}
                </bk-button>
              )}
            </div>
            <promql-monaco-editor
              minHeight={80}
              readonly={this.isReadonly}
              value={query.promql}
              isError={this.validationError?.aliases?.includes(query.alias)}
              executeQuery={() => this.$emit('execute', !this.validate())}
              onChange={(value: string) => this.handleQueryChange(query.alias, value)}
              onBlur={this.handleBlur}
            />
          </div>
        ))}
        <div class='source-expression-row'>
          <span class='source-expression-label'>{this.$t('表达式')}</span>
          <bk-input
            class='source-expression-input'
            behavior='simplicity'
            readonly={this.isReadonly}
            value={this.effectiveExpression}
            onChange={(value: string) => this.$emit('expressionChange', value)}
            onBlur={() => {
              this.validate();
              this.$emit('expressionBlur', this.effectiveExpression);
            }}
            onEnter={() => this.$emit('execute', !this.validate())}
          />
          {!this.isReadonly && (
            <bk-button class='source-add-query' disabled={!this.controller.nextAlias(this.queries)} onClick={this.handleAdd}>
              {this.$t('添加查询')}
            </bk-button>
          )}
        </div>
        {!this.isReadonly && <div class={['source-expression-hint', { 'is-error': !!this.validationError }]}>{this.hint}</div>}
        <bk-input
          class='source-step-input'
          type='number'
          min={10}
          precision={0}
          disabled={this.isReadonly}
          value={this.sourceData.step}
          onChange={(value: number) => this.$emit('stepChange', value)}
        >
          <div class='source-step-label' slot='prepend'>
            <span>Step</span>
            <AIWhaleIcon content='Step' tip={this.$t('数据步长').toString()} type='explanation' />
          </div>
        </bk-input>
        <bk-dialog
          value={!!this.deletingAlias}
          title={this.$t('删除查询 {alias}？', { alias: this.deletingAlias })}
          width={480}
          header-position='left'
          ext-cls='strategy-promql-delete-dialog'
          onCancel={() => { this.deletingAlias = ''; }}
        >
          <div class='source-delete-message'>
            <p>{this.$t('查询 {alias} 正被表达式 {expression} 引用。', { alias: this.deletingAlias, expression: this.effectiveExpression })}</p>
            <p>{this.$t('删除后需修正表达式；其他查询的别名不会改变。')}</p>
          </div>
          <div slot='footer'>
            <bk-button onClick={() => { this.deletingAlias = ''; }}>{this.$t('取消')}</bk-button>
            <bk-button outline theme='danger' onClick={() => this.removeQuery(this.deletingAlias)}>
              {this.$t('删除并修改公式')}
            </bk-button>
          </div>
        </bk-dialog>
      </div>
    );
  }
}
