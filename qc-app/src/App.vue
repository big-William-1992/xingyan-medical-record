<script setup>
import { useRoute } from 'vue-router'
import { useRouter } from 'vue-router'
import { ref, onMounted, watch } from 'vue'
import { Sunny, Moon } from '@element-plus/icons-vue'

const route = useRoute()
const router = useRouter()

const isDark = ref(false)

function toggleTheme() {
  isDark.value = !isDark.value
}

function applyTheme(dark) {
  const html = document.documentElement
  if (dark) {
    html.classList.add('dark')
  } else {
    html.classList.remove('dark')
  }
  localStorage.setItem('xy-theme', dark ? 'dark' : 'light')
}

onMounted(() => {
  const saved = localStorage.getItem('xy-theme')
  const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches
  isDark.value = saved ? saved === 'dark' : prefersDark
  applyTheme(isDark.value)
})

watch(isDark, applyTheme)

const menuItems = [
  { key: '/',         label: '概览',   icon: 'DataAnalysis' },
  { key: '/review',   label: '审核',   icon: 'DocumentChecked' },
  { key: '/stats',    label: '统计',   icon: 'TrendCharts', disabled: true },
  { key: '/settings', label: '设置',   icon: 'Setting', disabled: true },
]

function selectMenu(key) {
  router.push(key)
}
</script>

<template>
  <el-container class="app-layout">
    <!-- 侧边栏 -->
    <el-aside width="220px" class="sidebar">
      <div class="sidebar-brand">
        <div class="brand-icon">XY</div>
        <div>
          <div class="brand-name">星衍AI</div>
          <div class="brand-sub">放射质控系统</div>
        </div>
      </div>

      <el-menu
        :default-active="route.path"
        background-color="transparent"
        text-color="#9ca3af"
        active-text-color="#60a5fa"
        class="sidebar-menu"
        @select="selectMenu"
      >
        <el-menu-item v-for="item in menuItems" :key="item.key" :index="item.key">
          <el-icon><component :is="item.icon" /></el-icon>
          <span>{{ item.label }}</span>
          <el-tag v-if="item.disabled" type="info" size="small" effect="plain">即将推出</el-tag>
        </el-menu-item>
      </el-menu>

      <!-- 主题切换 -->
      <div class="theme-toggle-wrap">
        <el-button
          class="theme-toggle"
          :icon="isDark ? Sunny : Moon"
          @click="toggleTheme"
          circle
          plain
        >
          {{ isDark ? '亮色' : '暗色' }}
        </el-button>
      </div>

      <div class="sidebar-footer">
        <div class="user-info">
          <el-avatar :size="32" style="background: #2563eb">张</el-avatar>
          <div class="user-meta">
            <div class="user-name">张医生</div>
            <div class="user-org">XX医院 · 放射科</div>
          </div>
        </div>
      </div>
    </el-aside>

    <!-- 主内容区 -->
    <el-main class="main-content">
      <router-view />
    </el-main>
  </el-container>
</template>

<style scoped>
.app-layout { height: 100vh; }

.sidebar {
  background: var(--bg-secondary);
  border-right: 1px solid var(--border-color);
  display: flex;
  flex-direction: column;
  padding: 0;
}

.sidebar-brand {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 20px 18px;
  border-bottom: 1px solid var(--border-color);
}

.brand-icon {
  width: 36px; height: 36px; border-radius: 8px;
  background: linear-gradient(135deg, #2563eb, #0ea5e9);
  display: flex; align-items: center; justify-content: center;
  font-weight: 700; font-size: 14px; color: white; flex-shrink: 0;
}

.brand-name { font-size: 15px; font-weight: 600; color: var(--text-primary); line-height: 1.2; }
.brand-sub  { font-size: 11px; color: var(--text-muted); margin-top: 2px; }

.sidebar-menu { border: none; flex: 1; padding: 12px 0; }
.sidebar-menu .el-menu-item { height: 44px; line-height: 44px; margin: 2px 8px; border-radius: 6px; }
.sidebar-menu .el-menu-item:hover { background: var(--bg-tertiary) !important; }
.sidebar-menu .el-menu-item.is-active { background: #2563eb !important; color: white !important; }
.sidebar-menu .el-menu-item .el-icon { margin-right: 10px; }

.theme-toggle-wrap {
  padding: 12px 16px;
  border-top: 1px solid var(--border-color);
}

.theme-toggle {
  width: 100%;
  border-color: var(--bg-tertiary);
  color: var(--text-secondary);
  font-size: 13px;
}

.theme-toggle:hover {
  border-color: var(--accent);
  color: var(--accent-light);
}

.sidebar-footer { padding: 14px 16px; border-top: 1px solid var(--border-color); }
.user-info { display: flex; align-items: center; gap: 10px; }
.user-meta { min-width: 0; }
.user-name { font-size: 13px; color: var(--text-primary); font-weight: 500; }
.user-org  { font-size: 11px; color: var(--text-muted); }

.main-content { padding: 24px; background: var(--bg-primary); overflow-y: auto; }
</style>
