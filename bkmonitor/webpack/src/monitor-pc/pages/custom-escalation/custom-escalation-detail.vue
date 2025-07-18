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
<!--
 * @Date: 2021-06-14 21:01:49
 * @LastEditTime: 2021-06-14 21:06:48
 * @Description:
-->
<template>
  <div
    class="custom-detail-page-component"
    v-bkloading="{ isLoading: loading }"
  >
    <common-nav-bar
      class="common-nav-bar-single"
      :need-back="true"
      :need-copy-link="true"
      :route-list="$store.getters.navRouteList"
      nav-mode="copy"
    >
      <template slot="append">
        <span
          class="icon-monitor icon-audit"
          :class="{ active: isShowRightWindow }"
          @click="isShowRightWindow = !isShowRightWindow"
        />
      </template>
    </common-nav-bar>
    <bk-alert class="hint-alert">
      <i18n
        slot="title"
        path="数据上报好了，去 {0}"
      >
        <span
          style="color: #3a84ff; cursor: pointer"
          @click="handleJump"
        >
          {{ $t('查看数据') }}
        </span>
      </i18n>
    </bk-alert>
    <div class="custom-detail-page">
      <div class="custom-detail">
        <!-- 详情信息，名字可修改 -->
        <div class="detail-information">
          <div class="detail-information-title">
            {{ $t('基本信息') }}
          </div>
          <div class="detail-information-row">
            <span class="row-label">{{ $t('数据ID') }} : </span>
            <span
              class="row-content"
              v-bk-overflow-tips
              >{{ detailData.bk_data_id }}</span
            >
          </div>
          <div class="detail-information-row">
            <span class="row-label">Token : </span>
            <span
              class="row-content"
              v-bk-overflow-tips
              >{{ detailData.access_token }}</span
            >
          </div>
          <div class="detail-information-row">
            <span class="row-label">{{ $t('名称') }} : </span>
            <div
              v-if="!isShowEditName"
              style="display: flex; min-width: 0"
            >
              <span
                class="row-content"
                v-bk-overflow-tips
                >{{ detailData.name }}</span
              >
              <i
                v-if="detailData.name && !isReadonly"
                class="icon-monitor icon-bianji edit-name"
                @click="handleShowEdit"
              />
            </div>
            <bk-input
              v-else
              ref="nameInput"
              style="width: 240px"
              v-model="copyName"
              @blur="handleEditName"
            />
          </div>
          <div class="detail-information-row">
            <span class="row-label">{{ $t('英文名') }} : </span>
            <div
              v-if="!isShowEditDataLabel"
              style="display: flex; min-width: 0"
            >
              <span
                class="row-content"
                v-bk-overflow-tips
                >{{ detailData.data_label || '--' }}</span
              >
              <i
                v-if="!isShowEditDataLabel && !isReadonly"
                class="icon-monitor icon-bianji edit-name"
                @click="handleShowEditDataLabel"
              />
            </div>
            <bk-input
              v-else
              ref="dataLabelInput"
              style="width: 240px"
              v-model="copyDataLabel"
              @blur="handleEditDataLabel"
            />
          </div>
          <div class="detail-information-row">
            <span class="row-label">{{ $t('监控对象') }} : </span>
            <span
              class="row-content"
              v-bk-overflow-tips
              >{{ scenario }}</span
            >
          </div>
          <div
            v-if="type !== 'customEvent'"
            class="detail-information-row"
          >
            <span class="row-label">{{ $t('上报协议') }} : </span>
            <span
              v-if="detailData.protocol"
              class="row-content"
              v-bk-overflow-tips
            >
              {{ detailData.protocol === 'json' ? 'JSON' : 'Prometheus' }}
            </span>
            <span v-else> -- </span>
          </div>
          <div
            class="detail-information-row"
            :class="type === 'customEvent' ? 'last-row' : ''"
          >
            <span class="row-label">{{ type === 'customEvent' ? $t('是否为平台事件') : $t('作用范围') }} : </span>
            <bk-checkbox
              v-if="type === 'customEvent'"
              v-model="copyIsPlatform"
              :disabled="!isShowEditIsPlatform"
              @change="handleIsPlatformChange"
            />
            <span
              v-else
              class="row-content"
              v-bk-overflow-tips
            >
              {{ copyIsPlatform === false ? $t('本业务') : $t('全平台') }}
            </span>
          </div>
          <div
            v-if="type !== 'customEvent'"
            class="detail-information-row last-row"
          >
            <span class="row-label">{{ $t('描述') }} : </span>
            <div
              v-if="!isShowEditDesc"
              style="display: flex; min-width: 0"
            >
              <span
                class="row-content"
                v-bk-overflow-tips
                >{{ detailData.desc || '--' }}</span
              >
              <i
                v-if="!isReadonly"
                class="icon-monitor icon-bianji edit-name"
                @click="handleShowEditDes"
              />
            </div>
            <bk-input
              v-else
              ref="describeInput"
              style="width: 440px"
              class="form-content-textarea"
              v-model="copyDescribe"
              :rows="3"
              type="textarea"
              @blur="handleEditDescribe"
            />
          </div>
        </div>
        <!-- 自定义事件展示 -->
        <template v-if="type === 'customEvent'">
          <!-- 拉取的事件列表 -->
          <div
            class="detail-information detail-list"
            v-bkloading="{ isLoading: eventDataLoading }"
          >
            <div class="list-header">
              <div class="list-header-title">
                {{ $t('事件列表') }}
              </div>
              <bk-button
                class="list-header-immediately"
                v-bk-tooltips="{
                  content: $tc('刷新'),
                }"
                icon="icon-monitor icon-mc-alarm-recovered"
                @click="() => handleRefreshNow(true)"
              />
              <bk-select
                class="list-header-refresh"
                v-model="refreshList.value"
                :clearable="false"
                @change="handleRefreshChange"
              >
                <bk-option
                  v-for="(opt, index) in refreshList.list"
                  :id="opt.value"
                  :key="index"
                  :name="opt.name"
                />
              </bk-select>
              <bk-select
                class="list-header-date"
                v-model="shortcuts.value"
                :clearable="false"
                :popover-min-width="110"
                @change="handleTimeChange"
              >
                <bk-option
                  v-for="(opt, index) in shortcuts.list"
                  :id="opt.value"
                  :key="index"
                  :name="opt.name"
                />
              </bk-select>
            </div>
            <bk-table
              class="custom-event-table"
              :data="eventData"
              :height="tableVirtualRenderHeight"
              :outer-border="false"
              row-key="custom_event_id"
              virtual-render
            >
              <bk-table-column
                :label="$t('事件名称')"
                min-width="100"
                prop="custom_event_name"
              />
              <bk-table-column
                :label="$t('目标数量')"
                min-width="50"
              >
                <template #default="{ row }">
                  <div class="num-set">
                    {{ row.target_count }}
                  </div>
                </template>
              </bk-table-column>
              <bk-table-column
                :label="$t('事件数量')"
                min-width="50"
              >
                <template #default="{ row }">
                  <div class="num-set">
                    {{ row.event_count }}
                  </div>
                </template>
              </bk-table-column>
              <bk-table-column
                :label="$t('关联策略')"
                min-width="50"
              >
                <template #default="{ row }">
                  <span
                    :class="['num-set', { 'col-btn': row.related_strategies.length > 0 }]"
                    @click="handleGotoStrategy(row)"
                  >
                    {{ row.related_strategies.length }}
                  </span>
                  <!-- <div class="num-set"> {{ row.related_strategies.length }}</div> -->
                </template>
              </bk-table-column>
              <bk-table-column
                :label="$t('最近变更时间')"
                min-width="100"
              >
                <template #default="{ row }">
                  <span>{{ row.last_change_time || '--' }}</span>
                </template>
              </bk-table-column>
              <bk-table-column
                :label="$t('操作')"
                min-width="80"
              >
                <template #default="{ row }">
                  <bk-button
                    ext-cls="col-operator"
                    theme="primary"
                    text
                    @click="handleOpenSideslider(row.last_event_content, row.custom_event_name)"
                  >
                    {{ $t('查看原始数据') }}
                  </bk-button>
                  <bk-button
                    ext-cls="col-operator"
                    theme="primary"
                    text
                    @click="handleAddStrategy(row)"
                  >
                    {{ $t('添加策略') }}
                  </bk-button>
                </template>
              </bk-table-column>
            </bk-table>
          </div>
          <!-- 查看原始数据侧滑栏 -->
          <bk-sideslider
            :is-show.sync="sideslider.isShow"
            :quick-close="true"
            :width="656"
          >
            <div
              class="sideslider-title"
              slot="header"
            >
              <span>{{ sideslider.title + $t(' - 原始数据') }}</span>
              <span class="title-explain">{{ $t('（仅支持查看当前事件中最近一条的原始数据信息）') }}</span>
            </div>
            <div slot="content">
              <monaco-editor
                style="height: calc(100vh - 61px)"
                :language="'json'"
                :options="{ readOnly: true }"
                :value="JSON.stringify(sideslider.data, null, '\t')"
              />
            </div>
          </bk-sideslider>
        </template>
        <!-- 自定义指标展示 -->
        <template v-else>
          <div class="detail-information detail-list">
            <div class="list-header mb16">
              <div class="list-header-title">
                <span>{{ $t('时序列表') }}</span>
                <span class="title-desc">
                  {{ `（${$t('包括{0}个指标,{1}个维度', [metricNum, dimensionNum])}）` }}
                </span>
              </div>
            </div>
            <div class="button-control-wrap">
              <div class="button-control-left">
                <bk-button
                  class="mr10"
                  @click="() => handleShowGroupManage(true)"
                >
                  {{ $t('分组管理') }}
                </bk-button>
                <div class="search-select-wrap">
                  <search-select
                    :clearable="false"
                    :data="metricSearchData"
                    :model-value="metricSearchValue"
                    @change="handleMetricSearchValue"
                  />
                </div>
                <!-- <group-select
                  :list="groupSelectList"
                  :disabled="!selectionLeng"
                  v-model="batchGroupValue"
                  @change="handleBatchValueChange"
                  @list-change="(list) => (groupSelectList = list)"
                >
                  <bk-button icon-right="icon-angle-down" :disabled="!selectionLeng"
                  >{{ $t('批量分组') }}<span v-show="selectionLeng">{{ `(${selectionLeng})` }}</span></bk-button
                  >
                </group-select>
                <monitor-import
                  style="margin-right: 0; margin-left: 10px"
                  accept="application/json"
                  :return-text="true"
                  :base64="false"
                  @change="handleImportMetric"
                >
                  <bk-button>{{ $t('导入') }}</bk-button>
                </monitor-import>
                <monitor-export @click="handleExportMetric">
                  <bk-button>{{ $t('导出') }}</bk-button>
                </monitor-export> -->
              </div>
              <monitor-import
                style="margin-right: 24px"
                :base64="false"
                :return-text="true"
                accept=".csv"
                @change="handleImportMetric"
              >
                <span class="icon-monitor icon-xiazai2 link" />
                <span class="link">{{ $t('导入') }}</span>
              </monitor-import>
              <!-- <monitor-export @click="handleExportMetric"
                              style="margin-right: 24px;">
                <span class="icon-monitor icon-shangchuan link"></span>
                <span>{{ $t('导出') }}</span>
              </monitor-export> -->
              <span
                class="export-btn"
                @click="handleExportMetric"
              >
                <span class="icon-monitor icon-shangchuan link" />
                <span>{{ $t('导出') }}</span>
              </span>
              <div class="list-header-button">
                {{ $t('预览') }}
              </div>
              <bk-switcher
                v-model="isShowData"
                size="small"
                theme="primary"
                @change="handleShowDataChange"
              />
            </div>
            <!-- 指标/维度表 -->
            <div class="table-box">
              <div
                class="left-table"
                :class="{ 'left-active': isShowData }"
              >
                <bk-table
                  :data="metricTable"
                  :outer-border="true"
                >
                  <div
                    v-if="!!selectionLeng"
                    class="table-prepend"
                    slot="prepend"
                  >
                    <span class="add-msg">
                      <i18n path="当前已选择{0}条数据">
                        <span>{{ selectionLeng }}</span>
                      </i18n>
                    </span>
                    ,
                    <group-select-multiple
                      :list="groupSelectList"
                      :value="batchGroupValue"
                      @change="handleBatchGroupChange"
                      @toggle="handleBatchGroupToggle"
                    >
                      <span class="prepend-add-btn">
                        {{ $t('加入分组') }}
                        <span class="icon-monitor icon-mc-triangle-down" />
                      </span>
                      <template slot="extension">
                        <div
                          class="edit-group-manage"
                          @click="() => handleShowGroupManage(true)"
                        >
                          <span class="icon-monitor icon-shezhi" />
                          <span>{{ $t('分组管理') }}</span>
                        </div>
                      </template>
                    </group-select-multiple>
                    <!-- <group-select
                      :list="groupSelectList"
                      :disabled="!selectionLeng"
                      v-model="batchGroupValue"
                      @change="handleBatchValueChange"
                      @list-change="(list) => (groupSelectList = list)"
                    >
                      <span class="prepend-add-btn">
                        {{ $t('加入分组') }}
                        <span class="icon-monitor icon-mc-triangle-down"></span>
                      </span>
                    </group-select> -->
                  </div>
                  <bk-table-column
                    width="80"
                    :render-header="renderSelectionHeader"
                    align="center"
                  >
                    <template #default="{ row }">
                      <bk-checkbox
                        v-model="row.selection"
                        :disabled="row.monitor_type === 'dimension'"
                        @change="handleRowCheck($event, row)"
                      />
                    </template>
                  </bk-table-column>
                  <!-- 指标/维度 -->
                  <bk-table-column
                    width="150"
                    :label="$t('指标/维度')"
                    :render-header="renderMetricHeader"
                  >
                    <template slot-scope="scope">
                      {{ scope.row.monitor_type === 'metric' ? $t('指标') : $t('维度') }}
                    </template>
                  </bk-table-column>
                  <!-- 分组 -->
                  <bk-table-column
                    :label="$t('分组')"
                    :render-header="renderGroupHeader"
                    min-width="160"
                  >
                    <template slot-scope="scope">
                      <div style="display: flex">
                        <template v-if="scope.row.monitor_type === 'metric'">
                          <group-select-multiple
                            :groups-map="groupsMap"
                            :list="groupSelectList"
                            :metric-name="scope.row.name"
                            :value="scope.row.labels.map(item => item.name)"
                            @change="v => handleSelectGroup(v, scope.$index)"
                            @toggle="handleGroupSelectToggle"
                          >
                            <template v-if="scope.row.labels && scope.row.labels.length">
                              <div class="table-group-tags">
                                <span
                                  v-for="item in scope.row.labels.map(item => item.name)"
                                  class="table-group-tag"
                                  :key="item"
                                  @mouseenter="e => handleGroupTagTip(e, item)"
                                  @mouseleave="handleRemoveGroupTip"
                                >
                                  {{ item }}
                                </span>
                              </div>
                            </template>
                            <template v-else>
                              <div class="table-group-select">
                                {{ $t('未分组') }}<i class="icon-monitor icon-arrow-down" />
                              </div>
                            </template>
                            <template slot="extension">
                              <div
                                class="edit-group-manage"
                                @click="() => handleShowGroupManage(true)"
                              >
                                <span class="icon-monitor icon-shezhi" />
                                <span>{{ $t('分组管理') }}</span>
                              </div>
                            </template>
                          </group-select-multiple>
                          <!-- <group-select
                            style="margin-left: -8px"
                            v-model="scope.row.label"
                            :list="groupSelectList"
                            @list-change="(list) => (groupSelectList = list)"
                          >
                            <div class="table-group-select">
                              {{ scope.row.label || $t('未分组') }}<i class="icon-monitor icon-arrow-down"></i>
                            </div>
                          </group-select> -->
                        </template>
                        <template v-else> -- </template>
                      </div>
                    </template>
                  </bk-table-column>
                  <!-- 英文名 -->
                  <bk-table-column
                    :label="$t('英文名')"
                    min-width="100"
                    prop="name"
                  >
                    <template slot-scope="scope">
                      <div
                        class="overflow-tips"
                        v-bk-overflow-tips
                      >
                        {{ scope.row.name }}
                      </div>
                    </template>
                  </bk-table-column>
                  <!-- 别名 -->
                  <bk-table-column
                    :label="$t('别名')"
                    min-width="100"
                    prop="description"
                  >
                    <template slot-scope="scope">
                      <div class="cell-margin name">
                        <bk-input
                          v-model="scope.row.description"
                          :class="{ 'input-err': scope.row.descReValue }"
                          :placeholder="scope.row.monitor_type === 'metric' ? $t('输入指标别名') : $t('输入维度别名')"
                          size="small"
                          @blur="handleCheckDescName(scope.row, scope.$index)"
                        />
                        <bk-popover
                          class="change-name"
                          :tippy-options="{ a11y: false }"
                          placemnet="top-start"
                          trigger="mouseenter"
                        >
                          <i
                            v-if="scope.row.descReValue"
                            class="icon-monitor icon-remind"
                          />
                          <div slot="content">
                            <template v-if="scope.row.descReValue">
                              {{ $t('注意: 名字冲突') }}
                            </template>
                          </div>
                        </bk-popover>
                      </div>
                    </template>
                  </bk-table-column>
                  <!-- 类型 -->
                  <bk-table-column
                    width="120"
                    :label="$t('类型')"
                    prop="type"
                  />
                  <!-- 单位 -->
                  <bk-table-column
                    width="170"
                    :label="$t('单位')"
                    :render-header="renderUnitHeader"
                    prop="unit"
                  >
                    <template slot-scope="scope">
                      <div
                        v-if="unit.value && unit.index === scope.$index && scope.row.monitor_type === 'metric'"
                        class="cell-margin"
                        @mouseleave="handleMouseLeave"
                      >
                        <bk-select
                          v-model="scope.row.unit"
                          :clearable="false"
                          :popover-width="180"
                          searchable
                          @toggle="handleToggleChange"
                        >
                          <bk-option-group
                            v-for="(group, index) in unitList"
                            :key="index"
                            :name="group.name"
                          >
                            <bk-option
                              v-for="option in group.formats"
                              :id="option.id"
                              :key="option.id"
                              :name="option.name"
                            />
                          </bk-option-group>
                        </bk-select>
                      </div>
                      <div
                        v-else
                        class="cell-span"
                        @mouseenter="handleMouseenter(scope.$index)"
                      >
                        {{ scope.row.monitor_type === 'metric' ? handleFindUnitName(scope.row.unit) : '--' }}
                      </div>
                    </template>
                  </bk-table-column>
                  <!-- 空数据 -->
                  <!-- <div
                    class="empty"
                    slot="empty"
                  >
                    <i class="icon-monitor icon-remind empty-icon" />
                    <div>{{ $t('暂无指标/维度') }}</div>
                  </div> -->
                  <div slot="empty">
                    <empty-status
                      :text-map="{
                        empty: $t('暂无指标/维度'),
                        'search-empty': $t('搜索结果为空'),
                      }"
                      :type="emptyType"
                      @operation="handleEmptyOperation"
                    ></empty-status>
                  </div>
                </bk-table>
              </div>
              <!-- 数据预览 -->
              <div
                class="right-data"
                v-show="isShowData"
              >
                <ul class="ul-head">
                  <li class="host-type">
                    {{ $t('数据') }}
                  </li>
                  <li class="data-time">{{ $t('数据时间:') }}{{ detailData.last_time || $t('无数据') }}</li>
                </ul>
                <template v-if="metricTable.length">
                  <div v-bkloading="{ isLoading: dataLoading }">
                    <div
                      v-if="!!selectionLeng"
                      class="space-item"
                    />
                    <div
                      v-for="(item, index) in metricTable"
                      class="data-preview"
                      :key="index"
                    >
                      {{ allDataPreview[item.name] || $t('近5分钟无数据上报') }}
                    </div>
                  </div>
                </template>
                <div
                  v-else
                  class="no-data-preview"
                />
              </div>
            </div>
            <bk-pagination
              class="list-pagination"
              v-show="metricTable.length"
              :count="pagination.total"
              :current="pagination.page"
              :limit="pagination.pageSize"
              :limit-list="pagination.pageList"
              align="right"
              size="small"
              pagination-able
              show-total-count
              @change="handlePageChange"
              @limit-change="handleLimitChange"
            />
          </div>
        </template>
        <span
          v-if="type === 'customTimeSeries'"
          class="submit-div"
          v-bk-tooltips="{
            content: $tc('非当前业务，不允许操作'),
            placements: ['top'],
            disabled: !isReadonly,
          }"
        >
          <bk-button
            v-if="type === 'customTimeSeries'"
            class="mc-btn-add"
            v-authority="{ active: !authority.MANAGE_CUSTOM_METRIC }"
            :disabled="isReadonly"
            theme="primary"
            @click="
              authority.MANAGE_CUSTOM_METRIC
                ? handleSubmit()
                : handleShowAuthorityDetail(customAuthMap.MANAGE_CUSTOM_METRIC)
            "
          >
            {{ $t('提交') }}
          </bk-button>
        </span>
      </div>
      <!-- 展开内容 -->
      <div
        class="right-window"
        :class="{ active: isShowRightWindow }"
      >
        <!-- 右边展开收起按钮 -->
        <div
          class="right-button"
          :class="{ 'active-buttom': isShowRightWindow }"
          @click="isShowRightWindow = !isShowRightWindow"
        >
          <i
            v-if="isShowRightWindow"
            class="icon-monitor icon-arrow-right icon"
          />
          <i
            v-else
            class="icon-monitor icon-arrow-left icon"
          />
        </div>
        <div class="right-window-title">
          <span>{{ type === 'customEvent' ? $t('自定义事件帮助') : $t('自定义指标帮助') }}</span>
          <span
            class="title-right"
            @click="isShowRightWindow = !isShowRightWindow"
          >
            <span class="line" />
          </span>
        </div>
        <div class="right-window-content">
          <div v-if="detailData.protocol !== 'prometheus'">
            <div class="content-title">
              {{ $t('注意事项') }}
            </div>
            <span>{{ $t('API频率限制 1000/min，单次上报Body最大为500KB') }}</span>
          </div>
          <div
            class="content-title"
            :class="detailData.protocol !== 'prometheus' ? 'content-interval' : ''"
          >
            {{ $t('使用方法') }}
          </div>
          <div class="content-row">
            <span>{{
              detailData.protocol === 'prometheus' ? $t('不同云区域上报端点信息') : $t('不同云区域Proxy信息')
            }}</span>
            <div class="content-example">
              <div
                v-for="(item, index) in proxyInfo"
                :key="index"
              >
                {{ $t('管控区域') }} {{ item.bkCloudId }} <span style="margin-left: 10px">{{ item.ip }}</span>
              </div>
            </div>
          </div>
          <div
            v-if="detailData.protocol !== 'prometheus'"
            class="content-row"
          >
            <span>{{ $t('命令行直接调用样例') }}</span>
            <div class="content-example">curl -g -X POST http://${PROXY_IP}:10205/v2/push/ -d "${REPORT_DATA}"</div>
          </div>
          <div v-if="detailData.protocol === 'prometheus'">
            <div class="content-title content-interval">
              {{ $t('数据上报端点样例') }}
            </div>
            <div class="content-row">
              <pre class="content-example">
                http://${PROXY_IP}:4318
              </pre>
            </div>
            <div class="content-row mt10">
              <div class="content-title content-interval">
                {{ $t('sdk接入流程') }}
              </div>
              <div>
                {{
                  $t(
                    '用户使用 prometheus 原始 SDK 上报即可，不过需要指定蓝鲸的上报端点（$host:$port）以及 HTTP Headers。'
                  )
                }}
              </div>
              <pre class="content-example">
              X-BK-TOKEN=$TOKEN
              </pre>
              <div class="mt10">
                {{ $t('prometheus sdk 库：https://prometheus.io/docs/instrumenting/clientlibs/') }}
              </div>
            </div>

            <div class="content-row mt10">
              <div>{{ $t('各语言接入示例') }} :</div>
              <div class="mt5">Golang</div>
              <div class="mt5">
                {{
                  $t(
                    '1. 补充 headers，用于携带 token 信息。定义 Client 行为，由于 prometheus sdk 没有提供新增或者修改 Headers 的方法，所以需要实现 Do() interface，代码示例如下：'
                  )
                }}
              </div>
              <div class="mt5">
                {{
                  $t(
                    '2. 填写上报端点，在 `push.New("$endpoint", name)` 里指定。然后需要将自定义的 client 传入到 `pusher.Client($bkClient{})` 里面。'
                  )
                }}
              </div>
              <div class="content-prometheus">
                <pre class="content-example">
                  {{ sdkData.preGoOne }}
                </pre>
                <div
                  class="content-copy-prometheus"
                  @click="handleCopyPrometheus('golangCopy')"
                >
                  <i class="icon-monitor icon-mc-copy"></i>
                </div>
                <textarea
                  ref="golangCopy"
                  class="copy-textarea"
                />
              </div>
            </div>
            <div class="content-row">
              <div>Python</div>
              <div class="mt5">
                {{ $t('1. 补充 headers，用于携带 token 信息。实现一个自定义的 handler。') }}
              </div>
              <div>
                {{
                  $t(
                    '2. 填写上报端点，在 `push_to_gateway("$endpoint", ...)` 里指定。然后将自定义的 handler 传入到函数里。'
                  )
                }}
              </div>
              <div class="content-prometheus">
                <pre class="content-example">
                  {{ sdkData.prePythonOne }}
                </pre>
                <div
                  class="content-copy-prometheus"
                  @click="handleCopyPrometheus('pythonCopy')"
                >
                  <i class="icon-monitor icon-mc-copy"></i>
                </div>
                <textarea
                  ref="pythonCopy"
                  class="copy-textarea"
                />
              </div>
            </div>
          </div>
          <div
            v-else
            class="content-row"
          >
            <span>{{ $t('数据上报格式样例') }}</span>
            <pre class="content-example">
              {{ preData }}
            </pre>
            <div
              class="content-copy"
              @click="handleCopyData"
            >
              <i class="icon-monitor icon-mc-copy"></i>
            </div>
            <textarea
              ref="textCopy"
              class="copy-textarea"
            />
          </div>
        </div>
      </div>
    </div>
    <group-manage-dialog
      v-if="type === 'customTimeSeries'"
      :groups="groupList"
      :id="detailData.time_series_group_id"
      :metric-list="metricList"
      :show="groupManage.show"
      @change="handleGroupListChange"
      @show="handleShowGroupManage"
    />
  </div>
