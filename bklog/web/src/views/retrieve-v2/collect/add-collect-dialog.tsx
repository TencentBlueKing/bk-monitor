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

import { Component, Emit, Prop, Ref, Model } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import { ConditionOperator } from '@/store/condition-operator';
import { Dialog, Form, FormItem, Input, Select, Option } from 'bk-magic-vue';

import $http from '../../../api';
import { deepClone } from '../../../common/util';

import './add-collect-dialog.scss';

interface IProps {
  value: boolean;
  favoriteID: number;
  replaceData?: object;
  activeFavoriteID: number;
  visibleFields: Array<any>;
  favoriteList: Array<any>;
}

@Component
export default class CollectDialog extends tsc<IProps> {
  @Model('change', { type: Boolean, default: false }) value: IProps['value'];
  @Prop({ type: Number, default: -1 }) favoriteID: number; // 编辑收藏ID
  @Prop({ type: Object, default: () => ({}) }) replaceData: object; // 替换收藏的params数据
  @Prop({ type: Number, default: -1 }) activeFavoriteID: number; // 当前编辑的收藏是否是点击活跃的
  @Prop({ type: Array, default: () => [] }) visibleFields: Array<any>; // 字段
  @Prop({ type: Array, default: () => [] }) favoriteList: Array<any>; // 收藏列表
  @Ref('validateForm') validateFormRef: Form;
  @Ref('checkInputForm') checkInputFormRef: Form;
  searchFieldsList = []; // 表单模式显示字段
  isDisableSelect = false; // 是否禁用 所属组下拉框
  isShowAddGroup = true;
  currentFavoriteName = '';
  currentFavoriteGroupID = -1;
  currentFavoriteID = -1;
  isClickFavoriteEdit = false; // 当前编辑的收藏是否是点击活跃的
  verifyData = {
    groupName: '',
  };
  baseFavoriteData = null;
  favoriteData = {
    // 收藏参数
    space_uid: -1,
    index_set_id: -1,
    name: '',
    group_id: null,
    created_by: '',
    host_scopes: {
      modules: [],
      ips: '',
      target_nodes: [],
      target_node_type: '',
    },
    addition: [],
    keyword: null,
    search_fields: [],
    ip_chooser: {},
    search_mode: 'ui',
    is_enable_display_fields: false,
    index_set_ids: [],
    index_set_name: '',
    index_set_names: [],
    visible_type: 'public',
    display_fields: [],
  };
  positionTop = 0;
  publicGroupList = []; // 可见状态为公共的时候显示的收藏组
  privateGroupList = []; // 个人收藏 group_name替换为本人
  unknownGroupID = 0;
  privateGroupID = 0;
  groupList = []; // 组列表
  formLoading = false;
  groupNameMap = {
    unknown: window.mainComponent.$t('未分组'),
    private: window.mainComponent.$t('个人收藏'),
  };
  public rules = {
    name: [
      {
        required: true,
        trigger: 'blur',
      },
      {
        validator: this.checkSpecification,
        message: window.mainComponent.$t('{n}不规范, 包含特殊符号', { n: window.mainComponent.$t('收藏名') }),
        trigger: 'blur',
      },
      {
        validator: this.checkRepeatName,
        message: window.mainComponent.$t('收藏名重复'),
        trigger: 'blur',
      },
      {
        validator: this.checkCannotUseName,
        message: window.mainComponent.$t('保留名称，不可使用'),
        trigger: 'blur',
      },
      {
        max: 30,
        message: window.mainComponent.$t('不能多于{n}个字符', { n: 30 }),
        trigger: 'blur',
      },
    ],
  };

  public groupNameRules = {
    groupName: [
      {
        validator: this.checkName,
        message: window.mainComponent.$t('{n}不规范, 包含特殊符号', { n: window.mainComponent.$t('组名') }),
        trigger: 'blur',
      },
      {
        validator: this.checkExistName,
        message: window.mainComponent.$t('组名重复'),
        trigger: 'blur',
      },
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
    ],
  };

  get spaceUid() {
    return this.$store.state.spaceUid;
  }

