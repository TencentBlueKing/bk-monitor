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
import { Component, Emit, InjectReactive, Prop, Ref, Watch } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import { cloneDeep } from 'lodash';
import { getFieldOptionValues } from 'monitor-api/modules/apm_metric';
import { listCodeRedefinedRule, setCodeRedefinedRule } from 'monitor-api/modules/apm_service';
import { downloadFile } from 'monitor-common/utils';
import { random } from 'monitor-common/utils';
import TagBlock from 'monitor-pc/components/tag-block';
import { handleTransformToTimestamp } from 'monitor-pc/components/time-range/utils';
import { uploadJsonFile } from 'monitor-pc/pages/view-detail/utils';

import { VariablesService } from '../../../../utils/variable';

import type { CallOptions, CodeRedefineItem } from '../../type';
import type { TimeRangeType } from 'monitor-pc/components/time-range/time-range';
import ValueTagSelector from 'monitor-pc/components/retrieval-filter/value-tag-selector';
import type {
  IGetValueFnParams,
  IOptionsInfo,
  TGetValueFn,
} from 'monitor-pc/components/retrieval-filter/value-selector-typing';

import './code-redefine-slider.scss';
interface CodeRedefineSliderEvents {
  onShowChange(isShow: boolean): void;
}

interface CodeRedefineSliderProps {
  appName: string;
  callOptions?: Partial<CallOptions>;
  isShow: boolean;
  service: string;
  type: 'callee' | 'caller';
  variablesData?: Record<string, any>;
}

interface ColumnItem {
  label: string;
  loading: boolean;
  options: { text: string; value: string }[];
  prop: string;
  width?: number;
}

@Component
export default class CodeRedefineSlider extends tsc<CodeRedefineSliderProps, CodeRedefineSliderEvents> {
  @Prop({ default: false }) isShow: boolean;
  @Prop({ default: 'caller' }) type: 'callee' | 'caller';
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
  isCurrentCancelClick = false;
  /** 重复的规则id */
  repeatRulesIdSet = new Set();
  codeStatus = [
    { label: this.$tc('失败'), value: 'exception' },
    { label: this.$tc('超时'), value: 'timeout' },
    { label: this.$tc('成功'), value: 'success' },
  ];
  currentEditRowIndex = -1;
  isBatchEdit = false;
  isBatchEditSaving = false;

  get isCaller() {
    return this.type === 'caller';
  }