</template>

<script lang="ts">
import { Component, Mixins, Ref } from 'vue-property-decorator';

import SearchSelect from '@blueking/search-select-v3/vue2';
import dayjs from 'dayjs';
import {
  createOrUpdateGroupingRule,
  customTsGroupingRuleList,
  modifyCustomTsGroupingRuleList,
  validateCustomEventGroupLabel,
  validateCustomTsGroupLabel,
  modifyCustomTimeSeriesDesc,
} from 'monitor-api/modules/custom_report';

import MonacoEditor from '../../components/editors/monaco-editor.vue';
import EmptyStatus from '../../components/empty-status/empty-status';
import MonitorExport from '../../components/monitor-export/monitor-export.vue';
import MonitorImport from '../../components/monitor-import/monitor-import.vue';
import TableFiter from '../../components/table-filter/table-filter-new.vue';
import authorityMixinCreate from '../../mixins/authorityMixin';
import { SET_NAV_ROUTE_LIST } from '../../store/modules/app';
import CommonNavBar from '../monitor-k8s/components/common-nav-bar';
import ColumnCheck from '../performance/column-check/column-check.vue';
import { downCsvFile } from '../view-detail/utils';
import * as customAuth from './authority-map';
import GroupManageDialog, { matchRuleFn } from './group-manage-dialog';
import GroupSelectMultiple from './group-select-multiple';
import { csvToArr } from './utils';

