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

import { Component, Vue } from 'vue-property-decorator';

@Component
export default class documentLinkMixin extends Vue {
  public getDateConfig(date) {
    const cycle = {
      begin_time: '',
      end_time: '',
      cycle_config: {
        begin_time: '',
        end_time: '',
        type: date.type,
        day_list: [],
        week_list: [],
      },
    };
    if (date.type !== 1) {
      cycle.begin_time = date.dateRange[0];
      cycle.end_time = date.dateRange[1];
    }
    switch (date.type) {
      case 1:
        cycle.cycle_config.day_list = date.day.list;
        cycle.begin_time = date.single.range[0];
        cycle.end_time = date.single.range[1];
        break;
      case 2:
        cycle.cycle_config.day_list = date.day.list;
        cycle.cycle_config.begin_time = date.day.range[0];
        cycle.cycle_config.end_time = date.day.range[1];
        break;
      case 3:
        cycle.cycle_config.week_list = date.week.list;
        cycle.cycle_config.begin_time = date.week.range[0];
        cycle.cycle_config.end_time = date.week.range[1];
        break;
      case 4:
        cycle.cycle_config.day_list = date.month.list;
        cycle.cycle_config.begin_time = date.month.range[0];
        cycle.cycle_config.end_time = date.month.range[1];
        break;
    }
    return cycle;
  }
}
