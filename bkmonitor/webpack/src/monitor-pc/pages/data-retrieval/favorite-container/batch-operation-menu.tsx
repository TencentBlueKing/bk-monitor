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
import { Component, Prop, Ref } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import { bulkDeleteFavorite, bulkUpdateFavorite, createFavoriteGroup } from 'monitor-api/modules/model';

import type { IFavList } from '../typings';

import './batch-operation-menu.scss';

interface BatchOperationMenuEvents {
  onOperateChange(operate: string, value?: any): void;
}

interface BatchOperationMenuProps {
  favoriteGroupList: IFavList.favGroupList[];
  favoriteType: string;
  selectFavoriteList: IFavList.favList[];
}

@Component
export default class BatchOperationMenu extends tsc<BatchOperationMenuProps, BatchOperationMenuEvents> {
  @Prop({ type: Array }) selectFavoriteList: IFavList.favList[];
  @Prop({ type: String }) favoriteType: string;
  @Prop({ type: Array }) favoriteGroupList: IFavList.favGroupList[];

  @Ref('batchOperationMenu') batchOperationMenuRef;
  @Ref('batchMoveToGroupMenu') batchMoveToGroupMenuRef;
  @Ref('moveToGroupInput') moveToGroupInputRef;
  @Ref('checkInputAddForm') checkInputAddFormRef;

  /** 批量操作 */
  batchOperatePopoverInstance = null;
  /** 批量删除dialog */
  batchDeleteDialogVisible = false;
  /** 批量移动分组popover */
  batchMoveGroupPopoverInstance = null;
  /** 移动分组弹窗是否新增分组 */
  moveToGroupAddGroup = false;

  addGroupData = {
    name: '',
  };

