<!--
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
-->
<template>
  <div
    class="select-chart-wrap"
    v-bkloading="{ isLoading }"
  >
    <transition-group
      name="flip-list"
      tag="ul"
      class="selected-list-wrap"
      v-if="selectedList.length"
    >
      <li
        v-for="(item, index) in selectedList"
        :key="item.id"
        :class="[
          'selected-item',
          {
            active: DragData.toActive === index || selectedActive === item.id,
          },
        ]"
        draggable="true"
        @click="handleSelectItem(item)"
        @dragstart="handleDragStart($event, index)"
        @dragend="handleDragEnd($event, index)"
        @drop="handleDrop($event, index)"
        @dragenter="handleDragEnter($event, index)"
        @dragover="handleDragOver($event, index)"
      >
        <span class="icon-drag" />
        <span class="item-title">
          <span class="title">{{ item.name }}</span>
          <span
            class="des"
            v-bk-tooltips="{ content: handleBelonging(item), delay: 300, allowHTML: false }"
            >&nbsp;{{ `- ${$t('所属:')}${handleBelonging(item)}` }}</span
          >
        </span>
        <span
          @click.stop="handleDelSelected(index)"
          class="icon-monitor icon-mc-close"
        />
      </li>
    </transition-group>
    <div
      class="add-btn-wrap"
      v-show="!tool.show && !isDisabled"
    >
      <span
        class="add-btn"
        @click="handleAddChart"
        ><span class="icon-monitor icon-mc-add" />{{ $t('添加图表') }}</span
      >
    </div>
    <div
      class="select-tool-wrap"
      v-if="tool.show"
    >
      <div class="tool-left-wrap">
        <bk-tab
          class="tab-wrap"
          :active.sync="tool.active"
          type="unborder-card"
          @tab-change="handleTabChange"
        >
          <bk-tab-panel
            v-for="(tab, index) in tool.tabList"
            v-bind="tab"
            :key="index"
          />
        </bk-tab>
        <!-- <bk-select
          v-show="tool.active === 'default'"
          class="biz-list-wrap"
          v-model="DefaultCurBizIdList"
          multiple
          searchable
          :clearable="false"
          @change="handleChangeBizIdList"
        >
          <bk-option v-for="(option, index) in handleBizIdList" :key="index" :id="option.id" :name="option.text">
          </bk-option>
        </bk-select> -->
        <div
          class="biz-list-wrap"
          v-show="tool.active === 'default'"
        >
          <space-select
            :value="DefaultCurBizIdList"
            :space-list="$store.getters.bizList"
            :need-authority-option="false"
            :need-alarm-option="false"
            :need-defalut-options="true"
            @change="handleChangeBizIdList"
          />
        </div>
        <div
          class="biz-list-wrap"
          v-if="tool.active === 'grafana'"
        >
          <space-select
            :value="[curBizId]"
            :space-list="$store.getters.bizList"
            :need-authority-option="false"
            :need-alarm-option="false"
            :multiple="false"
            @change="handleGraphBizid"
          />
        </div>
        <!-- <bk-select
          v-if="tool.active === 'grafana'"
          searchable
          class="biz-list-wrap"
          v-model="curBizId"
          :clearable="false"
          @change="handleGraphBizid"
        >
          <bk-option v-for="(option, index) in bizIdList" :key="index" :id="option.id" :name="option.text"> </bk-option>
        </bk-select> -->
        <div class="left-list-wrap">
          <div
            v-for="(item, index) in leftList"
            :key="index"
            :class="['left-list-item', { active: leftActive === item.uid }]"
            @click="handleSelectLeftItem(item)"
          >
            {{ item.name }}
          </div>
        </div>
      </div>
      <div
        class="tool-right-wrap"
        v-bkloading="{ isLoading: isRightListLoading }"
      >
        <div class="right-title">
          {{ $t('可选图表({num})', { num: rightList.length }) }}
        </div>
        <div class="right-list-wrap">
          <checkbox-group
            v-model="rightSelect"
            :list="rightList"
            :active="selectedActive"
            :disabled="isDisabled"
          />
        </div>
        <div class="right-btn-wrap">
          <bk-button
            size="small"
            theme="primary"
            :disabled="false"
            @click="handleComfirm"
            >{{ $t('确认') }}</bk-button
          >
          <bk-button
            size="small"
            @click="handleCancel"
            >{{ $t('取消') }}</bk-button
          >
        </div>
      </div>
    </div>
  </div>
</template>

<script lang="ts">
import { getDashboardList } from 'monitor-api/modules/grafana';
import { buildInMetric, getPanelsByDashboard } from 'monitor-api/modules/report';
import { deepClone } from 'monitor-common/utils/utils';
import { Component, Emit, Model, Vue, Watch } from 'vue-property-decorator';

