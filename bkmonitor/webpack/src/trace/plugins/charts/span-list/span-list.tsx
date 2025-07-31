/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台社区版 (BlueKing PaaS Community Edition) available.
 *
 * Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
 *
 * 蓝鲸智云PaaS平台社区版 (BlueKing PaaS Community Edition) is licensed under the MIT License.
 *
 * License for 蓝鲸智云PaaS平台社区版 (BlueKing PaaS Community Edition):
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

import { type PropType, computed, defineComponent, reactive, ref, watch } from 'vue';

import { Pagination, Popover } from 'bkui-vue';
import { useI18n } from 'vue-i18n';

import { customFormatTime, formatDate, formatDuration } from '../../../components/trace-view/utils/date';
import { getSpanKindIcon } from '../../../utils';

import './span-list.scss';

export interface SpanListItem {
  bgColor?: string;
  collapsed?: boolean;
  collapsedSpanNum?: number;
  color: string;
  duration: number;
  icon: string;
  kind: number;
  mark?: string;
  name: string;
  operationName: string;
  spanId: string;
  spanIds?: string[];
  startTime: number;
}

export default defineComponent({
  name: 'SpanList',
  props: {
    // 子标题
    subTitle: {
      type: String,
      required: false,
      default: '',
    },
    // 对比状态
    isCompare: {
      type: Boolean,
      default: false,
    },
    spanList: {
      type: Array as PropType<SpanListItem[]>,
      required: true,
    },
  },
  emits: ['viewDetail', 'listChange'],
  setup(props, { emit }) {
    const { t } = useI18n();
    /** 每页显示条数 */
    const pageLimit = 30;
    /** 当前页 */
    const currentPage = ref(1);
    const spanListBody = ref(null);
    const sortOrder = reactive({
      type: 'time',
      sort: 'desc',
      popoverShow: false,
    });
    /** 判断列表区域是否出现滚动条 */
    const isScrollBody = ref(false);

    /** 分页当前显示的 span */
    const renderList = computed<SpanListItem[]>(() => {
      const list = JSON.parse(JSON.stringify(props.spanList));
      const { type, sort } = sortOrder;
      if (type === 'time') {
        if (sort === 'desc') {
          list.sort((a, b) => b.startTime - a.startTime);
        } else {
          list.sort((a, b) => a.startTime - b.startTime);
        }
      }
      const start = (currentPage.value - 1) * pageLimit;
      const end = currentPage.value * pageLimit;
      return list.slice(start, end);
    });

    const handleSortChange = (type: 'show' | 'sort' | 'type', value?) => {
      if (type === 'sort') {
        sortOrder.sort = sortOrder.sort === 'desc' ? 'asc' : 'desc';
      } else if (type === 'show') {
        sortOrder.popoverShow = value;
      }
    };

    /** 切换分页 */
    const handlePageChange = val => {
      currentPage.value = val;
    };

    watch(
      () => props.spanList,
      () => {
        handlePageChange(1);
        setTimeout(() => {
          isScrollBody.value = spanListBody.value?.scrollHeight > spanListBody.value?.clientHeight;
        }, 100);
      },
      { immediate: true }
    );

    /** 查看 span 详情 */
    const showSpanDetail = (span: SpanListItem) => {
      if (span.collapsed) {
        emit('listChange', span.spanIds, span);
      } else {
        emit('viewDetail', span);
      }
    };

    return {
      pageLimit,
      renderList,
      sortOrder,
      handleSortChange,
      showSpanDetail,
      currentPage,
      handlePageChange,
      spanListBody,
      isScrollBody,
      t,
    };
  },
  render() {
    const { subTitle, isCompare } = this.$props;
    return (
      <div class='span-list'>
        <div class='span-list-header'>
          {subTitle ? (
            <span class='sub-title'>
              {/* <span class='separator'>/</span> */}
              <i
                class='icon-monitor icon-back-left back-btn'
                onClick={() => this.$emit('listChange', [])}
              />
              <span
                class='text'
                title={subTitle}
              >
                {subTitle}
              </span>
            </span>
          ) : (
            <span
              class='title'
              onClick={() => this.$emit('listChange', [])}
            >
              Span List
            </span>
          )}

          <div class='filter-wrap'>
            <i
              class={['icon-monitor icon-paixu', this.sortOrder.sort === 'desc' ? 'down' : 'up']}
              onClick={() => this.handleSortChange('sort')}
            />
            <Popover
              disabled={true}
              is-show={this.sortOrder.popoverShow}
              theme='light'
              trigger='click'
              onAfterHidden={({ isShow }) => this.handleSortChange('show', isShow)}
              onAfterShow={({ isShow }) => this.handleSortChange('show', isShow)}
            >
              {{
                default: () => (
                  <div class='sort-select'>
                    <span class='text'>{this.t('产生时间')}</span>
                    <i class={['icon-monitor', this.sortOrder.popoverShow ? 'icon-arrow-up' : 'icon-arrow-down']} />
                  </div>
                ),
                content: () => (
                  <div class=''>
                    <div class='select-item'>{this.t('产生时间')}</div>
                  </div>
                ),
              }}
            </Popover>
          </div>
        </div>
        <div
          ref='spanListBody'
          style={`flex: ${this.isScrollBody ? 1 : 'unset'}`}
          class='span-list-body'
        >
          <ul class='list-ul'>
            {this.renderList.map(original => (
              <li
                key={original.spanId}
                style={`border-color: ${original.color}; background-color: ${isCompare ? original.bgColor : '#f5f7fa'}`}
                class={['list-li', { 'is-compare': isCompare }]}
                onClick={e => {
                  e.stopPropagation();
                  this.showSpanDetail(original);
                }}
              >
                <div class='list-li-header'>
                  {original.collapsed ? (
                    <span class='collapsed-number'>{original.collapsedSpanNum}</span>
                  ) : (
                    <i class={`icon-monitor span-icon span-kind icon-${getSpanKindIcon(original.kind)}`} />
                  )}
                  <span
                    class='span-name'
                    v-overflow-tips
                  >
                    {original.name}
                  </span>
                  {isCompare && ['removed', 'added'].includes(original.mark) ? (
                    <span class={`span-mark ${original.mark}`}>{original.mark}</span>
                  ) : (
                    <span class='span-eplaced'>{formatDuration(original.duration)}</span>
                  )}
                </div>
                <div class='arrow-down-icon'>
                  <div class='rect' />
                  <div class='arrow' />
                </div>
                <div class='list-li-body'>
                  <img
                    class='span-icon'
                    alt=''
                    src={original.icon}
                  />
                  <div
                    class='service-name'
                    v-overflow-tips
                  >
                    {original.operationName}
                  </div>
                  <span class='start-time'>
                    {`${formatDate(original.startTime)} ${customFormatTime(original.startTime, 'HH:mm:ss')}`}
                  </span>
                </div>
              </li>
            ))}
          </ul>
        </div>
        <div class='span-list-footer'>
          <div class='list-total'>
            <i18n-t keypath='共{0}条'>
              <span style='margin: 0 5px;'>{this.spanList.length || 0}</span>
            </i18n-t>
          </div>
          {this.isScrollBody && (
            // 分页组件，用于处理页面切换
            <Pagination
              v-model={this.currentPage} // 当前页码
              count={this.spanList.length} // 总记录数
              limit={this.pageLimit} // 当前每页显示的数据数量
              limit-list={[30]} // 每页显示的数据数量列表
              show-limit={false} // 是否显示每页显示数据数量选择器
              show-total-count={false} // 是否显示总记录数
              small
              onChange={this.handlePageChange} // 页面切换时的回调函数
            />
          )}
        </div>
      </div>
    );
  },
});
