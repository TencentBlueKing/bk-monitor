import { expect, test } from '@playwright/test';

test.skip('替换为本次需求范围内的验收场景', async ({ page }) => {
  await page.goto('/');
  await expect(page.locator('body')).toBeVisible();
});