import type { EmptyStatusOperationType } from '../../components/empty-status/types';
import type {
  IDetailData,
  IEditParams,
  IParams,
  IRefreshList,
  IShortcuts,
  ISideslider,
} from '../../types/custom-escalation/custom-escalation-detail';
import type { CreateElement } from 'vue';

import '@blueking/search-select-v3/vue2/vue2.css';

const NULL_LABEL = '__null_label__';

interface IGroupListItem {
  name: string;
  matchRules: string[];
  manualList: string[];
  matchRulesOfMetrics?: string[]; // 匹配规则匹配的指标数
}

@Component({
  components: {
    MonacoEditor,
    MonitorExport,
    MonitorImport,
    CommonNavBar,
    GroupManageDialog,
    GroupSelectMultiple,
    SearchSelect,
    EmptyStatus,
  },
})
export default class CustomEscalationDetail extends Mixins(authorityMixinCreate(customAuth)) {
  @Ref('nameInput') readonly nameInput!: HTMLInputElement;
  @Ref() readonly dataLabelInput!: HTMLInputElement;
  @Ref() readonly describeInput!: HTMLInputElement;
  @Ref('textCopy') readonly textCopy!: HTMLTextAreaElement;
  @Ref('golangCopy') readonly golangCopy!: HTMLTextAreaElement;
  @Ref('pythonCopy') readonly pythonCopy!: HTMLTextAreaElement;
  customAuthMap = customAuth;
  loading = false;
  isCreat = ''; // 是否从创建过来
  // type = 'customEvent' // 展示类型：customEvent 自定义事件 customTimeSeries 自定义指标
  copyName = ''; // 修改的名字
  copyDataLabel = ''; // 修改的英文名
  copyDescribe = ''; // 修改的描述
  copyIsPlatform = false; // 是否为平台指标、事件
  isShowEditName = false; // 是否显示名字编辑框
  isShowRightWindow = true; // 是否显示右侧帮助栏
  isShowEditDataLabel = false; // 是否展示英文名编辑框
  isShowEditIsPlatform = false; // 是否展示平台师表
  isShowEditDesc = false; // 是否展示描述编辑框
  scenario = ''; // 分类
  protocol = ''; // 上报协议
  proxyInfo = []; // 云区域分类数据
  preData = ''; // 数据上报格式样例
  sdkData: any = {}; // sdk 接入数据
  timer = null; // 定时器
  //  详情数据
  detailData: IDetailData = {
    bk_data_id: '',
    access_token: '',
    name: '',
    scenario: '',
    scenario_display: [],
    data_label: '',
    is_platform: false,
    protocol: '',
    last_time: '',
  };

  //  侧滑栏内容数据 事件数据
  sideslider: ISideslider = {
    isShow: false,
    title: '',
    data: {}, //  原始数据
  };

  //  事件列表数据 事件数据
  eventData = [];

  //  指标维度数据 时序数据
  metricData = [];
  isShowData = true; // 是否展示数据预览 时序数据
  unitList = []; // 单位list
  unit = {
    value: true,
    index: -1,
    toggle: false,
  };

  //  时间选择器选择项
  shortcuts: IShortcuts = {
    list: [],
    value: 1,
  };
  refreshList: IRefreshList;
  pagination = {
    page: 1,
    pageSize: 20,
    total: 100,
    pageList: [10, 20, 50, 100],
  };
  tableId = '';
  metricValue = {};
  dataLoading = false;

  batchGroupValue = [];

  groupSelectList: any = [
    {
      id: '',
      name: '未分组',
    },
  ];

  allCheckValue: 0 | 1 | 2 = 0; // 0: 取消全选 1: 半选 2: 全选
  metricCheckList: any = [];
  groupFilterList: string[] = [];
  metricFilterList: string[] = [];
  unitFilterList: string[] = [];
  groupManage = {
    show: false,
  };
  metricSearchValue = [];
  /* 筛选条件(简化) */
  metricSearchObj = {
    type: [],
    name: [],
    enName: [],
    unit: [],
    text: [],
  };
  /* 分组管理列表 */
  groupList: IGroupListItem[] = [];
  /* 每个匹配规则包含指标 */
  matchRulesMap = new Map();
  /* 每个组所包含的指标 */
  groupsMap: Map<string, IGroupListItem> = new Map();
  /* 每个指标包含的组 */
  metricGroupsMap = new Map();
  /* 指标列表 */
  metricList = [];
  /* 分组标签pop实例 */
  groupTagInstance = null;
  /* 用于判断分组下拉列表展开期间是否选择过 */
  isUpdateGroup = false;

