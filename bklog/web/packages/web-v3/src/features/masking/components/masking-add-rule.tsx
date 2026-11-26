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
import { Checkbox as Checkbox, RadioGroup as RadioGroup, Radio as Radio } from 'tdesign-vue-next';

import { Button as Button } from 'tdesign-vue-next';
import { ServicesInstance } from '@/platform/services';
import { toRaw } from 'vue';
import { asDictionary } from '@/shared/utils/typed-record';

import { renderDrawerFormSkeleton } from '@/shared/ui/loading/drawer-skeleton';
import { renderCodeSampleSkeleton } from '@/shared/ui/loading/list-skeleton';
import TextHighlight from '@/shared/ui/text-highlight';
import SourceTranslation from '@/platform/i18n/translation';

import { Component, Model, Emit, Prop, Ref, Watch } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import { Drawer as Sideslider, Form, FormItem, Input, Tooltip, Textarea, InputNumber, type FormInstanceFunctions, type FormRules, Collapse, CollapsePanel as CollapseItem, Table, Dialog, TagInput } from 'tdesign-vue-next';

import './masking-add-rule.scss';
import './masking-confirm-dialog.scss';
import { allocateOverlayZIndex, Z_INDEX_LAYERS } from '@/shared/global/overlay';

interface IProps {
  value: boolean;
  isEdit: boolean;
  ruleID: number | string;

  // Public props/events already installed by the source decorators.
  "isPublicRule"?: boolean;
  "tableStrList"?: string[];
  "addRuleFieldValue"?: IAddRuleFieldValue;
  "editAccessValue"?: IEditAccessValue;
  "onSubmitRule"?: (value: null) => void;
  "onChange"?: (value: boolean) => void;
}

interface IEditAccessValue {
  accessNum: number;
  accessInfo: any[];
}

interface IAddRuleFieldValue {
  field: string;
  fieldLog: string;
}

@Component
export default class MaskingAddRule extends tsc<IProps> {
  @Model('change', { type: Boolean, default: false }) value!: IProps['value'];
  @Prop({ type: Boolean, default: false }) isEdit!: boolean;
  @Prop({ type: Boolean, default: true }) isPublicRule!: boolean;
  @Prop({ type: Array, default: () => [] }) tableStrList!: string[];
  @Prop({ type: Number, default: 0 }) ruleID!: number | string;
  @Prop({
    type: Object,
    default: () => ({
      field: '',
      fieldLog: '',
    }),
  })
  addRuleFieldValue!: IAddRuleFieldValue;
  @Prop({
    type: Object,
    default: () => ({
      accessNum: 0,
      accessInfo: [],
    }),
  })
  editAccessValue!: IEditAccessValue;

  /** 用于存储当前展开的折叠项的数组 */
  activeCollapse: ((string))[] = [];
  /** 调试的原始日志 */
  logOriginal = '';
  /** 调试返回的日志 */
  debugLog = '';
  /** 是否正在进行调试请求的布尔值 */
  debugRequesting = false;
  /** 表示是否显示第二个确认对话框的布尔值 */
  drawerZIndex: number = Z_INDEX_LAYERS.DRAWER;
  confirmDialogZIndex: number = Z_INDEX_LAYERS.DIALOG;

  @Watch('value', { immediate: true })
  updateDrawerLayer(visible: boolean) {
    if (visible) this.drawerZIndex = allocateOverlayZIndex('DRAWER');
  }

  @Watch('isShowSecondConfirmDialog')
  updateConfirmDialogLayer(visible: boolean) {
    if (visible) this.confirmDialogZIndex = allocateOverlayZIndex();
  }

