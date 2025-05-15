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

// import _ from 'lodash';
// import { updateSceneView } from 'monitor-api/modules/scene_view';

import { deepClone } from 'monitor-common/utils';

import './index.scss';

interface IProps {
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
  @Prop({ type: Array, required: true }) readonly viewList: IProps['viewList'];
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
  @Watch('viewList')
  viewListChange(val) {
    console.log(val, '===');
    this.pageList = deepClone(this.viewList);
  }
  handleShowDialog() {
    this.isShowDialog = true;
  }
  handleEdit(item) {
    // item.edit = true;
    const list = this.pageList.map(view => Object.assign(view, { edit: item.id === view.id }));
    this.$set(this, 'pageList', list);
    console.log(item, '---');
  }
  handleDragend() {
    // 动画结束后关闭拖拽动画效果
    setTimeout(() => {
      this.dragData.from = null;
      this.dragData.to = null;
    }, 500);
    this.drag.active = -1;
  }
  handleDragEnter(index: number) {
    this.dragData.to = index;
  }
  handleDragLeave() {
    this.drag.active = -1;
  }
  handleDragOver(evt: DragEvent, index: number) {
    evt.preventDefault();
    this.drag.active = index;
  }

  handleDragStart(evt: DragEvent, index: number) {
    this.dragData.from = index;

    evt.dataTransfer.effectAllowed = 'move';
  }
  handleDrop() {
    const { from, to } = this.dragData;
    if (from === to || [from, to].includes(null)) return;
    const temp = this.pageList[from];
    this.pageList.splice(from, 1);
    this.pageList.splice(to, 0, temp);
    this.drag.active = -1;
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
          <transition-group
            name={this.dragData.from !== null ? 'flip-list' : 'filp-list-none'}
            tag='ul'
          >
            {this.pageList.map((item, index) => (
              <li
                key={`${item.edit}${index}`}
                class={['metric-view-drag-item']}
                draggable={this.isEditing}
                onDragend={this.handleDragend}
                onDragenter={() => this.handleDragEnter(index)}
                onDragleave={this.handleDragLeave}
                onDragover={evt => this.handleDragOver(evt, index)}
                onDragstart={evt => this.handleDragStart(evt, index)}
                onDrop={this.handleDrop}
              >
                {item.edit && (
                  <bk-input
                    class='drag-input'
                    value={item.name}
                  />
                )}
                {!item.edit && <i class='icon-monitor icon-mc-tuozhuai drag-icon' />}
                {!item.edit && <span class='label'>{item.name}</span>}
                {item.edit ? (
                  <span class='edit-icon-group'>
                    <i class='icon-monitor icon-mc-check-small save-icon' />
                    <i class='icon-monitor icon-mc-close close-icon' />
                  </span>
                ) : (
                  <span class='icon-group'>
                    <i
                      class='icon-monitor icon-bianji edit-icon'
                      onClick={() => this.handleEdit(item)}
                    />
                    <i class='icon-monitor icon-mc-delete-line del-icon' />
                  </span>
                )}
              </li>
            ))}
          </transition-group>
        </bk-dialog>
      </div>
    );
  }
}
