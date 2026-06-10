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
import { Component, InjectReactive, Prop, Ref, Watch } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import dayjs from 'dayjs';
import { cloneDeep } from 'lodash';
import { getFieldOptionValues } from 'monitor-api/modules/apm_metric';
import { listCodeRedefinedRule, serviceList, setCodeRedefinedRule } from 'monitor-api/modules/apm_service';
import { downloadFile, random } from 'monitor-common/utils';
import TagBlock from 'monitor-pc/components/tag-block';

import type { TimeRangeType } from 'monitor-pc/components/time-range/time-range';
import type { CallOptions, CodeRedefineItem } from 'monitor-ui/chart-plugins/plugins/apm-service-caller-callee/type';
import ValueTagSelector from 'monitor-pc/components/retrieval-filter/value-tag-selector';
import type {
  IGetValueFnParams,
  IOptionsInfo,
  TGetValueFn,
} from 'monitor-pc/components/retrieval-filter/value-selector-typing';

import './index.scss';

interface ColumnItem {
  label: string;
  loading: boolean;
  minWidth?: number;
  options: { text: string; value: string }[];
  prop: string;
  width?: number;
}

interface Props {
  /** 应用名（接口请求主键） */
  appName: string;
  /**是否批量编辑模式 */
  isBatchEdit: boolean;
  callOptions?: Partial<CallOptions>;
  variablesData?: Record<string, any>;
}

@Component
export default class RedefineTabContent extends tsc<Props> {
  @Prop({ default: '' }) appName: string;
  @Prop({ default: false }) isBatchEdit: boolean;
  @Prop({ default: window.innerHeight - 350 }) tableMaxHeight: number;

  @InjectReactive('timeRange') readonly timeRange!: TimeRangeType;
  @InjectReactive('callOptions') readonly callOptions: CallOptions;
  @InjectReactive({ from: 'variablesData', default: () => ({}) }) readonly variablesData!: Record<string, any>;

  @Ref('tableRef') tableRef!: any;

  /** 全量数据（作为编辑回滚快照） */
  data: CodeRedefineItem[] = [];
  /** 当前表格展示数据（可能被筛选） */
  showData: CodeRedefineItem[] = [];
  /** 表格加载状态 */
  tableLoading = false;

  /** 重复的规则id */
  repeatRulesIdSet = new Set<string>();

  columns: ColumnItem[] = [
    { label: this.$tc('类型'), prop: 'kind', options: [], loading: false, width: 124 },
    { label: this.$tc('被调服务'), prop: 'callee_server', options: [], loading: false, width: 260 },
    { label: this.$tc('被调 Service'), prop: 'callee_service', options: [], loading: false, width: 260 },
    { label: this.$tc('被调接口'), prop: 'callee_method', options: [], loading: false, width: 260 },
    { label: this.$tc('返回码'), prop: 'code_type_rules', options: [], loading: false },
    { label: this.$tc('作用范围'), prop: 'service_names', options: [], loading: false, width: 204 },
  ];

  codeStatus = [
    { label: this.$tc('失败'), value: 'exception' },
    { label: this.$tc('超时'), value: 'timeout' },
    { label: this.$tc('成功'), value: 'success' },
  ];

  callTypeOptions = [
    { text: this.$tc('主调'), value: 'caller' },
    { text: this.$tc('被调'), value: 'callee' },
  ];

  applyScopeOptions = [];

  /** 主调枚举值映射 */
  callerEnumOptionsMap = {
    callee_server: [],
    callee_service: [],
    callee_method: [],
  };

  /** 被调枚举值映射 */
  calleeEnumOptionsMap = {
    callee_server: [],
    callee_service: [],
    callee_method: [],
  };

  savingMap: Record<string, boolean> = {};
  ableSaveMap: Record<string, boolean> = {};
  filterValues: string[] = [];
  currentEditRowId: string = '';

  @Watch('currentEditRowId', { immediate: true })
  watchCurrentEditRowIdChange(id: string) {
    this.$emit('currentEditRowIdChange', id);
  }