  /* 数据预览ALL */
  allDataPreview = {};

  eventDataLoading = false;

  /* 所有单位数据 */
  allUnitList = [];
  /* 列表中已选的单位数据 */
  tableAllUnitList = [];

  get metricSearchData() {
    return [
      {
        name: window.i18n.t('匹配方式'),
        id: 'type',
        multiple: false,
        children: [
          { id: 'auto', name: window.i18n.t('自动') },
          { id: 'manual', name: window.i18n.t('手动') },
        ],
      },
      {
        name: window.i18n.t('组名'),
        id: 'name',
        multiple: false,
        children: [],
      },
      {
        name: window.i18n.t('英文名'),
        id: 'enName',
        multiple: false,
        children: [],
      },
      {
        name: window.i18n.t('单位'),
        id: 'unit',
        multiple: false,
        children: this.allUnitList,
      },
    ];
  }
  //  指标数量
  get metricNum() {
    return this.metricData.filter(item => item.monitor_type === 'metric').length;
  }

  //  维度数量
  get dimensionNum() {
    return this.metricData.filter(item => item.monitor_type === 'dimension').length;
  }

  //  别名列表
  get descNameList() {
    return this.metricData.map(item => item.description);
  }
  get metricTable() {
    const labelsMatchTypes = labels => {
      let temp = [];
      for (const item of labels) {
        temp = temp.concat(item.match_type);
      }
      temp = [...new Set(temp)];
      return temp;
    };
    // 模糊匹配
    const fuzzyMatch = (str: string, pattern: string) => {
      const lowerStr = String(str).toLowerCase();
      const lowerPattern = String(pattern).toLowerCase();
      return lowerStr.includes(lowerPattern);
    };
    const leng1 = this.groupFilterList.length;
    const leng2 = this.metricFilterList.length;
    const leng3 = this.unitFilterList.length;
    const typeLeng = this.metricSearchObj.type.length;
    const nameLeng = this.metricSearchObj.name.length;
    const enNameLeng = this.metricSearchObj.enName.length;
    const unitLeng = this.metricSearchObj.unit.length;
    const textleng = this.metricSearchObj.text.length;
    const filterList = this.metricData.filter(item => {
      const isMetric = item.monitor_type === 'metric';
      return (
        (leng1
          ? this.groupFilterList.some(
              g => item.labels.map(l => l.name).includes(g) || (!item.labels.length && g === NULL_LABEL)
            ) && isMetric
          : true) &&
        (leng2 ? this.metricFilterList.includes(item.monitor_type) : true) &&
        (leng3
          ? this.unitFilterList.some(u => {
              if (u === 'none') {
                return isMetric && (item.unit === 'none' || !item.unit);
              }
              if (u === '--') {
                return !isMetric;
              }
              return item.unit === u;
            })
          : true) &&
        (typeLeng
          ? isMetric && this.metricSearchObj.type.some(t => labelsMatchTypes(item.labels).includes(t))
          : true) &&
        (nameLeng
          ? isMetric && this.metricSearchObj.name.some(n => item.labels.some(l => fuzzyMatch(l.name, n)))
          : true) &&
        (enNameLeng ? this.metricSearchObj.enName.some(n => fuzzyMatch(item.name, n)) : true) &&
        (unitLeng
          ? isMetric && this.metricSearchObj.unit.some(u => fuzzyMatch(item.unit || (isMetric ? 'none' : ''), u))
          : true) &&
        (textleng
          ? this.metricSearchObj.text.some(t => {
              const monitorType = {
                指标: 'metric',
                维度: 'dimension',
              };
              return (
                item.monitor_type === t ||
                monitorType?.[t] === item.monitor_type ||
                (isMetric && item.labels.some(l => fuzzyMatch(l.name, t))) ||
                fuzzyMatch(item.name, t) ||
                fuzzyMatch(item.unit || (isMetric ? 'none' : ''), t)
              );
            })
          : true)
      );
    });
    this.changePageCount(filterList.length);
    // this.handleGroupList(fiterList);
    return filterList.slice(
      this.pagination.pageSize * (this.pagination.page - 1),
      this.pagination.pageSize * this.pagination.page
    );
  }

  get selectionLeng() {
    const selectionlist = this.metricTable.filter(item => item.selection);
    return selectionlist.length;
  }

  get type() {
    return this.$route.name === 'custom-detail-event' ? 'customEvent' : 'customTimeSeries';
  }

  get isReadonly() {
    return !!this.detailData.is_readonly;
  }

  get emptyType() {
    let emptyType = 'empty';
    for (const key in this.metricSearchObj) {
      if (this.metricSearchObj[key].length) {
        emptyType = 'search-empty';
        break;
      }
    }
    if (this.groupFilterList.length || this.metricFilterList.length || this.unitFilterList.length) {
      emptyType = 'search-empty';
    }
    return emptyType;
  }

  get tableVirtualRenderHeight() {
    return this.eventData.length ? Math.min(600, (this.eventData.length + 1) * 43 + 10) : undefined;
  }

  // @Watch('metricTable')
  // async handleMetricTableChange(v) {
  //   if (
  //     this.type === 'customTimeSeries'
  //     && this.isShowData
  //     && v.some(item => this.metricValue[item.name] === undefined)
  //   ) {
  //     this.dataLoading = true;
  //     const fieldList = v.map(set => set.name) || [];
  //     const data = await this.$store.dispatch('custom-escalation/getCustomTimeSeriesLatestDataByFields', {
  //       result_table_id: this.tableId,
  //       fields_list: fieldList
  //     });
  //     // eslint-disable-next-line camelcase
  //     this.metricValue = data?.fields_value || {};
  //     this.detailData.last_time = typeof data?.last_time === 'number'
  //       ? dayjs.tz(data.last_time * 1000).format('YYYY-MM-DD HH:mm:ss')
  //       : data?.last_time;
  //     this.dataLoading = false;
  //   }
  // }
  created() {
    this.updateNavData(this.$t('查看'));
    this.getDetailData();
    this.shortcuts.list = [
      {
        value: 1,
        name: this.$tc('近 1 小时'),
      },
      {
        value: 12,
        name: this.$tc('近 12 小时'),
      },
      {
        value: 24,
        name: this.$tc('近 1 天'),
      },
      {
        value: 168,
        name: this.$tc('近 7 天'),
      },
    ];
    this.refreshList = {
      list: [
        {
          value: 0,
          name: this.$tc('不刷新'),
        },
        {
          value: 60,
          name: this.$tc('每分钟'),
        },
        {
          value: 300,
          name: this.$tc('每五分钟'),
        },
      ],
      value: 0,
    };
  }

  beforeDestroy() {
    clearTimeout(this.timer);
    this.timer = null;
  }

  renderGroupHeader(h: CreateElement) {
    return h(TableFiter, {
      props: {
        title: this.$t('分组'),
        value: this.groupFilterList,
        list: [{ id: NULL_LABEL, name: this.$t('未分组') }, ...this.groupSelectList],
      },
      on: {
        change: v => {
          setTimeout(() => {
            this.pagination.page = 1;
            this.groupFilterList = v;
            this.updateAllSelection();
          }, 300);
        },
      },
    });
  }

  renderMetricHeader(h: CreateElement) {
    return h(TableFiter, {
      props: {
        title: this.$t('指标/维度'),
        value: this.metricFilterList,
        list: [
          { id: 'metric', name: this.$t('指标') },
          { id: 'dimension', name: this.$t('维度') },
        ],
      },
      on: {
        change: v => {
          setTimeout(() => {
            this.pagination.page = 1;
            this.metricFilterList = v;
            this.updateAllSelection();
          }, 300);
        },
      },
    });
  }

  renderSelectionHeader(h: CreateElement) {
    return h(ColumnCheck, {
      props: {
        list: [],
        value: this.allCheckValue,
        defaultType: 'current',
      },
      on: {
        change: this.handleCheckChange,
      },
    });
  }

  renderUnitHeader(h: CreateElement) {
    return h(TableFiter, {
      props: {
        title: this.$t('单位'),
        value: this.unitFilterList,
        list: this.tableAllUnitList,
      },
      on: {
        change: v => {
          setTimeout(() => {
            this.pagination.page = 1;
            this.unitFilterList = v;
            this.updateAllSelection();
          }, 300);
        },
      },
    });
  }

  changePageCount(count: number) {
    this.pagination.total = count;
  }

  // handleGroupList(list) {
  //   list.forEach((item) => {
  //     const res = this.groupSelectList.find(g => item.label === g.id);
  //     if (!res && item.monitor_type === 'metric' && item.label) {
  //       this.groupSelectList.push({
  //         id: item.label,
  //         name: item.label
  //       });
  //     }
  //   });
  // }

  handleRowCheck() {
    this.updateCheckValue();
  }

  updateAllSelection(v = false) {
    this.metricTable.forEach(item => item.monitor_type === 'metric' && (item.selection = v));
    this.updateCheckValue();
  }

  handleCheckChange({ value }) {
    this.updateAllSelection(value === 2);
    this.updateCheckValue();
  }

  updateCheckValue() {
    const metricLiist = this.metricTable.filter(item => item.monitor_type === 'metric');
    const checkedLeng = metricLiist.filter(item => item.selection).length;
    const allLeng = metricLiist.length;
    this.allCheckValue = 0;
    if (checkedLeng > 0) {
      this.allCheckValue = checkedLeng < allLeng ? 1 : 2;
    } else {
      this.allCheckValue = 0;
    }
  }

  // handleBatchValueChange(v) {
  //   if (v === '') return;
  //   this.metricTable.forEach((item) => {
  //     item.selection && (item.label = v);
  //   });
  //   this.$nextTick(() => {
  //     this.batchGroupValue = '';
  //     this.updateAllSelection();
  //   });
  // }
  handleShowDataChange(v) {
    if (v && !this.dataLoading) {
      // this.handleMetricTableChange(this.metricData);
    }
  }
  handlePageChange(v) {
    this.updateAllSelection();
    this.pagination.page = v;
  }
  handleLimitChange(v) {
    this.updateAllSelection();
    this.pagination.page = 1;
    this.pagination.pageSize = v;
  }
  //  从新建和列表页进来会去获取最近 1小时 拉取的事件
  getTimeParams() {
    const dateNow = dayjs.tz().format('YYYY-MM-DD HH:mm:ss');
    const lastDate = dayjs.tz(dateNow).add(-this.shortcuts.value, 'h').format('YYYY-MM-DD HH:mm:ss');
    return `${lastDate} -- ${dateNow}`;
  }

