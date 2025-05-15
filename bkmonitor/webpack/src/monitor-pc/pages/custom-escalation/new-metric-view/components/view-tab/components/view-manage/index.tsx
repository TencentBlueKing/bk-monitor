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
import { Component, Ref, Prop, Watch } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import draggable from 'vuedraggable';
// import _ from 'lodash';
import { updateSceneView } from 'monitor-api/modules/scene_view';
import { deepClone } from 'monitor-common/utils';

import './index.scss';

interface IProps {
  sceneId: string;
  payload: Record<string, any>;
  viewList: {
    id: string;
    name: string;
    edit?: boolean;
  }[];
}

interface IEmit {
  onSuccess: () => void;
}

@Component
export default class ViewManage extends tsc<IProps, IEmit> {
  @Prop({ type: String, required: true }) readonly sceneId: IProps['sceneId'];
  @Prop({ type: Array, required: true }) readonly viewList: IProps['viewList'];
  @Prop({ type: Object, default: () => ({}) }) readonly payload: IProps['payload'];
  isShowDialog = false;
  isEditing = false;
  /** 拖拽数据 */
  dragData: { from: number; to: number } = {
    from: null,
    to: null,
  };
  drag = {
    active: -1,
  };
  pageList = [];
  isDragging = false;
  dragCount = 0;
  lastDragTime = null;
  @Watch('viewList')
  viewListChange(val) {
    console.log(val, '===');
    this.pageList = deepClone(this.viewList);
  }
  handleShowDialog() {
    this.isShowDialog = true;
  }
  handleEdit(item) {
    this.pageList = this.pageList.map(view => Object.assign(view, { edit: item.id === view.id }));
  }
  handleClose() {
    this.pageList = this.pageList.map(view => Object.assign(view, { edit: false }));
  }
  async handleSave(item) {
    await updateSceneView({
      scene_id: this.sceneId,
      type: 'detail',
      config: {
        options: this.payload,
      },
      ...item,
    });
    this.$bkMessage({
      theme: 'success',
      message: this.$t('修改成功'),
    });
    this.handleClose();
    this.$emit('success');
  }
  handleDel(item) {
    console.log(item, 'item');
  }
  dragStart() {
    this.isDragging = true;
  }
  dragEnd() {
    this.isDragging = false;
    this.dragCount++;
    this.lastDragTime = new Date().toLocaleTimeString();
  }
  render() {
    return (
      <div
        class='metric-view-manage-btn'
        v-bk-tooltips={{ content: this.$t('视图管理') }}
        onClick={this.handleShowDialog}
      >
        <i class='icon-monitor icon-shezhi1' />
        <bk-dialog
          width={480}
          v-model={this.isShowDialog}
          draggable={false}
          header-position='left'
          render-directive='if'
          scrollable={false}
          title={this.$t('视图管理')}
        >
          <div class='metric-view-drag-item'>{this.$t('默认')}</div>
          {/* <draggable
            v-model={this.pageList}
            animation='150'
            disabled={true}
            on-end={this.dragEnd}
            on-start={this.dragStart}
          >
            <transition-group
              name={this.dragData.from !== null ? 'flip-list' : 'filp-list-none'}
              tag='ul'
            >
              {this.pageList.map((item, index) => (
                <div
                  key={index}
                  class='metric-view-drag-item'
                >
                  <span class='font-medium'>{item.name}</span>
                  <div class='flex items-center'>
                    <span class='text-xs text-neutral/50 mr-2'>#{index + 1}</span>
                    <i class='fa fa-arrows text-neutral/30' />
                  </div>
                </div>
              ))} */}
          {this.pageList.map((item, index) => (
            <li
              key={`${item.edit}${index}`}
              class={['metric-view-drag-item']}
            >
              {item.edit && (
                <bk-input
                  class='drag-input'
                  v-model={item.name}
                />
              )}
              {!item.edit && <i class='icon-monitor icon-mc-tuozhuai drag-icon' />}
              {!item.edit && <span class='label'>{item.name}</span>}
              {item.edit ? (
                <span class='edit-icon-group'>
                  <i
                    class='icon-monitor icon-mc-check-small save-icon'
                    onClick={() => this.handleSave(item)}
                  />
                  <i
                    class='icon-monitor icon-mc-close close-icon'
                    onClick={() => this.handleClose()}
                  />
                </span>
              ) : (
                <span class='icon-group'>
                  <i
                    class='icon-monitor icon-bianji edit-icon'
                    onClick={() => this.handleEdit(item)}
                  />
                  <i
                    class='icon-monitor icon-mc-delete-line del-icon'
                    onClick={() => this.handleDel(item)}
                  />
                </span>
              )}
            </li>
          ))}
          {/* </transition-group>
          </draggable> */}
        </bk-dialog>
      </div>
    );
  }
}
