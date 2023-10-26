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
import { Component, Emit, Prop, Ref, Watch } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';
import { Form, FormItem } from 'bk-magic-vue';

import { checkDuplicateName } from '../../../../monitor-api/modules/apm_meta';
import { Debounce, deepClone } from '../../../../monitor-common/utils/utils';
import { ICreateAppFormData } from '../../home/app-list';

import SelectCardItem, { IDescData, ThemeType } from './select-card-item';

import './select-system.scss';

export interface IListDataItem {
  title: string;
  list?: ICardItem[];
  children?: IListDataItem[];
  multiple?: boolean;
  other?: {
    title: string;
    checked: boolean;
    value: string;
  };
}
export interface ICardItem {
  id: string;
  title: string;
  theme: ThemeType;
  img: string;
  descData?: IDescData;
  hidden: boolean;
  checked: boolean;
}
interface IProps {
  loading: boolean;
  listData: IListDataItem[];
}
interface IEvents {
  onNextStep: void;
  onChange: ICreateAppFormData;
}
@Component
export default class SelectSystem extends tsc<IProps, IEvents> {
  @Prop({ type: Boolean }) loading: false;
  @Prop({ type: Array, default: () => [] }) listData: IListDataItem[];

  @Ref() addForm: any;

  isEmpy = false;
  localListData: IListDataItem[] = [];
  canNextStep = false;
  formData: ICreateAppFormData = {
    name: '',
    enName: '',
    desc: '',
    pluginId: ''
  };
  rules = {
    name: [
      {
        required: true,
        message: window.i18n.tc('输入应用名,1-50个字符'),
        trigger: 'blur'
      }
    ],
    enName: [
      {
        validator: val => /^[_|a-zA-Z][a-zA-Z0-9_]*$/.test(val) && val.length >= 5,
        message: window.i18n.t('输入5-50字符的字母开头、数字、下划线'),
        trigger: 'blur'
      }
    ]
  };
  /** 英文名是否重名 */
  existedName = false;
  /** 点击提交触发 */
  clickSubmit = false;

  created() {
    this.initData();
  }

  mounted() {
    this.canNextStep = this.validate();
  }

  @Watch('listData', { deep: true, immediate: true })
  listDataUpdate(list: IListDataItem[]) {
    this.localListData = deepClone(list);
  }

  /** 初始化页面数据 */
  initData() {
    this.rules.enName.push({
      message: window.i18n.tc('注意: 名字冲突'),
      trigger: 'none',
      validator: val => !this.existedName && !!val
    });
  }

  /** 批量修改整行卡片的选中状态 */
  handleRowChecked(row: IListDataItem, bool = false) {
    row.list.forEach(item => (item.checked = bool));
    if (!!row.other) {
      row.other.checked = bool;
      row.other.value = '';
    }
  }

  /** 点击卡片操作 单选 */
  // handleCheckedCardItem(cardItem: ICardItem, row: IListDataItem, val: boolean) {
  //   !row.multiple && this.handleRowChecked(row);
  //   cardItem.checked = val;
  //   this.canNextStep = this.validate();
  // }

  /** 选中其他选项 */
  handleOtherChecked(row: IListDataItem, val: boolean) {
    !row.multiple && this.handleRowChecked(row);
    row.other.checked = val;
  }

  /** 处理SelectCardItem的现隐 */
  @Debounce(200)
  handleSearch(keyword: string) {
    let isEmpy = true;
    const fn = (list: IListDataItem[]) => {
      list.forEach(row => {
        if (!!row.children?.length) {
          fn(row.children);
        } else {
          row.list?.forEach?.(cardItem => {
            const isMatch = cardItem.title.toLocaleLowerCase().includes(keyword.toLocaleLowerCase());
            cardItem.hidden = !isMatch;
            if (isMatch) isEmpy = false;
          });
        }
      });
    };
    fn(this.localListData);
    this.isEmpy = isEmpy;
  }

  /** 是否展示该行卡片 */
  handleShowRow(row: IListDataItem) {
    return (
      row.list?.some?.(item => !item.hidden) || row.children?.some?.(child => child.list?.some?.(item => !item.hidden))
    );
  }

  /** 校验数据 */
  validate(checkedList?: IListDataItem[]): boolean {
    const localCheckList = checkedList || this.getCheckedList();
    return localCheckList.every(
      row =>
        !!row.list?.length ||
        (row.other?.checked && !!row.other?.value) ||
        row.children?.some?.(child => !!child.list.length)
    );
  }

  /** 下一步操作 */
  async handleNextStep() {
    // const checkedList: IListDataItem[] = this.getCheckedList();
    // const isPass = this.validate(checkedList);
    // if (isPass) this.handleNext();

    /** 校验重名 */
    this.clickSubmit = true;
    const noExistedName = await this.handleCheckEnName(true);
    if (noExistedName) {
      const isPass = await this.addForm.validate();
      if (isPass) {
        // this.$router.replace({
        //   name: this.$route.name,
        //   params: {
        //     appInfo: JSON.stringify({ ...this.formData, ...{ pluginId: '' } })
        //   }
        // });
        this.handleNext();
      }
    }
  }

  @Emit('nextStep')
  @Emit('change')
  handleNext() {
    return deepClone(this.formData);
  }

