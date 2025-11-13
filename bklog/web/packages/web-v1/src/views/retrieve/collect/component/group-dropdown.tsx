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

import { Component, Prop, Inject, Ref, Watch } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import { Input, type Popover, Form, FormItem } from 'bk-magic-vue';

import type { IGroupItem, IFavoriteItem } from '../collect-index';

import './group-dropdown.scss';

interface IProps {
  dropType: string;
  groupList: IGroupItem[];
  groupName: string;
  isHoverTitle: boolean;
  data: IFavoriteItem | IGroupItem;
}

@Component
export default class CollectGroup extends tsc<IProps> {
  @Inject('handleUserOperate') handleUserOperate;

  @Prop({ type: String, default: 'group' }) dropType: string; // 分组类型
  @Prop({ type: String, default: '' }) groupName: string; // 组名
  @Prop({ type: Boolean, default: false }) isHoverTitle: boolean; // 鼠标是否经过表头
  @Prop({ type: Array, default: () => [] }) groupList: IGroupItem[]; // 组列表
  @Prop({ type: Object, required: true }) data: IFavoriteItem | IGroupItem; // 所有数据

  isShowNewGroupInput = false; // 是否展示新建分组
  isShowResetGroupName = false; // 是否展示重命名组名
  groupEditName = ''; // 创建分组名称
  newGroupName = '';
  operatePopoverInstance = null; // 收藏操作实例例
  groupListPopoverInstance = null; // 分组列表实例
  titlePopoverInstance = null; // 表头列表实例
  verifyData = {
    groupEditName: '',
  };

