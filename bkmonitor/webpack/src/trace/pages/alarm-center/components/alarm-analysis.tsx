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

import { defineComponent, reactive, shallowRef } from 'vue';
import { useI18n } from 'vue-i18n';

import { Message, Progress, Sideslider } from 'bkui-vue';
import { copyText } from 'monitor-common/utils';
import { storeToRefs } from 'pinia';

import { useAlarmCenterStore } from '../../../store/modules/alarm-center';

import './alarm-analysis.scss';

export interface PanelItemChildren {
  id: string;
  title: string;
  count: number;
  percent: number;
}

export interface AlarmAnalysisPanels {
  id: string;
  title: string;
  count: number;
  children: PanelItemChildren[];
}

export default defineComponent({
  name: 'AlarmAnalysis',
  setup() {
    const { t } = useI18n();
    const store = useAlarmCenterStore();

    const { alarmType } = storeToRefs(store);

    const expand = shallowRef(true);
    const panelList = shallowRef<AlarmAnalysisPanels[]>([
      {
        id: 'module',
        title: t('模块'),
        count: 10,
        children: [
          {
            id: 'module1',
            title: t('模块1'),
            count: 10,
            percent: 50,
          },
          {
            id: 'module2',
            title: t('模块2'),
            count: 10,
            percent: 50,
          },
        ],
      },
      {
        id: 'module',
        title: t('模块'),
        count: 10,
        children: [
          {
            id: 'module1',
            title: t('模块1'),
            count: 10,
            percent: 50,
          },
          {
            id: 'module2',
            title: t('模块2'),
            count: 10,
            percent: 50,
          },
        ],
      },
    ]);

    const handleConditionChange = (type, value) => {
      console.log(type, value);
    };

    /** 批量复制 */
    const handleCopyNames = (names: PanelItemChildren[] = []) => {
      const value = names.map(item => item.title).join('\n');
      copyText(value, msg => {
        Message({
          message: msg,
          theme: 'error',
        });
        return;
      });
      Message({
        message: t('复制成功'),
        theme: 'success',
      });
    };

    /** 渲染分析列表 */
    const renderAnalysisList = (panels: PanelItemChildren[]) => {
      return (
        <div class='analysis-list'>
          {panels.map(item => (
            <div
              key={item.id}
              class='analysis-item'
            >
              <div class='analysis-item-info'>
                <div class='text-wrap'>
                  <span
                    class='item-name'
                    v-overflow-tips
                  >
                    {item.title}
                  </span>
                  <span class='item-count'>{item.count}</span>
                  <span class='item-percent'>{item.percent}%</span>
                </div>
                <Progress
                  bg-color='#DCDEE5'
                  color='#5AB8A8'
                  percent={item.percent}
                  show-text={false}
                  stroke-width={4}
                />
              </div>
              <div class='analysis-item-tools'>
                <i
                  class='icon-monitor icon-a-sousuo'
                  onClick={() => handleConditionChange('equal', item)}
                />
                <i
                  class='icon-monitor icon-sousuo-'
                  onClick={() => handleConditionChange('not_equal', item)}
                />
              </div>
            </div>
          ))}
        </div>
      );
    };

    const detailSliderShow = shallowRef(false);
    const detailSliderLoading = shallowRef(false);
    const detailSliderInfo = reactive({
      title: '',
      count: 0,
    });
    const sliderAnalysisList = shallowRef<PanelItemChildren[]>([]);

    /** 查看全部 */
    const handleViewAll = async (panel: AlarmAnalysisPanels) => {
      detailSliderShow.value = true;
      detailSliderInfo.title = panel.title;
      detailSliderLoading.value = true;
      const data = await getTopNData();
      detailSliderLoading.value = false;
      sliderAnalysisList.value = data;
    };
    const handleSliderShowChange = (value: boolean) => {
      detailSliderShow.value = value;
    };
    const renderAnalysisSlider = () => {
      return (
        <Sideslider
          width='420'
          ext-cls='alarm-analysis-slider'
          is-show={detailSliderShow.value}
          transfer={true}
          quick-close
          onUpdate:isShow={handleSliderShowChange}
        >
          {{
            header: () => (
              <div class='alarm-analysis-slider-header'>
                <div class='alarm-analysis-title'>
                  <span
                    class='field-name'
                    v-overflow-tips
                  >
                    {detailSliderInfo.title}
                  </span>
                  (<div class='count'>{detailSliderInfo.count}</div> )
                  <i
                    class='icon-monitor icon-mc-copy'
                    v-bk-tooltips={{ content: '批量复制' }}
                    onClick={() => handleCopyNames(sliderAnalysisList.value)}
                  />
                </div>
              </div>
            ),
            default: () => renderAnalysisList(sliderAnalysisList.value),
          }}
        </Sideslider>
      );
    };

    const getTopNData = async () => {
      if (alarmType.value === 'alert') {
        return [];
      }
      if (alarmType.value === 'action') {
        return [];
      }
      return [];
    };

    return {
      t,
      expand,
      panelList,
      detailSliderShow,
      handleCopyNames,
      handleViewAll,
      renderAnalysisList,
      renderAnalysisSlider,
    };
  },
  render() {
    return (
      <div class='alarm-analysis-comp'>
        <div class='collapse-header'>
          <i class={['icon-monitor icon-mc-arrow-right arrow-icon', { expand: this.expand }]} />
          <div class='title'>{this.t('告警分析')}</div>
          <div class='settings'>
            <i class='icon-monitor icon-shezhi1' />
            <span>{this.t('设置')}</span>
          </div>
        </div>
        <div class='collapse-content'>
          {this.panelList.map(panel => (
            <div
              key={panel.id}
              class='panel-item'
            >
              <div class='panel-item-header'>
                <div class='header-left'>
                  <span class='title'>{panel.title}</span>
                  <div class='count'>{panel.count}</div>
                  <i
                    class='icon-monitor icon-mc-copy'
                    v-bk-tooltips={{ content: '批量复制' }}
                    onClick={() => this.handleCopyNames(panel.children)}
                  />
                </div>
                {panel.count > 5 && (
                  <span
                    class='header-right'
                    onClick={() => this.handleViewAll(panel)}
                  >
                    {this.t('查看全部')}
                  </span>
                )}
              </div>
              {this.renderAnalysisList(panel.children)}
            </div>
          ))}
        </div>
        {this.renderAnalysisSlider()}
      </div>
    );
  },
});