  rules = {
    name: [
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

  checkName() {
    if (this.addGroupData.name.trim() === '') return true;
    return /^[\u4e00-\u9fa5_a-zA-Z0-9`~!@#$%^&*()_\-+=<>?:"\s{}|,./;'\\[\]·~！@#￥%……&*（）——\-+={}|《》？：“”【】、；‘'，。、]+$/im.test(
      this.addGroupData.name.trim()
    );
  }

  checkExistName() {
    return !this.favoriteGroupList.some(item => item.name === this.addGroupData.name);
  }

  /** 批量操作 */
  handleBatchOperation(e) {
    if (this.batchOperatePopoverInstance) {
      this.batchOperatePopoverInstance.destroy?.();
      this.batchOperatePopoverInstance = null;
    }
    this.batchOperatePopoverInstance = this.$bkPopover(e.currentTarget, {
      content: this.batchOperationMenuRef,
      arrow: false,
      interactive: true,
      trigger: 'click',
      theme: 'light',
      placement: 'bottom-start',
      boundary: 'viewport',
      extCls: 'batch-operation-menu',
      onHidden: () => {
        this.batchOperatePopoverInstance.destroy?.();
        this.batchOperatePopoverInstance = null;
      },
    });
    this.batchOperatePopoverInstance.show(100);
  }

  /** 展示批量删除弹窗 */
  handleShowBatchDeleteDialog() {
    this.batchDeleteDialogVisible = true;
    this.batchOperatePopoverInstance.destroy?.();
    this.batchOperatePopoverInstance = null;
  }

  /** 批量删除收藏 */
  handleBatchDeleteFavorite() {
    bulkDeleteFavorite({
      type: this.favoriteType,
      ids: this.selectFavoriteList.map(item => item.id),
    }).then(() => {
      this.$bkMessage({ theme: 'success', message: this.$t('批量删除成功') });
      this.batchDeleteDialogVisible = false;
      this.$emit('operateChange', 'request-query-history');
    });
  }

  /** 展示批量移动到分组popover */
  handleShowMoveToGroupMenu(e: MouseEvent) {
    if (this.batchMoveGroupPopoverInstance) {
      this.batchMoveGroupPopoverInstance.destroy?.();
      this.batchMoveGroupPopoverInstance = null;
    }
    this.batchOperatePopoverInstance?.set({ hideOnClick: false });
    this.batchMoveGroupPopoverInstance = this.$bkPopover(e.currentTarget, {
      content: this.batchMoveToGroupMenuRef,
      interactive: true,
      theme: 'light',
      arrow: false,
      boundary: 'viewport',
      hideOnClick: true,
      offset: -4,
      distance: 2,
      placement: 'right-start',
      extCls: 'batch-move-to-group-menu',
      onHidden: () => {
        this.moveToGroupAddGroup = false;
        this.addGroupData.name = '';
        this.checkInputAddFormRef?.clearError();
        this.batchOperatePopoverInstance?.set({ hideOnClick: true });
        this.batchMoveGroupPopoverInstance.destroy?.();
        this.batchMoveGroupPopoverInstance = null;
      },
    });
    this.batchMoveGroupPopoverInstance.show(100);
  }

  handleBatchMoveToGroup(id: number) {
    bulkUpdateFavorite({
      type: this.favoriteType,
      configs: this.selectFavoriteList.map(item => ({
        id: item.id,
        name: item.name,
        group_id: id,
      })),
    }).then(() => {
      this.$bkMessage({ theme: 'success', message: this.$t('批量移动成功') });
      this.batchMoveGroupPopoverInstance?.hide();
      this.batchOperatePopoverInstance?.hide();
      this.$emit('operateChange', 'request-query-history');
    });
  }

  handleMoveToGroupAddGroupChange(show) {
    this.moveToGroupAddGroup = show;
    if (show) {
      this.$nextTick(() => {
        this.moveToGroupInputRef?.focus();
      });
    } else {
      this.addGroupData.name = '';
    }
  }

  handleAddGroupConfirm() {
    this.checkInputAddFormRef.validate().then(async () => {
      const data = await createFavoriteGroup({
        type: this.favoriteType,
        name: this.addGroupData.name,
      });
      this.handleBatchMoveToGroup(data.id);
    });
  }

  render() {
    return (
      <div class='batch-operation-menu-container'>
        <bk-button
          disabled={this.selectFavoriteList.length === 0}
          onClick={this.handleBatchOperation}
        >
          {this.$t('批量操作')} <i class='icon-monitor icon-arrow-down' />
        </bk-button>
        <div style='display: none'>
          <div
            ref='batchOperationMenu'
            class='batch-operation-menu-content'
          >
            <div
              class='operation-item'
              onMouseenter={this.handleShowMoveToGroupMenu}
            >
              {this.$t('移动至分组')}
              <i class='icon-monitor icon-arrow-right' />
            </div>
            <div
              class='operation-item'
              onClick={this.handleShowBatchDeleteDialog}
            >
              {this.$t('删除')}
            </div>
          </div>

          <div
            ref='batchMoveToGroupMenu'
            class='batch-move-to-group-menu-content'
          >
            <div class='group-list'>
              {this.favoriteGroupList.map(group => (
                <div
                  key={group.id}
                  class='group-item'
                  v-bk-overflow-tips
                  onClick={() => {
                    this.handleBatchMoveToGroup(group.id);
                  }}
                >
                  {group.name}
                </div>
              ))}
            </div>
            <div class='add-group-item'>
              {this.moveToGroupAddGroup ? (
                <div class='add-group-input'>
                  <bk-form
                    ref='checkInputAddForm'
                    style={{ width: '100%' }}
                    labelWidth={0}
                    {...{
                      props: {
                        model: this.addGroupData,
                        rules: this.rules,
                      },
                    }}
                  >
                    <bk-form-item property='name'>
                      <bk-input
                        ref='moveToGroupInput'
                        v-model={this.addGroupData.name}
                      />
                    </bk-form-item>
                  </bk-form>
                  <i
                    class='bk-icon icon-check-line'
                    onClick={this.handleAddGroupConfirm}
                  />
                  <i
                    class='bk-icon icon-close-line-2'
                    onClick={() => this.handleMoveToGroupAddGroupChange(false)}
                  />
                </div>
              ) : (
                <div
                  class='add-group-btn'
                  onClick={() => {
                    this.handleMoveToGroupAddGroupChange(true);
                  }}
                >
                  <i class='icon-monitor icon-jia' />
                  <span>{this.$t('新建分组')}</span>
                </div>
              )}
            </div>
          </div>
        </div>

        <bk-dialog
          width={480}
          ext-cls='batch-delete-dialog'
          v-model={this.batchDeleteDialogVisible}
        >
          <div class='dialog-content'>
            <div class='title'>{this.$t('确定删除选中的收藏项?')}</div>
            <div class='tips'>{this.$t('删除后，无法恢复，请谨慎操作!')}</div>
            <div class='favorite-list'>
              <div class='list-title'>
                <i18n path='已选择以下{0}个收藏对象'>
                  <span class='count'>{this.selectFavoriteList.length}</span>
                </i18n>
              </div>
              <div class='list'>
                {this.selectFavoriteList.map(item => (
                  <div
                    key={item.id}
                    class='item'
                    v-bk-overflow-tips
                  >
                    {item.name}
                  </div>
                ))}
              </div>
            </div>
          </div>
          <div
            class='footer-wrap'
            slot='footer'
          >
            <bk-button
              class='del-btn'
              theme='danger'
              onClick={this.handleBatchDeleteFavorite}
            >
              {this.$t('删除')}
            </bk-button>
            <bk-button
              onClick={() => {
                this.batchDeleteDialogVisible = false;
              }}
            >
              {this.$t('取消')}
            </bk-button>
          </div>
        </bk-dialog>
      </div>
    );
  }
}
