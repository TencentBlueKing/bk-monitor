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

import { Input, Popover, Form, FormItem } from 'bk-magic-vue';

import { IGroupItem, IFavoriteItem } from '../collect-index';
import PopInstanceUtil from '../../../../global/pop-instance-util';

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
  groupEditName = ''; // 创建分组名称
  newGroupName = '';
  operatePopoverInstance = null; // 收藏操作实例例
  groupListPopoverInstance = null; // 分组列表实例
  titlePopoverInstance = null; // 表头列表实例
  verifyData = {
    groupEditName: '',
  };
  tippyOption = {
    trigger: 'click',
    interactive: true,
    theme: 'light',
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

  popToolInstance = null;
  moreIconPopInstance = null;

  @Ref('groupMoveList') private readonly groupMoveListPopoverRef: Popover; // 移动到分组实例
  @Ref('titleDrop') private readonly titlePopoverRef: Popover; // 操作列表实例
  @Ref('checkInputForm') private readonly checkInputFormRef: Form; // 移动到分组实例
  @Ref('checkInputAddForm') private readonly checkInputAddFormRef: Form; // 移动到分组实例

  get unPrivateGroupList() {
    // 去掉个人收藏的组列表
    return this.groupList.filter(g => g.group_type !== 'private');
  }

  get userMeta() {
    // 用户信息
    return this.$store.state.userMeta;
  }

  get isUnknownGroup() {
    return this.data.group_id === this.groupList[this.groupList.length - 1]?.group_id;
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
    if (this.verifyData.groupEditName.trim() === '') return true;

    return /^[\u4e00-\u9fa5_a-zA-Z0-9`~!@#$%^&*()_\-+=<>?:"{}|,.\/;'\\[\]·~！@#￥%……&*（）——\-+={}|《》？：“”【】、；‘'，。、]+$/im.test(
      this.verifyData.groupEditName.trim(),
    );
  }

  checkExistName() {
    return !this.groupList.some(item => item.group_name === this.verifyData.groupEditName);
  }

  /** 重命名 */
  handleResetGroupName() {
    this.popToolInstance?.hide(100);
    this.titlePopoverInstance?.hide(200);

    this.checkInputFormRef.validate().then(() => {
      this.handleUserOperate('reset-group-name', {
        group_id: this.data.group_id,
        group_new_name: this.verifyData.groupEditName,
      });
      this.verifyData.groupEditName = '';
    });
  }
  /** 新增组 */
  handleChangeGroupInputStatus(type: string) {
    debugger;
    if (type === 'cancel') {
      this.isShowNewGroupInput = false;
      this.groupListPopoverInstance?.hide();
      return;
    }

    this.checkInputAddFormRef.validate().then(() => {
      this.newGroupName = this.verifyData.groupEditName;
      type === 'add' && this.handleUserOperate('add-group', this.verifyData.groupEditName);
      this.clearStatus();
      this.groupListPopoverInstance?.hide();
    });
  }

  handleClickLi(type: string, value?: any) {
    if (type === 'move-favorite') {
      // 如果是移动到其他组 则更新移动的ID
      Object.assign(this.data, { group_id: value });
    }
    this.handleUserOperate(type, this.data);
    this.groupListPopoverInstance?.hide();

    // 进行完操作时 清除组或者操作列表实例
    this.operatePopoverInstance?.destroy();
    this.operatePopoverInstance = null;
    this.groupListPopoverInstance?.destroy();
    this.groupListPopoverInstance = null;
    this.clearStatus(); // 清空状态
  }
  /** 点击移动分组操作 */
  handleClickMoveGroup(e) {
    if (!this.groupListPopoverInstance) {
      this.groupListPopoverInstance = new PopInstanceUtil({
        refContent: this.groupMoveListPopoverRef,
        onHiddenFn: () => {
          // 删除实例
          this.groupListPopoverInstance?.destroy?.();
          this.groupListPopoverInstance = null;
          this.clearStatus();
          this.newGroupName = '';
          return true;
        },
        tippyOptions: {
          interactive: true,
          theme: 'light shield',
          arrow: false,
          placement: 'right-start',
          zIndex: 999,
          appendTo: document.body,
          offset: [0, 2],
        },
      });
    }

    this.groupListPopoverInstance.show(e.target);
  }

  /** 点击收藏的icon  显示更多操作 */
  handleClickIcon(e) {
    if (!this.operatePopoverInstance) {
      this.operatePopoverInstance = new PopInstanceUtil({
        refContent: this.$refs.refOperateRoot as HTMLElement,
        onHiddenFn: () => {
          this.operatePopoverInstance?.destroy?.();
          this.operatePopoverInstance = null;
          this.groupListPopoverInstance = null;
          this.clearStatus(); // 清空状态
          return true;
        },
        tippyOptions: {
          interactive: true,
          theme: 'light shield',
          arrow: false,
          placement: 'bottom-start',
          hideOnClick: false,
          zIndex: 999,
        },
      });
    }

    this.operatePopoverInstance?.show(e.target);
  }

  handleMouseleaveMoreIcon() {
    this.operatePopoverInstance?.hide?.(300);
  }

  handleMouseleaveMoveGroupItem() {
    this.groupListPopoverInstance?.hide(300);
  }

  /**
   * 鼠标滑入移动到分组弹出区域
   */
  handleMoreListMouseenter() {
    this.groupListPopoverInstance?.cancelHide();
    this.operatePopoverInstance?.cancelHide();
  }

  handleMouseleaveMoveGroup() {
    this.groupListPopoverInstance?.hide(100);
    this.handleMouseleaveMoreIcon();
  }

  handleHoverIcon(e) {
    if (!this.titlePopoverInstance) {
      this.titlePopoverInstance = new PopInstanceUtil({
        refContent: this.titlePopoverRef,
        onHiddenFn: () => {
          this.isGroupNameEditShown = false;
          requestAnimationFrame(() => {
            this.titlePopoverInstance = null;
          });
          return true;
        },
        tippyOptions: {
          interactive: true,
          theme: 'light',
          arrow: false,
          placement: 'bottom-start',
          zIndex: 999,
        },
      });
    }

    this.titlePopoverInstance?.cancelHide();
    this.titlePopoverInstance.show(e.target);
  }

  handleHiddenIcon() {
    this.titlePopoverInstance?.hide(300);
  }

  isGroupNameEditShown = false;
  handleResetGroupTitleName(e: MouseEvent) {
    this.verifyData.groupEditName = this.groupName;

    if (this.popToolInstance === null) {
      this.popToolInstance = new PopInstanceUtil({
        refContent: this.$refs.refGroupNameEdit as HTMLElement,
        onHiddenFn: () => {
          this.isGroupNameEditShown = false;
          this.titlePopoverInstance?.setProps({ hideOnClick: true });
          this.titlePopoverInstance?.hide(100);
          return true;
        },
        onShowFn: () => {
          this.titlePopoverInstance?.setProps({ hideOnClick: false });
          this.titlePopoverInstance?.cancelHide();
          return true;
        },
        tippyOptions: {
          placement: 'bottom-start',
          zIndex: 200,
          appendTo: document.body,
          interactive: true,
          theme: 'light',
          arrow: true,
        },
      });
    }

    this.popToolInstance.show(e.target);
    this.isGroupNameEditShown = true;
  }

  handleCancelGroupTitleName() {
    this.verifyData.groupEditName = '';
    this.popToolInstance?.hide(100);
  }

  handleHoverGroupEditContent() {
    this.titlePopoverInstance?.cancelHide();
  }

  handleLeaveGroupEditContent() {
    if (!this.popToolInstance?.isShown()) {
      this.titlePopoverInstance?.hide(300);
    }
  }

  clearStatus() {
    this.isShowNewGroupInput = false;
    this.verifyData.groupEditName = '';
  }

  handleGroupKeyDown(value: string, type = 'add') {
    if (!!value) {
      if (type === 'add') this.handleChangeGroupInputStatus('add');
      if (type === 'reset') this.handleResetGroupName();
    }
  }

  render() {
    const groupDropList = () => (
      <div style={{ display: 'none' }}>
        <ul
          ref='titleDrop'
          class='dropdown-list bklog-v3-favorite-group-root'
          onMouseenter={this.handleHoverGroupEditContent}
          onMouseleave={this.handleLeaveGroupEditContent}
        >
          <li onClick={this.handleResetGroupTitleName}>{this.$t('重命名')}</li>
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
          class='dropdown-list bklog-v3-favorite-group-root'
          ref='refOperateRoot'
          onMouseenter={this.handleMoreListMouseenter}
          onMouseleave={this.handleMouseleaveMoreIcon}
        >
          <li onClick={() => this.handleClickLi('share')}>{this.$t('分享')}</li>
          <li onClick={() => this.handleClickLi('edit-favorite')}>{this.$t('编辑')}</li>
          <li onClick={() => this.handleClickLi('create-copy')}>{this.$t('克隆')}</li>
          <li
            class='move-group'
            onMouseenter={this.handleClickMoveGroup}
            onMouseleave={this.handleMouseleaveMoveGroupItem}
          >
            {this.$t('移动至分组')}
            <span class='bk-icon icon-angle-right more-icon'></span>
          </li>
          {!this.isUnknownGroup ? (
            <li onClick={() => this.handleClickLi('remove-group')}>{this.$t('从该组移除')}</li>
          ) : undefined}
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
          class='group-dropdown-list bklog-v3-favorite-group-root group-move-to-list'
          onMouseenter={this.handleMoreListMouseenter}
          onMouseleave={this.handleMouseleaveMoveGroup}
        >
          {this.showGroupList.map(item => (
            <li
              class={{ 'new-group-container': this.newGroupName === item.group_name }}
              onClick={() => this.handleClickLi('move-favorite', item.group_id)}
            >
              <span>{item.group_name}</span>
              {this.newGroupName === item.group_name && <span class='new-group'>New</span>}
            </li>
          ))}
          <li class='add-new-group'>
            {this.isShowNewGroupInput ? (
              [
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
                      placeholder={this.$t('请输入')}
                      clearable
                      onEnter={v => this.handleGroupKeyDown(v, 'add')}
                    ></Input>
                  </FormItem>
                </Form>,
                <div class='operate-button'>
                  <span
                    class='bk-icon icon-check-line'
                    style='color: #299E56'
                    onClick={() => this.handleChangeGroupInputStatus('add')}
                  ></span>
                  <span
                    style='color: #E71818'
                    class='bk-icon icon-close-line-2'
                    onClick={() => this.handleChangeGroupInputStatus('cancel')}
                  ></span>
                </div>,
              ]
            ) : (
              <div
                class='add-new-group'
                onClick={() => (this.isShowNewGroupInput = true)}
              >
                <span style='position:relative'>
                  <span class='bk-icon icon-plus-circle />'></span>
                  <span style='color:#4D4F56'>{this.$t('新建分组')}</span>
                </span>
              </div>
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
              onMouseleave={this.handleHiddenIcon}
            >
              <span
                class='title-number'
                v-show={!this.isHoverTitle && this.titlePopoverInstance === null}
              >
                {this.data.favorites.length}
              </span>
              <div
                style='margin-right:2px'
                class={['more-box', (this.titlePopoverInstance !== null || this.isGroupNameEditShown) && 'is-click']}
                v-show={this.isHoverTitle || this.titlePopoverInstance !== null || this.isGroupNameEditShown}
              >
                <span
                  style='font-size:18px'
                  class='bklog-icon bklog-more'
                ></span>
              </div>
            </div>
            {groupDropList()}
          </div>
        ) : (
          <div>
            <div class='more-container'>
              {this.$slots.default ?? (
                <div
                  style='margin-right:2px'
                  class={['more-box', { 'is-click': !!this.operatePopoverInstance }]}
                  onMouseenter={this.handleClickIcon}
                  onMouseleave={this.handleMouseleaveMoreIcon}
                >
                  <span
                    style='font-size:18px'
                    class='bklog-icon bklog-more'
                  ></span>
                </div>
              )}
            </div>
            {collectDropList()}
            {groupList()}
          </div>
        )}

        <div style='display:none;'>
          <div
            ref='refGroupNameEdit'
            onMouseenter={this.handleHoverIcon}
            class='bklog-v3-favorite-group-edit'
          >
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
              <FormItem
                error-display-type='normal'
                property='groupEditName'
              >
                <span style={{ fontSize: '14px' }}>
                  分组名称 <span style='color:red'>*</span>
                </span>
                <Input
                  vModel={this.verifyData.groupEditName}
                  placeholder={this.$t('{n}, （长度30个字符）', { n: this.$t('请输入') })}
                  clearable
                  onEnter={v => this.handleGroupKeyDown(v, 'reset')}
                ></Input>
              </FormItem>
            </Form>
            <div class='operate-button'>
              <span
                class='operate-button-custom button-first'
                onClick={this.handleResetGroupName}
              >
                {this.$t('确定')}
              </span>
              <span
                class='operate-button-custom button-second'
                onClick={this.handleCancelGroupTitleName}
              >
                {this.$t('取消')}
              </span>
            </div>
          </div>
        </div>
      </div>
    );
  }
}
