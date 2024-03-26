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
    class="metric-group"
    :class="{ active: show }"
  >
    <div class="group-header">
      <div
        class="left-box"
        @click="show = !show"
      >
        <i
          class="bk-icon group-icon"
          :class="show ? 'icon-right-shape' : 'icon-down-shape'"
        />
        <div class="group-name">
          {{ groupName }}
        </div>
        <!-- 默认分组不允许编辑，删除，添加规则 -->
        <i
          v-if="!isDefaultGroup"
          class="icon-monitor icon-bianji edit-icon"
          @click.stop="handleEditGroup"
        />
        <div class="group-num">
          <i18n path="共{0}个指标，{1}个维度">
            <span class="num-blod">{{ getMetricNum }}</span>
            <span class="num-blod">{{ getDimensionNum }}</span>
          </i18n>
        </div>
        <div
          v-if="!isDefaultGroup"
          class="rules-select"
        >
          <div
            class="rules-label"
            v-en-style="'width: 85px'"
          >
            {{ $t('匹配规则') }}
          </div>
          <div class="rules-content">
            <div
              :class="rulesClass"
              ref="rulesWrapRef"
            >
              <template v-for="rule of localGroupRules">
                <div
                  v-if="rule.type === 'value'"
                  :key="rule.value"
                  ref="ruleItemRef"
                  class="rule-item rule-tag"
                  @click.stop="e => showAddRulePopover(e, rule.value)"
                >
                  <span class="rule-name">{{ rule.value }}</span>
                  <i
                    class="icon-monitor icon-mc-close"
                    @click.stop="handleDelRule(rule.value)"
                  />
                </div>
                <div
                  v-if="rule.type === 'num-mark'"
                  :key="rule.type"
                  ref="rulesMarkRef"
                  class="rule-item rules-num-mark"
                  @click.stop="handleExpand"
                >
                  +{{ hiddenRuleNumber }}
                </div>
                <i
                  v-if="rule.type === 'add'"
                  :key="rule.type"
                  ref="addRuleRef"
                  class="icon-monitor icon-plus-line add-rule"
                  @click.stop="e => showAddRulePopover(e, '')"
                />
              </template>
            </div>
          </div>
        </div>
      </div>
      <div class="right-box">
        <bk-button
          text
          size="small"
          @click.stop="addRow('metric')"
        >
          <span class="icon-monitor icon-plus-line" />
          <span>{{ $t('指标') }}</span>
        </bk-button>
        <bk-button
          text
          size="small"
          class="mr-14"
          @click.stop="addRow('dimension')"
        >
          <span class="icon-monitor icon-plus-line" />
          <span>{{ $t('维度') }}</span>
        </bk-button>
        <bk-popconfirm
          v-if="!isDefaultGroup"
          :content="$t('是否删除该分组?')"
          width="288"
          trigger="click"
          @confirm="handleDelGroup"
        >
          <i class="icon-monitor icon-mc-delete-line" />
        </bk-popconfirm>
      </div>
    </div>
    <transition
      :css="false"
      @before-enter="beforeEnter"
      @enter="enter"
      @after-enter="afterEnter"
      @before-leave="beforeLeave"
      @leave="leave"
      @after-leave="afterLeave"
    >
      <div
        class="table-box"
        v-show="!show"
      >
        <div
          class="left-table"
          :class="{ 'left-active': isShowData }"
        >
          <bk-table
            :data="paginationData"
            :outer-border="false"
            :pagination="pagination"
            :show-pagination-info="false"
            :row-class-name="handleRowClassName"
            @page-change="handlePageChange"
            @page-limit-change="handleLimitChange"
          >
            <bk-table-column
              width="80"
              align="center"
              :render-header="renderSelection"
              :resizable="false"
            >
              <template slot-scope="scope">
                <bk-checkbox
                  v-model="scope.row.isCheck"
                  :disabled="scope.row.monitor_type === 'dimension'"
                  @change="handleCheckMetric(scope)"
                />
              </template>
            </bk-table-column>
            <bk-table-column
              :label="$t('指标/维度')"
              width="100"
            >
              <template slot-scope="scope">
                {{ scope.row.monitor_type === 'metric' ? $t('指标') : $t('维度') }}
              </template>
            </bk-table-column>
            <bk-table-column
              :label="$t('指标名')"
              min-width="150"
            >
              <template slot-scope="scope">
                <div class="cell-margin name">
                  <div
                    @mouseenter="handleInputMouseEnter(...arguments, scope.$index, scope.row.source_name)"
                    @mouseleave="handleInputMouseLeave"
                    class="name-cell-content"
                    :ref="'inputmetric' + scope.$index"
                  >
                    <div
                      v-if="!scope.row.showInput || scope.row.isFirst"
                      class="overflow-tips"
                      v-bk-overflow-tips
                      @click="handleClickInput(scope)"
                    >
                      <span v-if="scope.row.name">{{ scope.row.name }}</span>
                      <span
                        v-else
                        style="color: #c4c6cc"
                      >
                        {{ $t('输入指标id') }}
                      </span>
                    </div>
                    <bk-input
                      v-else
                      :value="scope.row.name"
                      :placeholder="scope.row.monitor_type === 'metric' ? $t('输入指标id') : $t('输入维度id')"
                      size="small"
                      :disabled="scope.row.isFirst || !!scope.row.source_name"
                      @blur="val => handleCheckName(scope.row, val)"
                      :class="{ 'input-err': scope.row.errValue || scope.row.reValue }"
                      :ref="`input${scope.$index}`"
                    />

                    <span
                      v-if="scope.row.errValue"
                      v-bk-tooltips="{
                        content: $t('注意: 名字冲突'),
                        placements: ['top']
                      }"
                      class="icon-monitor icon-remind fz-14"
                    />
                    <span
                      v-else-if="scope.row.reValue"
                      v-bk-tooltips="{
                        content: $t('自动转换'),
                        placements: ['top']
                      }"
                      @click.stop="handleRename(scope.row)"
                      class="zhuanghuan-btn"
                    >
                      <span class="icon-monitor icon-zhuanhuan" />
                    </span>
                  </div>
                </div>
              </template>
            </bk-table-column>
            <bk-table-column
              :label="$t('别名')"
              min-width="150"
            >
              <template slot-scope="scope">
                <div class="cell-margin name">
                  <bk-input
                    v-model="scope.row.description"
                    size="small"
                    :placeholder="scope.row.monitor_type === 'metric' ? $t('输入指标别名') : $t('输入维度别名')"
                    @blur="handleCheckDescName(scope.row)"
                    :class="{ 'input-err': scope.row.descReValue }"
                  />
                  <bk-popover
                    class="change-name"
                    placemnet="top-start"
                    trigger="mouseenter"
                    :tippy-options="{ a11y: false }"
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
            <bk-table-column
              :label="$t('类型')"
              width="100"
            >
              <template slot-scope="scope">
                <template v-if="scope.row.monitor_type === 'metric'">
                  <div
                    v-if="numType.value && numType.index === scope.$index"
                    class="cell-margin"
                    @mouseleave="handleMouseLeave('numType')"
                  >
                    <bk-select
                      v-model="scope.row.type"
                      :popover-options="selectPopoverOption"
                      @change="handleTypeChange(scope.row)"
                      :clearable="false"
                      @toggle="handleToggleChange(...arguments, 'numType')"
                    >
                      <bk-option
                        v-for="option in typeList"
                        :key="option.id"
                        :id="option.id"
                        :name="option.name"
                      />
                    </bk-select>
                  </div>
                  <div
                    v-else
                    class="cell-span"
                    @mouseenter="handleMouseenter(scope.$index, 'numType')"
                  >
                    {{ scope.row.type }}
                  </div>
                </template>
                <template v-else>
                  <div class="cell-span">
                    {{ scope.row.type }}
                  </div>
                </template>
              </template>
            </bk-table-column>
            <bk-table-column
              :label="$t('单位')"
              width="130"
            >
              <template slot-scope="scope">
                <div
                  class="cell-margin"
                  v-if="unit.value && unit.index === scope.$index && scope.row.monitor_type === 'metric'"
                  @mouseleave="handleMouseLeave('unit')"
                >
                  <bk-select
                    v-model="scope.row.unit"
                    :clearable="false"
                    :popover-width="120"
                    @toggle="handleToggleChange(...arguments, 'unit')"
                    @change="handleUnitChange(scope.row)"
                    :popover-options="selectPopoverOption"
                  >
                    <bk-option-group
                      v-for="(group, index) in unitList"
                      :name="group.name"
                      :key="index"
                    >
                      <bk-option
                        v-for="option in group.formats"
                        :key="option.id"
                        :id="option.id"
                        :name="option.name"
                      />
                    </bk-option-group>
                  </bk-select>
                </div>
                <div
                  v-else
                  class="cell-span"
                  @mouseenter="handleMouseenter(scope.$index, 'unit')"
                >
                  {{ handleFindUnitName(scope.row.unit) }}
                </div>
              </template>
            </bk-table-column>
            <bk-table-column
              :label="$t('启/停')"
              width="90"
            >
              <template slot-scope="scope">
                <bk-switcher
                  v-model="scope.row.is_active"
                  size="small"
                  theme="primary"
                  @change="handleActiveChange(scope.row)"
                />
              </template>
            </bk-table-column>
            <bk-table-column
              :label="$t('操作')"
              width="90"
              prop="create_time"
            >
              <template slot-scope="scope">
                <i
                  class="icon-monitor icon-mc-plus-fill"
                  @click="handleAddRow(scope)"
                />
                <i
                  class="icon-monitor icon-mc-minus-plus"
                  :class="{ 'not-del': !scope.row.isDel }"
                  @click="handleDelRow(scope)"
                />
              </template>
            </bk-table-column>
            <div
              slot="empty"
              class="empty"
            >
              <i class="icon-monitor icon-remind empty-i" />
              <div>
                {{ $t('暂无指标/维度') }}
                <span
                  class="blue"
                  @click="handleAddFirstRow"
                >
                  {{ $t('添加') }}
                </span>
              </div>
            </div>
          </bk-table>
        </div>
        <template v-if="!isFromHome">
          <div
            class="right-data"
            v-show="isShowData"
          >
            <ul class="ul-head">
              <li
                class="host-type"
                :class="{ active: osIndex === dataPreview.index }"
                v-for="(osType, osIndex) in osTypeList"
                :key="osIndex"
                @click="handleDataChange(osIndex, osType)"
              >
                {{ osType }}
              </li>
            </ul>
            <template v-if="paginationData.length">
              <div
                class="data-preview"
                v-for="(item, index) in paginationData"
                :key="index"
              >
                {{
                  [undefined, null].includes(item.value[dataPreview.type]) ? '--' : item.value[dataPreview.type] + ''
                }}
              </div>
            </template>
            <div
              v-else
              class="no-data-preview"
            />
          </div>
        </template>
      </div>
    </transition>

    <div style="display: none">
      <div
        ref="addRulePopoverRef"
        class="add-rule-popover-content"
      >
        <bk-input
          class="rule-name-input"
          v-model="addRule.name"
          clearable
        />
        <div
          class="err-msg"
          :style="{ display: addRule.msg ? 'block' : 'none' }"
        >
          {{ addRule.msg }}
        </div>
        <div class="desc">
          {{ $t('支持JS正则匹配方式， 如子串前缀匹配go_，模糊匹配(.*?)_total') }}
        </div>
        <div class="footer">
          <bk-button
            theme="primary"
            @click="addRuleConfirm"
          >
            {{ $t('保存并匹配') }}
          </bk-button>
          <bk-button
            theme="default"
            @click="addRuleCancel"
          >
            {{ $t('取消') }}
          </bk-button>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
