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

import { Component, Emit, Model, Prop, Ref } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import { createFavoriteGroup, listFavoriteGroup } from 'monitor-api/modules/model';
import VueJsonPretty from 'vue-json-pretty';

import { mergeWhereList } from '../../../components/retrieval-filter/utils';

import './add-collect-dialog.scss';
import 'vue-json-pretty/lib/styles.css';

interface IEvent {
  onCancel: () => void;
  onSubmit: {
    hideCallback: () => void;
    isEdit: boolean;
    value: any;
  };
}

interface IProps {
  editFavoriteData?: object;
  favoriteSearchType: string;
  favStrList: string[];
  keyword: object;
  value?: boolean;
}

interface ISubmitData {
  create_user: string;
  group_id: number | string;
  name: string;
}

@Component
export default class CollectDialog extends tsc<IProps, IEvent> {
  @Model('change', { type: Boolean, default: false }) value: IProps['value'];
  @Prop({ type: Object, default: () => ({}) }) keyword: any; // 当前弹窗展示的查询语句参数
  @Prop({ type: String, required: true }) favoriteSearchType: string; // 收藏类型
  @Prop({ type: Object, default: () => ({}) }) editFavoriteData: any; // 编辑收藏的数据
  @Prop({ type: Array, default: () => [] }) favStrList: string[]; // 收藏类型
  @Ref('validateForm') validateFormRef: any;
  @Ref('checkInputForm') checkInputFormRef: any;
  searchFieldsList = []; // 表单模式显示字段
  isShowAddGroup = true; // 是否展示新增组
  // groupName = ''; // 组名
  baseFavoriteData: ISubmitData = {
    // 用户可编辑的基础数据
    name: '',
    group_id: '0',
    create_user: '',
  };
  favoriteData: ISubmitData = {
    // 收藏数据
    name: '',
    group_id: '0',
    create_user: '',
  };
  verifyData = {
    groupName: '',
  };
  positionTop = 0;
  allGroupList = [];
  formLoading = false;
  isShowJsonKeywords = false; // 是否展示json格式的查询语句
  public rules = {
    name: [
      {
        required: true,
        trigger: 'blur',
      },
      {
        validator: this.checkSpecification,
        message: window.i18n.t('收藏名包含了特殊符号'),
        trigger: 'blur',
      },
      {
        validator: this.checkRepeatName,
        message: window.i18n.t('注意: 名字冲突'),
        trigger: 'blur',
      },
      {
        validator: this.checkCannotUseName,
        message: window.i18n.t('保留名称，不可使用'),
        trigger: 'blur',
      },
      {
        max: 30,
        message: window.i18n.t('注意：最大值为30个字符'),
        trigger: 'blur',
      },
    ],
  };

  public groupNameRules = {
    groupName: [
      {
        validator: this.checkName,
        message: window.i18n.t('组名不规范, 包含了特殊符号.'),
        trigger: 'blur',
      },
      {
        validator: this.checkExistName,
        message: window.i18n.t('注意: 名字冲突'),
        trigger: 'blur',
      },
      {
        required: true,
        message: window.i18n.t('必填项'),
        trigger: 'blur',
      },
      {
        max: 30,
        message: window.i18n.t('注意：最大值为30个字符'),
        trigger: 'blur',
      },
    ],
  };

  get isEditFavorite() {
    // 根据传参判断新增还是编辑
    if (this.editFavoriteData === null) return false;
    return Boolean(Object.keys(this.editFavoriteData).length);
  }