  //  获取详情
  async getDetailData() {
    this.loading = true;
    this.$store.commit('app/SET_NAV_TITLE', this.$t('加载中...'));
    // this.type = this.$route.params.type === 'customEvent' ? 'customEvent' : 'customTimeSeries'
    // this.isShowRightWindow = this.$route.params.isCreat === 'creat'; // 在第一次进来的时候展示右侧帮助栏
    const promiseItem: Promise<any>[] = [this.$store.dispatch('custom-escalation/getProxyInfo')];
    let title = '';
    if (this.type === 'customEvent') {
      const params: IParams = {
        // 自定义事件初次进入会请求最近1小时的数据
        time_range: this.getTimeParams(),
        bk_event_group_id: this.$route.params.id,
      };
      promiseItem.push(this.$store.dispatch('custom-escalation/getCustomEventDetail', params));
    } else {
      promiseItem.push(
        this.$store.dispatch('custom-escalation/getCustomTimeSeriesDetail', {
          time_series_group_id: this.$route.params.id,
        })
      );
      promiseItem.push(this.$store.dispatch('strategy-config/getUnitList'));
    }
    try {
      const data = await Promise.all(promiseItem);

      [this.proxyInfo] = data; // 云区域展示数据
      [, this.detailData] = data;
      this.updateNavData(`${this.$t('查看')} ${this.detailData.name}`);
      if (this.type === 'customTimeSeries') {
        [, , this.unitList] = data; // 单位list
        const allUnitList = [];
        const allUnitListMap = new Map();
        for (const groupItem of this.unitList) {
          for (const unitItem of groupItem?.formats || []) {
            if (unitItem.id) {
              allUnitList.push({
                id: unitItem.id,
                name: unitItem.name,
              });
              allUnitListMap.set(unitItem.id, unitItem.name);
            }
          }
        }
        this.allUnitList = allUnitList;
        title = `${this.$tc('route-' + '自定义指标').replace('route-', '')} - #${
          this.detailData.time_series_group_id
        } ${this.detailData.name}`;
        this.metricList =
          this.detailData.metric_json?.[0]?.fields?.filter(item => item.monitor_type === 'metric') || [];

        // 获取表格内的单位数据
        const tempSet = new Set();
        const tableAllUnitList = [];
        for (const metricItem of this.metricList) {
          if (!tempSet.has(metricItem.unit)) {
            const unitName = allUnitListMap.get(metricItem.unit);
            if (unitName) {
              tableAllUnitList.push({
                id: metricItem.unit,
                name: unitName,
              });
            }
          }
          tempSet.add(metricItem.unit);
        }
        this.tableAllUnitList = [
          ...tableAllUnitList,
          {
            id: 'none',
            name: 'none',
          },
          {
            id: '--',
            name: '--',
          },
        ];

        await this.getGroupList();
        await this.getAllDataPreview(this.detailData.metric_json[0].fields, this.detailData.table_id);
      } else {
        title = `${this.$tc('route-' + '自定义事件').replace('route-', '')} - #${this.detailData.bk_event_group_id} ${
          this.detailData.name
        }`;
      }
      this.$store.commit('app/SET_NAV_TITLE', title);
      this.handleDetailData(this.detailData);
      this.loading = false;
    } catch (error) {
      console.error(error);
      this.loading = false;
    }
  }
  /* 获取分组管理数据 */
  async getGroupList() {
    const data = await customTsGroupingRuleList({
      time_series_group_id: this.detailData.time_series_group_id,
    }).catch(() => []);
    this.groupList = data.map(item => ({
      name: item.name,
      matchRules: item.auto_rules,
      manualList: item.manual_list,
    }));
    this.groupsDataTidy();
  }

  /* 分组数据整理 */
  groupsDataTidy() {
    const metricNames = this.metricList.map(item => item.name);
    const allMatchRulesSet = new Set();
    const metricGroupsMap = new Map();
    this.groupList.forEach(item => {
      item.matchRules.forEach(rule => {
        allMatchRulesSet.add(rule);
      });
    });
    const allMatchRules = Array.from(allMatchRulesSet);
    /* 整理每个匹配规则配的指标数据 */
    allMatchRules.forEach(rule => {
      this.matchRulesMap.set(
        rule,
        metricNames.filter(name => matchRuleFn(name, rule))
      );
    });
    /* 整理每个组包含的指标 */
    this.groupList.forEach(item => {
      const tempSet = new Set();
      item.matchRules.forEach(rule => {
        const metrics = this.matchRulesMap.get(rule) || [];
        metrics.forEach(m => {
          tempSet.add(m);
        });
      });
      const matchRulesOfMetrics = Array.from(tempSet) as string[];
      this.groupsMap.set(item.name, {
        ...item,
        matchRulesOfMetrics,
      });
      /* 写入每个指标包含的组 */
      const setMetricGroup = (m, type) => {
        const metricItem = metricGroupsMap.get(m);
        if (metricItem) {
          const { groups, matchType } = metricItem;
          const targetGroups = [...new Set(groups.concat([item.name]))];
          const targetMatchType = JSON.parse(JSON.stringify(matchType));
          targetGroups.forEach(t => {
            if (t === item.name) {
              targetMatchType[t as string] = [...new Set((matchType[t as string] || []).concat([type]))];
            }
          });
          metricGroupsMap.set(m, {
            groups: targetGroups,
            matchType: targetMatchType,
          });
        } else {
          const matchTypeObj = {
            [item.name]: [type],
          };
          metricGroupsMap.set(m, {
            groups: [item.name],
            matchType: matchTypeObj,
          });
        }
      };
      matchRulesOfMetrics.forEach(m => {
        setMetricGroup(m, 'auto');
      });
      item.manualList.forEach(m => {
        setMetricGroup(m, 'manual');
      });
    });
    this.metricGroupsMap = metricGroupsMap;
    this.groupSelectList = this.groupList.map(item => ({
      id: item.name,
      name: item.name,
    }));
  }

  /** 更新面包屑 */
  updateNavData(name = '') {
    if (!name) return;
    // const oldRouteList = this.$store.getters.navRouteList;
    const routeList = [
      // oldRouteList[0]
    ];
    routeList.push({
      name,
      id: '',
    });
    this.$store.commit(`app/${SET_NAV_ROUTE_LIST}`, routeList);
  }

  //  处理详情数据
  handleDetailData(detailData: IDetailData) {
    if (this.type === 'customTimeSeries') {
      this.tableId = detailData.table_id;
      this.metricData = detailData.metric_json[0].fields.map(item =>
        // item.label === undefined && this.$set(item, 'label', '');
        ({
          ...item,
          selection: false,
          descReValue: false,
          labels: [],
        })
      );
      this.setMetricDataLabels();
      this.pagination.total = this.metricData.length;
      if (!this.metricData.length) {
        this.isShowData = false;
      }
    }
    this.scenario = `${detailData.scenario_display[0]} - ${detailData.scenario_display[1]}`;
    this.eventData = detailData.event_info_list;
    this.copyName = this.detailData.name;
    this.copyDataLabel = this.detailData.data_label || '';
    this.copyDescribe = this.detailData.desc || '';
    this.copyIsPlatform = this.detailData.is_platform ?? false;
    const str =
      this.type === 'customEvent'
        ? `# ${this.$t('事件标识名，最大长度128')}
                "event_name": "input_your_event_name",
                "event": {
                    # ${this.$t('事件内容，必需项')}
                    "content": "user xxx login failed"
                },`
        : `# ${this.$t('指标，必需项')}
        "metrics": {
            "cpu_load": 10
        },`;
    this.preData = `{
        # ${this.$t('数据通道标识，必需项')}
        "data_id": ${detailData.bk_data_id},
        # ${this.$t('数据通道标识验证码，必需项')}
        "access_token": "${detailData.access_token}",
        "data": [{
            ${str}
            # ${this.$t('来源标识如IP，必需项')}
            "target": "127.0.0.1",
            # ${this.$t('自定义维度，非必需项')}
            "dimension": {
                "module": "db",
                "location": "guangdong",
                # ${this.$t('event_type 为非必须项，用于标记事件类型，默认为异常事件')}
                # ${this.$t('recovery:恢复事件，abnormal:异常事件')}
                "event_type": "abnormal"
            },
            # ${this.$t('数据时间，精确到毫秒，非必需项')}
            "timestamp": ${new Date().getTime()}
        }]
    }`;
    // 判断如果是 prometheus 类型则展示不同的内容
    if (detailData.protocol === 'prometheus') {
      // # ${this.$t('event_type 为非必须项，用于标记事件类型，默认为异常事件')}
      this.sdkData.preGoOne = `type bkClient struct{}
func (c *bkClient) Do(r *http.Request) (*http.Response, error) {
	r.Header.Set("X-BK-TOKEN", "$TOKEN")
  // TOKEN 即在 saas 侧申请的 token
	return http.DefaultClient.Do(r)
}

func main() {
	register := prometheus.NewRegistry()
	register.MustRegister(promcollectors.NewGoCollector())

	name := "reporter"
	// 1) 指定蓝鲸上报端点 $bk.host:$bk.port
	pusher := push.New("\${PROXY_IP}:4318", name).
  Gatherer(register)

	// 2) 传入自定义 Client
	pusher.Client(&bkClient{})

	ticker := time.Tick(15 * time.Second)
	for {
		<-ticker
		if err := pusher.Push(); err != nil {
			log.Println("failed to push records to the server,
      error:", err)
			continue
		}
		log.Println("push records to the server successfully")
	}
}`;

      this.sdkData.prePythonOne = `from prometheus_client.exposition import
default_handler

# 定义基于监控 token 的上报 handler 方法
def bk_handler(url, method, timeout, headers, data):
    def handle():
        headers.append(['X-BK-TOKEN', '$TOKEN'])
        # TOKEN 即在 saas 侧申请的 token
        default_handler(url, method, timeout, headers, data)()
    return handle

from prometheus_client import CollectorRegistry,
Gauge, push_to_gateway
from prometheus_client.exposition
import bk_token_handler

registry = CollectorRegistry()
g = Gauge('job_last_success_unixtime',
'Last time a batch job successfully finished', registry=registry)
g.set_to_current_time()
push_to_gateway('\${PROXY_IP}:4318', job='batchA',
registry=registry, handler=bk_handler) # 上述自定义 handler`;
    }
  }

  /* 获取所有数据预览数据 */
  async getAllDataPreview(fields: { monitor_type: 'dimension' | 'metric'; name: string }[], tableId) {
    const fieldList = fields.filter(item => item.monitor_type === 'metric').map(item => item.name);
    const data = await this.$store.dispatch('custom-escalation/getCustomTimeSeriesLatestDataByFields', {
      result_table_id: tableId,
      fields_list: fieldList,
    });
    this.allDataPreview = data?.fields_value || {};
    this.detailData.last_time =
      typeof data?.last_time === 'number'
        ? dayjs.tz(data.last_time * 1000).format('YYYY-MM-DD HH:mm:ss')
        : data?.last_time;
  }

