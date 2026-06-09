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
import { getCodeRemarks, serviceList, setCodeRemark } from 'monitor-api/modules/apm_service';
import { downloadFile, random } from 'monitor-common/utils';

import type { TimeRangeType } from 'monitor-pc/components/time-range/time-range';
import type { CallOptions } from 'monitor-ui/chart-plugins/plugins/apm-service-caller-callee/type';
import ValueTagSelector from 'monitor-pc/components/retrieval-filter/value-tag-selector';
import type {
  IGetValueFnParams,
  IOptionsInfo,
  TGetValueFn,
} from 'monitor-pc/components/retrieval-filter/value-selector-typing';

import './index.scss';

interface CodeRemarkItem {
  code: string;
  id?: string;
  is_global: boolean;
  isNew?: boolean;
  kind: string;
  remark: string;
  service_names: string[];
  isImport?: boolean;
}

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
  callOptions?: Partial<CallOptions>;
  variablesData?: Record<string, any>;
  isBatchEdit: boolean;
}

@Component
export default class RemarkTabContent extends tsc<Props> {
  @Prop({ default: '' }) appName: string;
  @Prop({ default: false }) isBatchEdit: boolean;
  @Prop({ default: window.innerHeight - 350 }) tableMaxHeight: number;

  @InjectReactive('timeRange') readonly timeRange!: TimeRangeType;
  @InjectReactive('callOptions') readonly callOptions: CallOptions;
  @InjectReactive({ from: 'variablesData', default: () => ({}) }) readonly variablesData!: Record<string, any>;

  @Ref('tableRef') tableRef!: any;

  /** 全量数据（作为编辑前快照） */
  data: CodeRemarkItem[] = [];
  /** 表格当前展示数据（可能受过滤影响） */
  showData: CodeRemarkItem[] = [];
  /** 表格骨架屏状态 */
  tableLoading = false;

  /** 全局为 true 的重复的规则id */
  isGlobalTruerepeatRulesIdSet = new Set<string>();
  /** 全局为 false 的重复的规则id */
  isGlobalFalseRepeatRulesIdSet = new Set<string>();
  /** 返回码列空的行id */
  codeColumnEmptyIdSet = new Set<string>();
  /** 备注列空的行id */
  remarkColumnEmptyIdSet = new Set<string>();

  columns: ColumnItem[] = [
    { label: this.$tc('类型'), prop: 'kind', options: [], loading: false, width: 124, minWidth: 124 },
    { label: this.$tc('返回码'), prop: 'code', options: [], loading: false },
    { label: this.$tc('备注'), prop: 'remark', options: [], loading: false },
    { label: this.$tc('备注范围'), prop: 'service_names', options: [], loading: false },
  ];

  codeStatus = [
    { label: this.$tc('失败'), value: 'exception' },
    { label: this.$tc('超时'), value: 'timeout' },
    { label: this.$tc('成功'), value: 'success' },
  ];

  codeRegex = /^(?:[a-zA-Z0-9]+_)?\d+(?:~\d+)?(?:,(?:[a-zA-Z0-9]+_)?\d+(?:~\d+)?)*$/;

  callTypeOptions = [
    { text: this.$tc('主调'), value: 'caller' },
    { text: this.$tc('被调'), value: 'callee' },
  ];

  applyScopeOptions = [];
  savingMap: Record<string, boolean> = {};
  ableSaveMap: Record<string, boolean> = {};
  filterValues: string[] = [];
  callerEnumOptions = [];
  calleeEnumOptions = [];
  currentEditRowId = '';

  get showColumn() {
    return this.columns;
  }

  @Watch('currentEditRowId', { immediate: true })
  watchCurrentEditRowIdChange(id: string) {
    this.$emit('currentEditRowIdChange', id);
  }

