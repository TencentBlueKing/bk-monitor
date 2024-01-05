/* eslint-disable no-param-reassign */
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
import { formatDatetime } from '../../monitor-common/utils/utils';
import store from '../store/store';
/**
 * 通用跳转页面
 */
const gotoPageMixin = {
  data() {
    return {
      commonBaseUrl: `${window.site_url}${store.getters.bizId}`
    };
  },
  methods: {
    commonGotoPage(url) {
      window.location.href = `${this.commonBaseUrl}/${url}`;
    },
    customBizIdGotoPage(bizId = store.getters.bizId, url) {
      window.location.href = `${location.origin}${location.pathname}?bizId=${bizId}#${url}`;
    }
  }
};
/**
 * 通用拨测状态颜色
 */
const uptimeCheckMixin = {
  filters: {
    filterProcess(v) {
      if (v >= 99) {
        return 'rgb(45, 203, 86)'; // 绿色
      }
      if (v >= 95 && v < 99) {
        return 'rgb(255, 235, 0)'; // 黄色
      }
      if (v >= 80 && v < 95) {
        return 'rgb(255, 156, 1)'; // 橙色
      }
      return 'rgb(234, 54, 54)'; // 红色
    }
  },
  methods: {
    filterTaskDuration(v, status) {
      if (v === null && status === 'stoped') {
        return '#C4C6CC';
      }
      if (v <= 100 && v !== null) {
        return '#2dcb56';
      }
      if (v < 200 && v !== null) {
        return '#ffeb00';
      }
      if (v < 300 && v !== null) {
        return '#ff9c01';
      }
      return '#ea3436';
    },
    filterTaskDurationAlarm(v, alarm) {
      if (alarm) {
        return '#ea3436';
      }
      if (v === null) {
        return '#C4C6CC';
      }
      return '#313238';
    },
    filterAvailableAlarm(v, alarm) {
      if (alarm) {
        return '#ea3436';
      }
      if (v === null) {
        return '#C4C6CC';
      }
      return '#313238';
    },
    filterAvailable(v, status) {
      if (v === null && status === 'stoped') {
        return '#C4C6CC';
      }
      if (v <= 100 && v >= 99) {
        return '#2dcb56';
      }
      if (v < 99 && v >= 95) {
        return '#ffeb00';
      }
      if (v < 95 && v >= 90) {
        return '#ff9c01';
      }
      return '#ea3436';
    }
  }
};
const collapseMixin = {
  methods: {
    beforeEnter(el) {
      el.classList.add('collapse-transition');
      el.style.height = '0';
    },
    enter(el) {
      el.dataset.oldOverflow = el.style.overflow;
      if (el.scrollHeight !== 0) {
        el.style.height = `${el.scrollHeight}px`;
        setTimeout(() => {
          el.style.height = '';
        }, 300);
      } else {
        el.style.height = '';
      }
      el.style.overflow = 'hidden';
    },
    afterEnter(el) {
      el.classList.remove('collapse-transition');
      el.style.height = '';
      el.style.overflow = el.dataset.oldOverflow;
    },
    beforeLeave(el) {
      el.dataset.oldOverflow = el.style.overflow;
      el.style.height = `${el.scrollHeight}px`;
      el.style.overflow = 'hidden';
    },
    leave(el) {
      if (el.scrollHeight !== 0) {
        el.classList.add('collapse-transition');
        el.style.height = 0;
      }
    },
    afterLeave(el) {
      el.classList.remove('collapse-transition');
      el.style.height = '';
      el.style.overflow = el.dataset.oldOverflow;
    }
  }
};
const alarmShieldMixin = {
  methods: {
    getDateConfig(date) {
      const cycle = {
        begin_time: '',
        end_time: '',
        cycle_config: {
          begin_time: '',
          end_time: '',
          type: date.type,
          day_list: [],
          week_list: []
        }
      };
      if (date.type !== 1) {
        const [beginTime, endTime] = date.dateRange;
        cycle.begin_time = beginTime;
        cycle.end_time = endTime;
      }
      switch (date.type) {
        case 1:
          cycle.cycle_config.day_list = date.day.list;
          // eslint-disable-next-line prefer-destructuring
          cycle.begin_time = date.single.range[0];
          // eslint-disable-next-line prefer-destructuring
          cycle.end_time = date.single.range[1];
          break;
        case 2:
          cycle.cycle_config.day_list = date.day.list;
          // eslint-disable-next-line prefer-destructuring
          cycle.cycle_config.begin_time = date.day.range[0];
          // eslint-disable-next-line prefer-destructuring
          cycle.cycle_config.end_time = date.day.range[1];
          break;
        case 3:
          cycle.cycle_config.week_list = date.week.list;
          // eslint-disable-next-line prefer-destructuring
          cycle.cycle_config.begin_time = date.week.range[0];
          // eslint-disable-next-line prefer-destructuring
          cycle.cycle_config.end_time = date.week.range[1];
          break;
        case 4:
          cycle.cycle_config.day_list = date.month.list;
          // eslint-disable-next-line prefer-destructuring
          cycle.cycle_config.begin_time = date.month.range[0];
          // eslint-disable-next-line prefer-destructuring
          cycle.cycle_config.end_time = date.month.range[1];
          break;
      }
      return cycle;
    }
  }
};
const quickAlarmShieldMixin = {
  data() {
    return {
      options: {
        disabledDate(date) {
          return date.getTime() < Date.now() - 8.64e7 || date.getTime() > Date.now() + 8.64e7 * 181; // 限制用户只能选择半年以内的日期
        }
      },
      timeList: [
        { name: `0.5${window.i18n.t('小时')}`, id: 18 },
        { name: `1${window.i18n.t('小时')}`, id: 36 },
        { name: `12${window.i18n.t('小时')}`, id: 432 },
        { name: `1${window.i18n.t('天')}`, id: 864 },
        { name: `7${window.i18n.t('天')}`, id: 6048 }
      ]
    };
  },
  methods: {
    handleformat(time, fmte) {
      return formatDatetime(time, fmte);
    },
    getTime() {
      let begin = '';
      let end = '';
      if (this.timeValue === 0) {
        const [beginTime, endTime] = this.customTime;
        if (beginTime === '' || endTime === '') {
          this.rule.customTime = true;
          return false;
        }
        begin = this.handleformat(beginTime, 'yyyy-MM-dd hh:mm:ss');
        end = this.handleformat(endTime, 'yyyy-MM-dd hh:mm:ss');
      } else {
        begin = new Date();
        const nowS = begin.getTime();
        end = new Date(nowS + this.timeValue * 100000);
        begin = this.handleformat(begin, 'yyyy-MM-dd hh:mm:ss');
        end = this.handleformat(end, 'yyyy-MM-dd hh:mm:ss');
      }
      return { begin, end };
    },
    handleScopeChange(type) {
      this.timeValue = type;
      if (type === 0) {
        this.$nextTick(() => {
          this.$refs.time.visible = true;
        });
      } else {
        this.customTime = '';
      }
    }
  }
};
const strategyMapMixin = {
  data() {
    return {
      aggConditionColorMap: {
        AND: '#3A84FF',
        OR: '#3A84FF',
        '=': '#FF9C01',
        '>': '#FF9C01',
        '<': '#FF9C01',
        '<=': '#FF9C01',
        '>=': '#FF9C01',
        '!=': '#FF9C01',
        like: '#FF9C01',
        between: '#FF9C01',
        include: '#FF9C01',
        exclude: '#FF9C01',
        regex: '#FF9C01',
        nregex: '#FF9C01'
      },
      aggConditionFontMap: {
        '=': 'bold',
        '>': 'bold',
        '<': 'bold',
        '<=': 'bold',
        '>=': 'bold',
        '!=': 'bold',
        like: 'bold',
        between: 'bold',
        include: 'bold',
        exclude: 'bold',
        regex: 'bold',
        nregex: 'bold'
      },
      methodMap: {
        gte: '>=',
        gt: '>',
        lte: '<=',
        lt: '<',
        eq: '=',
        neq: '!=',
        like: 'like',
        between: 'between',
        include: 'include',
        exclude: 'exclude',
        reg: 'regex',
        nreg: 'nregex'
      }
    };
  }
};
const memberSelectorMixin = {
  methods: {
    renderMemberTag(node) {
      const parentClass = 'tag';
      const textClass = 'text';
      const avatarClass = 'avatar';
      return this.renderPublicCode(node, parentClass, textClass, avatarClass, 'tag');
    },
    renderMerberList(node) {
      const parentClass = 'bk-selector-node bk-selector-member only-notice';
      const textClass = 'text';
      const avatarClass = 'avatar';
      return this.renderPublicCode(node, parentClass, textClass, avatarClass, 'list');
    },
    renderPublicCode(node, parentClass, textClass, avatarClass) {
      return (
        <div class={parentClass}>
          {node.logo ? (
            <img
              alt=''
              class={avatarClass}
              src={node.logo}
            />
          ) : (
            <i
              class={
                node.type === 'group'
                  ? 'icon-monitor icon-mc-user-group only-img'
                  : 'icon-monitor icon-mc-user-one only-img'
              }
            ></i>
          )}
          {/* { type === 'list'
                      ? <span class={textClass}>{node.display_name} ({node.id})</span>
                      : <span class={textClass}>{node.display_name}</span> } */}
          {node.type === 'group' ? (
            <span class={textClass}>{node.display_name}</span>
          ) : (
            <span class={textClass}>
              {node.id} ({node.display_name})
            </span>
          )}
        </div>
      );
    }
  }
};
const importConfigMixin = {
  data() {
    return {
      taskQueue: [],
      timer: null,
      interval: 2000
    };
  },
  watch: {
    taskQueue: {
      handler(queue) {
        if (queue && queue.length > 0 && !this.timer) {
          // 开启定时任务
          // handleQueueCallBack 方法组件内部需要实现
          this.handleRunTimer(this.handleQueueCallBack);
        } else if (!queue || queue.length === 0) {
          // 结束所有任务
          clearTimeout(this.timer);
          this.timer = null;
        }
      },
      immediate: true
    }
  },
  beforeDestroy() {
    this.taskQueue = [];
  },
  beforeRouteLeave(to, from, next) {
    this.taskQueue = [];
    next();
  },
  methods: {
    handleRunTimer(cb) {
      const fn = async () => {
        await cb();
        if (this.taskQueue.length === 0) {
          clearTimeout(this.timer);
          this.timer = null;
          return;
        }
        this.timer = setTimeout(() => {
          fn();
        }, this.interval);
      };
      this.timer = setTimeout(fn, this.interval);
    }
  }
};
// 策略配置中转换静态阈值mixin
const strategyThresholdMixin = {
  methods: {
    // 前端数据格式转换为提交后台格式
    handleConfig2Threshold(config) {
      if (Array.isArray(config)) {
        return config.reduce(
          (pre, { method, threshold, condition }) => {
            if (condition === 'or') {
              pre.push([
                {
                  method,
                  threshold
                }
              ]);
            } else {
              pre[pre.length - 1].push({
                method,
                threshold
              });
            }
            return pre;
          },
          [[]]
        );
      }
      return [];
    },
    // 后台数据格式转换为前端展示格式
    handleThreshold2Config(threshold) {
      if (Array.isArray(threshold)) {
        return threshold.reduce((pre, cur, index) => {
          pre.push(
            ...cur.map((item, setIndex) => {
              if (index === 0 && setIndex === 0) {
                return item;
              }
              return {
                ...item,
                condition: index > 0 && setIndex === 0 ? 'or' : 'and'
              };
            })
          );
          return pre;
        }, []);
      }
      return [];
    }
  }
};
// 拖到拉伸mixin 注意需要结合具体dom使用
const resizeMixin = {
  data() {
    return {
      resizeState: {
        show: false,
        ready: false,
        left: 0,
        draging: false
      }
    };
  },
  beforeDestroy() {
    document.body.style.cursor = '';
    this.resizeState.dragging = false;
    this.resizeState.show = false;
    this.resizeState.ready = false;
  },
  methods: {
    handleMouseDown(e) {
      if (this.resizeState.ready) {
        let { target } = event;
        while (target && target.dataset.tag !== 'resizeTarget') {
          target = target.parentNode;
        }
        this.resizeState.show = true;
        const rect = e.target.getBoundingClientRect();
        document.onselectstart = function () {
          return false;
        };
        document.ondragstart = function () {
          return false;
        };
        const handleMouseMove = event => {
          this.resizeState.dragging = true;
          this.resizeState.left = event.clientX - rect.left;
        };
        const handleMouseUp = () => {
          if (this.resizeState.dragging) {
            this.left.width = this.resizeState.left;
          }
          document.body.style.cursor = '';
          this.resizeState.dragging = false;
          this.resizeState.show = false;
          this.resizeState.ready = false;
          document.removeEventListener('mousemove', handleMouseMove);
          document.removeEventListener('mouseup', handleMouseUp);
          document.onselectstart = null;
          document.ondragstart = null;
        };
        document.addEventListener('mousemove', handleMouseMove);
        document.addEventListener('mouseup', handleMouseUp);
      }
    },
    handleMouseMove() {
      let { target } = event;
      while (target && target.dataset.tag !== 'resizeTarget') {
        target = target.parentNode;
      }
      const rect = target.getBoundingClientRect();
      const bodyStyle = document.body.style;
      if (rect.width > 12 && rect.right - event.pageX < 8) {
        bodyStyle.cursor = 'col-resize';
        this.resizeState.ready = true;
      }
    },
    handleMouseOut() {
      document.body.style.cursor = '';
      this.resizeState.ready = false;
    }
  }
};
// 根据每个列表页面设置统一的pageSize 并保存
const commonPageSizeMixin = {
  methods: {
    handleSetCommonPageSize(pageSize = 10) {
      localStorage.setItem('__common_page_size__', pageSize);
    },
    handleGetCommonPageSize() {
      return +localStorage.getItem('__common_page_size__') || 10;
    }
  }
};

// 设置全局通用的Loading
const mainLoadingMixin = {
  watch: {
    mainLoading: {
      handler: 'handleSetMainLoading'
    }
  },
  methods: {
    handleSetMainLoading(v) {
      this.$store.commit('app/SET_MAIN_LOADING', v);
    }
  }
};

export {
  alarmShieldMixin,
  collapseMixin,
  commonPageSizeMixin,
  gotoPageMixin,
  importConfigMixin,
  mainLoadingMixin,
  memberSelectorMixin,
  quickAlarmShieldMixin,
  resizeMixin,
  strategyMapMixin,
  strategyThresholdMixin,
  uptimeCheckMixin
};
