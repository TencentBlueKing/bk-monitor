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
import { Component, Emit, Prop } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import { random } from 'monitor-common/utils/utils';

import { randomColor } from './color';
import UserSelector, { type IGroupListItem } from './user-selector';

import './user-list-sort.scss';

export interface IUserListItem {
  color: string;
  key: string;
  userList?: {
    id: string; // 用户id
    name: string; // 用户名称
    type: 'group' | 'user'; // 角色类型
  }[];
  users: {
    // 用户组
    id: string; // 用户id
    name: string; // 用户名
    type: 'group' | 'user';
  }[];
}
interface IEvents {
  onChange?: IUserListItem[];
}

interface IProps {
  colorIndex?: number; // 第几个颜色
  defaultGroupList?: IGroupListItem[];
  hasAdd?: boolean;
  value?: IUserListItem[]; // 轮值组
}

interface IUserItem {
  color: string;
  draggable: boolean; // 是否可抓取
  key: string;
  users: string[]; // 用于绑定到人员选择器
  userList: {
    id: string; // 用户id
    name: string; // 用户名称
    type: 'group' | 'user'; // 角色类型
  }[];
}

const defaultUserItem = (index: number) => {
  const color = randomColor(index);
  return {
    color,
    draggable: false,
    userList: [],
    users: [],
    key: random(8),
  };
};

@Component
export default class UserListSort extends tsc<IProps, IEvents> {
  @Prop({ type: Array, default: () => [] }) readonly defaultGroupList: IGroupListItem[];
  @Prop({ default: () => [], type: Array }) value: IUserListItem[];
  @Prop({ default: true, type: Boolean }) hasAdd: boolean;
  @Prop({ default: 0, type: Number }) colorIndex: number;

  userList: IUserItem[] = [];
  isDraging = false;
  dragOver: IUserItem = null;

  created() {
    if (this.value.length) {
      this.userList = this.value.map(item => ({
        ...item,
        draggable: false,
        users: item.users.map(u => u.id),
        userList: item.users,
      }));
    } else {
      this.userList.push(defaultUserItem(0));
    }
  }

  /* 添加用户组 */
  handleAdd() {
    this.userList.push(defaultUserItem(this.colorIndex));
    this.handleChange();
  }

  /* 是否可抓取 */
  handleDraggableChange(v: boolean, index: number) {
    this.userList[index].draggable = v;
  }
  /* 用户组更新 */
  handleUserChange(
    v: {
      // 用户组
      id: string; // 用户id
      name: string; // 用户名
      type: 'group' | 'user';
    }[],
    index: number
  ) {
    this.userList[index].users = v.map(item => item.id);
    this.userList[index].userList = v;
    this.handleChange();
  }

  /* 拖拽开始 */
  handleDragStart(event: DragEvent, index) {
    event.stopPropagation();
    event.dataTransfer.setData('user', JSON.stringify(this.userList[index]));
    this.isDraging = true;
  }
  /* 拖拽结束 */
  handleDragEnd(event: DragEvent) {
    event.stopPropagation();
    setTimeout(() => {
      this.isDraging = false;
      this.dragOver = null;
    }, 500);
  }
  /* 拖拽到目标处，返回目标数据 */
  handleDragOver(event: DragEvent, index) {
    event.stopPropagation();
    event.preventDefault();
    this.dragOver = JSON.parse(JSON.stringify(this.userList[index]));
  }
  /* 释放至目标 */
  handleDrop(event: DragEvent) {
    event.preventDefault();
    try {
      const dragItem: IUserItem = JSON.parse(event.dataTransfer.getData('user'));
      const dragIndex = this.userList.findIndex(item => item.key === dragItem.key); // 拖拽目标位置
      const dropIndex = this.userList.findIndex(item => item.key === this.dragOver.key); // 释放目标位置
      const tmp = this.userList.splice(dragIndex, 1);
      this.userList.splice(dropIndex, 0, tmp[0]);
      this.dragOver = null;
      this.handleChange();
    } catch {
      console.warn('parse drag data error');
    }
  }

  /* 删除 */
  handleDeleteItem(index: number) {
    this.userList.splice(index, 1);
    this.handleChange();
  }

  @Emit('change')
  handleChange() {
    return this.userList;
  }

  render() {
    return (
      <div class='user-sort-list-component'>
        <div class='user-list-wrap'>
          <transition-group
            name={'flip-list'}
            tag='ul'
          >
            {this.userList.map((item, index) => (
              <div
                key={item.key}
                class='user-list-item'
                draggable={item.draggable}
                onDragend={(event: DragEvent) => this.handleDragEnd(event)}
                onDragover={(event: DragEvent) => this.handleDragOver(event, index)}
                onDragstart={(event: DragEvent) => this.handleDragStart(event, index)}
                onDrop={(event: DragEvent) => this.handleDrop(event)}
              >
                <UserSelector
                  key={item.key}
                  color={item.color}
                  groupList={this.defaultGroupList}
                  hasDrag={this.hasAdd}
                  value={item.users}
                  onChange={v => this.handleUserChange(v as any, index)}
                  onDraggableChange={(v: boolean) => this.handleDraggableChange(v, index)}
                />
                <div class='right-wrap'>
                  {this.userList.length > 1 && (
                    <div
                      class='delete-btn'
                      onClick={() => this.handleDeleteItem(index)}
                    >
                      <span class='icon-monitor icon-mc-delete-line' />
                    </div>
                  )}
                </div>
              </div>
            ))}
          </transition-group>
          {this.hasAdd && (
            <bk-button
              class='add-btn'
              icon='plus'
              size='small'
              text={true}
              title='primary'
              onClick={this.handleAdd}
            >
              {window.i18n.t('添加用户组')}
            </bk-button>
          )}
        </div>
      </div>
    );
  }
}
