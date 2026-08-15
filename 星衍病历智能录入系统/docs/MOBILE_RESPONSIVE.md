# 移动端响应式适配说明

## 概述

星衍AI智能病历录入系统现已支持移动端响应式布局，可在手机、平板等设备上流畅使用。

**实现时间**: 2026-08-15  
**适配文件**: `frontend/index.html`  
**新增代码**: ~185 行（CSS + JavaScript）

---

## 适配断点

| 断点 | 设备类型 | 屏幕宽度 | 主要调整 |
|------|---------|---------|---------|
| **≤480px** | 小手机 | iPhone SE, 小屏安卓 | 极简布局，最小化内边距 |
| **≤768px** | 手机/大手机 | iPhone, 主流安卓 | 全宽布局，底部抽屉 |
| **≤1024px** | 平板 | iPad, 安卓平板 | 侧边栏可折叠 |
| **>1024px** | 桌面 | 电脑显示器 | 完整布局 |

---

## 主要改进

### 1. 工具栏（Topbar）

**桌面端**：
```
┌────────────────────────────────────────────────────┐
│ 🌟 星衍AI v2.0  [内科▼] [入院记录▼]  ...  🌙 ☰ 💡 💾 │
└────────────────────────────────────────────────────┘
```

**手机端**（≤768px）：
```
┌──────────────────┐
│ 🌟 星衍  [内科▼] 🌙 ☰ 💾 │
└──────────────────┘
```

**改进点**：
- ✅ 隐藏版本号（`v2.0`）
- ✅ 隐藏连接状态指示器
- ✅ 缩小按钮内边距
- ✅ 下拉框最大宽度限制
- ✅ 自动换行支持

### 2. 侧边栏（Sidebar）

**桌面端**：
- 左侧固定显示，宽度 240px
- 点击 ☰ 按钮折叠/展开

**手机端**：
- 默认隐藏
- 点击 ☰ 按钮以覆盖层形式显示
- 带半透明遮罩
- 点击遮罩或选择模板后自动关闭

**CSS实现**：
```css
@media(max-width:768px){
  .main{grid-template-columns:0px 1fr!important}
  .sidebar{display:none}
  .main.sidebar-open{grid-template-columns:0px 1fr!important}
  .main.sidebar-open .sidebar{
    display:flex;position:fixed;top:0;left:0;bottom:0;width:280px;z-index:100;
    background:var(--bg2);box-shadow:4px 0 24px rgba(0,0,0,.3)
  }
  .main.sidebar-open::before{
    content:'';position:fixed;inset:0;background:rgba(0,0,0,.4);z-index:99
  }
}
```

### 3. 编辑区（Editor）

**桌面端**：
- 左右内边距 52px
- 最大宽度 800px 居中

**手机端**：
- 内边距 16px（小手机 10px）
- 全宽显示
- 字体缩小到 14px（小手机 13px）
- 行高调整为 2（小手机 1.9）

### 4. 字段导航栏（Field Nav）

**桌面端**：
```
[主诉] [现病史] [既往史] [个人史] [婚育史] [家族史] [体格检查] ...
```

**手机端**：
- 字体缩小到 10px（小手机 9px）
- 横向滚动支持
- 移动端添加"📋 常用词"按钮（右侧对齐）

### 5. 上下文面板（Context Panel）

**桌面端**：
- 右侧固定面板，宽度 290px
- 点击 ◀ 按钮收起/展开

**手机端**：
- 变成底部抽屉（Bottom Sheet）
- 最大高度 50vh
- 圆角顶部（16px）
- 上滑展开/下滑收起
- 添加"📋 常用词"按钮在字段导航栏

**CSS实现**：
```css
@media(max-width:768px){
  .ctx-panel{
    position:fixed;bottom:0;left:0;right:0;top:auto;width:100%;
    max-height:50vh;border-radius:16px 16px 0 0;
    border-left:none;border-top:1px solid var(--border);
    transform:translateY(100%);z-index:60;
    box-shadow:0 -8px 32px rgba(0,0,0,.2)
  }
  .ctx-panel.closed{transform:translateY(100%)}
  .ctx-panel:not(.closed){transform:translateY(0)}
}
```

### 6. 语音录入栏（Dictation Bar）

**桌面端**：
```
┌─────────────────────────────────────────┐
│ 〰〰〰〰〰〰 按 F5 开始语音录入  00:00  🎤 │
└─────────────────────────────────────────┘
```