import SpaceSelect from '../../../components/space-select/space-select';
import type {
  IAddChartToolData,
  IChartDataItem,
  IChartListAllItem,
  IDefaultRadioList,
  IGraphValueItem,
} from '../types';

import checkboxGroup from './checkboxGroup.vue';
import { defaultRadioList } from './store';

/**
 * 添加内容-图表选择组件
 */
@Component({
  name: 'select-chart',
  components: {
    checkboxGroup,
    SpaceSelect,
  },
})
export default class SelectChart extends Vue {
  // value双向绑定
  @Model('valueChange', { type: Array }) value: string[];

  isLoading = false;
  isRightListLoading = false;
  // 选择图表工具的数据
  tool: IAddChartToolData = {
    show: false,
    active: 'grafana',
    tabList: [
      { name: 'default', label: window.i18n.t('内置') },
      { name: 'grafana', label: window.i18n.t('仪表盘') },
    ],
  };

  // active状态与列表数据
  selectedActive: string = null;
  selectedList: IGraphValueItem[] = [];
  rightList: IChartDataItem[] = [];
  // leftList: IChartListAllItem[] = []
  curBizId = `${window.cc_biz_id}`;
  DefaultCurBizIdList: string[] = [`${window.cc_biz_id}`];
  bizIdList: any = [];
  leftActive: string = null;
  rightSelect: IGraphValueItem[] = [];
  allGrafanaListMap: any = [];
  allDefaultList: any = [];
  defaultRadioList: IDefaultRadioList[] = defaultRadioList;
  radioMap: string[] = ['all', 'settings', 'notify'];

  // 拖拽数据状态记录
  DragData: any = {
    from: null,
    to: null,
    toActive: null,
  };

  get leftList(): IChartListAllItem[] {
    const isDefault = this.tool.active === 'default';
    const list = isDefault ? this.allDefaultList : this.allGrafanaListMap;
    return list || [];
  }
  // get rightList(): IChartDataItem[] {
  //   if (this.tool.active === 'default' && !this.DefaultCurBizIdList.length) return [];
  //   const allList = this.leftList.reduce((total, cur) => {
  //     cur.panels.forEach((item) => {
  //       const bizId = this.tool.active === 'default' ? this.DefaultCurBizIdList.sort().join(',') : this.curBizId;
  //       item.fatherId = cur.uid;
  //       item.key = `${bizId}-${this.leftActive}-${item.id}`;
  //     });
  //     total = total.concat(cur.panels);
  //     return total;
  //   }, []);
  //   return allList.filter(item => this.leftActive === item.fatherId && !/^-1/.test(item.key));
  // }

  get handleBizIdList() {
    return [
      ...this.defaultRadioList,
      ...this.bizIdList.map(item => ({
        id: String(item.id),
        text: item.text,
      })),
    ];
  }

  // 限制最多选择图表数
  get isDisabled(): boolean {
    const MAX = 20;
    return this.rightSelect.length >= MAX;
  }

  @Emit('valueChange')
  handleValueChange(v?: string) {
    return v || this.selectedList;
  }
  // 值更新
  @Watch('value', { immediate: true, deep: true })
  watchValueChange(v: IGraphValueItem[]) {
    this.selectedList = v;
    this.rightSelect = deepClone(v);
  }

  async created() {
    this.isLoading = true;
    await Promise.all([this.getChartList(), this.getBuildInMetric()]).finally(() => (this.isLoading = false));
    this.bizIdList = this.$store.getters.bizList.map(item => ({
      id: String(item.id),
      text: item.text,
    }));
  }

  /**
   * 获取内置图表数据
   */
  getBuildInMetric() {
    return buildInMetric().then(list => {
      this.allDefaultList = list;
    });
  }

  /**
   * 获取图表的panels列表数据
   */
  getPanelsList(uid: string) {
    return getPanelsByDashboard({ uid }).finally(() => (this.isRightListLoading = false));
  }

  /**
   * 获取图表列表数据
   */
  getChartList(needLoading = false) {
    // const noPermission = !this.bizIdList.some(item => `${item.id}` === `${this.curBizId}`)
    if (+this.curBizId === -1) return;
    needLoading && (this.isLoading = true);
    return getDashboardList({ bk_biz_id: this.curBizId })
      .then(list => {
        this.allGrafanaListMap = Array.isArray(list) ? list : list[this.curBizId] || [];
      })
      .catch(() => [])
      .finally(() => (this.isLoading = false));
  }

