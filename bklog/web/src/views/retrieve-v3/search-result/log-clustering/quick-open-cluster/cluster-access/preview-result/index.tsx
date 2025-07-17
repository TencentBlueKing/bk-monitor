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

import { defineComponent, onMounted, ref, watch } from 'vue';
import useLocale from '@/hooks/use-locale';
import * as echarts from 'echarts';

import './index.scss';

export default defineComponent({
  name: 'PreviewResult',
  setup() {
    const { t } = useLocale();

    const chartRef = ref(null);
    const chartInstance = ref();
    const showPreViewContent = ref(false);
    const showWarnTip = ref(false);
    const logDataList = ref(
      Array(10)
        .fill('')
        .map(
          () =>
            'Jul  9 15:29:02 VM_1_2_centos sJul  9 15:29:02 VM_1_2_centos sJul  9 15:29:02 VM_1_2_centos sJul  9 15:29:02 VM_1_2_centos sJul  9 15:29:02 VM_1_2_centos sJul  9 15:29:02 VM_1_2_centos sJul  9 15:29:02 VM_1_2_centos sJul  9 15:29:02 VM_1_2_centos sJul  9 15:29:02 VM_1_2_centos sJul  9 15:29:02 VM_1_2_centos sJul  9 15:29:02 VM_1_2_centos sJul  9 15:29:02 VM_1_2_centos sJul  9 15:29:02 VM_1_2_centos sJul  9 15:29:02 VM_1_2_centos sJul  9 15:29:02 VM_1_2_centos sJul  9 15:29:02 VM_1_2_centos sJul  9 15:29:02 VM_1_2_centos sJul  9 15:29:02 VM_1_2_centos s.',
        ),
    );

    watch(showPreViewContent, () => {
      if (showPreViewContent.value) {
        setTimeout(() => {
          chartInstance.value = echarts.init(chartRef.value);
          console.log('chartInstance === ', chartInstance.value);
          updateChart();
        });
      }
    });

    const updateChart = () => {
      chartInstance.value.setOption({
        grid: {
          top: 12, // 上边距为 0
          right: 0, // 右边距为 0
          bottom: 0, // 底边距为 0
          left: 0, // 左边距为 0
          containLabel: true, // 确保坐标轴标签不被裁剪（标签计入图表区域）
        },
        title: {},
        tooltip: {},
        legend: {},
        xAxis: {
          data: ['周一', '周二', '周三', '周四', '周五', '周六', '周日'],
          axisTick: { show: false },
          axisLabel: {
            textStyle: {
              color: '#979BA5',
            },
          },
          axisLine: {
            lineStyle: {
              color: '#F0F1F5',
              width: 1,
            },
          },
        },
        yAxis: {
          axisLabel: {
            textStyle: {
              color: '#979BA5',
            },
          },
          splitLine: {
            show: true,
            lineStyle: {
              color: '#F0F1F5',
              width: 1,
              type: 'line',
            },
          },
        },
        series: [
          {
            // name: '销量',
            type: 'bar',
            barWidth: 32,
            itemStyle: {
              color: '#A3B1CC',
            },
            data: [200, 200, 360, 100, 100, 230, 380],
          },
        ],
      });
    };

    const handleClickPreview = () => {
      showPreViewContent.value = true;
    };

    onMounted(() => {});

    return () => (
      <div class='preview-result-main'>
        {showWarnTip.value && <div class='warn-mask'></div>}
        <div class='operate-main'>
          <bk-button
            theme='primary'
            style='width: 88px'
            outline
            on-click={handleClickPreview}
          >
            {t('预览')}
          </bk-button>
          {showPreViewContent.value && (
            <div class='preview-tip'>
              {showWarnTip.value ? (
                <log-icon
                  class='warn-icon'
                  type='circle-alert-filled'
                />
              ) : (
                <log-icon
                  class='check-icon'
                  type='circle-correct-filled'
                />
              )}
              <span class='tip-text'>{showWarnTip.value ? t('配置有调整，请重新预览') : t('预览结果如下')}</span>
            </div>
          )}
        </div>
        {showPreViewContent.value && (
          <div class='preview-content'>
            <div class='item-title'>最近 1 周日志趋势</div>
            <div
              class='chart-main'
              ref={chartRef}
            ></div>
            <div class='item-title'>最近 10 条日志样例</div>
            <div class='log-demo-main'>
              {logDataList.value.map((item, index) => (
                <div class='row-data'>
                  <div class='count-num'>{index + 1}</div>
                  <div class='log-content'>{item}</div>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    );
  },
});
