import { defineComponent, ref, watch, onUnmounted } from 'vue';
import RetrieveHelper, { RetrieveEvent } from '@/views/retrieve-helper.tsx';
export default defineComponent({
  name: 'AutoRefresh',
  setup() {''
    const datasource = ref([
      { label: '关闭(off)', value: 'off' },
      { label: '1m', value: '1m' }, // 1分钟
      { label: '5m', value: '5m' }, // 5分钟
      { label: '15m', value: '15m' }, // 15分钟
      { label: '30m', value: '30m' }, // 30分钟
      { label: '1h', value: '1h' }, // 1小时
      { label: '2h', value: '2h' }, // 2小时
      { label: '1d', value: '1d' }, // 1天
    ]);

    const selectedValue = ref('off');
    let refreshTimer: number | null = null;

    /**
     * 将时间字符串转换为毫秒数
     * @param timeValue 格式如 "1m", "5m", "1h", "1d" 的字符串
     * @returns 毫秒数
     */
    const getTimeInMs = (timeValue: string): number => {
      if (timeValue === 'off') return 0;

      const unitMap: { [key: string]: number } = {
        m: 60 * 1000, // 分钟
        h: 60 * 60 * 1000, // 小时
        d: 24 * 60 * 60 * 1000, // 天
      };

      const unit = timeValue.slice(-1);
      const amount = parseInt(timeValue.slice(0, -1), 10);

      // 输入验证
      if (isNaN(amount) || amount <= 0) {
        return 0;
      }

      if (!unitMap[unit]) {
        return 0;
      }

      return amount * unitMap[unit];
    };

    const handleRefresh = () => {
      // store.dispatch("requestIndexSetQuery");
      RetrieveHelper.fire(RetrieveEvent.AUTO_REFRESH);
    };

    const clearRefreshTimer = () => {
      if (refreshTimer) {
        clearInterval(refreshTimer);
        refreshTimer = null;
      }
    };

    const setRefreshTimer = (timeValue: string) => {
      clearRefreshTimer();

      if (timeValue === 'off') return;

      const interval = getTimeInMs(timeValue);

      if (interval > 0) {
        refreshTimer = setInterval(handleRefresh, interval);
      }
    };

    // 监听选择值变化
    watch(
      selectedValue,
      (newVal) => {
        setRefreshTimer(newVal);
      },
      { immediate: true },
    );

    // 组件销毁时清理定时器
    onUnmounted(() => {
      clearRefreshTimer();
    });

    return {
      datasource,
      selectedValue,
      setRefreshTimer,
      clearRefreshTimer,
      getTimeInMs,
      handleRefresh,
    };
  },
  render() {
    return (
      <div class='auto-refresh'>
        <span
          class='bklog-icon bklog-auto-refresh'
          style='font-size:20px;margin:0 5px 0 5px'
        ></span>
        <bk-select
          disabled={false}
          v-model={this.selectedValue}
          style='width: 110px'
          ext-cls='select-custom'
          ext-popover-cls='select-popover-custom'
        >
          {this.datasource.map((option) => (
            <bk-option
              key={option.value}
              id={option.value}
              name={option.label}
            />
          ))}
        </bk-select>
        <span
          class='icon bklog-icon bklog-refresh2'
          style='font-size:20px;margin:0 5px 0 5px;cursor:pointer'
          onClick={this.handleRefresh}
        ></span>
      </div>
    );
  },
});
