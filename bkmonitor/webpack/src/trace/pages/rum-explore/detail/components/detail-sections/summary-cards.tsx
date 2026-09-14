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

import { CARD_TONE_COLOR } from '../../constants';
import { RumCardToneEnum } from '../../typings';

import type { IRumSummaryCardVM } from '../../typings';

/** 迷你柱状图的固定高度，柱高按最大值归一化 */
const SPARKLINE_HEIGHT = 32;

/** 统计卡片组：一行内的卡片等宽平铺，行与行之间等间距 */
export default defineComponent({
  name: 'RumSummaryCards',
  props: {
    rows: {
      type: Array as PropType<IRumSummaryCardVM[][]>,
      default: () => [],
    },
  },
  setup(props) {
    /** 迷你柱状图：末位柱体高亮，用于突出最新一个时间桶 */
    function renderSparkline(values: number[]) {
      const max = Math.max(...values, 1);
      return (
        <div class='card-sparkline'>
          {values.map((value, index) => (
            <span
              key={index}
              style={{
                height: `${Math.max((value / max) * SPARKLINE_HEIGHT, 2)}px`,
                backgroundColor: index === values.length - 1 ? '#EA3636' : '#3A84FF',
              }}
              class='sparkline-bar'
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
          class='rum-summary-card'
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
            <div class='card-value-row'>
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
                title={card.value}
              >
                {card.value}
              </span>
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

    return () => (
      <div class='rum-summary-cards'>
        {props.rows.map(row => (
          <div
            key={row.map(card => card.key).join('|')}
            class='summary-card-row'
          >
            {row.map(renderCard)}
          </div>
        ))}
      </div>
    );
  },
});
