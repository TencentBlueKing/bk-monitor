import { Component, Emit, InjectReactive, Prop, Ref, Watch } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';
import type { CallOptions, CodeRedefineItem } from '../../type';
import { handleTransformToTimestamp } from 'monitor-pc/components/time-range/utils';
import type { TimeRangeType } from 'monitor-pc/components/time-range/time-range';
import { getFieldOptionValues } from 'monitor-api/modules/apm_metric';
import { VariablesService } from '../../../../utils/variable';
import { downloadFile } from 'monitor-common/utils';
import { listCodeRedefinedRule, setCodeRedefinedRule } from 'monitor-api/modules/apm_service';
import { uploadJsonFile } from 'monitor-pc/pages/view-detail/utils';

import './code-redefine-slider.scss';
interface CodeRedefineSliderProps {
  isShow: boolean;
  type: 'caller' | 'callee';
  appName: string;
  service: string;
  callOptions?: Partial<CallOptions>;
  variablesData?: Record<string, any>;
}

interface CodeRedefineSliderEvents {
  onShowChange(isShow: boolean): void;
}

interface ColumnItem {
  label: string;
  prop: string;
  options: { value: string; text: string }[];
  loading: boolean;
  width?: number;
}

@Component
export default class CodeRedefineSlider extends tsc<CodeRedefineSliderProps, CodeRedefineSliderEvents> {
  @Prop({ default: false }) isShow: boolean;
  @Prop({ default: 'caller' }) type: 'caller' | 'callee';
  @Prop({ default: '' }) appName: string;
  @Prop({ default: '' }) service: string;
  @Prop({ default: () => ({}) }) callOptions: Partial<CallOptions>;
  @Prop({ default: () => ({}) }) variablesData: Record<string, any>;

  @InjectReactive('timeRange') readonly timeRange!: TimeRangeType;

  @Ref('fileRef') fileRef!: HTMLInputElement;
  @Ref('tableRef') tableRef!: any;

  data: CodeRedefineItem[] = [];

  loading = false;
  submitLoading = false;

  /** 重复的规则下标 */
  repeatRulesIndex = new Set();

  columns: ColumnItem[] = [
    { label: this.$tc('被调服务'), prop: 'callee_server', options: [], loading: false, width: 194 },
    { label: this.$tc('被调service'), prop: 'callee_service', options: [], loading: false, width: 194 },
    { label: this.$tc('被调接口'), prop: 'callee_method', options: [], loading: false, width: 252 },
    { label: this.$tc('返回码'), prop: 'code_type_rules', options: [], loading: false },
  ];

  codeStatus = [
    { label: this.$tc('失败'), value: 'exception' },
    { label: this.$tc('超时'), value: 'timeout' },
    { label: this.$tc('成功'), value: 'success' },
  ];

  codeRegex = /^(?:[a-zA-Z0-9]+_)?\d+(?:~\d+)?(?:,(?:[a-zA-Z0-9]+_)?\d+(?:~\d+)?)*$/;

  rules = {
    success: [
      {
        validator: val => !val || this.codeRegex.test(val),
        message: window.i18n.tc('返回码格式错误'),
        trigger: 'blur',
      },
    ],
    exception: [
      {
        validator: val => !val || this.codeRegex.test(val),
        message: window.i18n.tc('返回码格式错误'),
        trigger: 'blur',
      },
    ],
    timeout: [
      {
        validator: val => !val || this.codeRegex.test(val),
        message: window.i18n.tc('返回码格式错误'),
        trigger: 'blur',
      },
    ],
  };

  get showColumn() {
    if (this.type === 'callee') return this.columns.slice(1);
    return this.columns;
  }

  get infoData() {
    return [
      { key: 'type', label: this.$tc('类型'), value: this.type === 'caller' ? this.$tc('主调') : this.$tc('被调') },
      {
        key: 'service',
        label: this.type === 'caller' ? this.$tc('主调服务') : this.$tc('被调服务'),
        value: this.service,
      },
    ];
  }

  @Watch('isShow')
  watchShowChange(show: boolean) {
    if (show) {
      this.getCodeRedefineList();
      this.showColumn.filter(item => item.prop !== 'code_type_rules').map(item => this.getOptionListByKey(item.prop));
    } else {
      this.data = [];
      this.repeatRulesIndex = new Set();
    }
  }

  addRow(params?: CodeRedefineItem) {
    this.data.push({
      callee_server: params?.callee_server || (this.type === 'callee' ? this.service : ''),
      callee_service: params?.callee_service || '',
      callee_method: params?.callee_method || '',
      code_type_rules: {
        success: params?.code_type_rules?.success || '',
        exception: params?.code_type_rules?.exception || '',
        timeout: params?.code_type_rules?.timeout || '',
      },
    });
  }

