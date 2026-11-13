/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 *
 * Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
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


import { useApplicationStore } from '@/app/state/domains/application-store';
import { useGlobalsStore } from '@/app/state/domains/globals-store';


import { Tag as TTag } from 'tdesign-vue-next';

import { Button as Button } from 'tdesign-vue-next';
import { ServicesInstance } from '@/platform/services';
import { asDictionary } from '@/shared/utils/typed-record';

import { Component, Prop } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import { Table, Popup as Popover } from 'tdesign-vue-next';

import { getFlatObjValues } from '../../../../../shared/lib/util';

import './field-info.scss';

const TableColumn = (_props: Record<string, unknown>, { slots }: { slots: { default?: () => unknown } }) => slots.default?.();

interface MaskingRule {
  rule_id: number;
  field_name: string;
  state: string;
  match_pattern: string;
  operator: string;
  params: { template_string?: string; preserve_head?: number; preserve_tail?: number };
}
interface FieldPreview { origin: string; afterMasking: string; }
interface FieldMaskingConfig {
  field_name: string;
  rules: MaskingRule[];
  previewRules: MaskingRule[];
  preview?: FieldPreview[];
}
interface FieldRow {
  field_name: string;
  query_alias?: string;
  field_alias?: string;
  metadata_type?: string;
  field_time_format?: string;
  field_time_zone: string;
  is_analyzed?: boolean;
  tokenize_on_chars?: string;
  is_case_sensitive?: boolean;
  desensitize_config: MaskingRule[];
  preview: FieldPreview[];
}
interface IProps {
  value: boolean;

  // Public props/events already installed by the source decorators.
  "collectorData"?: object;
  "editAuthData"?: object;
  "editAuth"?: boolean;
  "isShowEditBtn"?: boolean;
}

@Component
export default class FieldInfo extends tsc<IProps> {
  @Prop({ type: Object, default: () => ({}) }) collectorData!: object;
  @Prop({ type: Object, default: () => ({}) }) editAuthData!: object;
  @Prop({ type: Boolean, default: false }) editAuth!: boolean;
  @Prop({ type: Boolean, default: false }) isShowEditBtn!: boolean;

  pagination = {
    /** 当前页数 */
    current: 1,
    /** 总数 */
    count: 1,
    /** 每页显示数量 */
    limit: 10,
  };

  timeField = '';

  tableList: FieldRow[] = [];

  tableShowList: FieldRow[] = [];

  recommendRuleIDMap = {};

  fieldOriginValueList: Record<string, unknown[]> = {};

  tableLoading = false;

  segmentRegStr = ',&*+:;?^=!$<>\'"{}()|[]\\/\\s\\r\\n\\t-';

  get spaceUid() {
    return useApplicationStore().spaceUid;
  }

  get isShowMaskingTemplate() {
    return useApplicationStore().isShowMaskingTemplate;
  }

  get globalsData() {
    return useGlobalsStore().globalsData;
  }

  // cmdb元数据
  get extra_labels() {
    return (this.collectorData as any).extra_labels?.map((item: { key: any; }) => `__ext.${item.key}`);
  }

  operatorMap = asDictionary({
    mask_shield: window.mainComponent.$t('掩码'),
    text_replace: window.mainComponent.$t('替换'),
  });

  jsonParseList: Record<string, unknown>[] = [];

  async created() {
    try {
      this.tableLoading = true;
      const maskingConfigs = await this.getMaskingConfig(); // 获取脱敏配置信息
      await this.handleRefreshConfigStr(); // 初始化日志查询输入框字符串
      const fieldConfigs = await this.matchMaskingRule(maskingConfigs);
      const previewConfigs = await this.getConfigPreview(fieldConfigs);
      this.questFieldsList(previewConfigs);
    } catch {
      this.tableLoading = false;
    } finally {
      this.tableLoading = false;
    }
  }

