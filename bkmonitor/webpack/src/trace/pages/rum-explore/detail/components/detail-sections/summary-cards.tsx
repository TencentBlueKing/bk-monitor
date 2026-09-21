/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 *
 * Copyright (C) 2017-2025 Tencent.  All rights reserved.
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
import { defineComponent } from 'vue';
import type { PropType } from 'vue';

import dayjs from 'dayjs';

import { CARD_TONE_COLOR } from '../../constants';
import { formatCount } from '../../registry/card-registry';
import { RumCardToneEnum } from '../../typings';

import type { IRumSparklinePoint, IRumSummaryCardGroupVM, IRumSummaryCardVM } from '../../typings';

import './summary-cards.scss';

/** 迷你柱状图的固定高度，柱高按最大值归一化 */
const SPARKLINE_HEIGHT = 32;

/** 柱状图 tips 的时间格式：秒级精度 + 时区偏移，与 utils.formatTime 保持同一展示口径 */
const SPARKLINE_TIME_FORMAT = 'YYYY-MM-DD HH:mm:ssZZ';

/** 统计卡片组：支持分组展示（组标题栏 + 组内卡片平铺），未传 groups 时退化为逐行一字排开 */
export default defineComponent({
  name: 'RumSummaryCards',
  props: {
    groups: {
      type: Array as PropType<IRumSummaryCardGroupVM[]>,
      default: () => [],
    },
    rows: {
      type: Array as PropType<IRumSummaryCardVM[][]>,
      default: () => [],
    },
  },
  setup(props) {
    /** 单根柱子的 tips：时间桶起点 · 该桶的次数 */
    function sparklineTip(point: IRumSparklinePoint) {
      const bucketTime = dayjs.tz(point.time * 1000).format(SPARKLINE_TIME_FORMAT);
      return (
        <span style='color: #fafbfd;display: flex;align-items: center;'>
          {bucketTime}{' '}
          <span
            style='align-items: center;
              background-color: rgba(1, 1, 1, .8);
              border-radius: 3px;
              display: flex;
              height: 18px;
              margin-left: 6px;
              padding: 0 5px;'
          >
            {formatCount(point.value)}
          </span>
        </span>
      );
    }

    /** 迷你柱状图：柱高按最大值归一化，最低 2px 保证 0 值桶仍可见；兜底 1 避免全 0 时出现 0/0 */
    function renderSparkline(points: IRumSparklinePoint[]) {
      const max = Math.max(...points.map(point => point.value), 1);
      return (
        <div class='card-sparkline'>
          {points.map((point, index) => (
            <span
              key={index}
              style={{
                height: `${Math.max((point.value / max) * SPARKLINE_HEIGHT, 2)}px`,
                backgroundColor: '#3A84FF',
              }}
              class='sparkline-bar'
              v-bk-tooltips={{
                content: sparklineTip(point),
                placement: 'top',
                /** 深色 tips 主题样式定义在 static/scss/global.scss */
                extCls: 'tooltip-chart-tips-dark-theme',
              }}
            />
          ))}
        </div>
      );
    }

    function renderCard(card: IRumSummaryCardVM) {
      const toneColor = CARD_TONE_COLOR[card.tone ?? RumCardToneEnum.DEFAULT];
      return (
        <div
          key={card.key}
          class={['rum-summary-card', card.cardCls]}
        >
          <div class='card-head'>
            <span class='card-label'>{card.label}</span>
            {card.operation ? (
              <span
                class='card-operation'
                onClick={card.operation.onClick}
              >
                <i class='icon-monitor icon-mc-copy' />
                {card.operation.label}
              </span>
            ) : null}
            {card.tag ? (
              <span
                style={{ color: card.tag.color, backgroundColor: card.tag.bgColor }}
                class='card-tag'
              >
                {card.tag.text}
              </span>
            ) : null}
          </div>
          {card.sparkline ? (
            renderSparkline(card.sparkline)
          ) : (
            <div class={['card-value-row', { 'unit-value-row': !!card.unit || !!card.growthRate }]}>
              {card.prefixTag ? (
                <span
                  style={{ backgroundColor: card.prefixTag.bgColor }}
                  class='card-prefix-tag'
                >
                  {card.prefixTag.text}
                </span>
              ) : null}
              <span
                style={{ color: toneColor }}
                class='card-value'
                v-overflow-tips
              >
                {card.value}
              </span>
              {card.growthRate ? (
                <span
                  style={{ color: CARD_TONE_COLOR[card.growthRate.tone ?? RumCardToneEnum.DEFAULT] }}
                  class='card-growth'
                >
                  {card.growthRate.text}
                </span>
              ) : null}
              {card.unit ? (
                <span
                  style={{ color: CARD_TONE_COLOR[card.unit.tone ?? RumCardToneEnum.DEFAULT] }}
                  class='card-unit'
                >
                  {card.unit.text}
                </span>
              ) : null}
            </div>
          )}
          {card.footer?.length ? (
            <div class='card-footer'>
              {card.footer.map(part => (
                <span
                  key={part.text}
                  style={{ color: part.tone ? CARD_TONE_COLOR[part.tone] : undefined }}
                >
                  {part.text}
                </span>
              ))}
            </div>
          ) : null}
        </div>
      );
    }

    /** 一行内的卡片等宽平铺 */
    function renderRow(cards: IRumSummaryCardVM[], key: string) {
      return (
        <div
          key={key}
          class='summary-card-row'
        >
          {cards.map(renderCard)}
        </div>
      );
    }

    return () => (
      <div class={['rum-summary-cards', { 'group-layout': props.groups.length > 0 }]}>
        {props.groups.length
          ? props.groups.map(group => (
              <div
                key={group.key}
                class='summary-card-group'
              >
                {group.title ? <div class='summary-card-group-title'>{group.title}</div> : null}
                {group.rows.map((row, index) => renderRow(row, `${group.key}_${index}`))}
              </div>
            ))
          : props.rows.map((row, index) => renderRow(row, String(index)))}
      </div>
    );
  },
});
