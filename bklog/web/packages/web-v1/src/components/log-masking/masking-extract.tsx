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

import { Component, Model, Emit, Ref } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import { Sideslider, Form, FormItem, Input, Button, type Popover } from 'bk-magic-vue';

import MaskingSelectRuleTable from './masking-select-rule-table';

import './masking-extract.scss';

interface IProps {
  value: boolean;
}

@Component
export default class MaskingExtract extends tsc<IProps> {
  @Model('change', { type: Boolean, default: false }) value: IProps['value'];

  logOriginal = '';
  debugRequesting = false;
  isShowSecondConfirmDialog = false;
  isMarginRight = false;
  tablePopoverInstance = null;
  directoryList = [{}];
  suffixList = [{}];

  @Ref('ruleTable') private readonly ruleTableRef: Popover;

  @Emit('change')
  hiddenSlider() {
    return false;
  }

  mounted() {}
  handleSubmit() {
    this.isShowSecondConfirmDialog = true;
  }
  handleDebugging() {}
  handleConfirmChange() {
    this.isShowSecondConfirmDialog = false;
    this.hiddenSlider();
  }

  getShowRowStyle(row: any) {
    return { background: (row.rowIndex + 1) % 2 === 0 ? '#F5F7FA' : '#FFF' };
  }

  addDirectory() {
    this.directoryList.push({});
  }

  delDirectory(index) {
    if (this.directoryList.length === 1) {
      return;
    }
    this.directoryList.splice(index, 1);
  }

  addSuffix() {
    this.suffixList.push({});
  }

  delSuffix(index) {
    if (this.suffixList.length === 1) {
      return;
    }
    this.suffixList.splice(index, 1);
  }

  handleSelectRule() {
    this.tablePopoverInstance?.hide();
  }

  handleClickAddNewRule(e) {
    // 判断当前是否有实例 如果有实例 则给操作列表常驻显示
    if (!this.tablePopoverInstance) {
      this.tablePopoverInstance = this.$bkPopover(e.target, {
        content: this.ruleTableRef,
        interactive: true,
        theme: 'light shield',
        trigger: 'manual',
        offset: '-40, 6',
        arrow: true,
        hideOnClick: false,
        appendTo: 'parent',
        placement: 'top-start',
        extCls: 'rule-table-dialog',
        zIndex: 999,
        onHidden: () => {
          this.destroyPopoverInstance();
        },
        onShow: () => {},
      });
      this.tablePopoverInstance.show(100);
    }
  }

  destroyPopoverInstance() {
    this.tablePopoverInstance?.hide();
    this.tablePopoverInstance?.destroy();
    this.tablePopoverInstance = null;
  }

  render() {
    const tableSlot = () => (
      <div style={{ display: 'none' }}>
        <div
          ref='ruleTable'
          class='rule-table-content'
        >
          <div style='padding: 16px;'>
            <span class='title'>{this.$t('选择脱敏规则')}</span>
            <MaskingSelectRuleTable onNewRuleSidesliderState={(state: boolean) => (this.isMarginRight = state)} />
          </div>
        </div>
      </div>
    );
    return (
      <Sideslider
        width={640}
        ext-cls={`${this.isMarginRight && 'open-add-rule-sideslider'}`}
        is-show={this.value}
        title={'新增提取'}
        quick-close
        transfer
        on-hidden={() => this.destroyPopoverInstance()}
        {...{
          on: {
            'update:isShow': this.hiddenSlider,
          },
        }}
      >
        <div
          class='masking-extract-slider'
          slot='content'
        >
          <Form
            ext-cls='masking-form'
            form-type='vertical'
            label-width={200}
          >
            <FormItem
              label={'名称'}
              required
            >
              <Input />
            </FormItem>
            <FormItem
              label={'脱敏设置'}
              required
            >
              <span
                class='masking-btn'
                onClick={e => this.handleClickAddNewRule(e)}
              >
                <Button size='small'>{this.$t('添加规则')}</Button>
              </span>
              <div class='masking-rule'>
                <span class='rule-name'>手机号脱敏</span>
                <span class='rule-value'>替换｜替换为 0</span>
                <i class='rule-icon bk-icon icon-close-circle-shape' />
              </div>
              <div class='masking-rule'>
                <span class='rule-name'>手机号脱敏</span>
                <span class='rule-value'>替换｜替换为 0</span>
                <i class='rule-icon bk-icon icon-close-circle-shape' />
              </div>
              <div class='form-item-tips'>
                <i
                  class='bklog-icon bklog-info-fill'
                  v-bk-tooltips={{ content: this.$t('字段名与表达式至少填写 1 个') }}
                />
              </div>
            </FormItem>
            <FormItem
              label={'用户列表'}
              required
            >
              <Input />
            </FormItem>
            <FormItem
              label={'授权目录'}
              required
            >
              {this.directoryList.map((item, index) => (
                <div
                  key={`${index}-${item}`}
                  class='length-change-item'
                >
                  <Input />
                  <div class='ml9'>
                    <i
                      class='bk-icon icon-plus-circle-shape icons'
                      onClick={() => this.addDirectory()}
                    />
                    <i
                      class={[
                        'bk-icon icon-minus-circle-shape icons ml9',
                        { disable: this.directoryList.length === 1 },
                      ]}
                      onClick={() => this.delDirectory(index)}
                    />
                  </div>
                </div>
              ))}
            </FormItem>
            <FormItem
              label={'文件后缀'}
              required
            >
              {this.suffixList.map((item, index) => (
                <div
                  key={`${index}-${item}`}
                  class='length-change-item'
                >
                  <Input />
                  <div class='ml9'>
                    <i
                      class='bk-icon icon-plus-circle-shape icons'
                      onClick={() => this.addSuffix()}
                    />
                    <i
                      class={['bk-icon icon-minus-circle-shape icons ml9', { disable: this.suffixList.length === 1 }]}
                      onClick={() => this.delSuffix(index)}
                    />
                  </div>
                </div>
              ))}
            </FormItem>
            <FormItem
              label={'授权目标'}
              required
            >
              <Button size='small'>{this.$t('选择目标')}</Button>
            </FormItem>
            <FormItem
              desc='hello desc'
              label={'执行人'}
              required
            >
              <div class='length-change-item'>
                <Input />
                <Button
                  class='ml9'
                  theme='primary'
                  outline
                >
                  {this.$t('改为我')}
                </Button>
              </div>
            </FormItem>
          </Form>

          <div class='submit-box'>
            <Button
              theme='primary'
              onClick={() => this.handleSubmit()}
            >
              {this.$t('提交')}
            </Button>
            <Button theme='default'>{this.$t('取消')}</Button>
          </div>
          {tableSlot()}
        </div>
      </Sideslider>
    );
  }
}
