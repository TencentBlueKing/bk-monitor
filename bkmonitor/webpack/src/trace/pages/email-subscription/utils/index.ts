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
import { useI18n } from 'vue-i18n';

export function getSendFrequencyText(data) {
  const { t } = useI18n();
  const hourTextMap = {
    0.5: t('每个小时整点,半点发送'),
    1: t('每个小时整点发送'),
    2: t('从0点开始,每隔2小时整点发送'),
    6: t('从0点开始,每隔6小时整点发送'),
    12: t('每天9:00,21:00发送')
  };
  const weekMap = [t('周一'), t('周二'), t('周三'), t('周四'), t('周五'), t('周六'), t('周日')];
  let str = '';
  if (!data?.frequency?.type) return '';
  switch (data.frequency.type) {
    case 1: {
      str = t('仅一次');
      break;
    }
    case 2: {
      str = `${t('每月 {0} 号', [data.frequency.day_list.toString()])} ${data.frequency.run_time}`;
      break;
    }
    case 3: {
      const weekStrArr = data.frequency.week_list.map(item => weekMap[item - 1]);
      const weekStr = weekStrArr.join(', ');
      str = `${weekStr} ${data.frequency.run_time}`;
      break;
    }
    case 4: {
      const dayArr = data.frequency.day_list.map(item => `${item}号`);
      const dayStr = dayArr.join(', ');
      str = `${dayStr} ${data.frequency.run_time}`;
      break;
    }
    case 5: {
      str = hourTextMap[data.frequency.hour];
      break;
    }
    default:
      str = data.frequency.run_time;
      break;
  }
  return str;
}