  /**
   * @desc: 获取脱敏规则字符串
   * @param {IRuleItem} item 脱敏规则参数
   * @returns {String} 返回脱敏规则字符串
   */
  getMaskingRuleStr(item: MaskingRule) {
    const endStr =
      item?.operator === 'text_replace'
        ? `${this.$t('替换为')} ${item?.params?.template_string}`
        : this.$t('保留前{0}位, 后{1}位', {
            0: item?.params?.preserve_head,
            1: item?.params?.preserve_tail,
          });
    return `${this.operatorMap[item?.operator]} | ${endStr}`;
  }

  async questFieldsList(maskingRule: FieldMaskingConfig[]) {
    try {
      const res = await ServicesInstance.retrieve.getLogTableHead<{ data: { time_field: string; fields: FieldRow[] } }>({
        params: {
          index_set_id: (this.collectorData as any).index_set_id,
        },
        query: { is_realtime: 'True' },
      });
      this.timeField = res.data.time_field;
      this.tableList = res.data.fields.map(item => {
        const findRules = maskingRule?.find(mItem => mItem.field_name === item.field_name);
        return {
          ...item,
          desensitize_config: findRules?.rules ?? [],
          preview: findRules?.preview ?? [],
        };
      });
      this.tableShowList = this.tableList.slice(0, this.pagination.limit);
      this.changePagination({
        current: 1,
        count: this.tableList.length,
      });
    } catch (e) {
      console.warn(e);
    } finally {
      this.tableLoading = false;
    }
  }

  /**
   * @desc: 获取保存的脱敏字段
   * @returns {Array}
   */
  async getMaskingConfig() {
    try {
      const res = await ServicesInstance.masking.getMaskingConfig<{ data: { field_configs: FieldMaskingConfig[] } }>(
        {
          params: { index_set_id: (this.collectorData as any)?.index_set_id },
        },
        { catchIsShowMessage: false },
      );
      return res.data.field_configs;
    } catch {
      return [];
    }
  }

  pageChange(newPage: number) {
    const { limit } = this.pagination;
    const startIndex = (newPage - 1) * limit;
    const endIndex = newPage * limit;
    this.tableShowList = this.tableList.slice(startIndex, endIndex);
    this.changePagination({
      current: newPage,
    });
  }

  pageLimitChange(limit: number) {
    this.tableShowList = this.tableList.slice(0, limit);
    this.changePagination({
      limit,
      current: 1,
      count: this.tableList.length,
    });
  }

  changePagination(pagination = {}) {
    Object.assign(this.pagination, pagination);
  }

  /**
   * @desc: 获取当前日志查询字符串
   */
  async handleRefreshConfigStr() {
    try {
      const res = await ServicesInstance.masking.getMaskingSearchStr({
        params: { index_set_id: (this.collectorData as any)?.index_set_id },
      });
      if (res.data.list.length) {
        this.jsonParseList = res.data.list.slice(0, 1);
        const flatJsonParseList = this.jsonParseList.map(item => {
          const { newObject } = getFlatObjValues(item);
          return newObject;
        });
        this.fieldOriginValueList = flatJsonParseList.reduce<Record<string, unknown[]>>((pre, cur) => {
          for (const [fieldKey, fieldVal] of Object.entries(cur)) {
            if (!pre[fieldKey]) {
              pre[fieldKey] = [];
            }
            pre[fieldKey].push(fieldVal ?? '');
          }
          return pre;
        }, {});
      }
    } catch {
      return '';
    }
  }

  /**
   * @desc: 接口获取脱敏预览
   * @param {Array} fieldList 字段列表
   * @returns {Object}
   */
  async getConfigPreview(fieldList: FieldMaskingConfig[] = []) {
    if (!this.jsonParseList.length) {
      return fieldList;
    }
    const fieldConfigs = fieldList
      .filter(item => item.previewRules.length)
      .map(item => ({
        field_name: item.field_name,
        rules: item.previewRules.map(rItem => {
          if (rItem.state === 'update') {
            // 更新同步后的预览 拿new_rule里的数据进行更新预览
            return {
              match_pattern: rItem.match_pattern,
              operator: rItem.operator,
              params: rItem.params,
            };
          }
          return { rule_id: rItem.rule_id };
        }),
      }));
    if (!fieldConfigs.length) {
      return fieldList;
    }
    try {
      const res = await ServicesInstance.masking.getConfigPreview<{ data: Record<string, (string | null)[]> }>({
        data: {
          logs: this.jsonParseList,
          field_configs: fieldConfigs,
        },
      });
      const previewResult = res.data;
      return fieldList.map(field => {
        const fieldPreview = previewResult[field.field_name];
        return {
          ...field,
          preview: this.getFieldPreview(field.field_name, fieldPreview),
        };
      });
    } catch {
      return fieldList;
    }
  }

