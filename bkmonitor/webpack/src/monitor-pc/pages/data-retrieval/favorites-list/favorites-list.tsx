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

import { deepClone } from 'monitor-common/utils/utils';

import type { IFavList } from '../typings';

import './favorites-list.scss';

@Component
export default class FavoritesList extends tsc<IFavList.IProps, IFavList.IEvent> {
  @Prop({ default: () => [], type: Array }) value: IFavList.IProps['value'];
  @Prop({ default: () => ({}), type: Object }) checkedValue: IFavList.IProps['checkedValue'];
  @Ref('scroll') scrollRef: HTMLBaseElement;
  @Ref('favMain') favMainRef: HTMLBaseElement;

  /** 收藏数据 */
  localValue: IFavList.favList[] = [];

  /** 展开更多 */
  isExpand = false;

  /** 允许过多滚动 */
  allowScroll = false;

  /** 新增高亮提示 */
  highlightList: number[] = [];

  /**
   * @description: 删除操作
   * @param {number} index
   * @return {*}
   */
  @Emit('deleteFav')
  handleDeleteItem(id: number, e: Event): number {
    e.stopPropagation();
    return id;
  }

  /**
   * @description: 选中收藏
   */
  @Emit('selectFav')
  emitSelectFav(data: IFavList.favList) {
    return {
      config: data.config,
      name: data.name,
    };
  }

  mounted() {
    this.favMainRef.addEventListener('transitionend', this.handleExpandEnd, false);
  }

  beforeDestroy() {
    this.favMainRef.removeEventListener('transitionend', this.handleExpandEnd, false);
  }

  /**
   * @description: 值更新
   */
  @Watch('value', { immediate: true })
  valueUpdate(newVal: IFavList.favList[]) {
    this.localValue = deepClone(newVal);
  }

  /**
   * @description: 监听动画结束
   * @param {TransitionEvent} evt
   * @return {*}
   */
  handleExpandEnd(evt: TransitionEvent) {
    if (evt.propertyName === 'max-height' && evt.target === this.favMainRef) {
      /** 动画完成开启滚动 */
      if (this.isExpand) {
        this.allowScroll = true;
      } else {
        this.scrollRef.scrollTo(0, 0);
        this.allowScroll = false;
      }
    }
  }

  /**
   * @description: 处理自动收起
   * @param {*} evt
   */
  handleClickOutSide(evt: Event) {
    const targetEl = evt.target as HTMLBaseElement;
    if (this.$el.contains(targetEl)) return;
    this.isExpand = false;
  }

  /**
   * @description: 展开更多
   * @param {*}
   * @return {*}
   */
  handleExpandMore(val = !this.isExpand) {
    this.isExpand = val;
    if (this.isExpand) {
      document.addEventListener('click', this.handleClickOutSide, false);
    } else {
      document.removeEventListener('click', this.handleClickOutSide, false);
    }
  }

  handleHighlight(item: IFavList.favList) {
    const isSame = JSON.stringify(item.config) === JSON.stringify(this.checkedValue?.config || {});
    return isSame;
  }

  render() {
    return (
      <div class={['favorites-list-wrap', { 'is-expand': this.isExpand }]}>
        <div
          ref='favMain'
          class='fav-main'
        >
          <div class='box-shadow' />
          <span class='fav-label'>{this.$t('收藏')}</span>
          <div
            ref='scroll'
            class={['fav-list-wrap', { 'allow-scroll': this.allowScroll && this.isExpand }]}
          >
            <ul class='fav-list'>
              {this.localValue.map((item, index) => (
                <li
                  key={index}
                  class={['fav-list-item', { active: this.handleHighlight(item) }]}
                  onClick={() => this.emitSelectFav(item)}
                >
                  <span class='fav-name'>{item.name}</span>
                  <i
                    class='icon-monitor icon-mc-close'
                    onClick={e => this.handleDeleteItem(item.id, e)}
                  />
                </li>
              ))}
            </ul>
          </div>
          <span class='arrow-down-wrap'>
            <i
              class={['icon-monitor', 'icon-arrow-down', { 'is-expand': this.isExpand }]}
              onClick={() => this.handleExpandMore()}
            />
          </span>
        </div>
      </div>
    );
  }
}
