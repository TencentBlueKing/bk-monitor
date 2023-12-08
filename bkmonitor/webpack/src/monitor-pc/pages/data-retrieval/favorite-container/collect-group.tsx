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

import { Component, Inject, Prop } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';
import dayjs from 'dayjs';

import { FavoriteIndexType, IFavList } from '../typings';

import GroupDropdown from './component/group-dropdown';

import './collect-group.scss';

@Component
export default class CollectGroup extends tsc<FavoriteIndexType.IContainerProps> {
  @Prop({ type: Object, required: true }) collectItem: IFavList.favGroupList; // 收藏元素
  @Prop({ type: Boolean, default: false }) isSearchFilter: boolean; // 是否搜索过滤
  @Prop({ default: () => ({}), type: Object }) favCheckedValue: IFavList.favList; // 当前点击的收藏
  @Prop({ type: Array, default: () => [] }) groupList: IFavList.groupList[]; // 组列表
  @Inject('handleUserOperate') handleUserOperate;
  isClickIcon = false; // 是否点击更多
  isHoverTitle = false;
  clickDrop = false; // 点击更多icon 防穿透
  favoriteMessageInstance = null; // 收藏更新信息实例

  get isCannotChange() {
    // 是否可以解散或重命名组
    return !this.collectItem.editable;
  }

  isActiveFavorite(id: number) {
    // 当前点击的收藏
    return id === this.favCheckedValue?.id;
  }

  /** 点击收藏 */
  handleClickCollect(item) {
    setTimeout(() => {
      this.clickDrop = false;
    }, 100);
    if (this.clickDrop) return;
    this.clickDrop = false;
    this.handleUserOperate('click-favorite', item);
  }

  /** 获取展示时间 */
  getShowTime(timeStr: string) {
    return dayjs.tz(timeStr).format('YYYY-MM-DD HH:mm:ss');
  }
  /** 鼠标移动到名称时 获取更新信息 */
  handleHoverFavoriteName(e, item) {
    if (!this.favoriteMessageInstance) {
      this.favoriteMessageInstance = this.$bkPopover(e.target, {
        content: `<div style="font-size: 12px;">
                    <div>${this.$t('创建人')}: ${item.create_user || '--'}</div>
                    <div>${this.$t('最近更新人')}: ${item.update_user || '--'}</div>
                    <div>${this.$t('最近更新时间')}: ${this.getShowTime(item.update_time)}</div>
                  </div>`,
        arrow: true,
        placement: 'top',
        onHidden: () => {
          this.favoriteMessageInstance?.destroy();
          this.favoriteMessageInstance = null;
        }
      });
      this.favoriteMessageInstance.show(500);
    }
  }

  render() {
    const groupDropdownSlot = (groupName: string) =>
      !this.isCannotChange ? (
        <GroupDropdown
          data={this.collectItem}
          groupList={this.groupList}
          groupName={groupName}
          isHoverTitle={this.isHoverTitle}
        />
      ) : (
        <span class='title-number'>{this.collectItem.favorites.length}</span>
      );
    const collectDropdownSlot = item => (
      <div onClick={() => (this.clickDrop = true)}>
        <GroupDropdown
          dropType={'collect'}
          data={item}
          groupList={this.groupList}
        />
      </div>
    );
    return (
      <div class='retrieve-collect-group'>
        <div
          class={[
            'group-title fl-jcsb',
            {
              'is-active': !this.isClickIcon,
              'is-move-cur': !this.isSearchFilter && !this.isCannotChange
            }
          ]}
          onMouseenter={() => (this.isHoverTitle = true)}
          onMouseleave={() => (this.isHoverTitle = false)}
        >
          <span
            class='group-cur'
            onClick={() => (this.isClickIcon = !this.isClickIcon)}
          >
            <span class={['bk-icon icon-play-shape', { 'is-active': !this.isClickIcon }]}></span>
            <span class='group-str'>{this.collectItem.name}</span>
          </span>
          {groupDropdownSlot(this.collectItem.name)}
        </div>
        <div class={['group-list', { 'list-hidden': this.isClickIcon }]}>
          {this.collectItem.favorites.map((item, index) => (
            <div
              key={index}
              class={['group-item', { active: this.isActiveFavorite(item.id) }]}
              onClick={() => this.handleClickCollect(item)}
            >
              <div
                class={{
                  'group-item-left': true,
                  'active-name': this.isActiveFavorite(item.id)
                }}
              >
                <span
                  class='fav-name'
                  onMouseenter={e => this.handleHoverFavoriteName(e, item)}
                >
                  {item.name}
                </span>
                {collectDropdownSlot(item)}
              </div>
            </div>
          ))}
        </div>
      </div>
    );
  }
}