  /**
   * @desc: 获取字段预览
   * @param {String} fieldName 字段名
   * @param {Array} previewResult 接口返回的预览值
   * @returns {Array}
   */
  getFieldPreview(fieldName = '', previewResult: (string | null)[] = []) {
    if (!previewResult.length) {
      return [];
    }
    if (!(this.jsonParseList.length && fieldName)) {
      return [];
    }
    if (!this.fieldOriginValueList[fieldName]) {
      return [];
    }
    const previewList: FieldPreview[] = [];
    const filterResult = previewResult.filter(item => item !== null);
    this.fieldOriginValueList[fieldName].forEach((item, index) => {
      const maskingValue = filterResult[index] ?? '';
      const origin = typeof item === 'object' ? JSON.stringify(item) : String(item);
      previewList[index] = {
        origin,
        afterMasking: maskingValue,
      };
    });
    return previewList;
  }

  /**
   * @desc: 获取日志查询生成的脱敏规则
   * @param {Boolean} maskingConfigs 是否是合并 合并情况下 change_state改为true
   * @returns {Array}
   */
  async matchMaskingRule(maskingConfigs: FieldMaskingConfig[] = []) {
    const allFields = this.jsonParseList.reduce<string[]>((pre, cur) => {
      const { newKeyStrList } = getFlatObjValues(cur);
      pre.push(...newKeyStrList);
      return pre;
    }, []);

    const fields = [...new Set(allFields)];

    if (!fields.length) {
      return maskingConfigs;
    }

    try {
      const res = await ServicesInstance.masking.matchMaskingRule<{ data: Record<string, { rule_id: number }[]> }>({
        data: {
          space_uid: this.spaceUid,
          logs: this.jsonParseList,
          fields,
        },
      });
      const matchRuleObj = res.data;
      return maskingConfigs.map(item => ({
        ...item,
        previewRules: item.rules.filter(rItem => {
          if (!matchRuleObj[rItem.field_name]) {
            return false;
          }
          const ruleIdList = matchRuleObj[rItem.field_name].map(mItem => mItem.rule_id);
          return ruleIdList.includes(rItem.rule_id);
        }),
      }));
    } catch {
      return maskingConfigs;
    }
  }

  handleClickEdit() {
    if (!this.editAuth && this.editAuthData) {
      useApplicationStore().updateState({ authDialogData: this.editAuthData });
      return;
    }
    const params = {
      collectorId: this.$route.params.collectorId,
    };
    this.$router.push({
      name: 'collectField',
      params,
      query: {
        spaceUid: useApplicationStore().spaceUid,
        backRoute: 'manage-collection',
        type: 'fieldInfo',
        step: '2',
        typeKey: (this.collectorData as any).log_access_type,
        indexSetId: this.$route.query.indexSetId,
      },
    });
  }

  getTimeZoneName(timeZone: string) {
    const foundItem = (this.globalsData.time_zone as { id: string; name: string }[]).find((item: { id: string; }) => item.id === timeZone);
    return foundItem ? foundItem.name : '';
  }