  isShowSecondConfirmDialog = false;
  /** 是否选中匹配字段的复选框的布尔值 */
  matchFieldCheckValue = true;
  /** 是否选中匹配表达式的复选框的布尔值 */
  matchExpressionCheckValue = true;
  /** 提交数据 */
  formData = {
    space_uid: '',
    rule_name: '',
    match_fields: [],
    match_pattern: '',
    operator: 'text_replace', // mask_shield, text_replace
    params: {
      preserve_head: 0,
      preserve_tail: 0,
      replace_mark: '*',
      template_string: '',
    },
    is_public: false,
  };
  /** 表单是否正在加载 */
  formLoading = false;
  /** 基础表单数据 */
  baseFromData = {
    space_uid: '',
    rule_name: '',
    match_fields: [],
    match_pattern: '',
    operator: 'text_replace', // mask_shield, text_replace
    params: {
      preserve_head: 0,
      preserve_tail: 0,
      replace_mark: '*',
      template_string: '',
    },
    is_public: false,
  };
  /** 提交的值 */
  submitVal = null;
  /** 场景路由映射 */
  scenarioRouteMap = asDictionary({
    log: 'collection-item',
    bkdata: 'bkdata-index-set-list',
    es: 'es-index-set-list',
    index_set: 'log-index-set-list',
    log_custom: 'custom-report',
  });
  /** 缓存的规则名 */
  cacheRuleName = '';
  /** 调试失败时候的提示 */
  debugErrorTipsStr = '';


  public rules: FormRules = {
    rule_name: [
      {
        required: true,
        message: window.mainComponent.$t('必填项'),
        trigger: 'blur',
      },
      {
        max: 30,
        message: window.mainComponent.$t('不能多于{n}个字符', { n: 30 }),
        trigger: 'blur',
      },
      {
        validator: this.checkRuleName,
        message: window.mainComponent.$t('已有脱敏规则名, 请重新填写。'),
        trigger: 'blur',
      },
    ],
    match_fields: [
      {
        validator: this.checkFieldsMatch,
        message: window.mainComponent.$t('必填项'),
        trigger: 'blur',
      },
    ],
    match_pattern: [
      {
        validator: this.checkExpressionMatch,
        message: window.mainComponent.$t('必填项'),
        trigger: 'blur',
      },
    ],
    params: [
      {
        validator: this.checkOperatorParams,
        message: window.mainComponent.$t('必填项'),
        trigger: 'blur',
      },
    ],
  };

  @Ref('submitForm') private readonly submitFormRef!: FormInstanceFunctions;

  get markList() {
    let markVal = this.debugLog.toString().match(/(<mark>).*?(<\/mark>)/g) || [];
    if (markVal.length) {
      markVal = markVal.map(item => item.replace(/<mark>/g, '').replace(/<\/mark>/g, ''));
    }
    return markVal;
  }

  @Watch('logOriginal')
  watchOriginStr(val: string) {
    if (!val) {
      this.debugLog = '';
    }
  }

  @Emit('submit-rule')
  emitSubmitRule() {
    return this.submitVal;
  }

  @Emit('change')
  hiddenSlider() {
    this.formData = structuredClone(toRaw(this.baseFromData));
    this.emitSubmitRule();
    this.debugLog = '';
    this.logOriginal = '';
    this.debugErrorTipsStr = '';
    this.matchFieldCheckValue = true;
    this.matchExpressionCheckValue = true;
    this.submitVal = null;
    return false;
  }

  /** 打开侧边栏 */
  showSlider() {
    this.baseFromData = structuredClone(toRaw(this.formData));
    if (this.addRuleFieldValue.field) {
      this.initFiledValue();
    }
    if (this.isEdit) {
      this.initFormState();
    }
    this.activeCollapse = ['1'];
  }

  get spaceUid() {
    return useApplicationStore().spaceUid;
  }

  get isShowAndIcon() {
    return this.matchFieldCheckValue && this.matchExpressionCheckValue;
  }

  get isCanClickDebugBtn() {
    // 脱敏正则，脱敏算子，原始日志，且选中脱敏正则checkBox才可点击调试
    return !(
      this.matchExpressionCheckValue &&
      this.formData.match_pattern &&
      this.logOriginal &&
      this.checkOperatorParams()
    );
  }

