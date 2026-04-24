import type { AdminConfig } from './schemas';

export const defaultAdminConfig: AdminConfig = {
  defaultEnvironmentId: 'local',
  environments: [
    {
      id: 'local',
      name: '本地开发',
      description: '本地 bkmonitor APIGW 联调环境',
      apiBaseUrl: 'http://localhost:8000',
      kernelRpcPath: '/api/v4/kernel_rpc/call/',
      authMode: 'apigw',
      appCode: 'bk_monitor',
      secretKey: '',
      readonly: true,
      tags: ['dev'],
      mockFallback: false
    },
    {
      id: 'staging',
      name: '预发布',
      description: '用于联调的预发布环境',
      apiBaseUrl: 'https://bkmonitor-staging.example.com',
      kernelRpcPath: '/app/kernel_rpc/call/',
      authMode: 'apigw',
      appCode: '',
      secretKey: '',
      readonly: true,
      tags: ['test', 'readonly'],
      mockFallback: false
    }
  ]
};