  get isCannotChangeVisible() {
    // 编辑时候判断是否是本人创建 如果非本人则禁用
    if (!this.isEditFavorite) return false;
    return this.favoriteData.create_user !== (window.user_name || window.username);
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
        value: item.code,
      }));
  }

  get dataIdFormItem() {
    if (this.favoriteSearchType === 'event')
      return {
        label: this.$t('数据ID'),
        value: this.keyword?.queryConfig?.result_table_id,
      };

    return null;
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
      hideCallback: () => this.handleShowChange(false),
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
        name: this.verifyData.groupName,
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
              {this.promqlShowData.map(item => (
                <div
                  key={`${item.label}_${item.value}`}
                  class='promql-box'
                >
                  <div class='promql-label'>{item.label}</div>
                  <div class='promql-val'>{item.value}</div>
                </div>
              ))}
            </div>
          ) : (
            <span class='string-json view-content'>
              <VueJsonPretty
                data={this.keyword}
                deep={5}
              />
            </span>
          )}
        </div>
      </div>
    );

    const eventKeywordsSlot = () => {
      if (this.keyword?.queryConfig?.query_string) return <span>{this.keyword.queryConfig.query_string}</span>;
      if (this.keyword?.queryConfig?.where?.length) {
        return (
          <div class='view-box is-expand'>
            <span class='string-json view-content'>
              <VueJsonPretty
                data={{
                  data_source_label: this.keyword.queryConfig?.data_source_label || '',
                  data_type_label: this.keyword.queryConfig?.data_type_label || '',
                  table: this.keyword.queryConfig?.result_table_id || '',
                  where: mergeWhereList(this.keyword.queryConfig.where, this.keyword.queryConfig?.commonWhere || []),
                }}
                deep={5}
              />
            </span>
          </div>
        );
      }
      return '*';
    };
    return (
      <bk-dialog
        width={480}
        ext-cls='add-collect-dialog'
        auto-close={false}
        header-position='left'
        mask-close={false}
        ok-text={this.isEditFavorite ? this.$t('保存') : this.$t('确定')}
        position={{ top: this.positionTop }}
        render-directive='if'
        title={this.isEditFavorite ? this.$t('编辑收藏') : this.$t('新增收藏')}
        value={this.value}
        on-confirm={this.handleSubmitFormData}
        on-value-change={this.handleValueChange}
      >
        <bk-form
          ref='validateForm'
          v-bkloading={{ isLoading: this.formLoading }}
          form-type='vertical'
          {...{
            props: {
              model: this.favoriteData,
              rules: this.rules,
            },
          }}
        >
          <bk-form-item
            class='group-name'
            label={this.$t('收藏名')}
            property='name'
            required
          >
            <bk-input
              class='collect-name'
              vModel={this.favoriteData.name}
              placeholder={this.$t('填写收藏名（长度30个字符）')}
            />
          </bk-form-item>

          <bk-form-item
            class='affiliation-group'
            label={this.$t('所属分组')}
            required
          >
            <bk-select
              vModel={this.favoriteData.group_id}
              clearable={false}
              ext-popover-cls='add-new-page-container'
              searchable
            >
              {this.allGroupList.map(item => (
                <bk-option
                  id={item.id}
                  key={item.id}
                  disabled={item.id === '0' && this.isCannotChangeVisible}
                  name={item.id === '0' ? `${item.name}${this.$t('（仅个人可见）')}` : item.name}
                >
                  <span>{item.name}</span>
                  <span style='color: #979BA5'>{item.id === '0' && this.$t('（仅个人可见）')}</span>
                </bk-option>
              ))}
              <div slot='extension'>
                {this.isShowAddGroup ? (
                  <div
                    class='select-add-new-group'
                    onClick={() => (this.isShowAddGroup = false)}
                  >
                    <div>
                      <i class='bk-icon icon-plus-circle' />
                      {this.$t('新增')}
                    </div>
                  </div>
                ) : (
                  <li
                    style={{ padding: '6px 0' }}
                    class='add-new-page-input'
                  >
                    <bk-form
                      ref='checkInputForm'
                      style={{ width: '100%' }}
                      labelWidth={0}
                      {...{
                        props: {
                          model: this.verifyData,
                          rules: this.groupNameRules,
                        },
                      }}
                    >
                      <bk-form-item property='groupName'>
                        <bk-input
                          vModel={this.verifyData.groupName}
                          maxlength={10}
                          placeholder={this.$t('输入组名,30个字符')}
                          clearable
                          onEnter={this.handleCreateGroup}
                        />
                      </bk-form-item>
                    </bk-form>
                    <div class='operate-button'>
                      <span
                        class='bk-icon icon-check-line'
                        onClick={this.handleCreateGroup}
                      />
                      <span
                        class='bk-icon icon-close-line-2'
                        onClick={this.handleCancelCreateGroup}
                      />
                    </div>
                  </li>
                )}
              </div>
            </bk-select>
          </bk-form-item>

          {this.dataIdFormItem && (
            <bk-form-item label={this.dataIdFormItem.label}>
              <div class='edit-information'>{this.dataIdFormItem.value}</div>
            </bk-form-item>
          )}

          <bk-form-item label={this.$t('查询语句')}>
            <div class='edit-information'>
              {this.favoriteSearchType === 'metric' ? metricKeywordsSlot() : eventKeywordsSlot()}
            </div>
          </bk-form-item>
        </bk-form>
      </bk-dialog>
    );
  }
}