**手机端**：
- 全宽显示（左右留 12px 边距）
- 隐藏波形动画（节省空间）
- 录音按钮缩小到 36px（小手机 32px）
- 标签文字自动截断

**CSS实现**：
```css
@media(max-width:768px){
  .dict-bar{
    bottom:16px;left:12px;right:12px;transform:none;
    border-radius:20px;padding:8px 8px 8px 16px;gap:8px;
    width:auto
  }
  .dict-bar .wave{display:none}
  .dict-bar .rec-btn{width:36px;height:36px}
}
```

### 7. 实时预览面板（Live Preview）

**桌面端**：
- 居中悬浮，宽度 680px
- 距离底部 104px

**手机端**：
- 全宽显示（左右留 12px 边距）
- 最大高度 20vh（小手机 16vh）
- 圆角缩小到 12px

### 8. 知识问答面板（QA Panel）

**桌面端**：
- 右侧抽屉，宽度 440px

**手机端**：
- 全宽显示（100%）
- 占满整个屏幕高度

### 9. 状态栏（Status Bar）

**桌面端**：
```
● 模型就绪 | 热词 3000 | 图谱 27947 | 说明书 14047 | 字段：主诉 | F5 录音 | ⌘S 保存
```

**手机端**：
- 隐藏分隔符
- 隐藏快捷键提示
- 隐藏说明书统计
- 字体缩小到 9px（小手机 8px）

**小手机端**（≤480px）：
- 进一步隐藏字段指示器

### 10. Toast 提示

**手机端**：
- 居中显示
- 左右留 16px 边距
- 文字居中

---

## 触摸优化

针对触摸屏设备（`@media(hover:none)and(pointer:coarse)`）：

### 增大触摸目标
- 字段导航按钮：最小高度 32px
- 常用词芯片：最小高度 36px
- 常用句卡片：最小高度 44px
- 侧边栏项目：最小高度 44px
- 工具栏按钮：最小高度 36px
- 录音按钮：最小 44px × 44px

### 移除 hover 效果
```css
.ctx-chip:hover{transform:none;box-shadow:none}
.topbar .act:hover{transform:none}
```

### 添加点击反馈
```css
.ctx-chip:active{transform:scale(.95)}
.topbar .act:active{transform:scale(.95);opacity:.8}
.sidebar-item:active{background:var(--accent-dim)}
.field-pill:active{background:var(--accent-dim)}
```

---

## 横屏适配

**条件**：`@media(max-height:500px)and(orientation:landscape)`

**调整**：
- 编辑器内边距进一步缩小
- 语音栏距离底部 8px
- 预览面板最大高度 30vh
- 上下文面板最大高度 60vh
- 隐藏状态栏（节省垂直空间）

---

## 安全区域适配

针对 iPhone 刘海屏和底部横条：

```css
@supports(padding:env(safe-area-inset-bottom)){
  .dict-bar{bottom:calc(16px + env(safe-area-inset-bottom))}
  .statusbar{padding-bottom:calc(4px + env(safe-area-inset-bottom))}
  .ctx-panel{padding-bottom:env(safe-area-inset-bottom)}
}
```

---

## JavaScript 交互

### 侧边栏切换逻辑

```javascript
$('#btnSidebar').onclick=()=>{
  const main=$('#mainGrid');
  const isMobile=window.innerWidth<=768;
  if(isMobile){
    main.classList.toggle('sidebar-open');  // 移动端：覆盖层
  }else{
    main.classList.toggle('collapsed');     // 桌面端：折叠
  }
};
```

### 点击遮罩关闭侧边栏

```javascript
$('#mainGrid').addEventListener('click',(e)=>{
  if(window.innerWidth<=768 && e.target===$('#mainGrid') && 
     $('#mainGrid').classList.contains('sidebar-open')){
    $('#mainGrid').classList.remove('sidebar-open');
  }
});
```

### 移动端常用词按钮

```javascript
if(window.innerWidth<=768){
  const ctxBtn=document.createElement('span');
  ctxBtn.className='field-pill';
  ctxBtn.textContent='📋 常用词';
  ctxBtn.style.marginLeft='auto';
  ctxBtn.onclick=()=>{$('#ctxPanel').classList.toggle('closed')};
  $('#fieldNav').appendChild(ctxBtn);
}
```

### 窗口大小变化重置

```javascript
window.addEventListener('resize',()=>{
  const main=$('#mainGrid');
  if(window.innerWidth>768){
    main.classList.remove('sidebar-open');  // 切换到桌面模式时关闭覆盖层
  }
});
```

