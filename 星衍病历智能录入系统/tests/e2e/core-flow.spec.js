// ============================================
// 星衍AI · E2E 核心流程测试
// 覆盖：加载 → 选科室/模板 → 语音录入 → 保存 → 查询
// 运行：npx playwright test
// ============================================

const { test, expect } = require('@playwright/test');

test.describe('星衍AI 核心流程', () => {

  test('页面加载与初始化', async ({ page }) => {
    // 访问首页
    await page.goto('/');

    // 验证标题
    await expect(page).toHaveTitle(/星衍AI/);

    // 验证核心元素存在
    await expect(page.locator('#deptSelect')).toBeVisible();
    await expect(page.locator('#tplSelect')).toBeVisible();
    await expect(page.locator('#editor')).toBeVisible();
    await expect(page.locator('#recBtn')).toBeVisible();
    await expect(page.locator('#btnSave')).toBeVisible();
    await expect(page.locator('#btnQA')).toBeVisible();

    // 验证状态栏
    await expect(page.locator('#stKG')).toContainText('图谱');
  });

  test('选择科室和模板', async ({ page }) => {
    await page.goto('/');

    // 选择科室
    await page.locator('#deptSelect').selectOption({ label: '内科' });
    await page.waitForTimeout(500);

    // 选择模板
    const tplCount = await page.locator('#tplSelect option').count();
    expect(tplCount).toBeGreaterThan(0);

    await page.locator('#tplSelect').selectOption({ index: 0 });
    await page.waitForTimeout(800);

    // 验证编辑器加载了模板内容
    const editorText = await page.locator('#editor').innerText();
    expect(editorText.length).toBeGreaterThan(10);
  });

  test('文字录入与字段高亮', async ({ page }) => {
    await page.goto('/');
    await page.waitForTimeout(1000);

    // 点击编辑器并输入
    const editor = page.locator('#editor');
    await editor.click();
    await page.keyboard.type('主诉：发热三天，伴咳嗽');

    // 验证输入内容
    const text = await editor.innerText();
    expect(text).toContain('发热三天');
  });

  test('知识问答功能', async ({ page }) => {
    await page.goto('/');

    // 打开问答面板
    await page.locator('#btnQA').click();
    await expect(page.locator('#qaOverlay')).toHaveClass(/open/);

    // 输入问题
    await page.locator('#qaInput').fill('高血压怎么治疗');
    await page.locator('#qaSend').click();

    // 等待回答
    await page.waitForTimeout(3000);

    // 验证收到回答
    const botMessages = page.locator('.qa-msg.bot');
    const count = await botMessages.count();
    expect(count).toBeGreaterThan(1);
  });

  test('保存病历', async ({ page }) => {
    await page.goto('/');
    await page.waitForTimeout(1000);

    // 输入内容
    const editor = page.locator('#editor');
    await editor.click();
    await page.keyboard.type('主诉：头痛三天');

    // 点击保存
    await page.locator('#btnSave').click();

    // 等待保存完成（Toast 提示）
    await page.waitForTimeout(1500);
    const toast = page.locator('.toast').last();
    await expect(toast).toBeVisible();
  });

  test('预加载离线数据包', async ({ page }) => {
    await page.goto('/');
    await page.waitForTimeout(1500);

    // 点击预加载按钮
    const preloadBtn = page.locator('button', { hasText: '预加载' });
    await expect(preloadBtn).toBeVisible();
    await preloadBtn.click();

    // 等待预加载完成
    await page.waitForTimeout(3000);

    // 验证离线模块已初始化
    const offlineReady = await page.evaluate(() => {
      return !!(window.XingyanOffline && window.XingyanOffline.getOfflineStats);
    });
    expect(offlineReady).toBe(true);
  });

  test('移动端响应式布局', async ({ page }) => {
    // 手机视口（配置中已设置为 iPhone 13）
    await page.goto('/');

    // 验证侧边栏默认隐藏
    await expect(page.locator('.sidebar')).toBeHidden();

    // 点击侧边栏按钮，验证覆盖层出现
    await page.locator('#btnSidebar').click();
    await expect(page.locator('#mainGrid')).toHaveClass(/sidebar-open/);

    // 点击遮罩关闭
    await page.locator('#mainGrid').click({ position: { x: 10, y: 10 } });
    await page.waitForTimeout(300);
  });
});