  handleValueChange(value: string, prop: string, index: number) {
    this.data[index][prop] = value;
    this.validRules();
  }

  renderColumn(item: ColumnItem) {
    switch (item.prop) {
      case 'callee_server':
      case 'callee_service':
      case 'callee_method':
        return (
          <bk-table-column
            key={item.prop}
            label={item.label}
            prop={item.prop}
            width={item.width}
            scopedSlots={{
              default: ({ row, $index }) => (
                <div class='interface-column'>
                  <bk-select
                    value={row[item.prop]}
                    allow-create
                    display-tag={true}
                    searchable
                    placeholder={this.$tc('请选择或输入')}
                    disabled={item.loading}
                    loading={item.loading}
                    showEmpty={!item.loading && !item.options.length}
                    onChange={v => this.handleValueChange(v, item.prop, $index)}
                  >
                    {item.options.map(opt => (
                      <bk-option
                        id={opt.value}
                        key={opt.value}
                        name={opt.text}
                      />
                    ))}
                  </bk-select>
                  {this.repeatRulesIndex.has($index) && item.prop === 'callee_method' && (
                    <i
                      class='icon-monitor icon-mind-fill'
                      v-bk-tooltips={{ content: this.$tc('被调服务、被调service、被调接口组合值唯一') }}
                    />
                  )}
                </div>
              ),
            }}
          />
        );
      case 'code_type_rules':
        return (
          <bk-table-column
            key={item.prop}
            label={item.label}
            prop={item.prop}
            width={item.width}
            render-header={() => {
              return (
                <div class='code-column-header'>
                  <span>{this.$tc('返回码')}</span>
                  <i
                    class='icon-monitor icon-hint'
                    v-bk-tooltips={{
                      content: this.$t(
                        '多个返回码之间用“，”分割，数值区间用～连接，有前缀的需要把前缀带上，比如：error_4003,200,3001~3005'
                      ),
                    }}
                  />
                </div>
              );
            }}
            scopedSlots={{
              default: ({ $index }) => (
                <bk-form
                  ref={`codeRulesForm_${$index}`}
                  class='code-rules'
                  label-width={0}
                  {...{
                    props: {
                      model: this.data[$index].code_type_rules,
                      rules: this.rules,
                    },
                  }}
                >
                  {this.codeStatus.map(item => (
                    <div
                      class='code-status-rule-item'
                      key={item.value}
                    >
                      <bk-form-item property={item.value}>
                        <bk-input v-model={this.data[$index].code_type_rules[item.value]} />
                      </bk-form-item>
                      <i18n path={'重定义为 {0}'}>
                        <span class={[item.value]}>{item.label}</span>
                      </i18n>
                    </div>
                  ))}
                </bk-form>
              ),
            }}
          />
        );
      default:
        return undefined;
    }
  }

  async getCodeRedefineList() {
    this.loading = true;
    const data = await listCodeRedefinedRule({
      app_name: this.appName,
      service_name: this.service,
      kind: this.type,
    }).finally(() => {
      this.loading = false;
    });
    if (data.length) {
      this.data = data.map(item => ({
        callee_server: item.callee_server,
        callee_service: item.callee_service,
        callee_method: item.callee_method,
        code_type_rules: item.code_type_rules,
      }));
    } else {
      this.addRow();
    }
  }

  /** 动态获取左侧列表的下拉值 */
  async getOptionListByKey(key: string) {
    const curOption = this.columns.find(item => item.prop === key);
    if (!curOption) return;
    curOption.loading = true;
    const [startTime, endTime] = handleTransformToTimestamp(this.timeRange);
    const variablesService = new VariablesService({
      app_name: this.appName,
      service_name: this.service,
    });
    const newParams = {
      ...variablesService.transformVariables(this.variablesData, {
        ...this.callOptions,
      }),
      start_time: startTime,
      end_time: endTime,
      field: key,
    };
    const data = await getFieldOptionValues({
      ...newParams,
      where: [...newParams.where],
    }).catch(() => []);
    curOption.loading = false;
    curOption.options = data;
  }

  async fileChange(e) {
    const files = e.target.files;
    const data = await uploadJsonFile<CodeRedefineItem[]>(files[0]).catch(() => false);
    if (!data || !Array.isArray(data)) {
      this.$bkMessage({
        theme: 'error',
        message: this.$t('文件格式不正确'),
      });
      return;
    }
    this.data = [];
    (data as CodeRedefineItem[]).map(item => this.addRow(item));
  }

