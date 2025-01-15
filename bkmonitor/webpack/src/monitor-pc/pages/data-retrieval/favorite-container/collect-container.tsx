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

import { Component, Emit, Prop, Provide, Watch } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import VueDraggable from 'vuedraggable';

import EmptyStatus from '../../../components/empty-status/empty-status';
import CollectGroup from './collect-group';

import type { EmptyStatusOperationType, EmptyStatusType } from '../../../components/empty-status/types';
import type { FavoriteIndexType, IFavList } from '../typings';

import './collect-container.scss';

@Component
export default class CollectContainer extends tsc<FavoriteIndexType.IContainerProps> {
  @Prop({ type: Array, required: true }) dataList: IFavList.favGroupList[]; // 收藏列表
  @Prop({ type: Array, required: true }) groupList: IFavList.groupList[]; // 组列表
  @Prop({ default: () => ({}), type: Object }) favCheckedValue: IFavList.favList; // 当前点击的收藏
  @Prop({ type: Boolean, default: false }) isSearchFilter: boolean; // 是否搜索过滤
  @Prop({ type: Boolean, default: false }) collectLoading: boolean; // 搜索loading
  @Prop({ type: String, default: 'empty' }) emptyStatusType: EmptyStatusType; // 空状态类型
  dragList: IFavList.favGroupList[] = []; // 可拖拽的收藏列表

  @Provide('handleUserOperate')
  handleUserOperate(type: string, value?: any) {
    this.handleValueChange(type, value);
  }

  @Watch('dataList', { deep: true, immediate: true })
  handleWatchDataList() {
    // 初始拖拽收藏列表
    this.dragList = JSON.parse(JSON.stringify(this.dataList));
  }

  @Emit('change')
  handleValueChange(type: string, value: any) {
    return {
      type,
      value,
    };
  }

  get isEmptyData() {
    // 是否是空数据
    return !this.dataList.length;
  }

  /** 拖拽结束 */
  handleMoveEnd() {
    const dragIDList = this.dragList.slice(1, this.dataList.length - 1).map(item => item.id);
    this.handleValueChange('drag-move-end', dragIDList);
  }

  /** 鼠标拖拽结束时 */
  handleMoveIng(e) {
    // 拖拽到的对象为未分组或个人组时不请求接口
    if (e.draggedContext.element.id === 0) return false;
    if (e.draggedContext.element.id === null) return false;
    if (e.relatedContext.element.id === 0) return false;
    if (e.relatedContext.element.id === null) return false;
    return true;
  }

  @Emit('handleOperation')
  handleOperation(type: EmptyStatusOperationType) {
    return type;
  }
  render() {
    return (
      <div class='retrieve-collect-container'>
        {this.$slots.default}
        <div
          class='group-container'
          v-bkloading={{ isLoading: this.collectLoading, zIndex: 999 }}
        >
          {!this.isEmptyData ? (
            <VueDraggable
              vModel={this.dragList}
              animation='150'
              disabled={true}
              handle='.group-title'
              move={this.handleMoveIng}
              on-end={this.handleMoveEnd}
            >
              <transition-group>
                {this.dragList.map(item => (
                  <div key={`${item.id}`}>
                    <CollectGroup
                      collectItem={item}
                      favCheckedValue={this.favCheckedValue}
                      groupList={this.groupList}
                      isSearchFilter={this.isSearchFilter}
                    />
                  </div>
                ))}
              </transition-group>
            </VueDraggable>
          ) : (
            <div class='data-empty'>
              <EmptyStatus
                type={this.emptyStatusType}
                onOperation={this.handleOperation}
              />
            </div>
          )}
        </div>
      </div>
    );
  }
}