  /**
   * 删除已选择
   * @params index 数据索引
   */
  handleDelSelected(index: number) {
    this.selectedList.splice(index, 1);
    const isEixstActive = this.selectedList.find(checked => checked.id === this.selectedActive);
    !isEixstActive && (this.selectedActive = null);
    this.handleValueChange();
  }

  /**
   * 选择
   * @params index 数据索引
   */
  handleSelectItem(item: IGraphValueItem) {
    if (this.selectedActive === item.id) return;
    this.selectedActive = item.id;
    const ids = item.id.split('-');
    const isDefault = !(typeof +ids[0] === 'number' && this.bizIdList.find(item => item.id === ids[0]));
    if (!isDefault && !this.bizIdList.find(item => item.id === ids[0])) return;
    // eslint-disable-next-line prefer-destructuring
    this.leftActive = ids[1];
    this.tool.show = true;
    this.tool.active = isDefault ? 'default' : 'grafana';
    // eslint-disable-next-line prefer-destructuring
    this.tool.active === 'default' ? (this.DefaultCurBizIdList = ids[0].split(',')) : (this.curBizId = ids[0]);
    this.rightSelect = deepClone(this.selectedList);
  }

  /**
   * 新建图表
   */
  handleAddChart() {
    this.rightSelect = deepClone(this.selectedList);
    this.tool.show = true;
  }

  /**
   * 左侧选中操作
   */
  async handleSelectLeftItem(item: IChartListAllItem) {
    item.bk_biz_id && (this.curBizId = `${item.bk_biz_id}`);
    this.leftActive = item.uid;
    this.isRightListLoading = true;
    let graphPanelsList = [];
    if (this.tool.active === 'default') {
      graphPanelsList = this.allDefaultList.find(i => i.panels).panels;
      this.isRightListLoading = false;
    } else {
      graphPanelsList = await this.getPanelsList(this.leftActive);
    }
    graphPanelsList.forEach(panel => {
      const bizId = this.tool.active === 'default' ? this.DefaultCurBizIdList.sort().join(',') : this.curBizId;
      panel.fatherId = item.uid;
      panel.key = `${bizId}-${this.leftActive}-${panel.id}`;
    });
    this.rightList = graphPanelsList.filter(item => this.leftActive === item.fatherId && !/^-1/.test(item.key)) || [];
  }

  /**
   * 确认操作
   */
  handleComfirm() {
    this.$parent?.handlerFocus();
    // this.selectedList = [...new Set(deepClone(this.rightSelect))].map(item => `${item}`)
    this.selectedList = deepClone(this.rightSelect);
    this.rightSelect = [];
    this.handleValueChange();
    this.tool.show = false;
    this.selectedActive = null;
  }

  /**
   * 取消操作
   */
  handleCancel() {
    this.tool.show = false;
    this.selectedActive = null;
    this.rightSelect = [];
  }

  handleTabChange() {
    this.tool.active === 'default'
      ? (this.DefaultCurBizIdList = [`${+window.cc_biz_id > -1 ? window.cc_biz_id : 'all'}`])
      : (this.curBizId = `${window.cc_biz_id}`);
    this.selectedActive = '';
    this.rightList = [];
    this.leftActive = null;
  }

  handleChangeBizIdList(list) {
    this.DefaultCurBizIdList = list;
    // const leng = list.length;
    // const lastChild = list[leng - 1];
    // const firstChild = list[0];
    // const { radioMap } = this;
    // const isAllRadio = list.every(item => radioMap.includes(item));
    // if (radioMap.includes(lastChild)) {
    //   this.DefaultCurBizIdList = [lastChild];
    // }
    // if (radioMap.includes(firstChild) && !isAllRadio && leng > 1) {
    //   this.DefaultCurBizIdList = this.DefaultCurBizIdList.filter(item => !radioMap.includes(item));
    // }
  }

  handleGraphBizid(v) {
    if (this.tool.active === 'default') return;
    if (v.length) {
      [this.curBizId] = v;
    }
    this.rightList = [];
    this.getChartList(true);
  }

  handleBelonging(item) {
    const res = item.id.split('-');
    const str = this.radioMap.includes(res[0]) ? this.defaultRadioList.find(item => item.id === res[0])?.title : res[0];
    return str;
  }

  /**
   * 以下为拖拽操作
   */
  handleDragStart(e: DragEvent, index: number) {
    this.DragData.from = index;
  }
  handleDragOver(e: DragEvent) {
    e.preventDefault();
    e.dataTransfer.effectAllowed = 'move';
  }
  handleDragEnd() {
    this.DragData = {
      from: null,
      to: null,
      toActive: null,
    };
  }
  handleDrop() {
    const { from, to } = this.DragData;
    if (from === to) return;
    const list = deepClone(this.selectedList);
    const temp = list[from];
    list.splice(from, 1);
    list.splice(to, 0, temp);
    this.handleValueChange(list);
  }
  handleDragEnter(e: DragEvent, index: number) {
    this.DragData.to = index;
    this.DragData.toActive = index;
  }
}
</script>