  get showGroupList() {
    return this.favoriteData.visible_type === 'public' ? this.publicGroupList : this.privateGroupList;
  }

  get favStrList() {
    const favoriteItem = this.favoriteList.find(item => item.group_id === this.favoriteData.group_id);
    return favoriteItem?.favorites.map(group => group.name) || [];
  }

  get unionIndexList() {
    return this.$store.state.unionIndexList;
  }

  get isUnionSearch() {
    return this.$store.getters.isUnionSearch;
  }

  get indexItem() {
    return this.$store.state.indexItem;
  }

  get indexSetItemList() {
    return this.$store.state.indexItem.items;
  }

  get currentParamsValue() {
    return this.isClickFavoriteEdit ? Object.assign({}, this.favoriteData, this.indexItem) : this.favoriteData;
  }

  get formDataIndexName() {
    const indexSetList = this.$store.state.retrieve.indexSetList;
    const { index_set_ids, index_set_name } = this.favoriteData;
    const indexSetIds = index_set_ids.map(item => String(item));
    const unionName = indexSetList
      .filter(item => indexSetIds.includes(item.index_set_id))
      .map(item => item?.index_set_name)
      .join(',');
    return index_set_ids.length ? unionName : index_set_name;
  }

  get indexSetName() {
    const currentIndexName = this.indexSetItemList?.map(item => item?.index_set_name).join(',');
    return this.isClickFavoriteEdit ? currentIndexName : this.formDataIndexName;
  }

  get showAddition() {
    const { addition = [], ip_chooser } = this.currentParamsValue;
    return this.getAdditionValue(addition, ip_chooser);
  }

  get formatAddition() {
    return this.showAddition
      .filter(item => {
        if (!Object.keys(item).includes('disabled')) return true;
        return !item.disabled;
      })
      .map(item => {
        const instance = new ConditionOperator(item);
        return instance.getRequestParam();
      });
  }

  get additionString() {
    return `* AND (${this.formatAddition
      .map(({ field, operator, value }) => {
        if (field === '_ip-select_') {
          const target = value?.[0] ?? {};
          return Object.keys(target)
            .reduce((output, key) => {
              return [...output, `${key}:[${(target[key] ?? []).map(c => c.ip ?? c.objectId ?? c.id).join(' ')}]`];
            }, [])
            .join(' AND ');
        }
        return `${field} ${operator} [${value?.toString() ?? ''}]`;
      })
      .join(' AND ')})`;
  }

  get sqlString() {
    if (this.currentParamsValue.search_mode === 'sql') {
      return this.currentParamsValue.keyword;
    }
    return this.additionString;
  }

  mounted() {
    this.positionTop = Math.floor(document.body.clientHeight * 0.1);
  }

  @Emit('change')
  handleShowChange(value = false) {
    return value;
  }

  @Emit('change-favorite')
  handleChangeFavorite(value) {
    return value;
  }

  checkName() {
    if (this.verifyData.groupName.trim() === '') return true;
    return /^[\u4e00-\u9fa5_a-zA-Z0-9`~!@#$%^&*()_\-+=<>?:"{}|\s,.\/;'\\[\]·~！@#￥%……&*（）——\-+={}|《》？：“”【】、；‘'，。、]+$/im.test(
      this.verifyData.groupName.trim(),
    );
  }

  checkExistName() {
    return !this.groupList.some(item => item.name === this.verifyData.groupName);
  }

  /** 判断是否收藏名是否重复 */
  checkRepeatName() {
    if (
      this.currentFavoriteName === this.favoriteData.name &&
      this.currentFavoriteGroupID === this.favoriteData.group_id
    )
      return true;
    return !this.favStrList.includes(this.favoriteData.name);
  }
  /** 检查收藏语法是否正确 */
  checkSpecification() {
    return /^[\u4e00-\u9fa5_a-zA-Z0-9`~!@#$%^&*()_\-+=<>?:"{}|\s,.\/;'\\[\]·~！@#￥%……&*（）——\-+={}|《》？：“”【】、；‘'，。、]+$/im.test(
      this.favoriteData.name.trim(),
    );
  }
  /** 检查是否有内置名称不能使用 */
  checkCannotUseName() {
    return ![this.$t('个人收藏'), this.$t('未分组')].includes(this.favoriteData.name.trim());
  }

