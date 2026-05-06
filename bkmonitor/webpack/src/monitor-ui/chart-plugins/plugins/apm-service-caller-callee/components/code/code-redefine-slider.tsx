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
import TagBlock from 'monitor-pc/components/tag-block';
import { random } from 'monitor-common/utils';
import { cloneDeep } from 'lodash';

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
  showData: CodeRedefineItem[] = [];

  tableLoading = false;

  /** 重复的规则id */
  repeatRulesIdSet = new Set();
  rowEditMap: Record<string, boolean> = {};

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
      this.showData = [];
      this.repeatRulesIdSet = new Set();
      this.rowEditMap = {};
    }
  }

  @Emit('showChange')
  handleShowChange(show: boolean) {
    return show;
  }
  /** 三者都为空时才校验「不能为空」；任一有值则不做该项提示，仅对已填内容做格式校验 */
  getCodeTypeRules(codeTypeRules: CodeRedefineItem['code_type_rules']) {
    const keys: Array<'success' | 'exception' | 'timeout'> = ['success', 'exception', 'timeout'];
    const isAllEmpty = () => keys.every(k => !(codeTypeRules[k] ?? '').toString().trim());

    const fieldRules = () => [
      {
        validator: () => !isAllEmpty(),
        message: window.i18n.tc('返回码不能为空'),
        trigger: 'blur',
      },
      {
        validator: (val: string) =>
          !(val ?? '').toString().trim() || this.codeRegex.test((val ?? '').toString().trim()),
        message: window.i18n.tc('返回码格式错误'),
        trigger: 'blur',
      },
    ];

    return {
      success: fieldRules(),
      exception: fieldRules(),
      timeout: fieldRules(),
    };
  }
  generateNewRow(params?: CodeRedefineItem) {
    return {
      id: random(8),
      isNew: true,
      isSaving: false,
      isAbleSave: false,
      callee_server: params?.callee_server || (this.type === 'callee' ? this.service : ''),
      callee_service: params?.callee_service || '',
      callee_method: params?.callee_method || '',
      kind: this.type,
      is_global: false,
      code_type_rules: {
        success: params?.code_type_rules?.success || '',
        exception: params?.code_type_rules?.exception || '',
        timeout: params?.code_type_rules?.timeout || '',
      },
    };
  }

  handleAddNewRow(params?: CodeRedefineItem) {
    this.data.unshift(this.generateNewRow(params));
    this.showData.unshift(cloneDeep(this.data[0]));
    this.handleEditRow(0);
  }

  handleValueChange(value: string, prop: string, index: number) {
    const newValue = value;
    if (['success', 'exception', 'timeout'].includes(prop)) {
      this.$set(this.showData[index].code_type_rules, prop, newValue);
    } else {
      this.$set(this.showData[index], prop, newValue);
    }
    this.validRules();
  }

  async getCodeRedefineList() {
    this.tableLoading = true;
    const data = await listCodeRedefinedRule({
      app_name: this.appName,
      service_name: this.service,
      kind: this.type,
    }).finally(() => {
      this.tableLoading = false;
    });
    if (data.length) {
      for (let index = 0; index < data.length; index++) {
        const id = random(8);
        data[index].id = id;
        data[index].isNew = false;
        data[index].isSaving = false;
        data[index].isAbleSave = true;
        this.$set(this.rowEditMap, id, false);
      }
      this.data = data;
      this.showData = cloneDeep(data);
    } else {
      this.handleAddNewRow();
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
    /**
     * 以 类型 + 被调服务 + 被调service + 被调接口 为组合key：
     * 1. 存量的覆盖更新
     * 2. 新增的追加到前面
     */
    const importKeySet = new Set<string>(
      data.map(item => `${item.kind}_${item.callee_server}_${item.callee_service}_${item.callee_method}`)
    );
    const replaceIds = new Set<string>();
    for (let index = 0; index < this.showData.length; index++) {
      const item = this.showData[index];
      const rowKey = `${item.kind}_${item.callee_server}_${item.callee_service}_${item.callee_method}`;
      if (importKeySet.has(rowKey)) {
        this.showData[index] = data.find(
          childItem =>
            `${childItem.kind}_${childItem.callee_server}_${childItem.callee_service}_${childItem.callee_method}` ===
            rowKey
        );
        replaceIds.add(this.showData[index].id);
      }
    }
    const newList = data.filter(item => !replaceIds.has(item.id));
    const tatalList = [...newList, ...this.showData];
    for (let index = 0; index < tatalList.length; index++) {
      const item = tatalList[index];
      this.$set(this.rowEditMap, item.id, true);
    }
    this.showData = tatalList;
  }

  handleImport() {
    this.fileRef?.click();
  }

  handleExport() {
    downloadFile(JSON.stringify(this.data, null, 2), 'application/json', 'code-redefine.json');
  }

  /** 校验填写的规则 */
  async validRules() {
    const values = this.showData.map(item =>
      this.type === 'caller'
        ? `${item.callee_server}_${item.callee_service}_${item.callee_method}`
        : `${item.callee_service}_${item.callee_method}`
    );
    const keyIdsMap: Record<string, string[]> = {};
    for (let index = 0; index < values.length; index++) {
      const item = values[index];
      if (!item) continue;
      if (keyIdsMap[item]) {
        keyIdsMap[item].push(this.showData[index].id);
      } else {
        keyIdsMap[item] = [this.showData[index].id];
      }
    }
    const repeatIds = Object.values(keyIdsMap)
      .filter(item => item.length > 1)
      .flat();
    this.repeatRulesIdSet = new Set(repeatIds);
    const codeValidate = this.showData.map(item => this.tableRef.$refs[`codeRulesForm_${item.id}`]?.validate());
    const codeValid = await Promise.allSettled(codeValidate);
    for (let index = 0; index < this.showData.length; index++) {
      const { id } = this.showData[index];
      if (this.repeatRulesIdSet.has(id) || codeValid[index].status === 'rejected') {
        this.$set(this.showData[index], 'isAbleSave', false);
      } else {
        this.$set(this.showData[index], 'isAbleSave', true);
      }
    }
    if (codeValid.some(item => item.status === 'rejected') || this.repeatRulesIdSet.size !== 0) {
      return false;
    }
    return true;
  }

  handleGlobalConfigClick() {
    const hash = `#/apm/application/config/${this.appName}?active=codeRedefine`;
    const url = location.href.replace(location.hash, hash);
    window.open(url, '_blank');
  }

  handleCancelEditRow(index: number) {
    this.$set(this.rowEditMap, this.showData[index].id, false);
    if (this.data[index].isNew && this.showData.length > 1) {
      const row = this.data[index];
      const isEmpty =
        (this.type === 'caller' ? row.callee_server === '' : true) &&
        row.callee_service === '' &&
        row.callee_method === '' &&
        row.code_type_rules.success === '' &&
        row.code_type_rules.exception === '' &&
        row.code_type_rules.timeout === '';
      if (isEmpty) {
        this.showData.splice(index, 1);
        this.data.splice(index, 1);
        return;
      }
    }
    this.$set(this.showData, index, cloneDeep(this.data[index]));
  }

  handleDeleteRow(index: number) {
    this.$bkInfo({
      title: this.$t('是否确认删除？'),
      theme: 'danger',
      okText: this.$t('删除'),
      cancelText: this.$t('取消'),
      // TODO：组件库bug，该配置无效，已提issue，待修复
      // confirmLoading: true,
      confirmFn: async () => {
        const dataList = this.showData.filter((item, i) => i !== index && !item.isNew);
        const params = {
          app_name: this.appName,
          service_name: this.service,
          kind: this.type,
          rules: dataList.map(item => ({
            kind: item.kind,
            callee_server: item.callee_server,
            callee_service: item.callee_service,
            callee_method: item.callee_method,
            code_type_rules: item.code_type_rules,
            is_global: item.is_global,
          })),
        };
        await setCodeRedefinedRule(params);
        this.showData.splice(index, 1);
        this.data.splice(index, 1);
        this.$bkMessage({
          message: this.$t('删除成功，需要 5 分钟左右生效。'),
          theme: 'success',
        });
      },
    });
  }

  handleEditRow(index: number) {
    this.$set(this.rowEditMap, this.showData[index].id, true);
  }

  async handleSaveEditRow(index: number) {
    const valid = await this.validRules();
    if (!valid) return;
    if (JSON.stringify(this.showData[index]) === JSON.stringify(this.data[index]) && !this.showData[index].isNew) {
      this.$set(this.rowEditMap, this.showData[index].id, false);
      return;
    }
    const params = {
      app_name: this.appName,
      service_name: this.service,
      kind: this.type,
      rules: this.showData.reduce((results, item, showIndex) => {
        if (!item.isNew || showIndex === index) {
          results.push({
            kind: item.kind,
            callee_server: item.callee_server,
            callee_service: item.callee_service,
            callee_method: item.callee_method,
            code_type_rules: item.code_type_rules,
            is_global: item.is_global,
          });
        }
        return results;
      }, []),
    };
    try {
      this.$set(this.showData[index], 'isSaving', true);
      await setCodeRedefinedRule(params);
      this.$set(this.showData[index], 'isNew', false);
      this.$set(this.rowEditMap, this.showData[index].id, false);
      this.$set(this.data, index, cloneDeep(this.showData[index]));
      this.$bkMessage({
        message: this.$t('配置保存成功，需要 5 分钟左右生效。'),
        theme: 'success',
      });
    } finally {
      this.$set(this.showData[index], 'isSaving', false);
      this.$set(this.data[index], 'isSaving', false);
    }
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
              default: ({ row, $index }) => {
                if (row.is_global) {
                  const isShowGlobalSign =
                    (row.kind === 'callee' && item.prop === 'callee_service') ||
                    (row.kind === 'caller' && item.prop === 'callee_server');
                  return (
                    <div class='interface-column-readonly'>
                      {isShowGlobalSign && <div class='rect-bar' />}
                      {isShowGlobalSign && (
                        <span
                          class='icon-monitor icon-web'
                          v-bk-tooltips={{ content: this.$tc('全局生效规则') }}
                        />
                      )}
                      <div
                        class='value-content'
                        v-bk-overflow-tips
                      >
                        {row[item.prop] === '' ? '--' : row[item.prop]}
                      </div>
                    </div>
                  );
                }
                if (!this.rowEditMap[row.id]) {
                  return (
                    <div
                      class='interface-column-readonly'
                      v-bk-overflow-tips
                    >
                      <div
                        class='value-content'
                        v-bk-overflow-tips
                      >
                        {row[item.prop] === '' ? '--' : row[item.prop]}
                      </div>
                    </div>
                  );
                }
                return (
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
                    {this.repeatRulesIdSet.has(row.id) && item.prop === 'callee_method' && (
                      <i
                        class='icon-monitor icon-mind-fill'
                        v-bk-tooltips={{
                          content:
                            this.type === 'caller'
                              ? this.$tc('被调服务、被调 Service、被调接口的组合值须唯一')
                              : this.$tc('被调 Service、被调接口的组合值须唯一'),
                        }}
                      />
                    )}
                  </div>
                );
              },
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
              default: ({ row, $index }) => {
                if (row.is_global) {
                  const isEmpty = this.codeStatus.every(item => !row.code_type_rules[item.value]);
                  if (isEmpty) {
                    return <span>--</span>;
                  }
                  return (
                    <div class='code-rules-readonly'>
                      {this.codeStatus.map(item => {
                        if (!row.code_type_rules[item.value]) {
                          return null;
                        }
                        return (
                          <div
                            class='code-status-rule-item'
                            key={item.value}
                          >
                            <TagBlock
                              class='code-tag-block'
                              data={row.code_type_rules[item.value].split(',')}
                              size='small'
                            />
                            <div class='code-status-rule-item-label'>
                              <i18n path={'重定义为 {0}'}>
                                <span class={[item.value]}>{item.label}</span>
                              </i18n>
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  );
                }
                if (!this.rowEditMap[row.id]) {
                  const isEmpty = this.codeStatus.every(item => !row.code_type_rules[item.value]);
                  if (isEmpty) {
                    return <span>--</span>;
                  }
                  return (
                    <div class='code-rules-readonly'>
                      {this.codeStatus.map(item => {
                        if (!row.code_type_rules[item.value]) {
                          return null;
                        }

                        return (
                          <div
                            class='code-status-rule-item'
                            key={item.value}
                          >
                            <TagBlock
                              class='code-tag-block'
                              data={row.code_type_rules[item.value].split(',')}
                              size='small'
                            />
                            <div class='code-status-rule-item-label'>
                              <i18n path={'重定义为 {0}'}>
                                <span class={[item.value]}>{item.label}</span>
                              </i18n>
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  );
                }
                return (
                  <bk-form
                    ref={`codeRulesForm_${row.id}`}
                    class='code-rules'
                    label-width={0}
                    {...{
                      props: {
                        model: row.code_type_rules,
                        rules: this.getCodeTypeRules(row.code_type_rules),
                      },
                    }}
                  >
                    {this.codeStatus.map(item => (
                      <div
                        class='code-status-rule-item'
                        key={item.value}
                      >
                        <bk-form-item property={item.value}>
                          <bk-input
                            value={row.code_type_rules[item.value]}
                            on-change={v => this.handleValueChange(v, item.value, $index)}
                          />
                        </bk-form-item>
                        <i18n path={'重定义为 {0}'}>
                          <span class={[item.value]}>{item.label}</span>
                        </i18n>
                      </div>
                    ))}
                  </bk-form>
                );
              },
            }}
          />
        );
      default:
        return undefined;
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
          <div class='top-btns'>
            <bk-button
              theme='primary'
              icon='plus'
              on-click={this.handleAddNewRow}
            >
              {this.$t('新增')}
            </bk-button>

            <div class='tip-text'>
              <i class='icon-monitor icon-tishi' />
              <span>{this.$t('点击')}</span>
              <bk-button
                theme='primary'
                size='small'
                class='global-config-btn'
                text
                on-click={this.handleGlobalConfigClick}
              >
                {/* <i class='icon-monitor icon-fenxiang' /> */}
                {this.$t('应用配置')}
              </bk-button>
              <span>{this.$t('可配置全局返回码规则')}</span>
            </div>
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
            {this.tableLoading ? (
              <div class='skeleton-wrap'>
                <div class='skeleton-element' />
                <div class='skeleton-element' />
                <div class='skeleton-element' />
              </div>
            ) : (
              <bk-table
                ref='tableRef'
                data={this.showData}
                border
                row-auto-height
                row-class-name={({ row }) => (row.is_global ? 'rule-row-global' : 'rule-row')}
              >
                {this.showColumn.map(item => this.renderColumn(item))}
                <bk-table-column
                  label={this.$tc('操作')}
                  width={136}
                  scopedSlots={{
                    default: ({ $index, row }) => {
                      if (row.is_global) {
                        return (
                          <div
                            class='global-config-main'
                            on-click={this.handleGlobalConfigClick}
                          >
                            <i class='icon-monitor icon-fenxiang' />
                            <span>{this.$t('修改全局配置')}</span>
                          </div>
                        );
                      }
                      if (this.rowEditMap[row.id]) {
                        return (
                          <div class='operate-btns'>
                            <bk-button
                              class='btn'
                              theme='primary'
                              disabled={!this.showData[$index].isAbleSave || this.showData[$index].isSaving}
                              loading={this.showData[$index].isSaving}
                              text
                              onClick={() => this.handleSaveEditRow($index)}
                            >
                              {this.$t('保存')}
                            </bk-button>
                            <bk-button
                              class='btn'
                              theme='primary'
                              text
                              onClick={() => this.handleCancelEditRow($index)}
                            >
                              {this.$t('取消')}
                            </bk-button>
                          </div>
                        );
                      }
                      return (
                        <div class='operate-btns'>
                          <bk-button
                            class='btn'
                            theme='primary'
                            text
                            onClick={() => this.handleEditRow($index)}
                          >
                            {this.$t('编辑')}
                          </bk-button>
                          {this.data.length > 1 && (
                            <bk-button
                              class='btn'
                              theme='danger'
                              text
                              onClick={() => this.handleDeleteRow($index)}
                            >
                              {this.$t('删除')}
                            </bk-button>
                          )}
                        </div>
                      );
                    },
                  }}
                />
              </bk-table>
            )}
          </div>
        </div>
      </bk-sideslider>
    );
  }
}
