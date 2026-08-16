// ============================================
// 星衍AI · Playwright E2E 测试配置
// 覆盖：登录 → 选模板 → 语音录入 → 保存 → 查询
// 运行：npx playwright test
// ============================================

const { defineConfig, devices } = require('@playwright/test');

module.exports = defineConfig({
  testDir: './tests/e2e',
  timeout: 60000,
  retries: 0,
  workers: 1, // 串行执行（避免数据库冲突）

  reporter: [
    ['list'],
    ['html', { outputFolder: 'test-results/e2e-report' }],
  ],

  use: {
    baseURL: process.env.E2E_BASE_URL || 'http://localhost:8765',
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
    video: 'retain-on-failure',
    viewport: { width: 390, height: 844 }, // 默认手机视口（移动端场景）
  },

  projects: [
    {
      name: 'mobile-chromium', // 手机端
      use: { ...devices['iPhone 13'] },
    },
    {
      name: 'desktop-chromium', // 桌面端
      use: { ...devices['Desktop Chrome'] },
    },
  ],

  // 全局前置：启动后端服务
  globalSetup: require.resolve('./tests/e2e/global-setup'),
});