<style lang="scss" scoped>
.select-chart-wrap {
  .flip-list-move {
    transition: transform 0.5s;
  }

  .selected-list-wrap {
    width: 465px;
    margin-bottom: 6px;
    border: 1px solid #dcdee5;

    .selected-item {
      display: flex;
      align-items: center;
      height: 38px;
      cursor: pointer;
      background: #fff;

      &:hover {
        background-color: #eef5ff;
      }

      &:not(:last-child) {
        border-bottom: 1px solid #dcdee5;
      }

      .icon-drag {
        position: relative;
        display: inline-block;
        flex-shrink: 0;
        width: 6px;
        height: 14px;
        margin: 0 8px;
        cursor: move;

        &::after {
          position: absolute;
          top: 0;
          width: 2px;
          height: 14px;
          content: ' ';
          border-right: 2px dotted #63656e;
          border-left: 2px dotted #63656e;
        }
      }

      .item-title {
        display: flex;
        flex: 1;
        align-items: center;

        .des {
          display: inline-block;
          max-width: 300px;
          overflow: hidden;
          color: #979ba5;
          text-overflow: ellipsis;
          white-space: nowrap;
        }
      }

      .icon-mc-close {
        display: flex;
        flex-shrink: 0;
        align-items: center;
        justify-content: center;
        width: 24px;
        height: 24px;
        margin-right: 3px;
        font-size: 24px;
        cursor: pointer;
      }
    }

    .active {
      background-color: #eef5ff;
    }
  }

  .add-btn-wrap {
    .add-btn {
      display: flex;
      align-items: center;
      width: 100px;
      font-size: 14px;
      color: #63656e;
      cursor: pointer;

      .icon-mc-add {
        font-size: 32px;
        color: #3a84ff;
      }
    }
  }

  .select-tool-wrap {
    display: flex;
    width: 664px;
    height: 327px;
    margin-top: 7px;
    background: #fff;
    border: 1px solid #dcdee5;
    border-radius: 2px 2px 0px 0px;

    .tool-left-wrap {
      flex: 278px 0;
      width: 278px;
      border-right: 1px solid #dcdee5;

      .tab-wrap {
        height: 32px;
        background-color: #fafbfd;
        border-bottom: 1px solid #dcdee5;

        :deep(.bk-tab-header) {
          /* stylelint-disable-next-line declaration-no-important */
          height: 100% !important;

          .bk-tab-label-wrapper {
            /* stylelint-disable-next-line declaration-no-important */
            height: 100% !important;

            .bk-tab-label-list {
              /* stylelint-disable-next-line declaration-no-important */
              height: 100% !important;

              .bk-tab-label-item {
                display: flex;
                align-items: center;
                justify-content: center;
              }

              .bk-tab-label {
                // height: 100%;
                font-size: 12px;
                line-height: 1;
              }
            }
          }
        }

        :deep(.bk-tab-label-list) {
          display: flex;
          width: 100%;
          padding: 0 20px;

          /* stylelint-disable-next-line no-descending-specificity */
          .bk-tab-label-item {
            flex: 1;
            min-width: 0;
            padding-right: 10px;
            padding-left: 10px;

            &.active {
              &::after {
                left: 0;
                width: 100%;
              }
            }
          }
        }

        :deep(.bk-tab-section) {
          padding: 0;
        }
      }

      .left-list-wrap {
        height: calc(100% - 78px);
        overflow-y: auto;

        .left-list-item {
          height: 32px;
          padding: 0 12px;
          font-size: 12px;
          line-height: 32px;
          color: #63656e;
          cursor: pointer;

          &:hover {
            background-color: #eef5ff;
          }
        }

        .active {
          background-color: #eef5ff;
        }
      }
      // .no-bk-biz-select {
      //   height: calc(100% - 40px);
      // }
      .biz-list-wrap {
        margin: 10px 12px 5px 12px;
      }
    }

    .tool-right-wrap {
      flex: 1;
      padding: 10px 0 0 14px;

      .right-title {
        height: 16px;
        margin-bottom: 9px;
        font-size: 12px;
        line-height: 16px;
        color: #c4c6cc;
        text-align: left;
      }

      .right-list-wrap {
        height: calc(100% - 68px);
        overflow-y: auto;
      }

      .right-btn-wrap {
        padding-right: 12px;
        margin-top: 4px;
        font-size: 0;
        text-align: right;

        & > :not(:last-child) {
          margin-right: 12px;
        }
      }
    }
  }
}
</style>
