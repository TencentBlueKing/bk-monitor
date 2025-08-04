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
    v-bkloading="{ isLoading }"
    class="select-chart-wrap"
  >
    <div class="select-tool-wrap">
      <div class="tool-left-wrap">
        <div class="tool-left-tab-wrap">
          <bk-tab
            class="tab-wrap"
            :active.sync="tool.active"
            type="card"
            @tab-change="handleTabChange"
          >
            <bk-tab-panel
              v-for="(tab, index) in tool.tabList"
              v-bind="tab"
              :key="index"
            />
          </bk-tab>
          <div class="placeholder-box" />
        </div>
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
        <div class="chart-dashboard-container">
          <div class="left-panel">
            <div
              v-show="tool.active === 'default'"
              class="biz-list-wrap"
            >
              <space-select
                :need-alarm-option="false"
                :need-authority-option="false"
                :need-defalut-options="true"
                :space-list="$store.getters.bizList"
                :value="DefaultCurBizIdList"
                @change="handleChangeBizIdList"
              />
              <bk-input
                v-model="defaultKeyWord"
                class="search-input"
                :clearable="true"
                :placeholder="$t('搜索 内置')"
                :right-icon="'bk-icon icon-search'"
                @change="handleDefaultSearch"
              />
            </div>
            <div
              v-if="tool.active === 'grafana'"
              class="biz-list-wrap"
            >
              <space-select
                :multiple="false"
                :need-alarm-option="false"
                :need-authority-option="false"
                :space-list="$store.getters.bizList"
                :value="[curBizId]"
                @change="handleGraphBizid"
              />
              <bk-input
                v-model="grafanaKeyWord"
                class="search-input"
                :clearable="true"
                :placeholder="$t('搜索 仪表盘')"
                :right-icon="'bk-icon icon-search'"
                @change="handleGrafanaSearch"
              />
            </div>
            <div class="left-list-wrap">
              <div
                v-for="(item, index) in leftList"
                :key="index"
                v-bk-overflow-tips
                :class="['left-list-item', { active: leftActive === item.uid }]"
                @click="handleSelectLeftItem(item)"
              >
                {{ item.name }}
              </div>
              <bk-exception
                v-if="exceptionType"
                class="exception"
                scene="part"
                :type="exceptionType"
              />
            </div>
          </div>
          <div class="right-panel">
            <div class="right-title">
              {{ $t('可选图表') }}
              <span class="chart-count">{{ `( ${rightList.length} )` }}</span>
            </div>
            <bk-input
              v-model="chartKeyWord"
              class="chart-search-input"
              :clearable="true"
              :placeholder="$t('搜索 图表')"
              :right-icon="'bk-icon icon-search'"
              @change="handleChartSearch"
            />
            <div
              v-bkloading="{ isLoading: isRightListLoading }"
              class="right-list-wrap"
            >
              <checkbox-group
                v-model="rightSelect"
                :active="selectedActive"
                :disabled="isDisabled"
                :list="rightList"
                @valueChange="handleValueChange"
              />
              <bk-exception
                v-if="!rightList.length"
                class="exception"
                scene="part"
                :type="chartKeyWord ? 'search-empty' : 'empty'"
              />
            </div>
          </div>
        </div>
      </div>
      <div class="selected-chart">
        <div class="container">
          {{ $t('已选图表') }} <span class="selected-chart-count">{{ `( ${selectedList.length} )` }}</span>
          <bk-button
            class="clear-button"
            :text="true"
            @click="handleClrSelected"
          >
            {{ $t('清空') }}
          </bk-button>
        </div>
        <transition-group
          class="selected-list-wrap"
          name="flip-list"
          tag="ul"
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
            @dragend="handleDragEnd($event, index)"
            @dragenter="handleDragEnter($event, index)"
            @dragover="handleDragOver($event, index)"
            @dragstart="handleDragStart($event, index)"
            @drop="handleDrop($event, index)"
          >
            <div class="selected-item-title">
              <span class="icon-monitor icon-mc-tuozhuai" />
              <span
                v-bk-overflow-tips
                class="item-title"
                >{{ item.name }}</span
              >
              <span
                class="icon-monitor icon-mc-close"
                @click.stop="handleDelSelected(index)"
              />
            </div>
            <span
              v-bk-tooltips="{ content: handleBelonging(item), delay: 300, allowHTML: false }"
              class="des"
              >{{ `${$t('所属:')}&nbsp;&nbsp;${handleBelonging(item)}` }}</span
            >
          </li>
        </transition-group>
        <bk-exception
          v-if="!selectedList.length"
          class="exception"
          scene="part"
          type="empty"
        />
      </div>
    </div>
  </div>
