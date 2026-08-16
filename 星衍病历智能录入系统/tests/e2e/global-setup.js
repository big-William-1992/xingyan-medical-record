// ============================================
// 星衍AI · E2E 测试全局前置
// 启动后端服务，测试完成后关闭
// ============================================

const { spawn } = require('child_process');
const path = require('path');

let serverProcess = null;

module.exports = async () => {
  const serverDir = path.resolve(__dirname, '..', '..');
  const port = process.env.E2E_PORT || '8765';

  console.log(`[E2E] 启动后端服务 (端口 ${port})...`);

  serverProcess = spawn(
    process.env.E2E_PYTHON || 'python3',
    ['app_server.py'],
    {
      cwd: serverDir,
      env: { ...process.env, PORT: port },
      stdio: 'pipe',
    }
  );

  // 等待服务就绪（最多 30 秒）
  const maxWait = 30000;
  const start = Date.now();
  while (Date.now() - start < maxWait) {
    try {
      const res = await fetch(`http://localhost:${port}/api/stats`);
      if (res.ok) {
        console.log('[E2E] 后端服务已就绪');
        return;
      }
    } catch (e) {
      // 还没就绪，继续等待
    }
    await new Promise((r) => setTimeout(r, 500));
  }

  throw new Error('[E2E] 后端服务启动超时');
};

// 全局后置：关闭服务
process.on('exit', () => {
  if (serverProcess) {
    serverProcess.kill();
  }
});