/* eslint-disable vue/no-mutating-props */
import { mapActions } from 'vuex';

import { collapseMixin } from '../../../../../common/mixins';
import ColumnCheck from '../../../../performance/column-check/column-check.vue';
import { judgeIsIllegal, metricNameTransFrom } from '../../../utils';

export default {
  name: 'MetricGroup',
  mixins: [collapseMixin],
  props: {
    isDefaultGroup: {
      // 是否是默认分组
      type: Boolean,
      default: false
    },
    metricData: {
      //  指标/维度数据
      type: Array,
      default: () => []
    },
    hideStop: Boolean,
    groupRules: {
      type: Array,
      default: () => []
    },
    groupName: String, //  分组名字
    groupIndex: Number, //  分组索引
    isShowData: Boolean, //  数据预览开关
    osTypeList: {
      //  调试类型
      type: Array,
      default: () => []
    },
    nameList: {
      // 英文名列表
      type: Array,
      default: () => []
    },
    descNameList: {
      //  别名列表
      type: Array,
      default: () => []
    },
    isFromHome: {
      type: Boolean,
      default: false
    },
    unitList: {
      //  动态单位表
      type: Array,
      default: () => []
    },
    typeList: {
      type: Array,
      default() {
        return [
          //  类别表
          { id: 'double', name: 'double' },
          { id: 'int', name: 'int' }
        ];
      }
    },
    transFromAll: {
      type: String,
      default: ''
    }
  },
  data() {
    return {
      show: false, //  是否展开
      dataPreview: {
        //  数据预览参数
        index: 0,
        type: this.osTypeList[0]
      },
      numType: {
        value: true,
        index: -1,
        toggle: false
      },
      unit: {
        value: true,
        index: -1,
        toggle: false
      },
      instance: null,
      selectPopoverOption: {
        boundary: 'body',
        flipBehavior: ['bottom']
      },
      pagination: {
        current: 1,
        count: this.metricData.length,
        limit: 10,
        limitList: [10, 20, 50, 100]
      },
      selectList: [
        {
          id: 'current',
          name: this.$t('本页全选')
        },
        {
          id: 'all',
          name: this.$t('跨页全选')
        }
      ],
      checkType: 'current',
      addRule: {
        name: '',
        index: -1,
        instance: null,
        msg: ''
      },
      rulesClass: {
        'rules-wrap': true,
        expand: false
      },
      hiddenRuleNumber: 0
    };
  },
  computed: {
    localGroupRules() {
      const data = this.groupRules.map(item => ({
        type: 'value',
        value: item
      }));
      /** 如果是展开状态或者没有隐藏的规则项，则额外补充一个添加按钮 */
      if (this.hiddenRuleNumber === 0 || this.rulesClass.expand) {
        return [
          ...data,
          {
            type: 'add'
          }
        ];
      }
      /** 根据需要隐藏的规则项数量，拼接展示 */
      return [
        ...data.slice(0, data.length - this.hiddenRuleNumber),
        {
          type: 'num-mark'
        },
        {
          type: 'add'
        },
        ...data.slice(data.length - this.hiddenRuleNumber)
      ];
    },
    // 表格前端分页
    paginationData() {
      const { limit, current } = this.pagination;
      // 根据是否开启隐藏已停用功能来判断展示的内容
      return this.metricData
        .filter(item => !this.hideStop || (this.hideStop && item.is_active))
        .sort((a, b) => a.name.localeCompare(b.name))
        .slice(limit * (current - 1), limit * current);
    },
    // 指标数量
    getMetricNum() {
      const res = this.metricData.filter(item => item.monitor_type === 'metric' && item.name !== '');
      return res.length;
    },
    // 维度数量
    getDimensionNum() {
      const res = this.metricData.filter(item => item.monitor_type === 'dimension' && item.name !== '');
      return res.length;
    },
    //  是否半选
    indeterminateValue() {
      if (this.checkType === 'current') {
        return this.paginationData.some(item => item.isCheck);
      }
      return this.metricData.some(item => item.isCheck);
    },
    // 是否全选
    allCheckValue() {
      if (this.checkType === 'current' && this.paginationData.length) {
        return this.paginationData.every(item => item.isCheck || item.monitor_type === 'dimension');
      }

      if (this.checkType === 'all' && this.metricData.length) {
        return this.metricData.every(item => item.isCheck || item.monitor_type === 'dimension');
      }

      return false;
    },
    // 是否全部为维度
    isAllDimension() {
      const data = this.checkType === 'current' ? this.paginationData : this.metricData;
      return data.every(item => item.monitor_type === 'dimension');
    },
    checkValue() {
      if (this.isAllDimension) {
        return 0;
      }

      if (this.allCheckValue) {
        return 2;
      }
      if (this.indeterminateValue) {
        return 1;
      }
      return 0;
    }
  },
  watch: {
    metricData(data) {
      this.pagination.count = data.length;
      this.$nextTick(() => {
        // 当前页全部删除时，跳转到上一页
        if (!this.paginationData.length && this.pagination.current > 1) {
          this.pagination.current -= 1;
        }
      });
    },
    transFromAll() {
      this.metricData.forEach((item) => {
        this.reNameFn(item);
      });
    },
    /** 监听匹配规则变化，判断有几条规则无法展示 */
    groupRules: {
      handler(val) {
        this.hiddenRuleNumber = 0;
        this.$nextTick(async () => {
          if (!val.length) return;
          /** 每个规则项之间的间距 */
          const MARGIN = 4;
          /** 数字标记占用宽度 */
          const numMarkWidth = 41;
          /** 已显示规则项的总宽度 */
          let widthTotal = 0;
          const { rulesWrapRef, addRuleRef } = this.$refs;
          const ruleTagList = rulesWrapRef.querySelectorAll('.rule-tag');
          /** 获取规则容器的宽度 */
          let { width: wrapWidth } = rulesWrapRef.getBoundingClientRect();
          if (wrapWidth <= 0) {
            await this.$nextTick();
            wrapWidth = rulesWrapRef.getBoundingClientRect().width || 0;
          }
          /** 获取添加规则按钮的宽度，默认为0 */
          const { width: addRuleWidth = 0 } = addRuleRef?.[0].getBoundingClientRect();
          /** 预留添加规则按钮和数字标记按钮宽度 */
          widthTotal = addRuleWidth + numMarkWidth;
          /** 查找开始被隐藏的规则项的索引 */
          const startInd = Array.from(ruleTagList).findIndex((item) => {
            const { width } = item.getBoundingClientRect();
            /*
             * 如果当前规则项的宽度加上已显示的规则项总宽度大于容器宽度,隐藏当前规则
             */
            if (widthTotal + width + MARGIN > wrapWidth) {
              return true;
            }
            /** 记录显示规则项的总宽度 */
            widthTotal += width + MARGIN;
            return false;
          });
          /** 如果没有需要隐藏的规则项，则赋值为0 */
          this.hiddenRuleNumber = startInd === -1 ? 0 : val.length - startInd;
        });
      },
      immediate: true
    }
  },
  async created() {
    this.metricData.forEach((row) => {
      this.checkNameFn(row);
    });
  },
  methods: {
    ...mapActions('plugin-manager', ['getReservedWords']),
    //  编辑分组
    handleEditGroup() {
      this.$emit('edit-group', this.groupIndex);
    },
    //  删除分组
    handleDelGroup() {
      this.$emit('del-group', this.groupIndex);
    },
    // 在当前行下面新增一行指标/维度
    handleAddRow(scope) {
      this.$emit('add-row', scope.row, this.groupIndex);
    },
    // 删除行
    handleDelRow(scope) {
      if (scope.row.isDel) {
        this.$emit('del-row', scope.row, this.groupIndex);
      }
    },
    //  增加初始行
    handleAddFirstRow() {
      this.$emit('add-first', this.groupIndex);
    },
    //  勾选指标联动勾选维度
    handleCheckMetric(scope) {
      if (scope.row.tag_list) {
        scope.row.tag_list.forEach((dimension) => {
          this.metricData.forEach((item) => {
            if (dimension.field_name === item.name) {
              item.isCheck = scope.row.isCheck;
            }
          });
        });
      }
    },
    // 勾选全部
    handleCheckAll({ value, type }) {
      this.resetCheckStatus(); // 从跨页全选切换到本页或者取消全选都要清空勾选操作
      // 全选操作
      if (value === 2) {
        // 有关联指标的维度集合
        const relatedDimensions = new Set();
        const data = type === 'current' ? this.paginationData : this.metricData;
        data.forEach((item) => {
          // 维度不能被勾选
          item.isCheck = value === 2 && item.monitor_type !== 'dimension';
          // 收集已勾选指标所关联的维度
          item.monitor_type === 'metric'
            && (item.tag_list || []).forEach(item => relatedDimensions.add(item.field_name));
        });
        // 自动勾选关联的维度
        this.metricData.forEach((item) => {
          item.monitor_type === 'dimension' && (item.isCheck = relatedDimensions.has(item.name));
        });
      }
      this.checkType = type;
    },
    // 数据预览切换
    handleDataChange(osIndex, osType) {
      this.dataPreview.index = osIndex;
      this.dataPreview.type = osType;
    },
    // 英文名失焦校验
    handleCheckName(row, val) {
      const oldName = row.name;
      row.name = val;
      this.$emit('edit-row', {
        type: 'name',
        data: {
          oldName,
          ...row
        },
        groupIndex: this.groupIndex
      });
      this.checkNameFn(row);
    },
    /* 英文名校验 */
    checkNameFn(row) {
      // 校验名字是否与关键字冲突
      const index = this.metricData.findIndex(item => item.id === row.id);
      const data = this.metricData[index];
      if (row.name !== '') {
        if (row.monitor_type === 'metric' && this.nameList.filter(item => item === row.name).length > 1) {
          data.errValue = true;
          data.reValue = false;
        } else if (
          row.monitor_type === 'dimension'
          && this.metricData.filter(item => item.name === row.name).length > 1
        ) {
          data.errValue = true;
          data.reValue = false;
        } else if (!judgeIsIllegal(row.name)) {
          data.errValue = false;
          data.reValue = true;
        } else {
          data.reValue = false;
          data.errValue = false;
        }
        row.showInput = false;
      } else {
        data.errValue = false;
        data.reValue = false;
      }
    },
    // 别名失焦校验
    handleCheckDescName(row) {
      // 校验名字是否与关键字冲突
      this.$set(row, 'descReValue', row.descReValue);
      if (row.description !== '') {
        if (this.descNameList.filter(item => item === row.description).length > 1) {
          row.descReValue = true;
        } else {
          row.descReValue = false;
        }
      } else {
        row.descReValue = false;
      }

      this.$emit('edit-row', {
        type: 'description',
        data: row,
        groupIndex: this.groupIndex
      });
    },
    //  转化有冲突的关键字指标/维度名
    handleRename(row) {
      this.reNameFn(row);
    },
    reNameFn(row) {
      const index = this.metricData.findIndex(item => item.id === row.id);
      this.metricData[index].source_name = row.name;
      this.metricData[index].name = metricNameTransFrom(row.name);
      this.metricData[index].reValue = false;
      this.checkNameFn(row);
    },
    handleInputMouseEnter(e, index, sourceName) {
      if (!sourceName) return;
      const inputRef = this.$refs[`inputmetric${index}`];
      this.instance = this.$bkPopover(inputRef, {
        content: this.$t('已转化成非冲突名字'),
        arrow: true,
        showOnInit: true,
        distance: 0,
        placement: 'top-start'
      });
      this?.instance?.show(100);
    },
    handleInputMouseLeave() {
      if (this.instance) {
        this.instance.hide(0);
        this.instance.destroy();
        this.instance = null;
      }
    },
    handleMouseenter(index, type) {
      if (type === 'numType') {
        this.numType.value = true;
        this.numType.index = index;
      } else {
        this.unit.value = true;
        this.unit.index = index;
      }
    },
    handleMouseLeave(type) {
      if (type === 'numType' && !this.numType.toggle) {
        this.numType.value = false;
        this.numType.index = -1;
      } else if (type === 'unit' && !this.unit.toggle) {
        this.unit.value = false;
        this.unit.index = -1;
      }
    },
    handleToggleChange(value, type) {
      if (type === 'numType') {
        this.numType.toggle = value;
      } else {
        this.unit.toggle = value;
      }
    },
    handleTypeChange(row) {
      row.is_diff_metric = row.type === 'diff';
      this.$emit('edit-row', {
        type: 'type',
        data: row,
        groupIndex: this.groupIndex
      });
    },
    handleUnitChange(row) {
      this.$emit('edit-row', {
        type: 'unit',
        data: row,
        groupIndex: this.groupIndex
      });
    },
    handleActiveChange(row) {
      this.$emit('edit-row', {
        type: 'active',
        data: row,
        groupIndex: this.groupIndex
      });
    },
    //  找到单位值对应的name
    handleFindUnitName(id) {
      let name = id;
      this.unitList.forEach((group) => {
        const res = group.formats.find(item => item.id === id);
        if (res) {
          name = res.name;
        }
      });
      return name;
    },
    // select表头渲染
    renderSelection(h) {
      return h(ColumnCheck, {
        props: {
          list: this.selectList,
          value: this.checkValue,
          defaultType: this.checkType,
          disabled: this.isAllDimension
        },
        on: {
          change: this.handleCheckAll
        }
      });
    },
    handleClickInput(scope) {
      scope.row.showInput = true;
      this.$nextTick(() => {
        const refname = `input${scope.$index}`;
        this.$refs?.[refname]?.focus();
      });
    },
    handlePageChange(page) {
      this.pagination.current = page;
    },
    handleLimitChange(limit) {
      this.pagination.current = 1;
      this.pagination.limit = limit;
    },
    resetCheckStatus() {
      this.metricData.forEach((item) => {
        // 维度不能被勾选
        item.isCheck = false;
      });
    },
    addRow(type) {
      this.handleAddRow({
        row: {
          monitor_type: type
        },
        groupIndex: this.groupIndex
      });
    },
    /**
     * @description: 当出现数据冲突情况给当前表格行添加类名
     * @param {*} row 当前行数据
     * @param {*} rowIndex 当前行索引
     * @return {*}
     */
    handleRowClassName({ row }) {
      return row.errValue || row.reValue || row.descReValue ? 'table-error-row' : '';
    },
    showAddRulePopover(e, val) {
      this.addRule.name = val;
      this.addRule.index = this.groupRules.findIndex(item => item === val);
      this.addRule.instance = this.$bkPopover(e.target, {
        content: this.$refs.addRulePopoverRef,
        trigger: 'click',
        placement: 'bottom',
        boundary: 'window',
        arrow: true,
        theme: 'light common-monitor',
        zIndex: 9999,
        interactive: true,
        onHidden: () => {
          this.addRule.instance?.destroy();
          this.addRule.instance = null;
          this.addRule.msg = '';
        }
      });
      this.addRule.instance?.show();
    },
    handleDelRule(rule) {
      this.$emit(
        'del-rule',
        this.groupRules.findIndex(item => item === rule)
      );
      this.changeCheckStatus();
    },
    addRuleConfirm() {
      if (!this.addRule.name) {
        this.addRule.msg = this.$tc('规则名不能为空');
        return;
      }
      if (this.groupRules.includes(this.addRule.name)) {
        this.addRule.msg = this.$tc('匹配规则重复了');
        return;
      }
      this.addRule.msg = '';
      this.$emit('add-rule', this.addRule.name, this.addRule.index);
      this.changeCheckStatus();
      this.addRuleCancel();
    },
    changeCheckStatus() {
      this.paginationData.forEach((metric) => {
        if (metric.tag_list) {
          metric.tag_list.forEach((name) => {
            this.paginationData.forEach((item) => {
              if (name === item.name) {
                item.isCheck = false;
              }
            });
          });
        }
      });
    },
    addRuleCancel() {
      this.addRule.instance?.hide();
    },
    handleDocumentClick(e) {
      if (!this.$refs.rulesWrapRef.contains(e.target) && !this.$refs.addRulePopoverRef.contains(e.target)) {
        this.rulesClass.expand = false;
        document.removeEventListener('click', this.handleDocumentClick, false);
      }
    },
    handleExpand() {
      this.rulesClass.expand = true;
      document.addEventListener('click', this.handleDocumentClick, false);
    }
  }
};
</script>