  addRow() {
    // 新增一条默认空规则，并立即进入编辑态
    const newRow = {
      id: random(8),
      code: '',
      remark: '',
      kind: 'callee',
      is_global: true,
      service_names: ['0'],
      isNew: true,
    };
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

  async getCodeEnumOptions() {
    // 近 1 小时时间范围，获取实时枚举候选
    const startTime = dayjs().subtract(1, 'hour').unix();
    const endTime = dayjs().unix();
    // 主调口径字段枚举
    this.callerEnumOptions = await getFieldOptionValues({
      field: 'code',
      start_time: startTime,
      end_time: endTime,
      app_name: this.appName,
      metric_field: 'rpc_client_handled_total',
    });
    // 被调口径字段枚举
    this.calleeEnumOptions = await getFieldOptionValues({
      field: 'code',
      start_time: startTime,
      end_time: endTime,
      app_name: this.appName,
      metric_field: 'rpc_server_handled_total',
    });
  }

  async getCodeRemarkList() {
    // 拉取服务端规则，失败与结束都要恢复 loading
    this.tableLoading = true;
    const data = await getCodeRemarks({
      app_name: this.appName,
    }).finally(() => {
      this.tableLoading = false;
    });
    if (data.length) {
      for (let index = 0; index < data.length; index++) {
        // 前端侧补充临时 id 与编辑状态字段
        const id = random(8);
        data[index].id = id;
        data[index].isNew = false;
        // 全局规则统一以 ['0'] 作为展示态占位
        if (data[index].is_global) {
          data[index].service_names = ['0'];
        }
        // 默认非编辑态
        this.currentEditRowId = '';
        this.$set(this.ableSaveMap, id, false);
        this.$set(this.savingMap, id, false);
      }
      // showData 用于页面展示；data 用于取消编辑时回滚
      this.showData = data;
      this.data = cloneDeep(data);
    } else {
      // 首次无数据时默认给一条可编辑空行，降低用户操作成本
      this.addRow();
    }
  }

  async getServiceList() {
    const data = await serviceList({
      app_name: this.appName,
    });
    this.applyScopeOptions = data.reduce(
      (results, item) => {
        // 仅接入 trpc 服务作为备注作用范围选项
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

  /** 校验填写的规则 */
  async validRules(rowId?: string) {
    // 全局规则：按 kind+code 判重
    const isGlobalTrueValues: string[] = [];
    // 非全局规则：按 kind+code+service 判重（同一行可能多个 service）
    const isGlobalFalseValues: string[][] = [];
    // 每次重新校验前先清空上轮错误集
    this.codeColumnEmptyIdSet.clear();
    this.remarkColumnEmptyIdSet.clear();
    for (let index = 0; index < this.showData.length; index++) {
      const item = !this.isBatchEdit
        ? rowId === this.showData[index].id
          ? this.showData[index]
          : this.data[index]
        : this.showData[index];
      // 必填校验：返回码不能为空
      if (this.showData[index].code === '') {
        this.codeColumnEmptyIdSet.add(item.id);
      }
      // 必填校验：备注不能为空
      if (this.showData[index].remark === '') {
        this.remarkColumnEmptyIdSet.add(item.id);
      }
      // 按 is_global 分流构造判重 key
      if (item.is_global) {
        isGlobalTrueValues.push(`${item.kind}_${item.code}`);
        isGlobalFalseValues.push([]);
      } else {
        const values = item.service_names.map(serviceName => `${item.kind}_${item.code}_${serviceName}`);
        isGlobalFalseValues.push(values);
        isGlobalTrueValues.push('');
      }
    }
    // 构建“全局规则”的 key -> 行 id 列表映射
    const isGlobalTrueKeyIdsMap: Record<string, string[]> = {};
    for (let index = 0; index < isGlobalTrueValues.length; index++) {
      const item = isGlobalTrueValues[index];
      if (!item) continue;
      if (isGlobalTrueKeyIdsMap[item]) {
        isGlobalTrueKeyIdsMap[item].push(this.showData[index].id);
      } else {
        isGlobalTrueKeyIdsMap[item] = [this.showData[index].id];
      }
    }
    const isGlobalTrueRepeatIds = Object.values(isGlobalTrueKeyIdsMap)
      .filter(item => item.length > 1)
      .flat();
    // 被重复命中的所有行 id
    this.isGlobalTruerepeatRulesIdSet = new Set(isGlobalTrueRepeatIds);
    // 构建“非全局规则”的 key -> 行 id 列表映射
    const isGlobalFalseKeyIdsMap: Record<string, string[]> = {};
    for (let index = 0; index < isGlobalFalseValues.length; index++) {
      const item = isGlobalFalseValues[index];
      if (!item.length) continue;
      for (let i = 0; i < item.length; i++) {
        const value = item[i];
        if (isGlobalFalseKeyIdsMap[value]) {
          isGlobalFalseKeyIdsMap[value].push(this.showData[index].id);
        } else {
          isGlobalFalseKeyIdsMap[value] = [this.showData[index].id];
        }
      }
    }
    const isGlobalFalseRepeatIds = Object.values(isGlobalFalseKeyIdsMap)
      .filter(item => item.length > 1)
      .flat();
    this.isGlobalFalseRepeatRulesIdSet = new Set(isGlobalFalseRepeatIds);
    for (let index = 0; index < this.showData.length; index++) {
      const { id } = this.showData[index];
      // if (id !== rowId) {
      //   continue;
      // }
      if (
        this.isGlobalTruerepeatRulesIdSet.has(id) ||
        this.isGlobalFalseRepeatRulesIdSet.has(id) ||
        this.codeColumnEmptyIdSet.has(id) ||
        this.remarkColumnEmptyIdSet.has(id)
      ) {
        this.$set(this.ableSaveMap, id, false);
      } else {
        this.$set(this.ableSaveMap, id, true);
      }
    }
    // 任一错误集非空，则本次校验失败
    if (
      this.isGlobalTruerepeatRulesIdSet.size !== 0 ||
      this.isGlobalFalseRepeatRulesIdSet.size !== 0 ||
      this.codeColumnEmptyIdSet.size !== 0 ||
      this.remarkColumnEmptyIdSet.size !== 0
    ) {
      return false;
    }
    return true;
  }

  async handleValueChange(value: string | string[], prop: string, id: string) {
    const index = this.showData.findIndex(item => item.id === id);
    let newValue = value;
    if (prop === 'service_names') {
      // 拷贝一份，避免直接改动事件原值
      newValue = cloneDeep(value);
      // “全局生效(0)”与具体服务互斥：
      // - 先选服务再选全局：保留全局
      // - 先选全局再选服务：移除全局
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
    // 先写入当前编辑值，再触发整表校验
    this.$set(this.showData[index], prop, newValue);
    this.validRules(this.showData[index].id);
  }

  handleCancelEditRow(id: string) {
    const showIndex = this.showData.findIndex(item => item.id === id);
    const dataIndex = this.data.findIndex(item => item.id === id);
    // 退出编辑态
    this.currentEditRowId = '';
    // 新增空白行取消时，直接删除，避免遗留无效数据
    if (this.data[dataIndex].isNew) {
      const row = this.data[dataIndex];
      const isEmpty =
        row.code === '' && row.remark === '' && row.service_names.length === 1 && row.service_names[0] === '0';
      if (isEmpty) {
        this.showData.splice(showIndex, 1);
        this.data.splice(dataIndex, 1);
        return;
      }
    }
    // 回滚到进入编辑前快照
    this.$set(this.showData, showIndex, cloneDeep(this.data[dataIndex]));
  }

  handleDeleteRow(id: string) {
    const showIndex = this.showData.findIndex(item => item.id === id);
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
        // 删除采用“全量提交剩余规则”方式
        const dataList = this.data.filter(item => item.id !== id && !item.isNew);
        const dataIndex = this.data.findIndex(item => item.id === id);
        const params = {
          app_name: this.appName,
          remarks: dataList.map(item => ({
            kind: item.kind,
            code: item.code,
            remark: item.remark,
            service_names: item.is_global ? [] : item.service_names,
            is_global: item.is_global,
          })),
        };
        await setCodeRemark(params);
        // 接口成功后再同步前端列表
        this.showData.splice(showIndex, 1);
        this.data.splice(dataIndex, 1);
        this.$bkMessage({
          message: this.$t('删除成功，需要 5 分钟左右生效。'),
          theme: 'success',
        });
      },
    });
  }

  handleEditRow(id: string) {
    // 切换为编辑态
    this.currentEditRowId = id;
  }

  async handleSaveEditRow(id: string) {
    const isRowValid = await this.validRules(id);
    if (!isRowValid) {
      return;
    }

    const showRow = this.showData.find(item => item.id === id);
    const dataIndex = this.data.findIndex(item => item.id === id);
    const dataRow = this.data[dataIndex];
    // 非新建行且内容未变更时，直接退出编辑态
    if (JSON.stringify(showRow) === JSON.stringify(dataRow) && !showRow.isNew) {
      this.currentEditRowId = '';
      return;
    }

    const params = {
      app_name: this.appName,
      remarks: this.data.reduce((results, item) => {
        if (item.id === id) {
          results.push({
            kind: showRow.kind,
            code: showRow.code,
            remark: showRow.remark,
            // 后端协议：全局规则 service_names 传空数组
            service_names: showRow.is_global ? [] : showRow.service_names,
            is_global: showRow.is_global,
          });
        } else if (!item.isNew) {
          results.push({
            kind: item.kind,
            code: item.code,
            remark: item.remark,
            service_names: item.is_global ? [] : item.service_names,
            is_global: item.is_global,
          });
        }
        return results;
      }, []),
    };
    try {
      // 行级 loading：避免重复点击提交
      this.$set(this.savingMap, showRow.id, true);
      await setCodeRemark(params);
      // 保存成功后将该行转为“非新增”，并更新快照
      this.$set(showRow, 'isNew', false);
      this.currentEditRowId = '';
      this.$set(this.data, dataIndex, cloneDeep(showRow));
      this.$bkMessage({
        message: this.$t('配置保存成功，需要 5 分钟左右生效。'),
        theme: 'success',
      });
    } finally {
      // 无论成败都要关闭 loading
      this.$set(this.savingMap, showRow.id, false);
      this.$set(this.ableSaveMap, showRow.id, false);
    }
  }

  handleFilterChange(filters: Record<string, string[]>) {
    // 仅使用“作用范围”这一列过滤值
    const values = Object.values(filters)[0];
    this.filterValues = values;
    if (values.length) {
      const valuesSet = new Set(values);
      const isIncluGlobal = valuesSet.has('0');
      // 命中条件：
      // 1. 行中任一 service 在筛选集合内；或
      // 2. 勾选了全局且当前行为全局规则
      const showData = this.data.filter(
        item => item.service_names.some(service => valuesSet.has(service)) || (isIncluGlobal && item.is_global)
      );
      this.showData = cloneDeep(showData);
    } else {
      // 清空筛选恢复全量数据
      this.showData = cloneDeep(this.data);
    }
  }

  renderTipContent(row: CodeRemarkItem) {
    // 统一产出“返回码列”错误提示图标及内容
    let content = '';
    if (this.codeColumnEmptyIdSet.has(row.id)) {
      content = this.$tc('返回码不能为空');
    } else if (row.is_global && this.isGlobalTruerepeatRulesIdSet.has(row.id)) {
      content = this.$tc('类型、返回码的组合值须唯一');
    } else if (!row.is_global && this.isGlobalFalseRepeatRulesIdSet.has(row.id)) {
      content = this.$tc('类型、返回码、备注范围的组合值须唯一');
    }
    return (
      content && (
        <i
          class='icon-monitor icon-mind-fill'
          v-bk-tooltips={{
            content: content,
          }}
        />
      )
    );
  }

  getValueCallback(kind: string): TGetValueFn {
    return (params: IGetValueFnParams): Promise<IOptionsInfo> => {
      const enumOptions = kind === 'caller' ? this.callerEnumOptions : this.calleeEnumOptions;
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

  handleValueTagSelectorChange(value: string, id: string) {
    this.handleValueChange(value, 'code', id);
  }

  handleImport(data: CodeRemarkItem[]) {
    /**
     * 以 类型 + 被调服务 + 被调service + 被调接口 为组合key：
     * 1. 存量的覆盖更新
     * 2. 新增的追加到前面
     */
    const importKeySet = new Set<string>(data.map(item => `${item.kind}_${item.code}_${item.is_global}`));
    const targetData = data.map(item => ({
      ...item,
      id: random(8),
    }));
    // 记录已被导入数据替换的旧行 id，用于后续生成新增列表
    const replaceIds = new Set<string>();
    for (let index = 0; index < this.showData.length; index++) {
      const item = this.showData[index];
      const rowKey = `${item.kind}_${item.code}_${item.is_global}`;
      if (importKeySet.has(rowKey)) {
        // 命中相同组合键时，用导入值覆盖当前行
        const replaceItem = targetData.find(
          childItem => `${childItem.kind}_${childItem.code}_${childItem.is_global}` === rowKey
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
      code: item.code,
      remark: item.remark,
      service_names: item.is_global ? [] : item.service_names,
      is_global: item.is_global,
    }));
    downloadFile(JSON.stringify(exportData, null, 2), 'application/json', 'code-remark.json');
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
      remarks: this.showData.reduce((results, item) => {
        results.push({
          kind: item.kind,
          code: item.code,
          remark: item.remark,
          service_names: item.is_global ? [] : item.service_names,
          is_global: item.is_global,
        });
        return results;
      }, []),
    };
    try {
      await setCodeRemark(params);
      this.$bkMessage({
        message: this.$t('配置保存成功，需要 5 分钟左右生效。'),
        theme: 'success',
      });
    } finally {
      // 无论成败都要关闭 loading
      this.$emit('batchSaveSuccess');
    }
  }

  renderColumn(item: ColumnItem) {
    // 按列类型拆分渲染逻辑，便于维护“只读态/编辑态”双视图
    switch (item.prop) {
      case 'kind':
        return (
          <bk-table-column
            key={item.prop}
            width={item.width}
            scopedSlots={{
              default: ({ row }) => {
                // 非编辑态：输出翻译后的枚举文本
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
                    {/* 编辑态：可输入可选择 */}
                    <bk-select
                      clearable={false}
                      display-tag={true}
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
      case 'code':
        return (
          <bk-table-column
            key={item.prop}
            width={item.width}
            scopedSlots={{
              default: ({ row }) => {
                // 非编辑态：纯文本 + 溢出提示
                if (this.currentEditRowId !== row.id && !this.isBatchEdit) {
                  return (
                    <div class='interface-column-readonly'>
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
                    {/* 编辑态：返回码支持搜索、选填与自定义创建 */}
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
                      getValueFn={this.getValueCallback(row.kind)}
                      onChange={data => this.handleValueTagSelectorChange(data as string, row.id)}
                    />
                    {/* 校验失败时显示错误图标 */}
                    {this.renderTipContent(row)}
                  </div>
                );
              },
            }}
            label={item.label}
            prop={item.prop}
          />
        );
      case 'remark':
        return (
          <bk-table-column
            key={item.prop}
            width={item.width}
            scopedSlots={{
              default: ({ row }) => {
                // 非编辑态：展示备注文本
                if (this.currentEditRowId !== row.id && !this.isBatchEdit) {
                  return (
                    <div class='interface-column-readonly'>
                      <div
                        class='value-content'
                        v-bk-overflow-tips
                      >
                        {row[item.prop]}
                      </div>
                    </div>
                  );
                }
                return (
                  <div class='interface-column'>
                    {/* 编辑态：备注输入框 */}
                    <bk-input
                      value={row[item.prop]}
                      onChange={v => this.handleValueChange(v, item.prop, row.id)}
                    />
                    {this.remarkColumnEmptyIdSet.has(row.id) && (
                      <i
                        class='icon-monitor icon-mind-fill'
                        v-bk-tooltips={{
                          content: this.$tc('备注不能为空'),
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
      case 'service_names':
        return (
          <bk-table-column
            key={item.prop}
            width={item.width}
            scopedSlots={{
              default: ({ row }) => {
                // 非编辑态：展示服务名列表；0 映射为“全局生效”
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
                    {/* 编辑态：多选作用范围，含“全局生效(0)”特殊值 */}
                    <bk-select
                      // allow-create
                      class='scoped-select'
                      clearable={false}
                      disabled={item.loading}
                      ext-popover-cls='scoped-select-popover'
                      loading={item.loading}
                      placeholder={this.$tc('请选择或输入')}
                      showEmpty={!item.loading && !item.options.length}
                      value={row[item.prop]}
                      multiple
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

  created() {
    // 初始化并行加载：规则列表 + 服务范围选项
    this.getCodeEnumOptions();
    this.getCodeRemarkList();
    this.getServiceList();
  }

  render() {
    return (
      <div class='code-redefine-content'>
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
              row-class-name='return-code-remark-row'
              border
              row-key='id'
              row-auto-height
              on-filter-change={this.handleFilterChange}
            >
              {this.showColumn.map(item => this.renderColumn(item))}
              <bk-table-column
                width={120}
                fixed='right'
                scopedSlots={{
                  default: ({ row }) => {
                    if (this.currentEditRowId === row.id) {
                      return (
                        <div class='operate-btns'>
                          <bk-button
                            class='btn'
                            disabled={!this.ableSaveMap[row.id]}
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
