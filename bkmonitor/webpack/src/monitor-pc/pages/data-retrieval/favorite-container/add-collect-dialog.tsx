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

import VueJsonPretty from 'vue-json-pretty';
import { Component, Emit, Model, Prop, Ref } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import { createFavoriteGroup, listFavoriteGroup } from '../../../../monitor-api/modules/model';

import './add-collect-dialog.scss';
import 'vue-json-pretty/lib/styles.css';

interface IProps {
  value?: boolean;
  editFavoriteData?: object;
  keyword: object;
  favoriteSearchType: string;
  favStrList: string[];
}

interface ISubmitData {
  name: string;
  group_id: string | number;
  create_user: string;
}

interface IEvent {
  onSubmit: {
    value: any;
    hideCallback: () => void;
    isEdit: boolean;
  };
  onCancel: () => void;
}

@Component
export default class CollectDialog extends tsc<IProps, IEvent> {
  @Model('change', { type: Boolean, default: false }) value: IProps['value'];
  @Prop({ type: Object, default: () => ({}) }) keyword: object; // 当前弹窗展示的查询语句参数
  @Prop({ type: String, required: true }) favoriteSearchType: string; // 收藏类型
  @Prop({ type: Object, default: () => ({}) }) editFavoriteData: object; // 编辑收藏的数据
  @Prop({ type: Array, default: () => [] }) favStrList: string[]; // 收藏类型
  @Ref('validateForm') validateFormRef: any;
  @Ref('checkInputForm') checkInputFormRef: any;
  searchFieldsList = []; // 表单模式显示字段
  isShowAddGroup = true; // 是否展示新增组
  // groupName = ''; // 组名
  baseFavoriteData: ISubmitData = {
    // 用户可编辑的基础数据
    name: '',
    group_id: '',
    create_user: ''
  };
  favoriteData: ISubmitData = {
    // 收藏数据
    name: '',
    group_id: '',
    create_user: ''
  };
  verifyData = {
    groupName: ''
  };
  positionTop = 0;
  allGroupList = [];
  publicGroupList = []; // 可见状态为公共的时候显示的收藏组
  privateGroupList = []; // 个人组
  formLoading = false;
  radioValue = 'null'; // 可见范围
  isShowJsonKeywords = false; // 是否展示json格式的查询语句
  public rules = {
    name: [
      {
        required: true,
        trigger: 'blur'
      },
      {
        validator: this.checkSpecification,
        message: window.i18n.t('收藏名包含了特殊符号'),
        trigger: 'blur'
      },
      {
        validator: this.checkRepeatName,
        message: window.i18n.t('注意: 名字冲突'),
        trigger: 'blur'
      },
      {
        validator: this.checkCannotUseName,
        message: window.i18n.t('保留名称，不可使用'),
        trigger: 'blur'
      },
      {
        max: 30,
        message: window.i18n.t('注意：最大值为30个字符'),
        trigger: 'blur'
      }
    ]
  };

  public groupNameRules = {
    groupName: [
      {
        validator: this.checkName,
        message: window.i18n.t('组名不规范, 包含了特殊符号.'),
        trigger: 'blur'
      },
      {
        validator: this.checkExistName,
        message: window.i18n.t('注意: 名字冲突'),
        trigger: 'blur'
      },
      {
        required: true,
        message: window.i18n.t('必填项'),
        trigger: 'blur'
      },
      {
        max: 30,
        message: window.i18n.t('注意：最大值为30个字符'),
        trigger: 'blur'
      }
    ]
  };

  get isEditFavorite() {
    // 根据传参判断新增还是编辑
    if (this.editFavoriteData === null) return false;
    return Boolean(Object.keys(this.editFavoriteData).length);
  }

  get isDisableSelect() {
    // 是否禁用分组下拉框
    return this.favoriteData.group_id === 0;
  }

  get isCannotChangeVisible() {
    // 编辑时候判断是否是本人创建 如果非本人则禁用
    if (!this.isEditFavorite) return false;
    return this.favoriteData.create_user !== (window.user_name || window.username);
  }

  get showGroupList() {
    // 展示的组列表
    return this.favoriteData.group_id === 0 ? this.privateGroupList : this.publicGroupList;
  }

  get bizId(): string {
    return this.$store.getters.bizId;
  }

  get isPromQlKeywords() {
    // 判断指标检索时 是否是promql查询
    if (this.keyword === null) return {};
    return 'promqlData' in this.keyword;
  }

  get promqlShowData() {
    const promqlArr = this.keyword?.promqlData ?? [];
    return promqlArr
      .filter(pItem => pItem.code)
      .map(item => ({
        label: `${window.i18n.t('查询项')}${item.alias}:`,
        value: item.code
      }));
  }