  /** 三者都为空时才校验「不能为空」；任一有值则不做该项提示，仅对已填内容做格式校验 */
  getCodeTypeRules(codeTypeRules: CodeRedefineItem['code_type_rules']) {
    const keys: Array<'exception' | 'success' | 'timeout'> = ['success', 'exception', 'timeout'];
    // success/exception/timeout 三项全部为空时，提示“返回码不能为空”
    const isAllEmpty = () => keys.every(k => !(codeTypeRules[k] ?? '').toString().trim());

    // 每个状态字段共享同一组校验：
    // 1. 三项至少填一项；2. 已填写值需要满足返回码格式
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

  generateNewRow() {
    // 新增行默认值：被调类型、全局生效、三类返回码均为空
    return {
      id: random(8),
      kind: 'callee',
      callee_server: '',
      callee_service: '',
      callee_method: '',
      code_type_rules: {
        success: '',
        exception: '',
        timeout: '',
      },
      isNew: true,
      is_global: true,
      service_names: ['0'],
    };
  }

  addRow() {
    // 新增后插入到顶部，并进入编辑态
    const newRow = this.generateNewRow();
    if (this.isBatchEdit) {
      this.showData.unshift(newRow);
      return;
    }

    this.$set(this.ableSaveMap, newRow.id, false);
    this.$set(this.savingMap, newRow.id, false);
    this.showData.unshift(newRow);
    this.data.unshift(cloneDeep(newRow));
    this.handleEditRow(newRow.id);
  }

  async getCodeRedefineList() {
    // 拉取重定义规则列表
    this.tableLoading = true;
    const data = await listCodeRedefinedRule({
      app_name: this.appName,
    }).finally(() => {
      this.tableLoading = false;
    });
    if (data.length) {
      for (let index = 0; index < data.length; index++) {
        // 补充前端运行时字段
        const id = random(8);
        data[index].id = id;
        data[index].isNew = false;
        // 全局规则在前端展示态固定为 ['0']
        if (data[index].is_global) {
          data[index].service_names = ['0'];
        }
        // 默认非编辑态
        this.currentEditRowId = '';
        this.$set(this.ableSaveMap, id, false);
        this.$set(this.savingMap, id, false);
      }
      // showData 用于展示，data 作为基准快照
      this.showData = data;
      this.data = cloneDeep(data);
    } else {
      // 无历史规则时给一条默认可编辑行
      this.addRow();
    }
  }

  async getServiceList() {
    const data = await serviceList({
      app_name: this.appName,
    });
    this.applyScopeOptions = data.reduce(
      (results, item) => {
        // 仅保留 trpc 服务作为作用范围候选
        if (item.system.name === 'trpc') {
          results.push({
            text: item.service_name,
            value: item.service_name,
          });
        }
        return results;
      },
      [
        {
          // 约定 value='0' 代表全局生效
          text: this.$tc('全局生效'),
          value: '0',
        },
      ]
    );
  }

  async getEnumOptions() {
    // 三个维度共用同一套拉取逻辑
    const fields = ['callee_server', 'callee_service', 'callee_method'];
    // 近 1 小时时间范围，获取实时枚举候选
    const startTime = dayjs().subtract(1, 'hour').unix();
    const endTime = dayjs().unix();
    // 主调口径字段枚举
    const callerResults = await Promise.all(
      fields.map(field =>
        getFieldOptionValues({
          field,
          start_time: startTime,
          end_time: endTime,
          app_name: this.appName,
          metric_field: 'rpc_client_handled_total',
        })
      )
    );
    // 被调口径字段枚举
    const calleeResults = await Promise.all(
      fields.map(field =>
        getFieldOptionValues({
          field,
          start_time: startTime,
          end_time: endTime,
          app_name: this.appName,
          metric_field: 'rpc_server_handled_total',
        })
      )
    );
    // fields 下标与查询结果下标一一对应，组装为 map 便于按列读取
    this.callerEnumOptionsMap = callerResults.reduce((acc, cur, index) => {
      acc[fields[index]] = cur;
      return acc;
    }, {});
    this.calleeEnumOptionsMap = calleeResults.reduce((acc, cur, index) => {
      acc[fields[index]] = cur;
      return acc;
    }, {});
  }

  /** 校验填写的规则 */
  async validRules(rowId?: string) {
    // 规则唯一键：类型+被调服务+被调service+被调接口+是否全局+作用范围
    // 两个同时处于编辑状态的记录，唯一性校验要根据那些已保存的数据来计算
    const data = this.isBatchEdit ? this.showData : this.data;
    const dataMap: Record<string, CodeRedefineItem> = data.reduce((acc, item) => {
      acc[item.id] = item;
      return acc;
    }, {});
    const values = this.showData.map(item => {
      const targetItem = rowId ? (item.id === rowId ? item : dataMap[item.id]) : item;
      const serviceNames = cloneDeep(targetItem.service_names).sort().join(',');
      return `${targetItem.kind}_${targetItem.callee_server}_${targetItem.callee_service}_${targetItem.callee_method}_${targetItem.is_global}_${serviceNames}`;
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
    // 收集每一行“返回码规则表单”的异步校验
    const codeValidate = this.showData.map(item => this.tableRef.$refs[`codeRulesForm_${item.id}`]?.validate());
    const codeValid = await Promise.allSettled(codeValidate);
    for (let index = 0; index < this.showData.length; index++) {
      const { id } = this.showData[index];
      if (
        this.repeatRulesIdSet.has(id) ||
        codeValid[index].status === 'rejected' ||
        JSON.stringify(this.showData[index]) === JSON.stringify(this.data[index])
      ) {
        this.$set(this.ableSaveMap, id, false);
      } else {
        this.$set(this.ableSaveMap, id, true);
      }
    }
    // 只要存在格式/必填错误或重复规则，则不允许保存
    if (codeValid.some(item => item.status === 'rejected') || this.repeatRulesIdSet.size !== 0) {
      return false;
    }
    return true;
  }

  async handleValueChange(value: string | string[], prop: string, id: string) {
    let newValue = value;
    const index = this.showData.findIndex(item => item.id === id);
    if (['success', 'exception', 'timeout'].includes(prop)) {
      // 三个返回码状态写入 code_type_rules 子对象
      this.$set(this.showData[index].code_type_rules, prop, newValue);
    } else {
      if (prop === 'kind') {
        // 当类型为「被调」时，「被调服务」不让填
        if (value === 'callee') {
          this.$set(this.showData[index], 'callee_server', '');
        }
      }
      if (prop === 'service_names') {
        // “全局生效(0)”与具体服务互斥，交互规则同 remark 组件
        newValue = cloneDeep(value);
        if (newValue.includes('0') && value.length > 1) {
          if (value[0] !== '0') {
            newValue = ['0'];
            this.$set(this.showData[index], 'is_global', true);
          } else {
            newValue = (newValue as string[]).filter(item => item !== '0');
            this.$set(this.showData[index], 'is_global', false);
          }
        }
      }
      // 普通字段直接写入当前行
      this.$set(this.showData[index], prop, newValue);
    }
    this.validRules(this.showData[index].id);
  }

  handleEditRow(id: string) {
    // 切换为编辑态
    this.currentEditRowId = id;
  }

  handleCancelEditRow(id: string) {
    // 退出编辑态
    this.currentEditRowId = '';
    const dataIndex = this.data.findIndex(item => item.id === id);
    const showIndex = this.showData.findIndex(item => item.id === id);
    const dataRow = this.data[dataIndex];
    // 新建且仍为空白的行，取消时直接移除
    if (dataRow.isNew && this.data.length > 0) {
      const isEmpty =
        dataRow.callee_server === '' &&
        dataRow.callee_service === '' &&
        dataRow.callee_method === '' &&
        dataRow.code_type_rules.success === '' &&
        dataRow.code_type_rules.exception === '' &&
        dataRow.code_type_rules.timeout === '' &&
        dataRow.service_names.length === 1 &&
        dataRow.service_names[0] === '0';
      if (isEmpty) {
        this.showData.splice(showIndex, 1);
        this.data.splice(dataIndex, 1);
        return;
      }
    }
    // 回滚到编辑前快照
    this.$set(this.showData, showIndex, cloneDeep(this.data[dataIndex]));
  }

  handleDeleteRow(id: string) {
    const showIndex = this.showData.findIndex(item => item.id === id);
    // 批量编辑模式下，直接删
    if (this.isBatchEdit) {
      this.showData.splice(showIndex, 1);
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
        // 删除通过“提交剩余全量规则”完成
        const dataList = this.data.filter(item => item.id !== id && !item.isNew);

        const dataIndex = this.data.findIndex(item => item.id === id);
        const params = {
          app_name: this.appName,
          rules: dataList.map(item => ({
            kind: item.kind,
            callee_server: item.callee_server,
            callee_service: item.callee_service,
            callee_method: item.callee_method,
            code_type_rules: item.code_type_rules,
            service_names: item.is_global ? [] : item.service_names,
            is_global: item.is_global,
          })),
        };
        await setCodeRedefinedRule(params);
        // 接口成功后再同步本地数组
        this.showData.splice(showIndex, 1);
        this.data.splice(dataIndex, 1);
        this.$bkMessage({
          message: this.$t('删除成功，需要 5 分钟左右生效。'),
          theme: 'success',
        });
      },
    });
  }

  async handleSaveEditRow(id: string) {
    const isRowValid = await this.validRules(id);
    if (!isRowValid) {
      return;
    }

    const showRow = this.showData.find(item => item.id === id);
    const dataIndex = this.data.findIndex(item => item.id === id);
    const dataRow = this.data[dataIndex];
    // 非新建且内容未变化时，无需调用接口
    if (JSON.stringify(showRow) === JSON.stringify(dataRow) && !showRow.isNew) {
      this.currentEditRowId = '';
      return;
    }

    const params = {
      app_name: this.appName,
      rules: this.data.reduce((results, item) => {
        if (item.id === id) {
          results.push({
            kind: showRow.kind,
            callee_server: showRow.callee_server,
            callee_service: showRow.callee_service,
            callee_method: showRow.callee_method,
            code_type_rules: showRow.code_type_rules,
            is_global: showRow.is_global,
            // 后端协议：全局规则 service_names 传空数组
            service_names: showRow.is_global ? [] : showRow.service_names,
          });
        } else if (!item.isNew) {
          results.push({
            kind: item.kind,
            callee_server: item.callee_server,
            callee_service: item.callee_service,
            callee_method: item.callee_method,
            code_type_rules: item.code_type_rules,
            service_names: item.is_global ? [] : item.service_names,
            is_global: item.is_global,
          });
        }
        return results;
      }, []),
    };
    try {
      // 行级 loading，防止重复提交
      this.$set(this.savingMap, showRow.id, true);
      await setCodeRedefinedRule(params);
      // 保存成功：更新编辑态与快照
      this.$set(showRow, 'isNew', false);
      this.currentEditRowId = '';
      this.$set(this.data, dataIndex, cloneDeep(showRow));
      this.$bkMessage({
        message: this.$t('配置保存成功，需要 5 分钟左右生效。'),
        theme: 'success',
      });
    } finally {
      // 无论成功失败都关闭 loading
      this.$set(this.savingMap, showRow.id, false);
      this.$set(this.ableSaveMap, showRow.id, false);
    }
  }

  handleFilterChange(filters: Record<string, string[]>) {
    // 读取“作用范围”列的过滤条件
    const values = Object.values(filters)[0];
    this.filterValues = values;
    if (values.length) {
      const valuesSet = new Set(values);
      const isIncluGlobal = valuesSet.has('0');
      // 命中当前服务或命中全局规则时保留
      const showData = this.data.filter(
        item => item.service_names.some(service => valuesSet.has(service)) || (isIncluGlobal && item.is_global)
      );
      this.showData = cloneDeep(showData);
    } else {
      // 清空筛选还原全量
      this.showData = cloneDeep(this.data);
    }
  }

  handleImport(data: CodeRedefineItem[]) {
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
    // 记录已被导入数据替换的旧行 id，用于后续生成新增列表
    const replaceIds = new Set<string>();
    for (let index = 0; index < this.showData.length; index++) {
      const item = this.showData[index];
      const rowKey = `${item.kind}_${item.callee_server}_${item.callee_service}_${item.callee_method}`;
      if (importKeySet.has(rowKey)) {
        // 命中相同组合键时，用导入值覆盖当前行
        const replaceItem = targetData.find(
          childItem =>
            `${childItem.kind}_${childItem.callee_server}_${childItem.callee_service}_${childItem.callee_method}` ===
            rowKey
        );
        replaceItem.service_names = replaceItem.is_global ? ['0'] : replaceItem.service_names;
        this.showData[index] = replaceItem;
        replaceIds.add(this.showData[index].id);
      }
    }
    // 剩余未替换项视为纯新增，插到表格前部
    const newList = targetData.reduce((results, item) => {
      if (!replaceIds.has(item.id)) {
        results.push({
          ...item,
          isImport: true,
          service_names: item.is_global ? ['0'] : item.service_names,
        });
      }
      return results;
    }, []);
    const tatalList = [...newList, ...this.showData];
    this.showData = tatalList;
  }

  handleExport() {
    // 以当前快照数据导出，保留结构与缩进方便二次编辑
    const exportData = this.data.map(item => ({
      kind: item.kind,
      callee_server: item.callee_server,
      callee_service: item.callee_service,
      callee_method: item.callee_method,
      code_type_rules: item.code_type_rules,
      service_names: item.is_global ? [] : item.service_names,
      is_global: item.is_global,
    }));
    downloadFile(JSON.stringify(exportData, null, 2), 'application/json', 'code-redefine.json');
  }

  getValueCallback(kind: string, prop: string): TGetValueFn {
    return (params: IGetValueFnParams): Promise<IOptionsInfo> => {
      const enumOptions = kind === 'caller' ? this.callerEnumOptionsMap[prop] : this.calleeEnumOptionsMap[prop];
      const search = params.search?.toLocaleLowerCase() ?? '';
      return Promise.resolve({
        count: 0 as const,
        list: enumOptions.reduce((results, item) => {
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

  handleValueTagSelectorChange(value: string, prop: string, id: string) {
    this.handleValueChange(value, prop, id);
  }

  handleCancelBatchEdit() {
    this.showData = cloneDeep(this.data);
  }

  handleBatchEdit() {
    this.currentEditRowId = '';
  }

  async handleBatchSave() {
    const validResult = await this.validRules();
    if (!validResult) {
      // 无论成功失败都关闭 loading
      this.$emit('batchSaveFailed');
      return;
    }
    const params = {
      app_name: this.appName,
      rules: this.showData.reduce((results, item) => {
        results.push({
          kind: item.kind,
          callee_server: item.callee_server,
          callee_service: item.callee_service,
          callee_method: item.callee_method,
          code_type_rules: item.code_type_rules,
          service_names: item.is_global ? [] : item.service_names,
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
      // 无论成功失败都关闭 loading
      this.$emit('batchSaveSuccess');
    }
  }

  created() {
    // 页面初始化：并行加载规则数据、枚举候选、作用范围选项
    this.getCodeRedefineList();
    this.getEnumOptions();
    this.getServiceList();
  }

  renderColumn(item: ColumnItem) {
    // 按列类型渲染“只读态 / 编辑态”双视图
    switch (item.prop) {
      case 'kind':
        return (
          <bk-table-column
            key={item.prop}
            width={item.width}
            scopedSlots={{
              default: ({ row }) => {
                // 非编辑态展示文本
                if (this.currentEditRowId !== row.id && !this.isBatchEdit) {
                  return (
                    <div>
                      {row[item.prop] === '' ? '--' : row[item.prop] === 'caller' ? this.$tc('主调') : this.$tc('被调')}
                    </div>
                  );
                }
                return (
                  <div class='interface-column'>
                    {(row.isImport || row.isNew) && <div class='new-sign-bar' />}
                    {/* 编辑态：类型可选且可自定义创建 */}
                    <bk-select
                      clearable={false}
                      placeholder={this.$tc('请选择或输入')}
                      value={row[item.prop]}
                      allow-create
                      onChange={v => this.handleValueChange(v, item.prop, row.id)}
                    >
                      {this.callTypeOptions.map(opt => (
                        <bk-option
                          id={opt.value}
                          key={opt.value}
                          name={opt.text}
                        />
                      ))}
                    </bk-select>
                  </div>
                );
              },
            }}
            label={item.label}
            prop={item.prop}
          />
        );
      case 'callee_server':
      case 'callee_service':
      case 'callee_method':
        return (
          <bk-table-column
            key={item.prop}
            width={item.width}
            scopedSlots={{
              default: ({ row }) => {
                // 非编辑态：纯文本
                if (this.currentEditRowId !== row.id && !this.isBatchEdit) {
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
                // 业务约束：kind=callee 时，callee_server 禁止输入
                const isCalleeServerDisabled = item.prop === 'callee_server' && row.kind === 'callee';
                const value = row[item.prop]
                  ? [
                      {
                        id: row[item.prop],
                        name: row[item.prop],
                      },
                    ]
                  : [];
                if (isCalleeServerDisabled) {
                  return <span style='color: #c4c6cc;'>{this.$t('被调无需选择')}</span>;
                }
                return (
                  <div class='interface-column'>
                    <ValueTagSelector
                      style='width: 100%'
                      v-bk-tooltips={{
                        content: this.$t('「被调」类型无需填写「被调服务」'),
                        disabled: !isCalleeServerDisabled,
                      }}
                      multiple={false}
                      fieldInfo={{
                        field: '',
                        alias: '',
                        methods: [],
                        isEnableOptions: true,
                      }}
                      value={value}
                      tippy-mode
                      getValueFn={this.getValueCallback(row.kind, item.prop)}
                      onChange={data => this.handleValueTagSelectorChange(data, item.prop, row.id)}
                    />
                    {this.repeatRulesIdSet.has(row.id) && item.prop === 'callee_method' && (
                      <i
                        class='icon-monitor icon-mind-fill'
                        v-bk-tooltips={{
                          content: this.$tc('类型、被调服务、被调Service、被调接口、是否全局的组合值须唯一'),
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
              default: ({ row }) => {
                // 非编辑态：按状态分组展示返回码，空值不展示
                if (this.currentEditRowId !== row.id && !this.isBatchEdit) {
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
                  // 编辑态：每行一个 form，支持按状态字段独立校验
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
                            // on-change 与组件事件命名保持一致
                            on-change={v => this.handleValueChange(v, item.value, row.id)}
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
            min-width={280}
            prop={item.prop}
          />
        );
      case 'service_names':
        return (
          <bk-table-column
            key={item.prop}
            width={item.width}
            scopedSlots={{
              default: ({ row }) => {
                // 非编辑态：作用范围列表
                if (this.currentEditRowId !== row.id && !this.isBatchEdit) {
                  return (
                    <div class='interface-column-readonly'>
                      <div class='tag-list-content'>
                        {row[item.prop].map(item => (
                          <bk-tag key={item}>{item === '0' ? this.$tc('全局生效') : item}</bk-tag>
                        ))}
                      </div>
                    </div>
                  );
                }
                return (
                  <div class='interface-column'>
                    {/* 编辑态：多选作用范围（含全局生效） */}
                    <bk-select
                      class='scoped-select'
                      clearable={false}
                      disabled={item.loading}
                      ext-popover-cls='scoped-select-popover'
                      loading={item.loading}
                      placeholder={this.$tc('请选择或输入')}
                      showEmpty={!item.loading && !item.options.length}
                      value={row[item.prop]}
                      multiple
                      display-tag
                      searchable
                      onChange={v => this.handleValueChange(v, item.prop, row.id)}
                    >
                      {this.applyScopeOptions.map(opt => (
                        <bk-option
                          id={opt.value}
                          key={opt.value}
                          name={opt.text}
                        />
                      ))}
                    </bk-select>
                  </div>
                );
              },
            }}
            filters={this.applyScopeOptions}
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
      <div class='return-code-redefine-content'>
        <div class='submit-table'>
          {this.tableLoading ? (
            <div class='skeleton-wrap'>
              <div class='skeleton-element' />
              <div class='skeleton-element' />
              <div class='skeleton-element' />
            </div>
          ) : (
            <bk-table
              ref='tableRef'
              max-height={this.tableMaxHeight}
              data={this.showData}
              empty-text={this.filterValues.length ? this.$tc('搜索结果为空') : this.$t('暂无数据')}
              row-class-name='return-code-redefine-row'
              border
              row-key='id'
              row-auto-height
              on-filter-change={this.handleFilterChange}
            >
              {this.columns.map(item => this.renderColumn(item))}
              <bk-table-column
                width={120}
                fixed='right'
                scopedSlots={{
                  default: ({ row }) => {
                    if (this.currentEditRowId === row.id && !this.isBatchEdit) {
                      return (
                        <div class='operate-btns'>
                          <bk-button
                            class='btn'
                            disabled={!this.ableSaveMap[row.id] || this.savingMap[row.id]}
                            loading={this.savingMap[row.id]}
                            theme='primary'
                            text
                            onClick={() => this.handleSaveEditRow(row.id)}
                          >
                            {this.$t('保存')}
                          </bk-button>
                          <bk-button
                            class='btn'
                            theme='primary'
                            text
                            onClick={() => this.handleCancelEditRow(row.id)}
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
                              disabled: this.currentEditRowId === '' || this.currentEditRowId === row.id,
                            }}
                          >
                            <bk-button
                              class='btn'
                              theme='primary'
                              disabled={this.currentEditRowId !== '' && this.currentEditRowId !== row.id}
                              text
                              onClick={() => this.handleEditRow(row.id)}
                            >
                              {this.$t('编辑')}
                            </bk-button>
                          </div>
                        )}
                        <div
                          v-bk-tooltips={{
                            content: this.$t('当前已有配置正在编辑，请先保存或取消'),
                            disabled: this.currentEditRowId === '' || this.currentEditRowId === row.id,
                          }}
                        >
                          <bk-button
                            class='btn'
                            theme='danger'
                            disabled={this.currentEditRowId !== '' && this.currentEditRowId !== row.id}
                            text
                            onClick={() => this.handleDeleteRow(row.id)}
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
    );
  }
}