  public rules = {
    groupEditName: [
      {
        validator: this.checkName,
        message: window.mainComponent.$t('{n}不规范, 包含特殊符号.', { n: window.mainComponent.$t('组名') }),
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

  @Ref('operate') private readonly operatePopoverRef: Popover; // 操作列表实例
  @Ref('groupMoveList') private readonly groupMoveListPopoverRef: Popover; // 移动到分组实例
  @Ref('titleDrop') private readonly titlePopoverRef: Popover; // 操作列表实例
  @Ref('checkInputForm') private readonly checkInputFormRef: Form; // 移动到分组实例
  @Ref('checkInputAddForm') private readonly checkInputAddFormRef: Form; // 移动到分组实例

  get unPrivateGroupList() {
    // 去掉个人收藏的组列表
    return this.groupList.slice(1);
  }

  get userMeta() {
    // 用户信息
    return this.$store.state.userMeta;
  }

  get isUnknownGroup() {
    return this.data.group_id === this.groupList.at(-1)?.group_id;
  }

  get showGroupList() {
    // 根据用户名判断是否时自己创建的收藏 若不是自己的则去除个人收藏选项
    return this.userMeta.username !== this.data.created_by ? this.unPrivateGroupList : this.groupList;
  }

  @Watch('showGroupList')
  async handleJumpNewGroup(val) {
    const newIndex = val.findIndex(item => item.group_name === this.newGroupName);
    await this.$nextTick();
    if (newIndex > 0) {
      const subLength = val.length - newIndex;
      const scrollTopNum = newIndex * 28 - (subLength < 3 ? 0 : 28 * 3);
      this.groupMoveListPopoverRef.scrollTop = scrollTopNum >= 0 ? scrollTopNum : 0;
    }
  }

  get isGroupDrop() {
    // 是否是组操作
    return this.dropType === 'group';
  }

  checkName() {
    if (this.verifyData.groupEditName.trim() === '') {
      return true;
    }

    return /^[\u4e00-\u9fa5_a-zA-Z0-9`~!@#$%^&*()_\-+=<>?:"{}|,./;'\\[\]·~！@#￥%……&*（）——\-+={}|《》？：“”【】、；‘'，。、]+$/im.test(
      this.verifyData.groupEditName.trim(),
    );
  }

  checkExistName() {
    return !this.groupList.some(item => item.group_name === this.verifyData.groupEditName);
  }

  /** 重命名 */
  handleResetGroupName() {
    this.checkInputFormRef.validate().then(() => {
      this.handleUserOperate('reset-group-name', {
        group_id: this.data.group_id,
        group_new_name: this.verifyData.groupEditName,
      });
      this.verifyData.groupEditName = '';
      this.isShowResetGroupName = false;
    });
  }
  /** 新增组 */
  handleChangeGroupInputStatus(type: string) {
    this.checkInputAddFormRef.validate().then(() => {
      this.newGroupName = this.verifyData.groupEditName;
      type === 'add' && this.handleUserOperate('add-group', this.verifyData.groupEditName);
      this.clearStatus();
    });
    type === 'cancel' && (this.isShowNewGroupInput = false);
  }
  handleClickLi(type: string, value?: any) {
    if (type === 'move-favorite') {
      // 如果是移动到其他组 则更新移动的ID
      Object.assign(this.data, { group_id: value });
    }
    this.handleUserOperate(type, this.data);
    // 进行完操作时 清除组或者操作列表实例
    this.operatePopoverInstance?.destroy?.();
    this.operatePopoverInstance = null;
    this.groupListPopoverInstance?.destroy?.();
    this.groupListPopoverInstance = null;
    this.clearStatus(); // 清空状态
  }
  /** 点击移动分组操作 */
  handleClickMoveGroup(e) {
    this.operatePopoverInstance?.set({ hideOnClick: false });
    // 判断当前是否有实例 如果有实例 则给操作列表常驻显示
    if (!this.groupListPopoverInstance) {
      this.groupListPopoverInstance = this.$bkPopover(e.target, {
        content: this.groupMoveListPopoverRef,
        interactive: true,
        theme: 'light shield',
        arrow: false,
        boundary: 'viewport',
        hideOnClick: true,
        offset: -1,
        distance: 2,
        sticky: true,
        placement: 'right-start',
        extCls: 'more-container',
        zIndex: 999,
        onHidden: () => {
          // 删除实例
          this.groupListPopoverInstance?.destroy();
          this.groupListPopoverInstance = null;
          this.clearStatus();
          this.operatePopoverInstance?.set({ hideOnClick: true });
          this.newGroupName = '';
        },
        onShow: () => {
          this.operatePopoverInstance?.set({ hideOnClick: false });
        },
      });
      this.groupListPopoverInstance.show(100);
    }
  }
  /** 点击收藏的icon  显示更多操作 */
  handleClickIcon(e) {
    if (!this.operatePopoverInstance) {
      this.operatePopoverInstance = this.$bkPopover(e.target, {
        content: this.operatePopoverRef,
        interactive: true,
        theme: 'light shield',
        arrow: false,
        boundary: 'viewport',
        hideOnClick: true, // 先是可被外部点击隐藏
        distance: 4,
        sticky: true,
        trigger: 'click',
        placement: 'bottom-start',
        extCls: 'more-container',
        zIndex: 999,
        onHidden: () => {
          this.operatePopoverInstance?.destroy?.();
          this.operatePopoverInstance = null;
          this.groupListPopoverInstance?.destroy?.();
          this.groupListPopoverInstance = null;
          this.clearStatus(); // 清空状态
        },
      });
      this.operatePopoverInstance.show(100);
    }
  }
  handleHoverIcon(e) {
    if (!this.titlePopoverInstance) {
      this.titlePopoverInstance = this.$bkPopover(e.target, {
        content: this.titlePopoverRef,
        interactive: true,
        theme: 'light',
        arrow: false,
        placement: 'bottom-start',
        boundary: 'viewport',
        extCls: 'more-container',
        distance: 4,
        zIndex: 999,
        onHidden: () => {
          this.titlePopoverInstance?.destroy();
          this.titlePopoverInstance = null;
          this.clearStatus();
        },
      });
      this.titlePopoverInstance.show(100);
    }
  }

  handleResetGroupTitleName() {
    this.verifyData.groupEditName = this.groupName;
    this.isShowResetGroupName = true;
  }

  clearStatus() {
    this.isShowNewGroupInput = false;
    this.isShowResetGroupName = false;
    this.verifyData.groupEditName = '';
  }

  handleGroupKeyDown(value: string, type = 'add') {
    if (value) {
      if (type === 'add') {
        this.handleChangeGroupInputStatus('add');
      }
      if (type === 'reset') {
        this.handleResetGroupName();
      }
    }
  }

  render() {
    const groupDropList = () => (
      <div style={{ display: 'none' }}>
        <ul
          ref='titleDrop'
          class='dropdown-list add-new-page-container'
        >
          {this.isShowResetGroupName ? (
            <li class='add-new-page-input'>
              <Form
                ref='checkInputForm'
                labelWidth={0}
                {...{
                  props: {
                    model: this.verifyData,
                    rules: this.rules,
                  },
                }}
              >
                <FormItem property='groupEditName'>
                  <Input
                    vModel={this.verifyData.groupEditName}
                    placeholder={this.$t('{n}, （长度30个字符）', { n: this.$t('请输入组名') })}
                    clearable
                    onEnter={v => this.handleGroupKeyDown(v, 'reset')}
                  />
                </FormItem>
              </Form>
              <div class='operate-button'>
                <span
                  class='bk-icon icon-check-line'
                  onClick={this.handleResetGroupName}
                />
                <span
                  class='bk-icon icon-close-line-2'
                  onClick={() => {
                    this.isShowResetGroupName = false;
                    this.verifyData.groupEditName = '';
                  }}
                />
              </div>
            </li>
          ) : (
            <li onClick={() => this.handleResetGroupTitleName()}>{this.$t('重命名')}</li>
          )}
          <li
            class='eye-catching'
            onClick={() => this.handleClickLi('dismiss-group')}
          >
            {this.$t('解散分组')}
          </li>
        </ul>
      </div>
    );
    const collectDropList = () => (
      <div style={{ display: 'none' }}>
        <ul
          ref='operate'
          class='dropdown-list'
        >
          <li onClick={() => this.handleClickLi('share')}>{this.$t('分享')}</li>
          <li onClick={() => this.handleClickLi('edit-favorite')}>{this.$t('编辑')}</li>
          <li onClick={() => this.handleClickLi('create-copy')}>{this.$t('克隆')}</li>
          <li
            class='move-group'
            onMouseenter={this.handleClickMoveGroup}
          >
            {this.$t('移动至分组')}
            <span class='bk-icon icon-angle-right more-icon' />
          </li>
          {this.isUnknownGroup ? undefined : (
            <li onClick={() => this.handleClickLi('remove-group')}>{this.$t('从该组移除')}</li>
          )}
          <li onClick={() => this.handleClickLi('new-link')}>{this.$t('新开标签页')}</li>
          <li
            class='eye-catching'
            onClick={() => this.handleClickLi('delete-favorite')}
          >
            {this.$t('删除')}
          </li>
        </ul>
      </div>
    );
    const groupList = () => (
      <div style={{ display: 'none' }}>
        <ul
          ref='groupMoveList'
          class='group-dropdown-list add-new-page-container'
        >
          {this.showGroupList.map(item => (
            <li
              key={item.group_id}
              class={{ 'new-group-container': this.newGroupName === item.group_name }}
              onClick={() => this.handleClickLi('move-favorite', item.group_id)}
            >
              <span>{item.group_name}</span>
              {this.newGroupName === item.group_name && <span class='new-group'>New</span>}
            </li>
          ))}
          <li class='add-new-group'>
            {this.isShowNewGroupInput ? (
              <li class='new-page-input'>
                <Form
                  ref='checkInputAddForm'
                  style={{ width: '100%' }}
                  labelWidth={0}
                  {...{
                    props: {
                      model: this.verifyData,
                      rules: this.rules,
                    },
                  }}
                >
                  <FormItem property='groupEditName'>
                    <Input
                      vModel={this.verifyData.groupEditName}
                      placeholder={this.$t('{n}, （长度30个字符）', { n: this.$t('请输入组名') })}
                      clearable
                      onEnter={v => this.handleGroupKeyDown(v, 'add')}
                    />
                  </FormItem>
                </Form>
                <div class='operate-button'>
                  <span
                    class='bk-icon icon-check-line'
                    onClick={() => this.handleChangeGroupInputStatus('add')}
                  />
                  <span
                    class='bk-icon icon-close-line-2'
                    onClick={() => this.handleChangeGroupInputStatus('cancel')}
                  />
                </div>
              </li>
            ) : (
              <li
                class='add-new-group'
                onClick={() => (this.isShowNewGroupInput = true)}
              >
                <span>
                  <span class='bk-icon icon-close-circle' />
                  <span>{this.$t('新建分组')}</span>
                </span>
              </li>
            )}
          </li>
        </ul>
      </div>
    );
    return (
      <div>
        {this.isGroupDrop ? (
          <div>
            <div
              class='more-container'
              onMouseenter={this.handleHoverIcon}
            >
              <span
                class='title-number'
                v-show={!this.isHoverTitle && this.titlePopoverInstance === null}
              >
                {this.data.favorites.length}
              </span>
              <div
                class={['more-box', this.titlePopoverInstance !== null && 'is-click']}
                v-show={this.isHoverTitle || this.titlePopoverInstance !== null}
              >
                <span class='bk-icon icon-more' />
              </div>
            </div>
            {groupDropList()}
          </div>
        ) : (
          <div>
            <div class='more-container'>
              {this.$slots.default ?? (
                <div
                  class={['more-box', { 'is-click': !!this.operatePopoverInstance }]}
                  onClick={this.handleClickIcon}
                >
                  <span class='bk-icon icon-more' />
                </div>
              )}
            </div>
            {collectDropList()}
            {groupList()}
          </div>
        )}
      </div>
    );
  }
}