  /** 筛选被选中的数据 */
  getCheckedList(): IListDataItem[] {
    const fn = (list: IListDataItem[]) =>
      list.map(row => {
        if (row.children) {
          return {
            ...row,
            children: fn(row.children)
          };
        }
        row.list = row.list.filter(item => item.checked);

        return row;
      });
    return fn(deepClone(this.localListData));
  }
  handleCancel() {
    this.$router.back();
  }
  /** 检查英文名是否重名 */
  handleCheckEnName(isSubmit = false) {
    return new Promise((resolve, reject) => {
      if (!this.formData.enName) return resolve(true);
      if (!/^[_|a-zA-Z][a-zA-Z0-9_]*$/.test(this.formData.enName) || this.formData.enName.length < 5)
        return reject(false);
      // eslint-disable-next-line @typescript-eslint/no-misused-promises
      setTimeout(async () => {
        if (this.clickSubmit && !isSubmit) {
          resolve(true);
        } else {
          this.clickSubmit = false;
          const { exists } = await checkDuplicateName({ app_name: this.formData.enName });
          this.existedName = exists;
          if (exists) {
            this.addForm.validateField('enName');
            reject(false);
          } else {
            resolve(true);
          }
        }
      }, 100);
    });
  }

  render() {
    /** 一行卡片 */
    const cardList = (list: ICardItem[], row: IListDataItem) =>
      list.map(
        cardItem =>
          !cardItem.hidden && (
            <SelectCardItem
              class='app-add-card-item'
              mode='small'
              title={cardItem.title}
              // theme={cardItem.theme}
              theme={'intro'}
              img={cardItem.img}
              multiple={row.multiple}
              checked={cardItem.checked}
              descData={cardItem.descData}
              // onClick={() => this.handleCheckedCardItem(cardItem, row, !cardItem.checked)}
            />
          )
      );
    return (
      <div
        class='select-system-wrap'
        v-bkloading={{ isLoading: this.loading }}
      >
        <div class='app-add-desc'>
          <div class='app-add-question'>{this.$t('什么是应用？')}</div>
          <div class='app-add-answer'>
            {this.$t('应用一般是拥有独立的站点，由多个Service共同组成，提供完整的产品功能，拥有独立的软件架构。 ')}
          </div>
          <div class='app-add-answer'>
            {this.$t(
              '从技术方面来说应用是Trace数据的存储隔离，在同一个应用内的数据将进行统计和观测。更多请查看产品文档。'
            )}
          </div>
        </div>

        {/* <bk-input
          class="card-item-search"
          onChange={this.handleSearch}
          placeholder={this.$t('输入搜索或筛选')}
          right-icon="bk-icon icon-search"></bk-input> */}
        {!this.isEmpy ? (
          [
            <div>
              {this.localListData.map(
                item =>
                  this.handleShowRow(item) && (
                    <div class='app-add-row'>
                      <div class='app-add-row-title'>{item.title}</div>
                      <div class='app-add-row-content'>
                        <div>
                          {!!item.list?.length && <div class='row-content-list'>{cardList(item.list, item)}</div>}
                          {!!item.children?.length &&
                            item.children.map(child =>
                              child.list.length ? (
                                <div class='app-add-row-child'>
                                  <div class='child-title'>{child.title}</div>
                                  <div class='child-row-content'>
                                    <div class='row-content-list'>
                                      {!!child.list?.length && cardList(child.list, child)}
                                    </div>
                                  </div>
                                </div>
                              ) : undefined
                            )}
                        </div>
                        {!!item.other && (
                          <div class='app-add-row-other'>
                            <bk-checkbox
                              v-model={item.other.checked}
                              onChange={val => this.handleOtherChecked(item, val)}
                            >
                              {item.other.title}
                            </bk-checkbox>
                            <bk-input
                              class='other-input simplicity-input'
                              v-model={item.other.value}
                              behavior='simplicity'
                            ></bk-input>
                          </div>
                        )}
                      </div>
                    </div>
                  )
              )}
            </div>
            // <div class="select-btn-row">
            // eslint-disable-next-line max-len
            //   <bk-button class="btn" theme="primary" onClick={this.handleNextStep} disabled={!this.canNextStep}>{this.$t('下一步')}</bk-button>
            //   <bk-button class="btn" onClick={this.handleCancel}>{this.$t('取消')}</bk-button>
            // </div>
          ]
        ) : (
          <bk-exception
            class='empty-page'
            type='search-empty'
          ></bk-exception>
        )}

        <Form
          class='app-add-form'
          {...{
            props: {
              model: this.formData,
              rules: this.rules
            }
          }}
          label-width={84}
          ref='addForm'
        >
          <FormItem
            label={this.$t('应用名称')}
            required
            property='name'
            error-display-type='normal'
          >
            <bk-input
              v-model={this.formData.name}
              maxlength={50}
              placeholder={this.$t('输入应用名,1-50个字符')}
            />
          </FormItem>
          <FormItem
            label={this.$t('英文名')}
            required
            property='enName'
            error-display-type='normal'
          >
            <bk-input
              v-model={this.formData.enName}
              maxlength={50}
              placeholder={this.$t('输入5-50字符的字母开头、数字、下划线')}
              onBlur={() => this.handleCheckEnName()}
            />
          </FormItem>
          <FormItem label={this.$t('描述')}>
            <bk-input
              type='textarea'
              v-model={this.formData.desc}
            ></bk-input>
          </FormItem>
          <FormItem>
            <bk-button
              class='btn mr10'
              theme='primary'
              onClick={this.handleNextStep}
              // disabled={!this.canNextStep}
            >
              {this.$t('下一步')}
            </bk-button>
            <bk-button
              class='btn'
              onClick={this.handleCancel}
            >
              {this.$t('取消')}
            </bk-button>
          </FormItem>
        </Form>
      </div>
    );
  }
}
