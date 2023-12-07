/*
 * Tencent is pleased to support the open source community by making BK-LOG 蓝鲸日志平台 available.
 * Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
 * BK-LOG 蓝鲸日志平台 is licensed under the MIT License.
 *
 * License for BK-LOG 蓝鲸日志平台:
 * --------------------------------------------------------------------
 *
 * Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated
 * documentation files (the "Software"), to deal in the Software without restriction, including without limitation
 * the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software,
 * and to permit persons to whom the Software is furnished to do so, subject to the following conditions:
 * The above copyright notice and this permission notice shall be included in all copies or substantial
 * portions of the Software.
 *
 * THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT
 * LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN
 * NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY,
 * WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE
 * SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE
 */

import { Component as tsc } from 'vue-tsx-support';
import { Component, PropSync, Prop, Emit, Ref } from 'vue-property-decorator';
import { Select, Option, Tag, Form, FormItem, Input } from 'bk-magic-vue';
import $http from '../../api';
import './index.scss';

interface IProps {
  propLabelList: IPropLabelList;
  selectLabelList: IPropLabelList;
}

interface IPropLabelList {
  color: string;
  name: string;
  tag_id: number;
  is_built_in?: boolean;
}

@Component
export default class QueryStatement extends tsc<IProps> {
  @PropSync('label', { type: Array }) propLabelList: Array<IPropLabelList>;
  @Prop({ type: Object, required: true }) rowData: any;
  @Prop({ type: Array, required: true }) selectLabelList: Array<IPropLabelList>;
  @Ref('checkInputForm') private readonly checkInputFormRef: Form;

  /** 是否展示添加标签 */
  isShowNewGroupInput = false;

  verifyData = {
    labelEditName: '',
  };

  rules = {
    labelEditName: [
      {
        validator: this.checkTagName,
        message: this.$t('已有同名标签'),
        trigger: 'blur',
      },
      {
        required: true,
        message: this.$t('必填项'),
        trigger: 'blur',
      },
    ],
  };

  get isDisabledAddNewTag() {
    // console.log(this.rowData);
    return this.rowData.status === 'terminated';
  }

  /** 过滤掉内置标签的标签列表 */
  get filterBuiltInList() {
    return this.selectLabelList.filter(item => !item.is_built_in);
  }

  /** 索引集展示的标签 */
  get showLabelList() {
    const showIDlist = this.filterBuiltInList.map(item => item.tag_id);
    return this.propLabelList.filter(item => showIDlist.includes(item.tag_id),
    );
  }

  /** 单选框标签下拉列表 */
  get showGroupSelectLabelList() {
    const propIDlist = this.propLabelList.map(item => item.tag_id);
    return this.filterBuiltInList.map(item => ({
      ...item,
      disabled: propIDlist.includes(item.tag_id),
    }));
  }

  @Emit('refreshLabelList')
  initLabelSelectList() {
    return {};
  }

  checkTagName() {
    return !this.selectLabelList.some(
      item => item.name === this.verifyData.labelEditName.trim(),
    );
  }

  /** 给索引集添加标签 */
  addLabelToIndexSet(tagID: number) {
    if (!tagID) return;
    $http
      .request('unionSearch/unionAddLabel', {
        params: {
          index_set_id: this.rowData.index_set_id,
        },
        data: {
          tag_id: tagID,
        },
      })
      .then(() => {
        const newLabel = this.selectLabelList.find(
          item => item.tag_id === tagID,
        );
        this.propLabelList.push(newLabel);
        this.$bkMessage({
          theme: 'success',
          message: this.$t('操作成功'),
        });
      })
      .finally(() => {});
  }

  /** 新增标签 */
  handleChangeLabelStatus(operate: string) {
    if (operate === 'add') {
      this.checkInputFormRef.validate().then(
        async () => {
          $http
            .request('unionSearch/unionCreateLabel', {
              data: {
                name: this.verifyData.labelEditName.trim(),
              },
            })
            .then(() => {
              this.initLabelSelectList();
            })
            .finally(() => {
              this.verifyData.labelEditName = '';
              this.isShowNewGroupInput = false;
            });
        },
        () => {},
      );
    } else {
      this.isShowNewGroupInput = false;
    }
  }

  handleLabelKeyDown(val: string) {
    if (val) this.handleChangeLabelStatus('add');
  }

  /** 删除采集项的标签 */
  handleDeleteTag(tagID: number) {
    $http
      .request('unionSearch/unionDeleteLabel', {
        params: {
          index_set_id: this.rowData.index_set_id,
        },
        data: {
          tag_id: tagID,
        },
      })
      .then(() => {
        this.propLabelList = this.propLabelList.filter(
          item => item.tag_id !== tagID,
        );
        this.$bkMessage({
          theme: 'success',
          message: this.$t('操作成功'),
        });
      })
      .finally(() => {});
  }

  toggleSelect(val: boolean) {
    if (!val) {
      this.isShowNewGroupInput = false;
      this.verifyData.labelEditName = '';
    }
  }

  render() {
    return (
      <div class="label-select">
        <div
          class="label-tag-container"
          v-bk-overflow-tips={{
            content: `${this.showLabelList
              .map(item => item.name)
              .join(', ')}`,
          }}
        >
          {this.showLabelList.map(item => (
            <Tag>
              <span class="label-tag">
                <span>{item.name}</span>
                <i
                  class="bk-icon icon-close"
                  onClick={() => this.handleDeleteTag(item.tag_id)}
                ></i>
              </span>
            </Tag>
          ))}
        </div>
        <Select
          searchable
          popover-min-width={240}
          popover-options={{ boundary: 'window', distance: 30 }}
          disabled={this.isDisabledAddNewTag}
          onSelected={this.addLabelToIndexSet}
          onToggle={this.toggleSelect}
          scopedSlots={{
            trigger: () => (
              <div
                class={[
                  'add-label-btn',
                  {
                    disabled: this.isDisabledAddNewTag,
                  },
                ]}
              >
                <i class="bk-icon icon-plus-line"></i>
              </div>
            ),
          }}
        >
          <div class="new-label-container" slot="extension">
            {this.isShowNewGroupInput ? (
              <div class="new-label-input">
                <Form
                  labelWidth={0}
                  style={{ width: '100%' }}
                  ref="checkInputForm"
                  {...{
                    props: {
                      model: this.verifyData,
                      rules: this.rules,
                    },
                  }}
                >
                  <FormItem property="labelEditName">
                    <Input
                      clearable
                      vModel={this.verifyData.labelEditName}
                      onEnter={v => this.handleLabelKeyDown(v)}
                    ></Input>
                  </FormItem>
                </Form>
                <div class="operate-button">
                  <span
                    class="bk-icon icon-check-line"
                    onClick={() => this.handleChangeLabelStatus('add')}
                  ></span>
                  <span
                    class="bk-icon icon-close-line-2"
                    onClick={() => this.handleChangeLabelStatus('cancel')}
                  ></span>
                </div>
              </div>
            ) : (
              <div
                class="add-new-label"
                onClick={() => (this.isShowNewGroupInput = true)}
              >
                <i class="bk-icon icon-plus-circle"></i>
                <span>{this.$t('新增标签')}</span>
              </div>
            )}
          </div>
          <div class="group-list">
            {this.showGroupSelectLabelList.map(item => (
              <Option
                class="label-option"
                id={item.tag_id}
                name={item.name}
                disabled={item.disabled}
              ></Option>
            ))}
          </div>
        </Select>
      </div>
    );
  }
}
