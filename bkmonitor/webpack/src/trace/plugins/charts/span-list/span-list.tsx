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

import { computed, defineComponent, PropType, ref, watch } from 'vue';
import { Pagination } from 'bkui-vue';

import { Span } from '../../../components/trace-view/typings';
import { formatDate, formatDuration, formatTime } from '../../../components/trace-view/utils/date';
import { useTraceStore } from '../../../store/modules/trace';
import { getSpanKindIcon } from '../../../utils';

import './span-list.scss';

export default defineComponent({
  name: 'SpanList',
  props: {
    // 过滤的 Span Id 列表
    filterSpanIds: {
      type: Array as PropType<string[]>,
      default: () => []
    },
    // 子标题
    subTitle: {
      type: String,
      required: false,
      default: ''
    },
    // 是否折叠
    isCollapsed: {
      type: Boolean,
      required: false
    },
    // 对比的 Span 列表
    compareSpanList: {
      type: Array as PropType<Span[]>,
      default: () => []
    },
    // 对比状态
    isCompare: {
      type: Boolean,
      default: false
    }
  },
  emits: ['viewDetail', 'listChange'],
  setup(props, { emit }) {
    const store = useTraceStore();

    /** 每页显示条数 */
    const pageLimit = 30;
    /** 当前页 */
    const currentPage = ref(1);
    /** 分页当前显示的 span */
    const renderList = ref([]);
    const spanListBody = ref(null);
    /** 判断列表区域是否出现滚动条 */
    const isScrollBody = ref(false);

    /** 当前trace的所有span */
    const spanList = computed(() => store.traceTree?.spans || []);
    /** 当前过滤的所有span */
    const localList = computed(() => {
      const list = props.isCompare && props.compareSpanList.length ? props.compareSpanList : spanList.value;
      if (props.filterSpanIds.length) return list.filter(item => props.filterSpanIds.includes(item.span_id));
      return list;
    });

    /** 切换分页 */
    const handlePageChange = val => {
      currentPage.value = val;
      const start = (currentPage.value - 1) * pageLimit;
      const end = currentPage.value * pageLimit;
      renderList.value = localList.value.slice(start, end);
    };

    watch(
      () => localList.value,
      () => {
        handlePageChange(1);
        setTimeout(() => {
          isScrollBody.value = spanListBody.value?.scrollHeight > spanListBody.value?.clientHeight;
        }, 100);
      },
      { immediate: true }
    );

    /** 查看 span 详情 */
    const showSpanDetail = (span: Span) => {
      emit('viewDetail', span);
    };

    return {
      pageLimit,
      localList,
      renderList,
      showSpanDetail,
      currentPage,
      handlePageChange,
      spanListBody,
      isScrollBody
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
              ></i>
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
        </div>
        <div
          class='span-list-body'
          ref='spanListBody'
          style={`flex: ${this.isScrollBody ? 1 : 'unset'}`}
        >
          {/* <VirtualRender
          list={this.renderList}
          lineHeight={48}
          v-slots={{
            default: ({ data }) => ()
          }}>
        </VirtualRender> */}
          <ul class='list-ul'>
            {this.renderList.map(original => (
              <li
                class={['list-li', { 'is-compare': isCompare }]}
                style={`border-color: ${original.color}; background-color: ${isCompare ? original.bgColor : '#f5f7fa'}`}
                key={original.spanID}
                onClick={e => {
                  e.stopPropagation();
                  this.showSpanDetail(original);
                }}
              >
                <div class='list-li-header'>
                  <i class={`icon-monitor span-icon span-kind icon-${getSpanKindIcon(original.kind)}`}></i>
                  <span class='span-name'>{original.service_name}</span>
                  {isCompare && ['removed', 'added'].includes(original.mark) ? (
                    <span class={`span-mark ${original.mark}`}>{original.mark}</span>
                  ) : (
                    <span class='span-eplaced'>{formatDuration(original.duration)}</span>
                  )}
                </div>
                <div class='list-li-body'>
                  <img
                    src={original.icon}
                    class='span-icon'
                    alt=''
                  />
                  <span class='service-name'>{original.operationName}</span>
                  <span class='start-time'>
                    {`${formatDate(original.startTime)} ${formatTime(original.startTime)}`}
                  </span>
                </div>
              </li>
            ))}
          </ul>
        </div>
        <div class='span-list-footer'>
          <div class='list-total'>{this.$t('共{0}条', [this.localList.length])}</div>
          {this.isScrollBody && (
            // 分页组件，用于处理页面切换
            <Pagination
              v-model={this.currentPage} // 当前页码
              small
              limit-list={[30]} // 每页显示的数据数量列表
              show-limit={false} // 是否显示每页显示数据数量选择器
              limit={this.pageLimit} // 当前每页显示的数据数量
              show-total-count={false} // 是否显示总记录数
              count={this.localList.length} // 总记录数
              onChange={this.handlePageChange} // 页面切换时的回调函数
            />
          )}
        </div>
      </div>
    );
  }
});