  get columns(): ColumnItem[] {
    return [
      { label: this.$tc('被调服务'), prop: 'callee_server', options: [], loading: false, width: 245 },
      {
        label: this.$tc('被调 Service'),
        prop: 'callee_service',
        options: [],
        loading: false,
        width: this.isCaller ? 245 : 300,
      },
      {
        label: this.$tc('被调接口'),
        prop: 'callee_method',
        options: [],
        loading: false,
        width: this.isCaller ? 245 : 300,
      },
      {
        label: this.$tc('返回码'),
        prop: 'code_type_rules',
        options: [],
        loading: false,
        width: this.isCaller ? 320 : 400,
      },
    ];
  }

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
      this.currentEditRowIndex = -1;
      this.isBatchEdit = false;
    }
  }

  @Emit('showChange')
  handleShowChange(show: boolean) {
    return show;
  }
  /** 三者都为空时才校验「不能为空」；任一有值则不做该项提示，仅对已填内容做格式校验 */
  getCodeTypeRules(codeTypeRules: CodeRedefineItem['code_type_rules']) {
    const keys: Array<'exception' | 'success' | 'timeout'> = ['success', 'exception', 'timeout'];
    const isAllEmpty = () => keys.every(k => !(codeTypeRules[k] ?? '').toString().trim());

    const fieldRules = () => [
      {
        validator: () => !isAllEmpty(),
        message: window.i18n.tc('返回码不能为空'),
        trigger: 'blur',
      },
      {
        validator: (val: string) =>
          !(val ?? '').toString().trim() ||
          /^(?:[a-zA-Z0-9]+_)?-?\d+(?:~-?\d+)?(?:,(?:[a-zA-Z0-9]+_)?-?\d+(?:~-?\d+)?)*$/.test(
            (val ?? '').toString().trim()
          ),
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
    if (this.isBatchEdit) {
      this.showData.unshift(this.generateNewRow(params));
      return;
    }

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
    this.validRules(index);
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
        this.currentEditRowIndex = -1;
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
    const data = await uploadJsonFile<CodeRedefineItem[]>(files[0]).catch(() => []);
    const isDataValid =
      this.type === 'caller' ? data.every(item => item.callee_server) : data.every(item => !item.callee_server);
    if (!data || !Array.isArray(data) || !isDataValid) {
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
    const targetData = data.map(item => ({
      ...item,
      id: random(8),
    }));
    const replaceIds = new Set<string>();
    for (let index = 0; index < this.showData.length; index++) {
      const item = this.showData[index];
      const rowKey = `${item.kind}_${item.callee_server}_${item.callee_service}_${item.callee_method}`;
      if (importKeySet.has(rowKey)) {
        this.showData[index] = targetData.find(
          childItem =>
            `${childItem.kind}_${childItem.callee_server}_${childItem.callee_service}_${childItem.callee_method}` ===
            rowKey
        );
        replaceIds.add(this.showData[index].id);
      }
    }
    const newList = targetData.reduce((results, item) => {
      if (!replaceIds.has(item.id)) {
        results.push({
          ...item,
          isImport: true,
        });
      }
      return results;
    }, []);
    const tatalList = [...newList, ...this.showData];
    this.showData = tatalList;
    this.isBatchEdit = true;
  }

  handleImport() {
    if (this.fileRef) {
      this.fileRef.value = '';
      this.fileRef.click();
    }
  }

  handleExport() {
    const exportData = this.data.reduce((results, item) => {
      if (!item.is_global) {
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
    }, []);
    downloadFile(JSON.stringify(exportData, null, 2), 'application/json', 'code-redefine.json');
  }

  /** 校验填写的规则 */
  async validRules(rowIndex?: number) {
    const values = this.showData.map((item, index) => {
      const targetItem = rowIndex === undefined ? item : rowIndex === index ? item : this.data[index];
      return this.type === 'caller'
        ? `${targetItem.callee_server}_${targetItem.callee_service}_${targetItem.callee_method}_${targetItem.is_global}`
        : `${targetItem.callee_service}_${targetItem.callee_method}_${targetItem.is_global}`;
    });
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
    if (this.isCurrentCancelClick) {
      this.isCurrentCancelClick = false;
      return;
    }

    const hash = `#/apm/application/config/${this.appName}?active=codeRedefine`;
    const url = location.href.replace(location.hash, hash);
    window.open(url, '_blank');
  }

  handleCancelEditRow(index: number) {
    this.isCurrentCancelClick = true;
    this.currentEditRowIndex = -1;
    if (this.data[index].isNew && this.showData.length > 0) {
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
    if (this.isBatchEdit) {
      this.showData.splice(index, 1);
      return;
    }
    this.$bkInfo({
      title: this.$t('是否确认删除？'),
      theme: 'danger',
      okText: this.$t('删除'),
      cancelText: this.$t('取消'),
      // TODO：组件库bug，该配置无效，已提issue，待修复
      // confirmLoading: true,
      confirmFn: async () => {
        const dataList = this.data.filter((item, i) => i !== index && !item.isNew);
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
    this.currentEditRowIndex = index;
  }

  async handleSaveEditRow(index: number) {
    const isRowValid = await this.validRules(index);
    if (!isRowValid) {
      return;
    }

    if (JSON.stringify(this.showData[index]) === JSON.stringify(this.data[index]) && !this.showData[index].isNew) {
      this.currentEditRowIndex = -1;
      return;
    }
    const params = {
      app_name: this.appName,
      service_name: this.service,
      kind: this.type,
      rules: this.showData.reduce((results, item, showIndex) => {
        // 编辑态且不是当前行，则提交原始数据
        if (this.currentEditRowIndex === showIndex && showIndex !== index && !item.isNew) {
          const rowItem = this.data.find(i => i.id === item.id);
          if (rowItem) {
            results.push({
              kind: rowItem.kind,
              callee_server: rowItem.callee_server,
              callee_service: rowItem.callee_service,
              callee_method: rowItem.callee_method,
              code_type_rules: rowItem.code_type_rules,
              is_global: rowItem.is_global,
            });
          }
          // 非编辑态或当前行，则提交编辑态数据
        } else if (!item.isNew || showIndex === index) {
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
      this.currentEditRowIndex = -1;
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

  getValueCallback(list: { value: string; text: string }[]): TGetValueFn {
    return (params: IGetValueFnParams): Promise<IOptionsInfo> => {
      const search = params.search?.toLocaleLowerCase() ?? '';
      return Promise.resolve({
        count: 0 as const,
        list: list.reduce((results, item) => {
          if (
            !search ||
            String(item.value).toLocaleLowerCase().includes(search) ||
            String(item.text).toLocaleLowerCase().includes(search)
          ) {
            results.push({
              id: item.value,
              name: item.text,
            });
          }
          return results;
        }, []),
      });
    };
  }

  handleValueTagSelectorChange(value: string, prop: string, index: number) {
    this.handleValueChange(value, prop, index);
  }

  handleBatchEdit() {
    this.isBatchEdit = true;
    this.currentEditRowIndex = -1;
  }

  handleCancelBatchEdit() {
    this.isBatchEdit = false;
    this.showData = cloneDeep(this.data);
  }

  async handleBatchEditSave() {
    this.isBatchEditSaving = true;
    const isValid = await this.validRules();
    if (!isValid) {
      this.isBatchEditSaving = false;
      return;
    }

    const params = {
      app_name: this.appName,
      service_name: this.service,
      kind: this.type,
      rules: this.showData.reduce((results, item) => {
        results.push({
          kind: item.kind,
          callee_server: item.callee_server,
          callee_service: item.callee_service,
          callee_method: item.callee_method,
          code_type_rules: item.code_type_rules,
          is_global: item.is_global,
        });

        return results;
      }, []),
    };
    try {
      await setCodeRedefinedRule(params);
      this.$bkMessage({
        message: this.$t('配置保存成功，需要 5 分钟左右生效。'),
        theme: 'success',
      });
    } finally {
      this.isBatchEditSaving = false;
      this.isBatchEdit = false;
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
            width={item.width}
            scopedSlots={{
              default: ({ row, $index }) => {
                const isFirstColumn =
                  (row.kind === 'callee' && item.prop === 'callee_service') ||
                  (row.kind === 'caller' && item.prop === 'callee_server');
                if (row.is_global) {
                  return (
                    <div class='interface-column-readonly'>
                      {isFirstColumn && <div class='rect-bar' />}
                      {isFirstColumn && (
                        <div class='global-sign-wrapper'>
                          <span
                            class='icon-monitor icon-web'
                            v-bk-tooltips={{ content: this.$tc('全局生效规则') }}
                          />
                        </div>
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
                if (this.currentEditRowIndex !== $index && !this.isBatchEdit) {
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
                const value = row[item.prop]
                  ? [
                      {
                        id: row[item.prop],
                        name: row[item.prop],
                      },
                    ]
                  : [];
                return (
                  <div class='interface-column'>
                    {(row.isImport || row.isNew) && isFirstColumn && <div class='new-sign-bar' />}
                    <ValueTagSelector
                      style='width: 100%'
                      multiple={false}
                      fieldInfo={{
                        field: '',
                        alias: '',
                        methods: [],
                        isEnableOptions: true,
                      }}
                      value={value}
                      tippy-mode
                      getValueFn={this.getValueCallback(item.options)}
                      onChange={data => this.handleValueTagSelectorChange(data as string, item.prop, $index)}
                    />
                    {this.repeatRulesIdSet.has(row.id) && item.prop === 'callee_method' && (
                      <i
                        class='icon-monitor icon-mind-fill'
                        v-bk-tooltips={{
                          content:
                            this.type === 'caller'
                              ? this.$tc('被调服务、被调 Service、被调接口、是否全局的组合值须唯一')
                              : this.$tc('被调 Service、被调接口、是否全局的组合值须唯一'),
                        }}
                      />
                    )}
                  </div>
                );
              },
            }}
            label={item.label}
            prop={item.prop}
          />
        );
      case 'code_type_rules':
        return (
          <bk-table-column
            key={item.prop}
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
                            key={item.value}
                            class='code-status-rule-item'
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
                if (this.currentEditRowIndex !== $index && !this.isBatchEdit) {
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
                            key={item.value}
                            class='code-status-rule-item'
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
                        key={item.value}
                        class='code-status-rule-item'
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
            label={item.label}
            prop={item.prop}
          />
        );
      default:
        return undefined;
    }
  }

  render() {
    return (
      <bk-sideslider
        width={1250}
        class='code-redefine-slider'
        is-show={this.isShow}
        title={this.$t('返回码重定义')}
        quick-close
        {...{ on: { 'update:isShow': this.handleShowChange } }}
      >
        <div
          class='code-redefine-slider-content'
          slot='content'
        >
          <div class='info-table'>
            {this.infoData.map(item => (
              <div
                key={item.key}
                class='table-row'
              >
                <div class='row-label'>{item.label}</div>
                <div class='row-value'>{item.value}</div>
              </div>
            ))}
          </div>
          <div class='top-btns'>
            <span
              v-bk-tooltips={{
                content: this.$t('当前已有配置正在编辑，请先保存或取消'),
                disabled: this.currentEditRowIndex === -1,
              }}
            >
              <bk-button
                icon='plus'
                theme='primary'
                disabled={this.currentEditRowIndex !== -1}
                on-click={this.handleAddNewRow}
              >
                {this.$t('新增')}
              </bk-button>
            </span>
            {!this.isBatchEdit ? (
              <bk-button on-click={this.handleBatchEdit}>
                <i class='icon-monitor icon-mc-wholesale-editor' />
                {this.$t('批量编辑')}
              </bk-button>
            ) : (
              <div class='batch-group'>
                <bk-button
                  outline
                  theme='primary'
                  disabled={this.isBatchEditSaving}
                  loading={this.isBatchEditSaving}
                  on-click={this.handleBatchEditSave}
                >
                  <div class='save-btn'>
                    <i class='bk-icon icon-save' />
                    {this.$t('保存')}
                  </div>
                </bk-button>
                <bk-button
                  icon='close'
                  on-click={this.handleCancelBatchEdit}
                >
                  {this.$t('取消')}
                </bk-button>
              </div>
            )}
            <div class='tip-text'>
              <i class='icon-monitor icon-tishi' />
              <span>{this.$t('点击')}</span>
              <bk-button
                class='global-config-btn'
                size='small'
                theme='primary'
                text
                on-click={this.handleGlobalConfigClick}
              >
                {this.$t('应用配置')}
              </bk-button>
              <span>{this.$t('可配置全局返回码规则')}</span>
            </div>
          </div>
          <div class='submit-table'>
            <div class='explore-btns'>
              <input
                ref='fileRef'
                class='hidden-file-input'
                accept='application/json'
                type='file'
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
                row-key='id'
                row-class-name={({ row }) => (row.is_global ? 'rule-row-global' : 'rule-row')}
                border
                row-auto-height
              >
                {this.showColumn.map(item => this.renderColumn(item))}
                <bk-table-column
                  width={100}
                  // fixed='right'
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
                      if (this.currentEditRowIndex === $index && !this.isBatchEdit) {
                        return (
                          <div class='operate-btns'>
                            <bk-button
                              class='btn'
                              disabled={!this.showData[$index].isAbleSave || this.showData[$index].isSaving}
                              loading={this.showData[$index].isSaving}
                              theme='primary'
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
                          {!this.isBatchEdit && (
                            <div
                              v-bk-tooltips={{
                                content: this.$t('当前已有配置正在编辑，请先保存或取消'),
                                disabled: this.currentEditRowIndex === -1 || this.currentEditRowIndex === $index,
                              }}
                            >
                              <bk-button
                                class='btn'
                                theme='primary'
                                disabled={this.currentEditRowIndex !== -1 && this.currentEditRowIndex !== $index}
                                text
                                onClick={() => this.handleEditRow($index)}
                              >
                                {this.$t('编辑')}
                              </bk-button>
                            </div>
                          )}
                          <div
                            v-bk-tooltips={{
                              content: this.$t('当前已有配置正在编辑，请先保存或取消'),
                              disabled: this.currentEditRowIndex === -1 || this.currentEditRowIndex === $index,
                            }}
                          >
                            <bk-button
                              class='btn'
                              theme='danger'
                              disabled={
                                this.currentEditRowIndex !== -1 &&
                                this.currentEditRowIndex !== $index &&
                                !this.isBatchEdit
                              }
                              text
                              onClick={() => this.handleDeleteRow($index)}
                            >
                              {this.$t('删除')}
                            </bk-button>
                          </div>
                        </div>
                      );
                    },
                  }}
                  label={this.$tc('操作')}
                />
              </bk-table>
            )}
          </div>
        </div>
      </bk-sideslider>
    );
  }
}