  render() {
    const nickNameSlot = {
      default: ({ row }: { row: FieldRow }) => <span>{row.query_alias || row.field_alias || '--'}</span>,
    };

    const fieldNameSlot = {
      default: ({ row }: { row: FieldRow }) => {
        return (
          <div>
            {row.field_name}
            {row.metadata_type === 'path' || this.extra_labels?.includes(row.field_name) ? (
              <TTag
                style={{borderRadius: '6px'}}
                theme={"primary"} variant='light' data-v2-display='tag'
              >
                {this.$t('元数据')}
              </TTag>
            ) : (
              ''
            )}
            {row.field_time_format ? (
              <TTag
                v-log-tooltip={this.getTimeZoneName(row.field_time_zone)}
                style={{borderRadius: '6px'}}
                theme={"success"} variant='light' data-v2-display='tag'
              >
                {this.$t('指定日志时间')}
              </TTag>
            ) : (
              ''
            )}
          </div>
        );
      },
    };

    const getMaskingPopover = (row: FieldRow) => {
      if (!row.desensitize_config?.length) {
        return;
      }
      return (
        <Popover
          v-slots={{
            content: () => (
              <div class='masking-popover'>
                <div class='label-box'>
                  <div class='label'>{this.$t('脱敏算子')}:&nbsp;</div>
                  <div class='rule'>
                    {row.desensitize_config.map((item, index) => (
                      <span key={index}>{this.getMaskingRuleStr(item)}</span>
                    ))}
                  </div>
                </div>
                <div class='label-box'>
                  <div class='label'>{this.$t('结果预览')}:&nbsp;</div>
                  <div class='rule'>
                    {row.preview.length
                      ? row.preview.map((item, index) => (
                          <div
                            key={index}
                            class='preview-result'
                          >
                            {/* 脱敏权限未实现 先不展示脱敏前的结果 */}
                            {/* <span class="old title-overflow" v-log-overflow-tips>{item.origin}</span>
                      <i class="bk-icon icon-arrows-right"></i> */}
                            <span
                              class='result title-overflow'
                              v-log-overflow-tips
                            >
                              {item.afterMasking}
                            </span>
                          </div>
                        ))
                      : '-'}
                  </div>
                </div>
              </div>
            ),
          }}
          extCls='masking-tag'
          tippyOptions={{
            placement: 'top',
            theme: 'light',
          }}
        >
          <span class='masking-tag-box'>{this.$t('已脱敏')}</span>
        </Popover>
      );
    };

    const maskingStateSlot = {
      default: ({ row }: { row: FieldRow }) => <div>{getMaskingPopover(row)}</div>,
    };

    const tokenizeSlot = {
      default: ({ row }: { row: FieldRow }) => {
        return (
          <div>
            {row.is_analyzed ? (
              <div>
                <div>{row.tokenize_on_chars ? row.tokenize_on_chars : this.$t('默认分词符')}</div>
                <div>
                  {this.$t('大小写敏感')}: {row.is_case_sensitive ? this.$t('是') : this.$t('否')}
                </div>
              </div>
            ) : (
              <div>{this.$t('不分词')}</div>
            )}
          </div>
        );
      },
    };

    return (
      <div class='field-info-table'>
        {this.isShowEditBtn && (
          <div class='edit-btn-container'>
            <Button
              style='min-width: 88px; color: var(--bklog-brand-primary, #3a84ff)'
              v-cursor={{ active: !this.editAuth }}
              theme='default'
              onClick={() => this.handleClickEdit()}
            >
              {this.$t('编辑')}
            </Button>
          </div>
        )}

        <Table
          v-loading={{ loading: this.tableLoading }}
          data={this.tableShowList}
          pagination={this.pagination}
          size='small'
          onPageChange={this.pageChange}
          onPageLimitChange={this.pageLimitChange}
        >
          <TableColumn
            nativeCellSlot={true}
            key={'field_name'}
            label={this.$t('字段名')}
            v-slots={fieldNameSlot}
          />

          <TableColumn
            nativeCellSlot={true}
            key={'field_alias'}
            label={this.$t('别名')}
            v-slots={nickNameSlot}
          />

          <TableColumn
            key={'field_type'}
            label={this.$t('数据类型')}
            prop={'field_type'}
          />

          {/* <TableColumn
            label={this.$t('结果样例')}
            key={'sample'}
            prop={'field_type'}
          ></TableColumn> */}

          {this.isShowMaskingTemplate && (
            <TableColumn
              nativeCellSlot={true}
              key={'masking_state'}
              label={this.$t('脱敏状态')}
              v-slots={maskingStateSlot}
            />
          )}

          <TableColumn
            nativeCellSlot={true}
            key={'tokenize_on_chars'}
            label={this.$t('分词符')}
            v-slots={tokenizeSlot}
          />
        </Table>
      </div>
    );
  }
}