  handleImport() {
    this.fileRef?.click();
  }

  handleExport() {
    downloadFile(JSON.stringify(this.data, null, 2), 'application/json', 'code-redefine.json');
  }

  @Emit('showChange')
  handleShowChange(show: boolean) {
    return show;
  }

  /** 校验填写的规则 */
  async validRules() {
    const values = this.data.map(item => `${item.callee_server}_${item.callee_service}_${item.callee_method}`);
    const repeatRules = new Set();
    const set = new Set();
    for (let index = 0; index < values.length; index++) {
      const item = values[index];
      if (set.has(item)) {
        repeatRules.add(index);
      } else {
        set.add(item);
      }
    }
    this.repeatRulesIndex = repeatRules;
    if (this.repeatRulesIndex.size !== 0) return false;
    const codeValidate = this.data.map((_, index) => this.tableRef.$refs[`codeRulesForm_${index}`].validate());
    const codeValid = await Promise.all(codeValidate)
      .then(() => true)
      .catch(() => false);
    if (!codeValid) return false;
    return true;
  }

  async handleSave() {
    const valid = await this.validRules();
    if (!valid) return;
    this.submitLoading = true;
    const data = await setCodeRedefinedRule({
      app_name: this.appName,
      service_name: this.service,
      kind: this.type,
      rules: this.data,
    })
      .catch(() => false)
      .finally(() => {
        this.submitLoading = false;
      });
    if (data) {
      this.$bkMessage({
        theme: 'success',
        message: this.$t('保存成功'),
      });
      this.handleShowChange(false);
    }
  }

  render() {
    return (
      <bk-sideslider
        class='code-redefine-slider'
        is-show={this.isShow}
        width={1250}
        quick-close
        title={this.$t('返回码重定义')}
        {...{ on: { 'update:isShow': this.handleShowChange } }}
      >
        <div
          class='code-redefine-slider-content'
          slot='content'
        >
          <div class='info-table'>
            {this.infoData.map(item => (
              <div
                class='table-row'
                key={item.key}
              >
                <div class='row-label'>{item.label}</div>
                <div class='row-value'>{item.value}</div>
              </div>
            ))}
          </div>

          <div class='submit-table'>
            <div class='explore-btns'>
              <input
                class='hidden-file-input'
                type='file'
                accept='application/json'
                ref='fileRef'
                onChange={this.fileChange}
              />
              <bk-button
                class='btn'
                theme='primary'
                text
                onClick={this.handleImport}
              >
                {this.$t('导入')}
              </bk-button>
              <bk-button
                class='btn'
                theme='primary'
                text
                onClick={this.handleExport}
              >
                {this.$t('导出')}
              </bk-button>
            </div>
            {this.loading ? (
              <div class='skeleton-wrap'>
                <div class='skeleton-element' />
                <div class='skeleton-element' />
                <div class='skeleton-element' />
              </div>
            ) : (
              <bk-table
                ref='tableRef'
                data={this.data}
                border
                row-auto-height
                row-class-name='rule-row'
              >
                {this.showColumn.map(item => this.renderColumn(item))}
                <bk-table-column
                  label={this.$tc('操作')}
                  width={136}
                  scopedSlots={{
                    default: ({ $index }) => (
                      <div class='operate-btns'>
                        <bk-button
                          class='btn'
                          theme='primary'
                          text
                          onClick={() => {
                            this.addRow(this.data[$index]);
                          }}
                        >
                          {this.$t('复制')}
                        </bk-button>
                        <bk-button
                          class='btn'
                          theme='primary'
                          text
                          onClick={() => {
                            this.addRow();
                          }}
                        >
                          {this.$t('新增')}
                        </bk-button>
                        {this.data.length > 1 && (
                          <bk-button
                            class='btn'
                            theme='danger'
                            text
                            onClick={() => {
                              this.data.splice($index, 1);
                            }}
                          >
                            {this.$t('删除')}
                          </bk-button>
                        )}
                      </div>
                    ),
                  }}
                />
              </bk-table>
            )}
          </div>

          <div class='submit-btns'>
            <bk-button
              loading={this.submitLoading}
              theme='primary'
              onClick={this.handleSave}
            >
              {this.$tc('保存')}
            </bk-button>
            <bk-button
              loading={this.submitLoading}
              onClick={() => {
                this.handleShowChange(false);
              }}
            >
              {this.$tc('取消')}
            </bk-button>
          </div>

          <div class='tips'>{this.$t('配置修改保存后，需 5 分钟左右生效')}</div>
        </div>
      </bk-sideslider>
    );
  }
}
