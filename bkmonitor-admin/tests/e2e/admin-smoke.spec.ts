import { expect, test } from '@playwright/test';

test('opens datasource list and navigates to result table fields', async ({ page }) => {
  await page.request.post('/admin-api/environments', {
    data: {
      id: 'e2e-mock',
      name: 'E2E Mock',
      description: 'Playwright smoke test environment',
      apiBaseUrl: 'http://127.0.0.1:9',
      kernelRpcPath: '/api/v4/kernel_rpc/call/',
      authMode: 'apigw',
      appCode: 'bk_monitor',
      secretKey: '',
      readonly: true,
      tags: ['e2e'],
      mockFallback: true
    }
  });
  await page.request.patch('/admin-api/config/default-environment', {
    data: { environmentId: 'e2e-mock' }
  });

  await page.goto('/datasources?env=e2e-mock');
  await expect(page.getByText('资源管理')).toBeVisible();
  await expect(page.getByText('系统设置')).toBeVisible();
  await expect(page.getByRole('heading', { name: 'DataSource' })).toBeVisible();
  await page.getByRole('link', { name: '50010' }).click();
  await expect(page.getByRole('heading', { name: 'custom_metric_demo' })).toBeVisible();
  await page.getByRole('link', { name: '2_bkmonitor_time_series.__default__' }).click();
  await expect(page.getByRole('heading', { name: '字段' })).toBeVisible();
  await expect(page.getByRole('cell', { name: 'metric_2', exact: true })).toBeVisible();
  await page.getByRole('link', { name: '环境配置' }).click();
  await expect(page.getByRole('heading', { name: '环境配置' })).toBeVisible();
  await expect(page.getByLabel('切换环境')).toBeVisible();
  await expect(page.getByLabel('显示 secret_key')).toBeVisible();
});