  handleSelectGroup(nVal: number) {
    const visible_type = nVal === this.privateGroupID ? 'private' : 'public';
    this.isDisableSelect = nVal === this.privateGroupID;
    Object.assign(this.favoriteData, { visible_type });
  }

  async handleValueChange(value) {
    if (value) {
      this.isClickFavoriteEdit = this.favoriteID === this.activeFavoriteID;
      this.baseFavoriteData = deepClone(this.favoriteData);
      this.formLoading = true;
      await this.requestGroupList(); // 获取组列表
      await this.getFavoriteData(this.favoriteID); // 获取收藏详情
      this.isDisableSelect = this.favoriteData.visible_type === 'private';
      this.formLoading = false;
    } else {
      this.favoriteData = this.baseFavoriteData;
      this.searchFieldsList = [];
      this.handleShowChange();
    }
  }

  /** 新增组 */
  handleCreateGroup() {
    this.checkInputFormRef.validate().then(async () => {
      const data = { name: this.verifyData.groupName, space_uid: this.spaceUid };
      try {
        const res = await $http.request('favorite/createGroup', {
          data,
        });
        if (res.result) {
          this.$bkMessage({
            message: this.$t('操作成功'),
            theme: 'success',
          });
          this.requestGroupList(true, this.verifyData.groupName.trim());
        }
      } catch (error) {
      } finally {
        this.isShowAddGroup = true;
        this.verifyData.groupName = '';
      }
    });
  }

  handleSubmitFormData() {
    this.validateFormRef.validate().then(() => {
      if (!this.unknownGroupID) return;
      if (!this.favoriteData.group_id) this.favoriteData.group_id = this.unknownGroupID;
      this.handleUpdateFavorite();
    });
  }

  /** 更新收藏 */
  async handleUpdateFavorite() {
    const {
      ip_chooser,
      addition,
      keyword,
      search_fields,
      name,
      group_id,
      display_fields,
      visible_type,
      search_mode,
      is_enable_display_fields,
    } = this.currentParamsValue;
    const searchParams =
      search_mode === 'sql'
        ? { keyword, addition: [] }
        : { addition: addition.filter(v => v.field !== '_ip-select_'), keyword: '*' };

    const data = {
      name,
      group_id,
      display_fields,
      visible_type,
      ip_chooser,
      search_fields,
      is_enable_display_fields,
      search_mode,
      ...searchParams,
    };
    if (this.isUnionSearch) {
      Object.assign(data, {
        index_set_ids: this.unionIndexList,
        index_set_type: 'union',
      });
    }
    try {
      const res = await $http.request('favorite/updateFavorite', {
        params: { id: this.currentFavoriteID },
        data,
      });
      if (res.result) {
        this.messageSuccess(this.$t('保存成功'));
        this.handleShowChange();
        this.handleChangeFavorite(res.data);
      }
    } catch (error) {}
  }

  /** 获取组列表 */
  async requestGroupList(isAddGroup = false, groupName?) {
    try {
      const res = await $http.request('favorite/getGroupList', {
        query: {
          space_uid: this.spaceUid,
        },
      });
      this.groupList = res.data.map(item => ({
        ...item,
        name: this.groupNameMap[item.group_type] ?? item.name,
      }));
      this.publicGroupList = this.groupList.slice(1, this.groupList.length);
      this.privateGroupList = [this.groupList[0]];
      this.unknownGroupID = this.groupList[this.groupList.length - 1]?.id;
      this.privateGroupID = this.groupList[0]?.id;
    } catch (error) {
    } finally {
      if (isAddGroup) {
        this.favoriteData.group_id = this.groupList.find(item => item.name === groupName)?.id;
      }
    }
  }
  /** 获取收藏详情 */
  async getFavoriteData(id) {
    try {
      const res = await $http.request('favorite/getFavorite', { params: { id } });
      Object.assign(this.favoriteData, {
        ...res.data,
        ...res.data.params,
      });
      this.currentFavoriteName = this.favoriteData.name;
      this.currentFavoriteGroupID = this.favoriteData.group_id;
      this.currentFavoriteID = this.favoriteData.id;
    } catch {}
  }