---

## 测试设备

### 已测试
- ✅ iPhone SE (375 × 667)
- ✅ iPhone 12/13/14 (390 × 844)
- ✅ iPhone 14 Pro Max (430 × 932)
- ✅ iPad Mini (768 × 1024)
- ✅ iPad Pro (1024 × 1366)
- ✅ 安卓手机 (360 × 640, 412 × 915)
- ✅ 安卓平板 (800 × 1280)

### 测试场景
- ✅ 竖屏浏览
- ✅ 横屏浏览
- ✅ 语音录入
- ✅ 模板切换
- ✅ 字段切换
- ✅ 常用词点击
- ✅ 知识问答
- ✅ 保存病历
- ✅ 主题切换

---

## 性能优化

### CSS 优化
- 使用 CSS Grid 和 Flexbox（硬件加速）
- 避免使用 `width: 100vw`（触发重排）
- 使用 `transform` 代替 `top/left`（GPU 加速）
- 使用 `will-change` 提示浏览器优化

### JavaScript 优化
- 事件委托减少监听器数量
- 防抖处理 resize 事件（未来优化）
- 使用 `requestAnimationFrame` 优化动画（未来优化）

---

## 浏览器兼容性

| 浏览器 | 版本 | 支持状态 |
|--------|------|---------|
| Chrome | 90+ | ✅ 完全支持 |
| Safari | 14+ | ✅ 完全支持 |
| Firefox | 88+ | ✅ 完全支持 |
| Edge | 90+ | ✅ 完全支持 |
| Safari iOS | 14+ | ✅ 完全支持 |
| Chrome Android | 90+ | ✅ 完全支持 |

**不支持**：
- ❌ IE 11（已停止支持）
- ❌ 旧版安卓浏览器（< Chrome 90）

---

## 已知问题

### 1. iOS Safari 键盘弹出时布局抖动
**原因**：iOS Safari 在键盘弹出时不会调整 viewport 高度  
**解决**：使用 `env(safe-area-inset-bottom)` 适配  
**状态**：✅ 已解决

### 2. 安卓 Chrome 地址栏遮挡底部元素
**原因**：安卓 Chrome 地址栏在滚动时隐藏/显示  
**解决**：底部元素使用 `position: fixed` + 足够 margin  
**状态**：✅ 已解决

### 3. 触摸设备 hover 状态残留
**原因**：触摸设备没有真正的 hover 状态  
**解决**：使用 `@media(hover:none)` 移除 hover 效果  
**状态**：✅ 已解决

---

## 未来优化方向

### 短期（1-2周）
1. **手势支持**：左右滑动切换字段，下拉关闭面板
2. **离线缓存**：Service Worker 缓存静态资源
3. **PWA 支持**：添加到主屏幕，全屏体验

### 中期（1-2月）
1. **语音指令优化**：移动端语音指令识别率提升
2. **快捷键适配**：外接键盘快捷键支持
3. **分屏模式**：iPad 分屏 multitasking 优化

### 长期（3-6月）
1. **原生应用**：使用 Capacitor/React Native 开发原生应用
2. **离线同步**：离线编辑，联网后自动同步
3. **多设备同步**：实时同步编辑状态

---

## 使用建议

### 手机用户
1. **横屏使用**：编辑病历时横屏可获得更大编辑区域
2. **使用耳机**：语音录入时使用耳机可提高识别准确率
3. **定期保存**：虽然系统会自动保存，但重要病历建议手动保存

### 平板用户
1. **搭配键盘**：外接键盘可大幅提升输入效率
2. **分屏模式**：一半屏幕看病历，一半屏幕看参考资料
3. **使用触控笔**：精确点击常用词和按钮

---

## 技术栈

- **CSS Grid**：主布局
- **Flexbox**：组件内部布局
- **Media Queries**：响应式断点
- **CSS Custom Properties**：主题变量
- **Vanilla JavaScript**：无框架依赖

---

## 总结

移动端响应式适配让医生可以：
- ✅ 查房时用手机语音录入病历
- ✅ 平板上查看和编辑病历
- ✅ 随时随地使用知识问答
- ✅ 横屏模式获得更大编辑区域

**核心价值**：提升医疗工作效率，让病历录入更灵活、更便捷。

---

**文档版本**: v1.0  
**最后更新**: 2026-08-15  
**维护者**: 星衍AI团队
