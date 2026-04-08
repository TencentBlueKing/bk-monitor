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

import { computed, defineComponent } from 'vue';

import { CommonTimezoneOptions } from '@blueking/date-picker';
import dayjs from 'dayjs';
import advancedFormat from 'dayjs/plugin/advancedFormat';
import { useI18n } from 'vue-i18n';

import './timezone-tips.scss';

dayjs.extend(advancedFormat);

export default defineComponent({
  name: 'TimezoneTips',
  props: {
    timezone: {
      type: String,
      default: dayjs.tz.guess(),
    },
  },
  setup(props) {
    const { t } = useI18n();

    // 动态计算时区详情
    const timezoneInfo = computed(() => {
      const info = {
        name: props.timezone || dayjs.tz.guess(),
        abbr: '',
        offset: '',
        country: '',
      };
      try {
        for (const item of CommonTimezoneOptions) {
          if (item.label) {
            for (const infoItem of item.options) {
              if (infoItem.label === info.name) {
                info.abbr = infoItem.abbreviation || '';
                info.country = infoItem.country || '';
                info.offset = infoItem.utc || '';
                break;
              }
            }
            if (info.abbr) {
              break;
            }
          }
        }
        return info;
      } catch (_e) {
        // 容错处理
        return info;
      }
    });

    return {
      t,
      timezoneInfo,
    };
  },
  render() {
    const { name, abbr, offset, country } = this.timezoneInfo;
    return (
      <span class='timezone-tips-component'>
        <span class='icon-monitor icon-tips' />
        <span class='timezone-name'>{`${this.t('当前业务时区')}：${name}`}</span>
        <span class='timezone-region'>
          {country}，{abbr}
        </span>
        <span class='timezone-offset'>{offset}</span>
      </span>
    );
  },
});