  checkFieldsMatch() {
    if (!this.matchFieldCheckValue) {
      return true;
    }
    return !!this.formData.match_fields.length;
  }

  checkExpressionMatch() {
    if (!this.matchExpressionCheckValue) {
      return true;
    }
    return !!this.formData.match_pattern;
  }

  checkOperatorParams() {
    if (this.formData.operator === 'mask_shield') {
      return this.formData.params.preserve_head >= 0 && this.formData.params.preserve_tail >= 0;
    }
    return !!this.formData.params.template_string;
  }

  checkRuleName() {
    // 编辑状态，且规则名未变动 返回正确的规则
    if (this.isEdit && this.cacheRuleName === this.formData.rule_name) {
      return true;
    }
    // 判断是否规则名是否重复
    return !this.tableStrList.includes(this.formData.rule_name);
  }

  async initFormState() {
    try {
      this.formLoading = true;
      const resData = await ServicesInstance.masking.getDesensitize({
        params: { rule_id: this.ruleID },
      });
      Object.assign(this.formData, (resData as any).data);
      if (this.isEdit) {
        this.cacheRuleName = this.formData.rule_name;
      }
      this.matchFieldCheckValue = !!this.formData.match_fields.length;
      this.matchExpressionCheckValue = !!this.formData.match_pattern;
    } finally {
      this.formLoading = false;
    }
  }

  /** 从字段添加的规则将初始化字段和采样 */
  initFiledValue() {
    const { field, fieldLog } = this.addRuleFieldValue;
    this.formData.match_fields.push(field);
    this.logOriginal = fieldLog;
  }

  handleSubmit() {
    this.submitFormRef.validate().then(async result => {
      if (result !== true) return;
      if (this.isEdit) {
        this.isShowSecondConfirmDialog = true;
        return;
      }
      await this.submitRequest();
      this.hiddenSlider();
    });
  }
  /** 提交规则 */
  async submitRequest() {
    this.submitVal = null;
    const params = { rule_id: this.ruleID };
    const fParams = this.formData.params;
    const operatorParams =
      this.formData.operator === 'mask_shield'
        ? {
            preserve_tail: Number(fParams.preserve_tail),
            preserve_head: Number(fParams.preserve_head),
            replace_mark: fParams.replace_mark,
          }
        : { template_string: fParams.template_string ?? '' };
    const paramsData = {
      rule_name: this.formData.rule_name,
      match_fields: this.formData.match_fields,
      match_pattern: this.formData.match_pattern,
      operator: this.formData.operator,
      operator_params: operatorParams,
    };
    const createObj = this.isPublicRule ? { is_public: true } : { is_public: false, space_uid: this.spaceUid };
    const data = this.isEdit ? { ...paramsData } : { ...createObj, ...paramsData };
    const requestStr = this.isEdit ? 'updateDesensitize' : 'createDesensitize';
    await ServicesInstance.masking[requestStr]({
        params,
        data,
      })
      .then(res => {
        this.isShowSecondConfirmDialog = false;
        this.submitVal = res.data;
      });
  }

  /** 获取调试后的结果预览 */
  async handleDebugging() {
    this.debugRequesting = true;
    const fParams = this.formData.params;
    const operatorParams =
      this.formData.operator === 'mask_shield'
        ? {
            preserve_tail: Number(fParams.preserve_tail),
            preserve_head: Number(fParams.preserve_head),
            replace_mark: fParams.replace_mark,
          }
        : { template_string: fParams.template_string ?? '' };
    const data = {
      log_sample: this.logOriginal,
      match_pattern: this.formData.match_pattern,
      operator: this.formData.operator,
      params: operatorParams,
    };
    await ServicesInstance.masking.desensitizeDebug({ data }, { catchIsShowMessage: false })
      .then(res => {
        this.debugLog = res.data;
        this.debugErrorTipsStr = '';
      })
      .catch(err => {
        this.debugErrorTipsStr = err.message;
        this.debugLog = '';
      })
      .finally(() => {
        this.debugRequesting = false;
      });
  }

