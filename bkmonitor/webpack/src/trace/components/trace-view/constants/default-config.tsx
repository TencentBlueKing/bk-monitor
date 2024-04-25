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

import deepFreeze from 'deep-freeze';

import { FALLBACK_DAG_MAX_NUM_SERVICES } from './index';
// import getVersion from '../utils/version/get-version';

// const { version } = require('../../package.json');

export default deepFreeze(
  Object.defineProperty(
    {
      archiveEnabled: false,
      dependencies: {
        dagMaxNumServices: FALLBACK_DAG_MAX_NUM_SERVICES,
        menuEnabled: true,
      },
      linkPatterns: [],
      qualityMetrics: {
        menuEnabled: false,
        menuLabel: 'Trace Quality',
      },
      menu: [
        {
          label: 'About Jaeger',
          items: [
            {
              label: 'Website/Docs',
              url: 'https://www.jaegertracing.io/',
            },
            {
              label: 'Blog',
              url: 'https://medium.com/jaegertracing/',
            },
            {
              label: 'Twitter',
              url: 'https://twitter.com/JaegerTracing',
            },
            {
              label: 'Discussion Group',
              url: 'https://groups.google.com/forum/#!forum/jaeger-tracing',
            },
            {
              label: 'Online Chat',
              url: 'https://cloud-native.slack.com/archives/CGG7NFUJ3',
            },
            {
              label: 'GitHub',
              url: 'https://github.com/jaegertracing/',
            },
            {
              // label: `Jaeger ${getVersion().gitVersion}`,
            },
            {
              // label: `Commit ${getVersion().gitCommit.substring(0, 7)}`,
            },
            {
              // label: `Build ${getVersion().buildDate}`,
            },
            {
              // label: `Jaeger UI v${version}`,
            },
          ],
        },
      ],
      search: {
        maxLookback: {
          label: '2 Days',
          value: '2d',
        },
        maxLimit: 1500,
      },
      tracking: {
        gaID: null,
        trackErrors: true,
        customWebAnalytics: null,
      },
      monitor: {
        menuEnabled: true,
        emptyState: {
          mainTitle: 'Get started with Service Performance Monitoring',
          subTitle:
            'A high-level monitoring dashboard that helps you cut down the time to identify and resolve anomalies and issues.',
          description:
            'Service Performance Monitoring aggregates tracing data into RED metrics and visualizes them in service and operation level dashboards.',
          button: {
            text: 'Read the Documentation',
            onClick: () => window.open('https://www.jaegertracing.io/docs/latest/spm/'),
          },
          alert: {
            message: 'Service Performance Monitoring requires a Prometheus-compatible time series database.',
            type: 'info',
          },
        },
        docsLink: 'https://www.jaegertracing.io/docs/latest/spm/',
      },
    },
    // fields that should be individually merged vs wholesale replaced
    '__mergeFields',
    { value: ['dependencies', 'search', 'tracking'] }
  )
);

// eslint-disable-next-line @typescript-eslint/naming-convention
export const deprecations = [
  {
    formerKey: 'dependenciesMenuEnabled',
    currentKey: 'dependencies.menuEnabled',
  },
  {
    formerKey: 'gaTrackingID',
    currentKey: 'tracking.gaID',
  },
];