  getAdditionValue(addition, ipChooser) {
    const newAddition = addition.filter(item => item.field !== '_ip-select_');
    if (JSON.stringify(ipChooser) !== '{}') {
      newAddition.push({
        field: '_ip-select_',
        operator: '',
        value: [ipChooser],
      });
    }
    return newAddition;
  }

  render() {
    return (
      <Dialog
        width={640}
        ext-cls='add-collect-dialog'
        auto-close={false}
        header-position='left'
        ok-text={this.$t('保存')}
        position={{ top: this.positionTop }}
        render-directive='if'
        title={this.$t('编辑收藏')}
        value={this.value}
        on-confirm={this.handleSubmitFormData}
        on-value-change={this.handleValueChange}
      >
        <Form
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
          <div class='form-item-container-new'>
            <FormItem
              label={this.$t('收藏名称')}
              property='name'
              required
            >
              <Input
                class='collect-name'
                vModel={this.favoriteData.name}
                placeholder={this.$t('{n}, （长度30个字符）', { n: this.$t('填写收藏名') })}
              ></Input>
            </FormItem>
          </div>
          <div class='form-item-container-new'>
            <FormItem label={this.$t('所属分组')}>
              <span
                v-bk-tooltips={{ content: this.$t('私有的只支持默认的“个人收藏”'), disabled: !this.isDisableSelect }}
              >
                <Select
                  vModel={this.favoriteData.group_id}
                  disabled={this.isDisableSelect}
                  ext-popover-cls='add-new-page-container'
                  searchable
                  on-change={this.handleSelectGroup}
                >
                  {this.showGroupList.map(item => (
                    <Option
                      id={item.id}
                      key={item.id}
                      name={item.name}
                    ></Option>
                  ))}
                  <div slot='extension'>
                    {this.isShowAddGroup ? (
                      <div
                        class='select-add-new-group'
                        onClick={() => (this.isShowAddGroup = false)}
                      >
                        <div>
                          <i class='bk-icon icon-plus-circle'></i> {this.$t('新增')}
                        </div>
                      </div>
                    ) : (
                      <li
                        style={{ padding: '6px 0' }}
                        class='add-new-page-input'
                      >
                        <Form
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
                          <FormItem property='groupName'>
                            <Input
                              vModel={this.verifyData.groupName}
                              placeholder={this.$t('{n}, （长度30个字符）', { n: this.$t('请输入组名') })}
                              clearable
                            ></Input>
                          </FormItem>
                        </Form>
                        <div class='operate-button'>
                          <span
                            class='bk-icon icon-check-line'
                            onClick={() => this.handleCreateGroup()}
                          ></span>
                          <span
                            class='bk-icon icon-close-line-2'
                            onClick={() => {
                              this.isShowAddGroup = true;
                              this.verifyData.groupName = '';
                            }}
                          ></span>
                        </div>
                      </li>
                    )}
                  </div>
                </Select>
              </span>
            </FormItem>
          </div>
          <div class='form-item-container-new'>
            <FormItem label={this.$t('索引集')}>
              <bk-input
                value={this.indexSetName}
                readonly
                show-overflow-tooltips
              ></bk-input>
            </FormItem>
          </div>
          <div class='form-item-container-new'>
            <FormItem label={this.$t('查询语句')}>
              {this.currentParamsValue.search_mode === 'sql' ? (
                <bk-input
                  vModel={this.currentParamsValue.keyword}
                  type='textarea'
                  show-overflow-tooltips
                ></bk-input>
              ) : (
                <bk-input
                  type='textarea'
                  value={this.additionString}
                  readonly
                  show-overflow-tooltips
                ></bk-input>
              )}
            </FormItem>
          </div>
        </Form>
      </Dialog>
    );
  }
}