  //  点击icon展示name编辑
  handleShowEdit() {
    this.isShowEditName = true;
    this.$nextTick(() => {
      this.nameInput.focus();
    });
  }
  /** 点击显示英文名的编辑 */
  handleShowEditDataLabel() {
    this.isShowEditDataLabel = true;
    this.$nextTick(() => {
      this.dataLabelInput.focus();
    });
  }
  /** 点击显示描述的编辑 */
  handleShowEditDes() {
    this.isShowEditDesc = true;
    this.$nextTick(() => {
      this.describeInput.focus();
    });
  }
  /** 编辑是否为平台指标、事件 */
  async handleIsPlatformChange() {
    if (this.type === 'customEvent') {
      this.loading = true;
      await this.handleSave({ is_platform: this.copyIsPlatform });
    }
    this.detailData.is_platform = this.copyIsPlatform;
    this.isShowEditIsPlatform = false;
    this.loading = false;
  }
  /** 编辑英文名 */
  async handleEditDataLabel() {
    if (!this.copyDataLabel || this.copyDataLabel === this.detailData.data_label) {
      this.copyDataLabel = this.detailData.data_label;
      this.isShowEditDataLabel = false;
      return;
    }
    if (/[\u4e00-\u9fa5]/.test(this.copyDataLabel)) {
      this.$bkMessage({ theme: 'error', message: this.$tc('输入非中文符号') });
      return;
    }
    const ExistPass =
      this.type === 'customEvent'
        ? await validateCustomEventGroupLabel({
            data_label: this.copyDataLabel,
            bk_event_group_id: this.detailData.bk_event_group_id,
          }).catch(() => false)
        : await validateCustomTsGroupLabel({
            data_label: this.copyDataLabel,
            time_series_group_id: this.detailData.time_series_group_id,
          }).catch(() => false);
    if (!ExistPass) {
      return;
    }
    if (this.type === 'customEvent') {
      this.loading = true;
      await this.handleSave({ data_label: this.copyDataLabel });
    }
    this.detailData.data_label = this.copyDataLabel;
    this.isShowEditDataLabel = false;
    this.loading = false;
  }

  //  编辑名字
  async handleEditName() {
    if (!(this.copyName && this.copyName !== this.detailData.name)) {
      this.copyName = this.detailData.name;
      this.isShowEditName = false;
      return;
    }
    //  名字是否重复校验
    let isOkName = true;
    const res =
      this.type === 'customEvent'
        ? await this.$store
            .dispatch('custom-escalation/validateCustomEventName', {
              params: { name: this.copyName, bk_event_group_id: this.detailData.bk_event_group_id },
            })
            .then(res => res.result ?? true)
            .catch(() => false)
        : await this.$store
            .dispatch('custom-escalation/validateCustomTimetName', {
              params: { name: this.copyName, time_series_group_id: this.detailData.time_series_group_id },
            })
            .then(res => res.result ?? true)
            .catch(() => false);
    if (!res) {
      isOkName = false;
    }
    if (!isOkName) {
      this.copyName = this.detailData.name;
      this.$nextTick(() => {
        this.nameInput.focus();
      });
      return;
    }
    if (this.type === 'customEvent') {
      const params: IEditParams = {
        bk_event_group_id: this.detailData.bk_event_group_id,
        name: this.copyName,
        scenario: this.detailData.scenario,
        is_enable: true,
      };
      this.loading = true;
      await this.$store.dispatch('custom-escalation/editCustomEvent', params);
    }
    this.detailData.name = this.copyName;
    this.isShowEditName = false;
    this.loading = false;
  }

  /* 保存描述信息 */
  async handleSaveDesc() {
    const params = {
      bk_biz_id: this.detailData.bk_biz_id,
      time_series_group_id: this.detailData.time_series_group_id,
      desc: this.copyDescribe,
    };
    return await modifyCustomTimeSeriesDesc(params).catch(({ message }) => {
      this.$bkMessage({ message, theme: 'error' });
    });
  }

  // 编辑描述
  async handleEditDescribe() {
    if (!this.copyDescribe.trim() || this.copyDescribe.trim() === this.detailData.desc) {
      this.copyDescribe = this.detailData.desc;
      this.isShowEditDesc = false;
      return;
    }
    this.isShowEditDesc = false;
    const data = await this.handleSaveDesc();
    if (data) {
      this.$bkMessage({ theme: 'success', message: this.$t('变更成功') });
      this.detailData.desc = this.copyDescribe;
      return;
    }
    this.copyDescribe = this.detailData.desc;
  }

  /** 保存自定义事件编辑 */
  handleSave(data: Record<string, any> = {}) {
    const params: IEditParams = {
      bk_event_group_id: this.detailData.bk_event_group_id,
      name: this.detailData.name,
      data_label: this.detailData.data_label ?? '',
      is_platform: this.detailData.is_platform ?? false,
      scenario: this.detailData.scenario,
      is_enable: true,
    };
    Object.assign(params, data);
    this.loading = true;
    return this.$store.dispatch('custom-escalation/editCustomEvent', params);
  }

  //  查看原始数据侧滑栏
  handleOpenSideslider(data: {}, title: string) {
    this.sideslider.isShow = true;
    this.sideslider.data = data;
    this.sideslider.title = title;
  }

  // 添加策略
  handleAddStrategy(row) {
    const data: any = {
      data_source_label: 'custom',
      data_type_label: 'event',
      interval: 60,
      method: 'COUNT',
      metric_field: row.custom_event_name,
      result_table_id: this.detailData.table_id,
      result_table_label: this.detailData.scenario,
    };
    this.$router.push({
      name: 'strategy-config-add',
      params: {
        data,
      },
    });
  }
  // 跳转关联策略
  handleGotoStrategy(row) {
    if (!row.related_strategies.length) return;
    this.$router.push({
      name: 'strategy-config',
      params: {
        bkStrategyId: row.related_strategies.map(id => id),
      },
    });
  }

  //  改变事件列表刷新时间
  handleRefreshChange(value: number) {
    if (value === 0) return;
    clearTimeout(this.timer);
    this.timer = null;

    this.timer = setTimeout(async () => {
      await this.handleRefreshNow();
      this.handleRefreshChange(value);
    }, 1000 * value);
  }
  /* 立即刷新 */
  async handleRefreshNow(isRefreshNow?: boolean) {
    this.eventDataLoading = true;
    const params: IParams = {
      // 自定义事件初次进入会请求最近半小时的数据
      time_range: this.getTimeParams(),
      bk_event_group_id: this.$route.params.id,
      need_refresh: isRefreshNow ? true : undefined,
    };
    const detailData = await this.$store.dispatch('custom-escalation/getCustomEventDetail', params);
    this.eventData = detailData.event_info_list;
    this.eventDataLoading = false;
  }

  //  改变事件列表时间选择
  async handleTimeChange() {
    const timeRange = this.getTimeParams();
    const params: IParams = {
      bk_event_group_id: this.$route.params.id,
      time_range: timeRange,
    };
    try {
      this.detailData = await this.$store.dispatch('custom-escalation/getCustomEventDetail', params);
      this.handleDetailData(this.detailData);
      this.loading = false;
    } catch (error) {
      this.loading = false;
    }
  }

  //  复制数据上报样例
  handleCopyData() {
    const str =
      this.type === 'customEvent'
        ? `"event_name": "input_your_event_name",
        "event": {
            "content": "user xxx login failed"
        },`
        : `"metrics": {
            "cpu_load": 10
        },`;
    const example = `{
    "data_id": ${this.detailData.bk_data_id},
    "access_token": "${this.detailData.access_token}",
    "data": [{
        ${str}
        "target": "127.0.0.1",
        "dimension": {
            "module": "db",
            "location": "guangdong"
        },
        "timestamp": ${new Date().getTime()}
    }]
}`;
    this.textCopy.value = example;
    this.textCopy.select();
    document.execCommand('copy');
    this.$bkMessage({
      theme: 'success',
      message: this.$t('样例复制成功'),
    });
  }

  // 复制Prometheus  sdk 接入流程代码
  handleCopyPrometheus(type) {
    this[type].value = type === 'golangCopy' ? this.sdkData.preGoOne : this.sdkData.prePythonOne;
    this[type].select();
    document.execCommand('copy');
    this.$bkMessage({
      theme: 'success',
      message: this.$t('样例复制成功'),
    });
  }
  //  自定义指标保存
  async handleSubmit() {
    if (!this.copyDataLabel) {
      this.$bkMessage({
        theme: 'error',
        message: this.$t('填写英文名'),
      });
      return;
    }
    if (/[\u4e00-\u9fa5]/.test(this.copyDataLabel)) {
      this.$bkMessage({ theme: 'error', message: this.$tc('输入非中文符号的英文名') });
      return;
    }
    this.loading = true;
    const params = {
      time_series_group_id: this.detailData.time_series_group_id,
      name: this.copyName,
      data_label: this.copyDataLabel,
      is_platform: this.copyIsPlatform,
      metric_json: [
        {
          fields: this.metricData.map(item => ({
            ...item,
            label: item?.labels?.map(l => l.name) || [],
            labels: undefined,
          })),
          table_name: 'base',
          table_desc: '默认分类',
        },
      ],
    };
    await this.handleSaveGroupManage();
    const data = await this.$store.dispatch('custom-escalation/editCustomTime', params);
    if (data) {
      this.$bkMessage({ theme: 'success', message: this.$t('变更成功') });
    }
    this.loading = false;
  }

  //  别名失焦校验
  handleCheckDescName(row) {
    // 校验别名是否冲突
    if (row.description !== '') {
      if (this.descNameList.filter(item => item === row.description).length > 1) {
        row.descReValue = true;
      } else {
        row.descReValue = false;
      }
    }
  }

  //  指标/维度表交互
  handleMouseenter(index) {
    this.unit.value = true;
    this.unit.index = index;
  }

  //  指标/维度表交互
  handleMouseLeave() {
    if (!this.unit.toggle) {
      this.unit.value = false;
      this.unit.index = -1;
    }
  }

  //  指标/维度表交互
  handleToggleChange(value) {
    this.unit.toggle = value;
  }

