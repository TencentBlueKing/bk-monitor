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
import { Component, Prop, Watch } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

// import _ from 'lodash';
import { bulkUpdateSceneViewOrderAndName, deleteSceneView } from 'monitor-api/modules/scene_view';
import { deepClone } from 'monitor-common/utils';
import draggable from 'vuedraggable';

import './index.scss';

interface IEmit {
  onSuccess: () => void;
}

interface IProps {
  payload: Record<string, any>;
  sceneId: string;
  viewList: {
    edit?: boolean;
    id: string;
    name: string;
  }[];
}

@Component({
  name: 'ViewManage',
  components: {
    draggable,
  },
})
export default class ViewManage extends tsc<IProps, IEmit> {
  @Prop({ type: String, required: true }) readonly sceneId: IProps['sceneId'];
  @Prop({ type: Array, required: true }) readonly viewList: IProps['viewList'];
  @Prop({ type: Object, default: () => ({}) }) readonly payload: IProps['payload'];
  /** 是否修改了顺序或者名字 */
  isChange = false;
  /** 是否有删除的操作 */
  isDelChange = false;
  isShowDialog = false;
  /** 拖拽数据 */
  dragData: { from: number; to: number } = {
    from: null,
    to: null,
  };
  pageList = [];
  isDragging = false;
  dragCount = 0;
  lastDragTime = null;
  delList = [];
  isLoading = false;

  @Watch('viewList', { immediate: true })
  viewListChange() {
    this.pageList = deepClone(this.viewList);
  }
  handleShowDialog() {
    this.isChange = false;
    this.isDelChange = false;
    this.isShowDialog = true;
    this.delList = [];
  }

  async handleSave() {
    /** 是否有做任何修改或者删除操作 */
    if (!this.isChange && !this.isDelChange) {
      return;
    }
    let handleRes = false;
    this.isLoading = true;
    /** 有修改操作才调用修改接口 */
    if (this.isChange) {
      handleRes = await this.handleUpdateNameOrSort();
    }
    /** 有删除操作才调用删除接口 */
    if (this.isDelChange) {
      handleRes = await this.handleDelView();
    }
    this.isLoading = false;
    if (handleRes) {
      this.$bkMessage({
        theme: 'success',
        message: this.$t('修改成功'),
      });
      this.isShowDialog = false;
      this.$emit('success');
    }
  }
  /** 修改排序或者名字 */
  handleUpdateNameOrSort() {
    const { pageList } = this;
    const config = pageList.reduce((acc, item) => {
      if (item.id !== undefined && item.name !== undefined) {
        acc.push({ id: item.id, name: item.name });
      }
      return acc;
    }, []);
    if (config.length === 0) {
      return Promise.resolve(false);
    }
    return bulkUpdateSceneViewOrderAndName({
      scene_id: this.sceneId,
      type: 'detail',
      config,
    })
      .then(() => true)
      .catch(() => false);
  }
  /** 删除视图操作 */
  handleDelView() {
    return deleteSceneView({
      scene_id: this.sceneId,
      ids: this.delList,
      type: 'detail',
    })
      .then(() => true)
      .catch(() => false);
  }
  /** 删除 */
  handleDel(item) {
    this.isDelChange = true;
    this.delList.push(item.id);
    this.pageList = this.pageList.filter(view => view.id !== item.id);
  }
  dragStart() {
    this.isDragging = true;
  }
  dragEnd() {
    this.isDragging = false;
    this.dragCount++;
    this.lastDragTime = new Date().toLocaleTimeString();
    this.isChange = true;
  }
  handleClose() {
    this.isShowDialog = false;
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
          class='metric-view-manage-dialog'
          v-model={this.isShowDialog}
          draggable={false}
          header-position='left'
          render-directive='if'
          scrollable={false}
          title={this.$t('视图管理')}
        >
          <draggable
            v-model={this.pageList}
            options={{ animation: 200 }}
            onEnd={this.dragEnd}
            onStart={this.dragStart}
          >
            <transition-group
              class='metric-view-drag-list'
              name={this.dragData.from !== null ? 'flip-list' : 'flip-list-none'}
              tag='ul'
            >
              {this.pageList.map((item, index) => (
                <li
                  key={`${item.edit}${index}`}
                  class={['metric-view-drag-item']}
                >
                  <i class='icon-monitor icon-mc-tuozhuai drag-icon' />
                  <bk-input
                    class='drag-input'
                    v-model={item.name}
                    onChange={() => {
                      this.isChange = true;
                    }}
                  />
                  <span class='icon-group'>
                    <i
                      class='icon-monitor icon-mc-delete-line del-icon'
                      onClick={() => this.handleDel(item)}
                    />
                  </span>
                </li>
              ))}
            </transition-group>
          </draggable>
          <div slot='footer'>
            <bk-button
              style={{ marginRight: '5px' }}
              loading={this.isLoading}
              theme='primary'
              onClick={this.handleSave}
            >
              {this.$t('确定')}
            </bk-button>
            <bk-button onClick={this.handleClose}>{this.$t('取消')}</bk-button>
          </div>
        </bk-dialog>
      </div>
    );
  }
}