  async handleDialogConfirm() {
    await this.submitRequest();
    this.hiddenSlider();
  }

  formatterStr(content: string) {
    // 匹配高亮标签
    let value = content;
    const markVal = content.toString().match(/(<mark>).*?(<\/mark>)/g) || [];
    if (markVal.length) {
      value = String(value)
        .replace(/<mark>/g, '')
        .replace(/<\/mark>/g, '');
    }
    return value;
  }

  handleChangeFieldCheck(newValue: boolean) {
    this.matchFieldCheckValue = newValue;
    if (!newValue) {
      this.formData.match_fields = [];
    }
  }

  handleChangeExpressionCheck(newValue: boolean) {
    this.matchExpressionCheckValue = newValue;
    this.activeCollapse = newValue ? ['1'] : [];
    if (!newValue) {
      this.formData.match_pattern = '';
    }
  }

  handleValueBlur(val: string) {
    if (val !== '') {
      this.formData.match_fields.push(val);
    }
  }

  /** 接入项跳转 */
  handleJumpAccess(row: { ids: Iterable<unknown>|null|undefined; scenario_id: string|number; }) {
    const setList = new Set(row.ids);
    const idList = [...setList].join(',');
    const { href } = this.$router.resolve({
      name: this.scenarioRouteMap[row.scenario_id],
      query: {
        ids: encodeURIComponent(idList),
        spaceUid: useApplicationStore().spaceUid,
      },
    });
    window.open(href, '_blank', 'noopener,noreferrer');
  }

  handleChangeCoverNumber() {
    // 默认赋值0
    const {
      params: { preserve_head: preserveHead, preserve_tail: preserveTail },
    } = this.formData;
    this.formData.params.preserve_head = preserveHead ? preserveHead : 0;
    this.formData.params.preserve_tail = preserveHead ? preserveTail : 0;
  }