  //  找到单位值对应的name
  handleFindUnitName(id) {
    let name = 'none';
    this.unitList.forEach(group => {
      const res = group.formats.find(item => item.id === id);
      if (res) {
        name = res.name;
      }
    });
    return name;
  }
  handleExportMetric() {
    // typeof cb === 'function'
    //   && cb(
    //     // eslint-disable-next-line @typescript-eslint/no-unused-vars
    //     this.metricData.map(({ descReValue, ...item }) => item),
    //     `${this.detailData.name}-${dayjs.tz().format('YYYY-MM-DD HH-mm-ss')}.json`
    //   );
    const allUnit = [];
    this.unitList.forEach(group => {
      group.formats.forEach(item => {
        allUnit.push(item.id);
      });
    });
    let i = 0;
    let unitStr = ';';
    allUnit.forEach(item => {
      i += 1;
      unitStr += `${item}、`;
      if (i > 4) {
        unitStr += '\n';
        i = 0;
      }
    });
    // const allUnitStr = allUnit.join('、');
    const descStr = [
      this.$t('"单位可选类型: {unitStr}\n分组分隔方式(仅;分隔). \n导入时-表示不更新. 空单元格表示置空"', { unitStr }),
      '',
      '',
      '',
      '',
      '',
    ].join(',');
    const transformTableDataToCsvStr = (tableThArr: string[], tableTdArr: Array<string[]>): string => {
      const csvList = [];
      csvList.push(descStr);
      csvList.push(['', '', '', '', '', '']);
      csvList.push(tableThArr.join(','));
      tableTdArr.forEach(row => {
        const rowString = row.reduce((str, item, index) => str + (index ? ',' : '') + item, '');
        csvList.push(rowString);
      });
      const csvString = csvList.join('\n');
      return csvString;
    };
    const thArr = [
      this.$t('指标/维度'),
      this.$t('分组'),
      this.$t('英文名'),
      this.$t('别名'),
      this.$t('类型'),
      this.$t('单位'),
    ];
    const tdArr = [];
    this.metricData.forEach(item => {
      const row = [
        item.monitor_type,
        item.labels.map(l => l.name).join(';') || '-',
        item.name,
        item.description || '-',
        item.type || '-',
        item.unit || '-',
      ];
      tdArr.push(row);
    });
    const csvStr = transformTableDataToCsvStr(thArr as string[], tdArr);
    downCsvFile(csvStr, `${this.detailData.name}-${dayjs.tz().format('YYYY-MM-DD HH-mm-ss')}.csv`);
  }
  /* 导入数据时不在分组管理的分组需要自动新建此分组 */
  concatLabels(metricName: string, oldLabels: { name: string; match_type: string[] }[], target: string[]) {
    /* 添加分组 */
    const addGroup = name => {
      this.groupList.push({
        manualList: [metricName],
        matchRules: [],
        name,
      });
      this.groupsMap.set(name, {
        manualList: [metricName],
        matchRules: [],
        matchRulesOfMetrics: [],
        name,
      });
      const params = {
        time_series_group_id: this.detailData.time_series_group_id,
        name,
        manual_list: [metricName],
        auto_rules: [],
      };
      createOrUpdateGroupingRule(params);
    };
    const labels = [];
    labels.push(...oldLabels);
    const tempLabels = labels.map(item => item.name);
    target.forEach(item => {
      if (!/^[\u4E00-\u9FA5A-Za-z0-9_-]+$/g.test(item)) return;
      if (tempLabels.includes(item)) {
        const setLabel = labels.find(l => l.name === item);
        setLabel.match_type = [...new Set(setLabel.match_type.concat(['manual']))];
      } else {
        labels.push({
          name: item,
          match_type: ['manual'],
        });
      }
      if (!this.groupsMap.has(item)) {
        !!item && addGroup(item);
      }
    });
    const autoLabels = labels.filter(item => item.match_type.includes('auto')).map(item => item.name);
    const targetLabels = [];
    labels.forEach(item => {
      if (autoLabels.includes(item.name) || target.includes(item.name)) {
        targetLabels.push(item);
      }
    });
    return targetLabels;
  }
  /* 导入数据 */
  handleImportMetric(data: string) {
    const allUnit = [];
    this.unitList.forEach(group => {
      group.formats.forEach(item => {
        allUnit.push(item.id);
      });
    });
    const arr = csvToArr(data);
    arr.slice(3).forEach(row => {
      const name = row[2];
      const unitNeedUpdate = row[5] !== '-';
      const unit = row[5] || '';
      const descriptionNeedUpdate = row[3] !== '-';
      const description = row[3] || '';
      const labelsNeedUpdate = row[1] !== '-';
      const labels = row[1]?.split?.(';') || [];
      if (name) {
        const setItem = this.metricData.find(set => set.name === name);
        if (setItem) {
          if (setItem.monitor_type === 'metric') {
            if (unitNeedUpdate) setItem.unit = allUnit.includes(unit) ? unit : '';
            if (labelsNeedUpdate) setItem.labels = this.concatLabels(setItem.name, setItem.labels, labels);
          }
          if (descriptionNeedUpdate) setItem.description = description || '';
          setItem.selection = false;
        }
      }
    });
    this.groupsDataTidy();
  }
  /* 弹出分组管理 */
  handleShowGroupManage(v: boolean) {
    if (v) {
      this.updateGroupList();
    }
    this.groupManage.show = v;
  }
  /* 分组管理指标 */
  handleSelectGroup(value, index) {
    const metricName = this.metricTable[index].name;
    const labels = [];
    this.groupList.forEach(item => {
      const groupItem = this.groupsMap.get(item.name);
      const { matchRulesOfMetrics, manualList } = groupItem;
      const tempObj = {
        name: item.name,
        match_type: [],
      };
      if (matchRulesOfMetrics.includes(metricName)) {
        tempObj.match_type.push('auto');
      }
      if (value.includes(item.name)) {
        tempObj.match_type.push('manual');
        this.groupsMap.set(item.name, {
          ...groupItem,
          manualList: [...new Set(manualList.concat([metricName]))],
        });
      } else {
        this.groupsMap.set(item.name, {
          ...groupItem,
          manualList: manualList.filter(m => m !== metricName),
        });
      }
      if (tempObj.match_type.length) labels.push(tempObj);
    });
    this.isUpdateGroup = true;
    this.metricTable[index].labels = labels;
    this.updateGroupList();
  }
  /* 分组管理数据更新 */
  handleGroupListChange(groupList) {
    this.groupList = groupList;
    this.groupsDataTidy();
    this.metricData.forEach(item => {
      if (item.monitor_type === 'metric') {
        const groupItem = this.metricGroupsMap.get(item.name);
        if (groupItem) {
          item.labels = groupItem.groups.map(g => ({
            name: g,
            match_type: groupItem.matchType[g],
          }));
        } else {
          item.labels = [];
        }
      }
    });
  }
  /* 更新分组管理 */
  updateGroupList() {
    this.groupList = this.groupList.map(item => ({
      ...item,
      manualList: this.groupsMap.get(item.name)?.manualList || [],
    }));
  }
  /* 保存分组管理 */
  async handleSaveGroupManage() {
    const params = {
      time_series_group_id: this.detailData.time_series_group_id,
      group_list: this.groupList.map(item => ({
        name: item.name,
        manual_list: item.manualList,
        auto_rules: item.matchRules,
      })),
    };
    await modifyCustomTsGroupingRuleList(params).catch(() => false);
  }

  /* 选择分组下拉框收起展开 */
  handleGroupSelectToggle(v: boolean) {
    if (!v) {
      if (this.isUpdateGroup) {
        this.handleSaveGroupManage();
      }
    } else {
      this.isUpdateGroup = false;
    }
  }
  /* 分组tag tip展示 */
  handleGroupTagTip(event, groupName) {
    const groupItem = this.groupsMap.get(groupName);
    const manualCount = groupItem?.manualList?.length || 0;
    const matchRules = groupItem?.matchRules || [];
    this.groupTagInstance = this.$bkPopover(event.target, {
      placement: 'top',
      boundary: 'window',
      arrow: true,
      content: `<div>${this.$t('手动分配指标数')}：${manualCount}</div><div>${this.$t('匹配规则')}：${
        matchRules.length ? matchRules.join(',') : '--'
      }</div>`,
    });
    this.groupTagInstance.show();
  }
  handleRemoveGroupTip() {
    this.groupTagInstance?.hide?.();
    this.groupTagInstance?.destroy?.();
  }
  /* 批量分组 */
  handleBatchGroupChange(value: string[]) {
    this.batchGroupValue = value;
  }
  handleBatchGroupToggle(v: boolean) {
    if (!v && this.batchGroupValue.length) {
      this.metricTable.forEach((item, index) => {
        if (item.selection) {
          this.handleSelectGroup(this.batchGroupValue, index);
        }
      });
      this.batchGroupValue = [];
      this.handleSaveGroupManage();
    }
  }
  /* 搜索 */
  handleMetricSearchValue(v) {
    this.metricSearchValue = v;
    const search = {
      type: [],
      name: [],
      enName: [],
      unit: [],
      text: [],
    };
    for (const item of this.metricSearchValue) {
      if (item.id === 'type') {
        search.type = [...new Set(search.type.concat(item.values.map(v => v.id)))];
      }
      if (item.id === 'name') {
        search.name = [...new Set(search.name.concat(item.values.map(v => v.id)))];
      }
      if (item.id === 'enName') {
        search.enName = [...new Set(search.enName.concat(item.values.map(v => v.id)))];
      }
      if (item.id === 'unit') {
        search.unit = [...new Set(search.unit.concat(item.values.map(v => v.id)))];
      }
      if (item.type === 'text') {
        search.text = [...new Set(search.text.concat([item.id]))];
      }
    }
    this.metricSearchObj = search;
  }
  /* 通过分组管理计算每个指标包含的组 */
  setMetricDataLabels() {
    this.metricData.forEach(item => {
      if (item.monitor_type === 'metric') {
        const groupItem = this.metricGroupsMap.get(item.name);
        if (groupItem) {
          item.labels = groupItem.groups.map(g => ({
            name: g,
            match_type: groupItem.matchType[g],
          }));
        } else {
          item.labels = [];
        }
      }
    });
  }

  handleJump() {
    const toView = {
      customEvent: () => {
        this.$router.push({
          name: 'custom-escalation-event-view',
          params: { id: String(this.detailData.bk_event_group_id) },
          query: { name: this.detailData.name },
        });
      },
      customTimeSeries: () => {
        this.$router.push({
          name: 'custom-escalation-view',
          params: { id: String(this.detailData.time_series_group_id) },
          query: { name: this.detailData.name },
        });
      },
    };
    toView[this.type]();
  }

  handleEmptyOperation(type: EmptyStatusOperationType) {
    if (type === 'clear-filter') {
      for (const key in this.metricSearchObj) {
        this.metricSearchValue = [];
        this.metricSearchObj[key] = [];
        this.metricFilterList = [];
        this.unitFilterList = [];
        this.groupFilterList = [];
      }
    }
  }
}
</script>

<style lang="scss" scoped>
@import '../../theme/index';