  mounted() {
    this.positionTop = Math.floor(document.body.clientHeight * 0.1);
  }

  @Emit('change') // 展开或关闭弹窗
  handleShowChange(value = false) {
    return value;
  }

  @Emit('cancel') // 取消
  handleCancelDialog() {}

  @Emit('submit') // 提交保存
  handleSubmitChange() {
    return {
      value: this.favoriteData,
      isEdit: this.isEditFavorite,
      hideCallback: () => this.handleShowChange(false)
    };
  }

  checkName() {
    if (this.verifyData.groupName.trim() === '') return true;
    return /^[\u4e00-\u9fa5_a-zA-Z0-9`~!@#$%^&*()_\-+=<>?:"\s{}|,./;'\\[\]·~！@#￥%……&*（）——\-+={}|《》？：“”【】、；‘'，。、]+$/im.test(
      this.verifyData.groupName.trim()
    );
  }

  checkExistName() {
    return !this.allGroupList.some(item => item.name === this.verifyData.groupName);
  }

  async handleValueChange(value) {
    if (value) {
      this.formLoading = true;
      await this.getFavoriteGroupList(); // 获取组列表
      if (this.isEditFavorite) {
        // 是否是编辑收藏
        const { config, ...reset } = this.editFavoriteData;
        Object.assign(this.favoriteData, reset); // 如果是编辑则合并编辑详情
        this.radioValue = this.favoriteData.group_id === 0 ? '0' : 'null'; // 赋值可见范围
      } else {
        this.radioValue = 'null';
      }
    } else {
      Object.assign(this.favoriteData, this.baseFavoriteData); // 关闭弹窗 恢复基础数据
      this.isShowJsonKeywords = false;
      this.handleShowChange(false);
      this.handleCancelDialog();
    }
  }

  /** 新增组 */
  handleCreateGroup() {
    this.checkInputFormRef.validate().then(() => {
      createFavoriteGroup({
        bk_biz_id: this.bizId,
        type: this.favoriteSearchType,
        name: this.verifyData.groupName
      })
        .then(() => {
          this.getFavoriteGroupList(true, this.verifyData.groupName.trim());
        })
        .finally(() => {
          this.isShowAddGroup = true;
          this.verifyData.groupName = '';
        });
    });
  }

  handleCancelCreateGroup() {
    this.isShowAddGroup = true;
    this.verifyData.groupName = '';
  }

  handleClickRadio(value: string) {
    this.favoriteData.group_id = value === 'null' ? null : 0;
  }
  /** 新增或更新收藏 */
  handleSubmitFormData() {
    this.validateFormRef
      .validate()
      .then(() => {
        this.formLoading = true;
        const groupIDStr = String(this.favoriteData.group_id);
        const isUnKnowGroup = groupIDStr === 'null' || groupIDStr === '';
        this.favoriteData.group_id = isUnKnowGroup ? null : Number(groupIDStr);
        this.handleSubmitChange();
      })
      .finally(() => {
        this.formLoading = false;
      });
  }

  /** 获取组列表 */
  async getFavoriteGroupList(isAddGroup = false, groupName?: string) {
    try {
      const param = { type: this.favoriteSearchType };
      const res = await listFavoriteGroup(param);
      const filterGroupList = res.map(item => ({ id: `${item.id}`, name: item.name }));
      this.allGroupList = filterGroupList;
      this.publicGroupList = filterGroupList.slice(1, filterGroupList.length);
      this.privateGroupList = [filterGroupList[0]];
    } catch (error) {
      console.warn(error);
    } finally {
      if (isAddGroup) {
        this.favoriteData.group_id = this.allGroupList.find(item => item.name === groupName)?.id;
      }
      this.formLoading = false;
    }
  }
  /** 判断是否收藏名是否重复 */
  checkRepeatName() {
    if (this.isEditFavorite) return true;
    return !this.favStrList.includes(this.favoriteData.name);
  }
  /** 检查收藏语法是否正确 */
  checkSpecification() {
    return /^[\u4e00-\u9fa5_a-zA-Z0-9`~!@#$%^&*()_\-+=<>?:"\s{}|,./;'\\[\]·~！@#￥%……&*（）——\-+={}|《》？：“”【】、；‘'，。、]+$/im.test(
      this.favoriteData.name.trim()
    );
  }
  /** 检查是否有内置名称不能使用 */
  checkCannotUseName() {
    return ![this.$t('个人收藏'), this.$t('未分组')].includes(this.favoriteData.name.trim());
  }