  render() {
    const accessTableSlot = () => (
      <Table
        rowKey='scenario_id'
        hideSortTips={true}
        stripe={true}
        class='masking-access-table'
        size='small'
        data={this.editAccessValue.accessInfo}
        onDataChange={data => { this.editAccessValue.accessInfo = data; }}
        columns={[
          { colKey: 'scenario_name', title: this.$t('日志来源') },
          { colKey: 'ids', title: this.$t('应用次数'), width: 125, align: 'center',
            sorter: (a, b) => a.ids.length - b.ids.length,
            cell: (_h, { row }) => (
              <Button size='small' theme='primary' variant='text'
                onClick={() => this.handleJumpAccess(row as { ids: string[]; scenario_id: string })}>
                {row.ids.length}
              </Button>
            ) },
        ]}
      />
    );

    return (
      <Sideslider
        v-slots={{
          default: () => (
            <div
              class='masking-rule-slider'
              v-loading={{ loading: this.formLoading, indicator: renderDrawerFormSkeleton }}
            >
              <Form
                ref='submitForm'
                class='masking-form'
                labelAlign='top'
                requiredMarkPosition='right'
                {...{
                  ...{
                    data: this.formData,
                    rules: this.rules,
                  },
                }}
              >
                <FormItem
                  label={this.$t('规则名称')}
                  name='rule_name'
                  requiredMark
                >
                  <Input v-model={this.formData.rule_name} />
                </FormItem>
                <FormItem
                  label={this.$t('匹配项')}
                  name='match_fields'
                  requiredMark
                >
                  <div class='masking-field'>
                    <Checkbox
                      class='group-check-box'
                      checked={this.matchFieldCheckValue}
                      disabled={!this.matchExpressionCheckValue}
                      onChange={this.handleChangeFieldCheck}
                    >
                      {this.$t('匹配字段名')}
                    </Checkbox>
                    <TagInput
                      v-model={this.formData.match_fields}
                      disabled={!this.matchFieldCheckValue}
                      onBlur={(_value, { inputValue }) => this.handleValueBlur(inputValue)}
                    />
                  </div>
                  <div
                    class='left-and'
                    v-show={this.isShowAndIcon}
                  >
                    <div>{this.$t('且')}</div>
                  </div>
                  <div
                    v-en-style='left: 80px;'
                    class='form-item-tips'
                  >
                    <i
                      class='bklog-icon bklog-info-fill'
                      v-log-tooltip={{ content: this.$t('字段名与表达式至少填写 1 个') }}
                    />
                  </div>
                </FormItem>
                <FormItem name='match_pattern' requiredMark={false}>
                  <div class='masking-expression'>
                    <Checkbox
                      class='group-check-box'
                      checked={this.matchExpressionCheckValue}
                      disabled={!this.matchFieldCheckValue}
                      onChange={this.handleChangeExpressionCheck}
                    >
                      {this.$t('匹配正则表达式')}
                    </Checkbox>
                    <div class='debug'>
                      <Input
                        v-model={this.formData.match_pattern}
                        disabled={!this.matchExpressionCheckValue}
                      />
                    </div>
                  </div>
                </FormItem>
                <FormItem
                  class='masking-rule'
                  label={() => (
                    <span class='masking-operator-label'>
                      <span>{(this.$t('脱敏算子') as string).replace('label-', '')}</span>
                      <span class='masking-operator-required' aria-hidden='true'>*</span>
                      {this.formData.operator === 'text_replace' && (
                      <Tooltip
                        attach='body'
                        placement='top-left'
                        popperOptions={{ strategy: 'fixed' }}
                        overlayClassName='masking-operator-tooltip'
                        overlayInnerStyle={{ maxWidth: '320px', whiteSpace: 'normal' }}
                        zIndex={this.drawerZIndex + 1}
                        content={`${this.$t('支持引用正则表达式中的命名分组。如正则表达式为 ')}(?P<phone>\\w{6,16})${this.$t('，可通过 ${phone} 进行引用')}`}
                      >
                        <span class='regex-item-tips'><i class='bklog-icon bklog-info-fill' /></span>
                      </Tooltip>
                      )}
                    </span>
                  )}
                  name='params'
                  requiredMark={false}
                >
                  <RadioGroup direction='horizontal' v-model={this.formData.operator}>
                    <Radio value={'text_replace'}>{this.$t('替换')}</Radio>
                    <Radio value={'mask_shield'}>{this.$t('掩码')}</Radio>
                  </RadioGroup>
                  {this.formData.operator === 'text_replace' ? (
                    <div class='replace-item'>
                      <div class='space-item-label'>{this.$t('替换为')}</div>
                      <Input
                        style='flex: 1;'
                        v-model={this.formData.params.template_string}
                      />
                    </div>
                  ) : (
                    <SourceTranslation tag='div' class='cover-item' path='保留前{0}位, 后{1}位'>
                      <InputNumber
                        v-model={this.formData.params.preserve_head}
                        min={0}
                        decimalPlaces={0}
                        theme='column'
                        onBlur={() => this.handleChangeCoverNumber()}
                      />
                      <InputNumber
                        v-model={this.formData.params.preserve_tail}
                        min={0}
                        decimalPlaces={0}
                        theme='column'
                        onBlur={() => this.handleChangeCoverNumber()}
                      />
                    </SourceTranslation>
                  )}
                </FormItem>
              </Form>

              <Collapse
                class='regular-debugging'
                v-model={this.activeCollapse}
              >
                <CollapseItem
                  v-slots={{
                    default: () => (
                      <div class='debugging-box'>
                        <div class='debug-input'>
                          <span class='debug-title'>{this.$t('原始日志')}</span>
                          <div class='debugging-log'>
                            <Textarea
                              class='debugging-input'
                              v-model={this.logOriginal}
                              placeholder={this.$t('请输入')}
                              autosize={{ minRows: 3, maxRows: 6 }}
                            />
                            {!!this.debugErrorTipsStr && <span class='debug-error'>{this.debugErrorTipsStr}</span>}
                          </div>
                        </div>
                        <span
                          v-log-tooltip={{
                            disabled: !this.isCanClickDebugBtn,
                            placement: 'right',
                            content: this.$t('正则表达式，脱敏算子，原始日志都填写后才可点击预览。'),
                          }}
                        >
                          <Button
                            style='font-size: var(--bklog-font-body, 12px);'
                            disabled={this.isCanClickDebugBtn}
                            theme='primary'

                            onClick={this.handleDebugging} variant={(true) ? 'outline' : 'base'}
                          >
                            {this.$t('结果预览')}
                          </Button>
                        </span>
                        <div class='debug-input'>
                          <span class='debug-title'>{this.$t('脱敏结果')}</span>
                          <div
                            class='effect-log'
                            v-loading={{ loading: this.debugRequesting, indicator: renderCodeSampleSkeleton }}
                          >
                            <TextHighlight
                              style='word-break: break-all; white-space:pre-line;'
                              queries={this.markList}
                            >
                              {this.formatterStr(this.debugLog)}
                            </TextHighlight>
                          </div>
                        </div>
                      </div>
                    ),
                  }}
                  disabled={!this.matchExpressionCheckValue}
                  value='1'
                  header={this.$t('脱敏结果预览')}
                  expandIcon={() => (
                    <span class={{ 'masking-preview-arrow': true, 'is-expanded': this.activeCollapse.includes('1') }} />
                  )}
                />
              </Collapse>

              <Dialog
                width={400}
                dialogClassName='masking-rule-confirm-dialog'
                header={false}
                visible={this.isShowSecondConfirmDialog}
                onClose={() => (this.isShowSecondConfirmDialog = false)}
                zIndex={this.confirmDialogZIndex}
                footer={false}
              >
                <div class='delete-dialog-container'>
                  <span class='delete-title'>{this.$t('确认{n}该规则？', { n: this.$t('修改') })}</span>
                  <span class='delete-text'>
                    {this.$t('当前脱敏规则被应用{n}次，修改规则后，现有脱敏配置需同步后生效，请确认是否保存编辑。', {
                      n: this.editAccessValue.accessNum,
                    })}
                  </span>
                  {accessTableSlot()}
                  <div class='delete-button'>
                    <Button
                      theme='primary'
                      onClick={() => this.handleDialogConfirm()}
                    >
                      {this.$t('确认')}
                    </Button>
                    <Button
                      theme='default'
                      onClick={() => (this.isShowSecondConfirmDialog = false)}
                    >
                      {this.$t('取消')}
                    </Button>
                  </div>
                </div>
              </Dialog>
            </div>
          ),
          footer: () => (
            <div class='submit-box'>
                <Button
                  theme='primary'
                  onClick={() => this.handleSubmit()}
                >
                  {this.$t('提交')}
                </Button>
                <Button
                  theme='default'
                  onClick={() => this.hiddenSlider()}
                >
                  {this.$t('取消')}
                </Button>
              </div>
          ),
        }}
        drawerClassName='masking-rule-drawer'
        size='640px'
        attach='body'
        visible={this.value}
        zIndex={this.drawerZIndex}
        header={() => (
          <div class='masking-rule-drawer-header'>
            <button type='button' class='masking-rule-drawer-close' aria-label={this.$t('关闭')} onClick={this.hiddenSlider}>
              <span />
            </button>
            <span>{this.$t('{n}脱敏规则', { n: this.isEdit ? this.$t('编辑') : this.$t('新增') })}</span>
          </div>
        )}
        closeOnOverlayClick
        closeOnEscKeydown
        footer={true}
        onBeforeOpen={this.showSlider}
        onClose={this.hiddenSlider}
      ></Sideslider>
    );
  }
}