/* stylelint-disable */
.custom-detail-page-component {
  overflow: hidden;
  height: 100%;

  .hint-alert {
    display: inline-block;
    margin: 5px 16px 5px 20px;
    border-color: transparent;
    background: transparent;

    :deep(.icon-info) {
      margin-right: 5px;
      color: #979ba5;
    }
  }

  .icon-audit {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 30px;
    height: 30px;
    font-size: 16px;
    overflow: hidden;
    &::before {
      width: 16px;
      height: 16px;
    }
    &:hover {
      color: #63656e;
      cursor: pointer;
      border-radius: 50%;
      background-color: #f0f1f5;
    }
    &.active {
      border-radius: 2px;
      background-color: #e1ecff;
      color: #3a84ff;
    }
  }
  .common-nav-bar-single {
    padding-right: 19px;
  }
}
.custom-detail-page {
  display: flex;
  align-items: flex-start;
  max-height: calc(100% - 96px);
  height: calc(100% - 96px);
  overflow: hidden;
  .custom-detail {
    font-size: 12px;
    position: relative;
    max-height: 100%;
    padding: 0 16px 20px 20px;
    overflow-y: auto;
    flex: 1;
    // margin-bottom: 30px;
    .detail-information {
      padding: 20px 20px 4px 37px;
      border-radius: 2px;
      background: $whiteColor;
      box-shadow: 0 1px 2px 0 rgba(0, 0, 0, 0.1);
      margin-bottom: 16px;
      @include border-1px($color: $defaultBorderColor);
      &-title {
        font-weight: bold;
        color: $defaultFontColor;
        margin-bottom: 16px;
      }
      &-row {
        height: 32px;
        width: 576px;
        margin-bottom: 4px;
        display: flex;
        align-items: center;
        line-height: 16px;
        .row-label {
          text-align: right;
          width: 100px;
          margin-right: 26px;
          flex-shrink: 0;
        }
        .row-content {
          color: #313238;
          min-width: 0;
          overflow: hidden;
          text-overflow: ellipsis;
          white-space: nowrap;
        }
        .edit-name {
          color: $defaultBorderColor;
          font-size: 24px;
          &:hover {
            color: $primaryFontColor;
            cursor: pointer;
          }
        }
      }
      .last-row {
        margin-bottom: 72px;
      }
    }
    .detail-list {
      // padding-bottom: 24px;
      .list-header {
        display: flex;
        align-items: center;
        margin: 3px 0 25px 0;
        &-title {
          flex-grow: 1;
          font-weight: bold;
          .title-desc {
            color: $unsetIconColor;
            font-weight: normal;
          }
        }
        &-button {
          color: $primaryFontColor;
          margin-right: 8px;
        }
        &-refresh {
          margin-right: 10px;
          width: 110px;
        }
        &-immediately {
          margin-right: 10px;
          :deep(.icon-mc-alarm-recovered) {
            font-size: 16px;
          }
        }
        &-date {
          width: 110px;
        }
      }
      :deep(.custom-event-table) {
        .bk-virtual-render.bk-scroll-x {
          overflow-x: hidden;
        }
      }
      .mb16 {
        margin-bottom: 16px;
      }
      .button-control-wrap {
        display: flex;
        align-items: center;
        margin-bottom: 16px;
        .button-control-left {
          flex: 1;
          display: flex;
          .search-select-wrap {
            width: 240px;
          }
        }
        .export-btn {
          color: #3a84ff;
          margin-right: 24px;
          cursor: pointer;
        }
        .link {
          color: #3a84ff;
        }
        .import-disabled {
          cursor: not-allowed;
          .link {
            color: #c4c6cc;
          }
        }
        .icon-xiazai2,
        .icon-shangchuan {
          margin-right: 6px;
        }
      }
      .num-set {
        text-align: right;
        width: 48px;
      }
      .col-btn {
        color: #3a84ff;
        cursor: pointer;
      }
      :deep(.table-box) {
        display: flex;
        overflow: hidden;
        .bk-form-input,
        .bk-select {
          border: 1px solid #fff;
          &:hover {
            background: #f5f6fa;
            border: 1px solid #f5f6fa;
          }
        }
        .bk-form-input[disabled] {
          color: #63656e;
          background: #fff !important;
          border-color: #fff !important;
          cursor: no-drop;
        }
        .is-focus {
          border-color: #3a84ff;
          box-shadow: none;
          &:hover {
            background: #fff;
            border-color: #3a84ff;
          }
        }
        .bk-table-empty-text {
          padding: 29px 0 0 0;
          height: 92px;
        }

        .left-table {
          margin-right: 4px;
          width: 100%;
          transition: width 0.5s;
          .overflow-tips {
            text-overflow: ellipsis;
            overflow: hidden;
            white-space: nowrap;
          }
          .cell-margin {
            margin-left: -10px;
            .icon-change {
              color: #ea3636;
            }
          }
          .cell-span {
            height: 26px;
            line-height: 26px;
            padding-left: 1px;
          }
          .name {
            position: relative;
            .change-name {
              position: absolute;
              right: 10px;
              top: 0;
              font-size: 20px;
              color: #ea3636;
              i {
                font-size: 16px;
                margin-top: 5px;
              }
              .icon-remind {
                display: inline-block;
                cursor: pointer;
              }
            }
          }
          .input-err {
            :deep(.bk-form-input) {
              padding: 0 30px 0 10px;
            }
          }
          :deep(.bk-table-row td) {
            background: #fff !important;
          }
          .table-group-tags {
            display: flex;
            align-items: center;
            .table-group-tag {
              height: 22px;
              background: #f0f1f5;
              border-radius: 2px;
              padding: 0 10px;
              display: flex;
              align-items: center;
              justify-content: center;
              white-space: nowrap;
              margin-right: 8px;
              &:hover {
                background: #dcdee5;
              }
            }
          }
          .table-group-select {
            position: relative;
            min-width: 160px;
            height: 26px;
            padding-right: 40px;
            line-height: 26px;
            white-space: nowrap;
            padding-left: 8px;
            .icon-arrow-down {
              display: none;
              position: absolute;
              right: 8px;
              top: 0;
              font-size: 24px;
            }
            &:hover {
              background: #f0f1f5;
              .icon-arrow-down {
                display: inline-block;
              }
            }
          }
          .table-prepend {
            display: flex;
            align-items: center;
            justify-content: center;
            height: 32px;
            background: #f5f7fa;
            .group-select-wrap {
              min-height: auto;
            }
            .prepend-add-btn {
              color: #3a84ff;
              cursor: pointer;
              display: flex;
              align-items: center;
              .icon-mc-triangle-down {
                font-size: 16px;
              }
            }
          }
          .bk-table-empty-block {
            min-height: 300px;
            position: relative;
            top: -90px;
          }
        }
        .left-active {
          width: calc(100% - 420px);
        }
        .right-data {
          width: 420px;
          display: flex;
          flex-direction: column;
          .ul-head {
            display: flex;
            background: #000;
            .host-type {
              display: flex;
              align-items: center;
              justify-content: center;
              color: $whiteColor;
              height: 42px;
              width: 71px;
              background: #313238;
              position: relative;
              &:after {
                content: '';
                width: 71px;
                height: 2px;
                position: absolute;
                background: $primaryFontColor;
                top: 0;
              }
            }
            .data-time {
              margin-left: 15px;
              display: flex;
              align-items: center;
            }
          }
          .space-item {
            height: 34px;
            background: #63656e;
          }
          .data-preview {
            height: 43px;
            line-height: 43px;
            color: $unsetIconColor;
            background: #313238;
            padding: 0 20px;
            border-bottom: 1px solid #3b3c42;
          }
          .no-data-preview {
            height: 305px;
            width: 420px;
            background: #313238;
          }
        }
      }
      :deep(.bk-table-linear::before) {
        display: none;
      }
      .list-pagination {
        height: 64px;
        padding: 15px 0;
      }
    }
    :deep(.bk-sideslider-wrapper) {
      background: #313239;
    }
    .sideslider-title {
      display: flex;
      align-items: center;
      .title-explain {
        color: $unsetIconColor;
        font-size: 12px;
      }
    }
    // ::-webkit-scrollbar {
    //   display: none;
    // }
    .submit-div {
      display: inline-block;
    }
    .form-content-textarea {
      position: relative;
      bottom: -30px;
    }
  }
  .right-window {
    background: $whiteColor;
    z-index: 10;
    position: relative;
    height: calc(100vh - 104px);
    border: 0;
    width: 0px;
    overflow: visible;
    &.active {
      width: 400px;
      min-width: 400px;
      @include border-1px($color: $defaultBorderColor);
    }
    &-title {
      height: 40px;
      width: 100%;
      font-size: 14px;
      color: #313238;
      line-height: 40px;
      padding: 0 24px;
      display: flex;
      align-items: center;
      justify-content: space-between;
      .title-right {
        display: flex;
        align-items: center;
        justify-content: center;
        width: 24px;
        height: 24px;
        border-radius: 50%;
        &:hover {
          background: #eaebf0;
          cursor: pointer;
        }
        .line {
          width: 9px;
          height: 2px;
          background: #63656e;
        }
      }
    }
    &-content {
      height: calc(100% - 40px);
      padding: 16px 23px 0;
      color: $defaultFontColor;
      overflow-x: hidden;
      overflow-y: scroll;
      .content-title {
        font-weight: bold;
        margin-bottom: 10px;
      }
      .content-interval {
        margin-top: 25px;
      }
      .content-row {
        position: relative;
        margin-bottom: 16px;
        .content-example {
          overflow-x: auto;
          margin-top: 6px;
          padding: 10px 14px;
          background: #f4f4f7;
          overflow-x: auto;
        }
        .content-copy {
          position: absolute;
          top: 30px;
          right: 10px;
          width: 20px;
          height: 20px;
          text-align: center;
          line-height: 20px;
          background: #ffffff;
          box-shadow: 0 2px 4px 0 #1919290d;
          border-radius: 2px;
          @include hover($cursor: pointer);

          .icon-mc-copy {
            font-size: 12px;
            color: #3a84ff;
          }
        }
        .content-prometheus {
          position: relative;
          .content-copy-prometheus {
            position: absolute;
            top: 6px;
            right: 6px;
            width: 20px;
            height: 20px;
            text-align: center;
            line-height: 20px;
            background: #ffffff;
            box-shadow: 0 2px 4px 0 #1919290d;
            border-radius: 2px;
            @include hover($cursor: pointer);

            .icon-mc-copy {
              font-size: 12px;
              color: #3a84ff;
            }
          }
        }

        .copy-textarea {
          height: 0px;
          opacity: 0;
        }
      }
      pre {
        margin: 0;
        line-height: 20px;
      }
    }
    .right-button {
      position: absolute;
      left: -16px;
      top: calc(50% - 72px);
      z-index: 2;
      width: 16px;
      height: 72px;
      display: flex;
      align-items: center;
      justify-content: center;
      background: #eaebf0;
      border: 1px solid #dcdee5;
      border-radius: 4px 0 0 4px;

      @include hover($cursor: pointer);
      .icon {
        font-size: 24px;
        color: #979ba5;
      }
      div {
        margin: -4px 0 0 6px;
      }
    }
  }
}
.edit-group-manage {
  display: flex;
  align-items: center;
  justify-content: center;
  .icon-shezhi {
    font-size: 16px;
    margin-right: 4px;
  }
}
</style>