<style lang="scss" scoped>
/* stylelint-disable no-descending-specificity */

.pl5 {
  padding-left: 5px;
}

.pr5 {
  padding-right: 5px;
}

.mr-12 {
  margin-right: 14px;
}

.metric-group {
  margin-top: 16px;
  color: #63656e;
  transition: height .5s;

  :deep(.bk-form-input),
  :deep(.bk-select) {
    border: 1px solid #fff;

    &:hover {
      background: #f5f6fa;
      border: 1px solid #f5f6fa;
    }
  }

  :deep(.bk-table-header) {
    .is-first {
      .bk-table-header-label {
        overflow: visible;
      }
    }
  }

  .num-blod {
    font-weight: bold;
  }

  .group-header {
    display: flex;
    align-items: center;
    height: 40px;
    background: #f0f1f5;
    border: 1px solid #dcdee5;
    border-bottom: 1px solid #f0f1f5;
    border-radius: 2px 2px 0 0;

    .left-box {
      display: flex;
      flex: 1;
      align-items: center;
      height: 40px;
      padding-left: 16px;
      cursor: pointer;

      .group-icon {
        margin-right: 8px;
        font-size: 15px;
      }

      .group-name {
        margin-right: 8px;
        font-size: 14px;
        font-weight: bold;
      }

      .group-num {
        margin-left: 40px;
        color: #979ba5;
      }

      .rules-select {
        display: flex;
        flex: 1;
        align-items: center;
        padding-left: 150px;

        .rules-label {
          width: 60px;
          margin-right: 8px;
          font-size: 12px;
          color: #63656e;
        }

        .rules-content {
          position: relative;
          flex: 1;
          height: 22px;
        }

        .rules-wrap {
          display: flex;
          flex-wrap: wrap;
          height: 22px;
          overflow-y: hidden;
        }

        .rules-wrap.expand {
          position: absolute;
          z-index: 999;
          width: 100%;
          height: auto;
          padding: 5px 0 0 5px;
          background-color: #fff;
          border: 1px solid #dcdee5;

          .rule-item {
            width: max-content;
            margin-bottom: 5px;
          }
        }

        .rule-item {
          display: flex;
          align-items: center;
          max-width: calc(100% - 5px);
          height: 22px;
          padding: 0 16.5px;
          margin-right: 4px;
          font-size: 12px;
          line-height: 20px;
          background: #fafbfd;
          border: 1px solid #979ba54d;
          border-radius: 2px;

          &.active,
          &:hover {
            padding: 0 5px 0 10px;
            color: #3a84ff;
            background: #edf4ff;
            border: 1px solid #3a84ff4d;
            border-radius: 2px;

            .icon-mc-close {
              display: inline-block;
            }
          }

          .rule-name {
            max-width: 100%;
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
          }

          .icon-mc-close {
            display: none;
            font-size: 18px;
          }
        }

        .rules-num-mark {
          justify-content: center;
          width: 37px;
          padding: 0;

          &:hover {
            padding: 0;
          }
        }

        .add-rule {
          padding: 5px;
          line-height: normal;
          color: #3a84ff;
        }
      }

      .icon-right-shape {
        color: #c4c6cc;
      }

      .icon-down-shape {
        color: #63656e;
      }
    }

    .edit-icon {
      font-size: 24px;
      color: #979ba5;
      cursor: pointer;

      &:hover {
        color: #3a84ff;
      }
    }

    .icon-mc-delete-line {
      margin-right: 28px;
      font-size: 16px;
      cursor: pointer;

      &:hover {
        color: #3a84ff;
      }
    }

    .right-box {
      display: flex;
      align-items: center;
      justify-content: end;
      width: 230px;
      height: 40px;

      .icon-plus-line {
        font-size: 14px;
      }
    }
  }

  &.active {
    .group-header {
      border-bottom: 1px solid #dcdee5;
    }
  }

  .table-box {
    display: flex;
    overflow-x: hidden;
    border: 1px solid #dcdee5;
    border-top: none;

    .left-table {
      width: 100%;
      transition: width .5s;

      .name {
        position: relative;

        .change-name {
          position: absolute;
          top: 0;
          right: 10px;
          font-size: 20px;
          color: #ea3636;

          i {
            display: inline-block;
            margin-top: 5px;
            font-size: 16px;
          }

          .icon-remind {
            cursor: pointer;
          }

          .icon-change {
            margin-top: 2px;
            font-size: 20px;
          }
        }
      }

      .cell-margin {
        margin-left: -10px;

        .overflow-tips {
          flex: 1;
          height: 26px;
          padding-left: 11px;
          overflow: hidden;
          line-height: 26px;
          text-overflow: ellipsis;
          white-space: nowrap;

          &:hover {
            background: #f5f6fa;
          }
        }

        .icon-change {
          font-size: 20px;
          color: #ea3636;
        }
      }

      .cell-span {
        height: 26px;
        padding-left: 1px;
        line-height: 26px;
      }

      .icon-mc-plus-fill,
      .icon-mc-minus-plus {
        font-size: 16px;
        color: #c4c6cc;
        cursor: pointer;

        &:hover {
          color: #3a84ff;
        }
      }

      .icon-mc-plus-fill {
        margin-right: 12px;
      }

      .not-del {
        color: #dcdee5;
        cursor: no-drop;
      }

      .input-err {
        :deep(.bk-form-input) {
          padding: 0 30px 0 10px;
        }
      }

      .zhuanghuan-btn {
        display: inline-flex;
        align-items: center;
        justify-content: center;
        width: 22px;
        height: 22px;
        margin-left: 8px;
        cursor: pointer;
        background: #fee;
        border: 1px solid #fd9c9c66;
        border-radius: 2px;

        .icon-zhuanhuan {
          color: #ea3636;
        }

        &:hover {
          background: #ea3636;
          border: 1px solid #ea3636;

          .icon-zhuanhuan {
            color: #fff;
          }
        }
      }

      .fz-14 {
        font-size: 14px;
      }

      .icon-remind {
        color: #ea3636;
      }

      .name-cell-content {
        display: flex;
        align-items: center;
        justify-content: space-between;
      }

      :deep(.bk-table-row) {
        td {
          /* stylelint-disable-next-line declaration-no-important */
          background: #fff;
        }
      }

      :deep(.table-error-row) {
        td {
          background: #f0f1f5;
        }
      }

      :deep(.bk-form-input[disabled]) {
        color: #63656e;
        cursor: no-drop;

        /* stylelint-disable-next-line declaration-no-important */
        background: #fff !important;

        /* stylelint-disable-next-line declaration-no-important */
        border-color: #fff !important;
      }

      :deep(.is-focus) {
        border-color: #3a84ff;
        box-shadow: none;

        &:hover {
          background: #fff;
          border-color: #3a84ff;
        }
      }

      .empty {
        display: flex;
        flex-direction: column;
        align-items: center;
        height: 93px;
        padding-top: 32px;

        &-i {
          margin-bottom: 4px;
          font-size: 24px;
          color: #c4c6cc;
          cursor: pointer;
        }

        .blue {
          color: #3a84ff;
          cursor: pointer;
        }
      }

      :deep(.bk-table-empty-text) {
        padding: 0;
      }
    }

    .left-active {
      width: calc(100% - 300px);
    }

    .right-data {
      display: flex;
      flex-direction: column;
      width: 300px;

      .ul-head {
        display: flex;
        background: #000;

        .host-type {
          display: flex;
          align-items: center;
          justify-content: center;
          min-width: 71px;
          height: 42px;
          padding: 0 16px;
          color: #fff;
          cursor: pointer;
        }

        .active {
          position: relative;
          height: 42px;
          overflow: hidden;
          background: #313238;

          &:after {
            position: absolute;
            top: 0;
            width: 100%;
            height: 2px;
            content: '';
            background: #3a84ff;
          }
        }
      }

      .data-preview {
        height: 43px;
        padding: 0 20px;
        line-height: 43px;
        color: #979ba5;
        background: #313238;
        border-bottom: 1px solid #3b3c42;
      }

      .no-data-preview {
        width: 420px;
        height: 93px;
        background: #313238;
      }
    }
  }
}

:deep(.bk-group-options) {
  .bk-option-content {
    padding: 0 0 0 16px;
  }
}

.add-rule-popover-content {
  padding: 16px;

  .rule-name-input {
    width: 250px;
    margin-bottom: 4px;
  }

  .err-msg {
    line-height: 20px;
    color: #f56c6c;
  }

  .desc {
    margin-bottom: 15px;
    font-size: 12px;
    line-height: 20px;
    color: #979ba5;
  }

  .footer {
    text-align: right;

    .bk-button {
      height: 26px;
      padding: 0 12px;
      font-size: 12px;
      line-height: 26px;
    }
  }
}
</style>