  render() {
    const metricKeywordsSlot = () => (
      <div class={['view-box', { 'is-expand': this.isShowJsonKeywords }]}>
        <div
          class={{ 'view-content': this.isShowJsonKeywords }}
          onClick={() => (this.isShowJsonKeywords = true)}
        >
          {this.isPromQlKeywords ? (
            <div class='view-content'>
              {this.promqlShowData.map((item, index) => (
                <div class='promql-box'>
                  <div class='promql-label'>{item.label}</div>
                  <div class='promql-val'>{item.value}</div>
                  {this.promqlShowData.length - 1 !== index && <br />}
                </div>
              ))}
            </div>
          ) : (
            <span class='string-json view-content'>
              <VueJsonPretty
                deep={5}
                data={this.keyword}
              />
            </span>
          )}
        </div>
      </div>
    );
    const eventKeywordsSlot = () => <span>{this.keyword?.queryConfig.query_string}</span>;
    return (
      <bk-dialog
        value={this.value}
        title={this.isEditFavorite ? this.$t('编辑收藏') : this.$t('新增收藏')}
        ok-text={this.isEditFavorite ? this.$t('保存') : this.$t('确定')}
        header-position='left'
        ext-cls='add-collect-dialog'
        render-directive='if'
        width={480}
        position={{ top: this.positionTop }}
        mask-close={false}
        auto-close={false}
        on-value-change={this.handleValueChange}
        on-confirm={this.handleSubmitFormData}
      >
        <bk-form
          form-type='vertical'
          ref='validateForm'
          v-bkloading={{ isLoading: this.formLoading }}
          {...{
            props: {
              model: this.favoriteData,
              rules: this.rules
            }
          }}
        >
          <div class='edit-information'>
            <span>{this.$t('查询语句')}</span>
            {this.favoriteSearchType === 'metric' ? metricKeywordsSlot() : eventKeywordsSlot()}
          </div>
          <bk-form-item
            label={this.$t('收藏名')}
            required
            property='name'
            class='group-name'
          >
            <bk-input
              class='collect-name'
              vModel={this.favoriteData.name}
              placeholder={this.$t('填写收藏名（长度30个字符）')}
            ></bk-input>
          </bk-form-item>

          <bk-form-item
            class='collect-radio'
            label={this.$t('可见范围')}
            required
          >
            <bk-radio-group
              vModel={this.radioValue}
              on-change={this.handleClickRadio}
            >
              <bk-radio value={'null'}>
                {this.$t('公开')}({this.$t('本业务可见')})
              </bk-radio>
              <bk-radio
                value={'0'}
                disabled={this.isCannotChangeVisible}
              >
                {this.$t('私有')}
                {this.$t('(仅个人可见)')}
              </bk-radio>
            </bk-radio-group>
          </bk-form-item>
          <bk-form-item
            label={this.$t('所属组')}
            class='affiliation-group'
          >
            <bk-select
              vModel={this.favoriteData.group_id}
              disabled={this.isDisableSelect}
              ext-popover-cls='add-new-page-container'
              searchable
            >
              {this.showGroupList.map(item => (
                <bk-option
                  id={item.id}
                  key={item.id}
                  name={item.name}
                ></bk-option>
              ))}
              <div slot='extension'>
                {this.isShowAddGroup ? (
                  <div
                    class='select-add-new-group'
                    onClick={() => (this.isShowAddGroup = false)}
                  >
                    <div>
                      <i class='bk-icon icon-plus-circle'></i>
                      {this.$t('新增')}
                    </div>
                  </div>
                ) : (
                  <li
                    class='add-new-page-input'
                    style={{ padding: '6px 0' }}
                  >
                    <bk-form
                      labelWidth={0}
                      style={{ width: '100%' }}
                      ref='checkInputForm'
                      {...{
                        props: {
                          model: this.verifyData,
                          rules: this.groupNameRules
                        }
                      }}
                    >
                      <bk-form-item property='groupName'>
                        <bk-input
                          clearable
                          placeholder={this.$t('输入组名,30个字符')}
                          vModel={this.verifyData.groupName}
                          onEnter={this.handleCreateGroup}
                          maxlength={10}
                        ></bk-input>
                      </bk-form-item>
                    </bk-form>
                    <div class='operate-button'>
                      <span
                        class='bk-icon icon-check-line'
                        onClick={this.handleCreateGroup}
                      ></span>
                      <span
                        class='bk-icon icon-close-line-2'
                        onClick={this.handleCancelCreateGroup}
                      ></span>
                    </div>
                  </li>
                )}
              </div>
            </bk-select>
          </bk-form-item>
        </bk-form>
      </bk-dialog>
    );
  }
}