</template>

<script lang="ts">
import { Component, Emit, Model, Vue, Watch } from 'vue-property-decorator';

import { getDashboardList } from 'monitor-api/modules/grafana';
import { buildInMetric, getPanelsByDashboard } from 'monitor-api/modules/report';
import { deepClone } from 'monitor-common/utils/utils';

import SpaceSelect from '../../../components/space-select/space-select';
import checkboxGroup from './checkboxGroup.vue';
import { defaultRadioList } from './store';

import type {
  IAddChartToolData,
  IChartDataItem,
  IChartListAllItem,
  IDefaultRadioList,
  IGraphValueItem,
} from '../types';

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

  // 仪表盘搜索关键字
  grafanaKeyWord: string = null;
  defaultKeyWord: string = null;
  chartKeyWord: string = null;
  graphPanelsList: IChartDataItem[] = [];

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
    const list = this.tool.active === 'default' ? this.allDefaultList : this.allGrafanaListMap;
    const keyWord = this.tool.active === 'default' ? this.defaultKeyWord : this.grafanaKeyWord;
    return keyWord ? list.filter(item => item.text.toLowerCase().includes(keyWord.toLowerCase())) : list;
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

  // 内置  / 仪表盘 空数据类型
  get exceptionType(): string {
    // 选择使用的关键字
    const selectedKeyWord = this.tool.active === 'grafana' ? this.grafanaKeyWord : this.defaultKeyWord;
    // 根据条件返回异常类型
    if (!this.leftList.length) {
      return selectedKeyWord ? 'search-empty' : 'empty';
    }
    // 如果没有需要显示的异常类型，返回 null
    return null;
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
   * 清空已选择
   */
  handleClrSelected() {
    this.selectedList = [];
    this.selectedActive = null;
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

    this.leftActive = ids[1];
    this.tool.active = isDefault ? 'default' : 'grafana';

    this.tool.active === 'default' ? (this.DefaultCurBizIdList = ids[0].split(',')) : (this.curBizId = ids[0]);
    this.rightSelect = deepClone(this.selectedList);
  }

  /**
   * 左侧选中操作
   */
  async handleSelectLeftItem(item: IChartListAllItem) {
    item.bk_biz_id && (this.curBizId = `${item.bk_biz_id}`);
    this.leftActive = item.uid;
    this.isRightListLoading = true;
    this.graphPanelsList = [];
    if (this.tool.active === 'default') {
      this.graphPanelsList = this.allDefaultList.find(i => i.panels).panels;
      this.isRightListLoading = false;
    } else {
      this.graphPanelsList = await this.getPanelsList(this.leftActive);
    }
    this.graphPanelsList.forEach(panel => {
      const bizId = this.tool.active === 'default' ? this.DefaultCurBizIdList.sort().join(',') : this.curBizId;
      panel.fatherId = item.uid;
      panel.key = `${bizId}-${this.leftActive}-${panel.id}`;
    });
    this.rightList =
      this.graphPanelsList.filter(item => this.leftActive === item.fatherId && !/^-1/.test(item.key)) || [];
  }

  /**
   * 更新可选图表
   */
  updateRightList() {
    const filteredList = this.graphPanelsList.filter(
      item =>
        this.leftActive === item.fatherId &&
        !/^-1/.test(item.key) &&
        (!this.chartKeyWord || item.title.toLowerCase().includes(this.chartKeyWord.toLowerCase())) // 使用搜索关键字进行过滤
    );
    this.rightList = filteredList || [];
  }

  handleGrafanaSearch(v) {
    this.grafanaKeyWord = v;
  }
  handleDefaultSearch(v) {
    this.defaultKeyWord = v;
  }
  handleChartSearch(v) {
    this.chartKeyWord = v;
    this.updateRightList();
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

  .select-tool-wrap {
    display: flex;
    width: 810px;
    height: 480px;
    margin-top: 7px;
    background: #fff;
    border: 1px solid #dcdee5;
    border-top: 0;
    border-radius: 2px;

    .tool-left-wrap {
      width: 570px;

      .tool-left-tab-wrap {
        display: flex;

        .tab-wrap {
          width: 176px;
          height: 42px;
          background-color: #fafbfd;

          :deep(.bk-tab-header) {
            /* stylelint-disable-next-line declaration-no-important */
            height: 100% !important;

            .bk-tab-label-list {
              /* stylelint-disable-next-line declaration-no-important */
              height: 100% !important;
            }
          }

          :deep(.bk-tab-label-list) {
            display: flex;

            .bk-tab-label-item {
              display: flex;
              flex: 1;
              align-items: center;
              justify-content: center;
              min-width: 0;
              border-bottom: 1px solid #dcdee5;

              &.active {
                border-bottom: none;

                &::after {
                  position: absolute;
                  top: -1px;
                  right: 0;
                  width: 100%;
                  height: 4px;
                  content: '';
                  background-color: #3a84ff;
                }
              }

              .bk-tab-label {
                font-size: 12px;
              }
            }
          }

          :deep(.bk-tab-section) {
            padding: 0;
            border: none;
          }
        }

        .placeholder-box {
          flex: 1;
          height: 42px;
          background: #fafbfd;
          border-top: 1px solid #dcdee5;
          border-bottom: 1px solid #dcdee5;
        }
      }

      .chart-dashboard-container {
        display: flex;
        height: calc(100% - 42px);
        padding-top: 12px;

        .left-panel {
          width: 280px;
          height: 100%;

          .biz-list-wrap {
            margin: 0px 13px 4px 11px;

            .search-input {
              margin-top: 8px;
            }
          }

          .left-list-wrap {
            position: relative;
            height: calc(100% - 76px);
            overflow-y: auto;

            .left-list-item {
              height: 32px;
              padding: 0 12px;
              overflow: hidden;
              font-size: 12px;
              line-height: 32px;
              color: #63656e;
              text-overflow: ellipsis;
              white-space: nowrap;
              cursor: pointer;

              &:hover {
                background-color: #eef5ff;
              }
            }

            .active {
              color: #3a84ff;
              background-color: #e1ecff;
            }
          }
        }

        .right-panel {
          flex: 1;
          height: 100%;
          border-left: 1px solid #dcdee5;

          .right-title {
            height: 32px;
            margin-bottom: 8px;
            margin-left: 12px;
            font-size: 12px;
            font-weight: 700;
            line-height: 32px;
            color: #313238;

            .chart-count {
              font-weight: 400;
            }
          }

          .chart-search-input {
            width: calc(100% - 24px);
            margin-left: 12px;
          }

          .right-list-wrap {
            height: calc(100% - 70px);
            overflow-y: auto;

            .checkbox-group-wrap {
              padding-right: 12px;
              margin-left: 12px;
            }
          }
        }
      }
    }

    .selected-chart {
      position: relative;
      flex: 1;
      width: 240px;
      padding: 10px 12px 0;
      line-height: 1;
      background: #f5f7fa;
      border-top: 1px solid #dcdee5;
      border-left: 1px solid #dcdee5;

      .container {
        display: flex;
        align-items: center;
        justify-content: space-between;
        font-size: 12px;
        font-weight: 700;
        color: #313238;

        .selected-chart-count {
          margin-left: 4px;
          font-weight: normal;
        }

        .clear-button {
          margin-left: auto;
          font-size: 12px;
          font-weight: normal;
        }
      }

      .selected-list-wrap {
        height: calc(100% - 32px);
        margin: 10px 0 6px;
        overflow-y: auto;

        & > :not(:first-child) {
          margin-top: 2px;
        }

        .selected-item {
          height: 44px;
          padding-top: 2px;
          cursor: pointer;
          background: #fff;
          border-radius: 2px;
          box-shadow: 0 1px 1px 0 #00000014;

          .selected-item-title {
            display: flex;
            align-items: center;
          }

          .des {
            display: inline-block;
            max-width: 300px;
            margin-left: 24px;
            overflow: hidden;
            color: #979ba5;
            text-overflow: ellipsis;
            white-space: nowrap;
          }

          .icon-mc-tuozhuai {
            display: inline-block;
            flex-shrink: 0;
            margin: 0 6px 0 8px;
            font-size: 10px;
            color: #979ba5;
            cursor: move;
          }

          .item-title {
            display: inline-block;
            width: 162px;
            height: 20px;
            overflow: hidden;
            font-size: 12px;
            line-height: 20px;
            color: #313238;
            text-overflow: ellipsis;
            white-space: nowrap;
          }

          .icon-mc-close {
            display: flex;
            align-items: center;
            justify-content: center;
            width: 24px;
            height: 24px;
            margin-right: 3px;
            font-size: 18px;
            color: #979ba5;
            cursor: pointer;
            visibility: hidden;
          }

          &:hover {
            background-color: #eaebf0;

            .icon-mc-close {
              visibility: visible;
            }
          }
        }
      }
    }
  }

  .exception {
    position: absolute;
    top: 50%;
    left: 50%;
    transform: translate(-50%, -50%);
  }
}
</style>
