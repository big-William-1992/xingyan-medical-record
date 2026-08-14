<script setup>
import { ref, computed, onMounted, onUnmounted, nextTick, watch } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import gsap from 'gsap'
import { fetchReports, fetchStats, fetchQcItems, fetchSeverityMap } from '../api/index.js'

const router = useRouter()

// ─── 数据状态 ───
const reports = ref([])
const stats = ref(null)
const qcItems = ref([])
const severityMap = ref({})
const loading = ref(true)

const statsCards = computed(() => {
  if (!stats.value) return []
  const s = stats.value
  return [
    { label: '今日审核',   value: s.today.total,  sub: `通过 ${s.today.passed} · 打回 ${s.today.rejected}`, color: '#3b82f6' },
    { label: '本周审核',   value: s.week.total,   sub: `通过 ${s.week.passed} · 打回 ${s.week.rejected}`, color: '#8b5cf6' },
    { label: '平均得分',   value: s.avgScore,     sub: '百分制',                                       color: '#10b981', suffix: '分' },
    { label: '待审核',     value: s.today.pending, sub: '需尽快处理',                                   color: '#f59e0b' },
  ]
})

const expandedRows = ref([])

function goToReview() {
  router.push('/review')
}

function viewReport(id) {
  router.push(`/report?id=${id}`)
}

// 按分组整理质控检查项
const qcGroups = computed(() => {
  const groups = {}
  for (const item of qcItems.value) {
    if (!groups[item.group]) groups[item.group] = []
    groups[item.group].push(item)
  }
  return groups
})

function getQcPassRate(checks) {
  if (!checks) return 0
  const values = Object.values(checks).filter(v => v !== null)
  if (!values.length) return 0
  const passed = values.filter(v => v === true).length
  return Math.round(passed / values.length * 100)
}

function getQcCheckStatus(checks, key) {
  const v = checks?.[key]
  if (v === true) return { type: 'success', label: '通过' }
  if (v === false) return { type: 'danger', label: '不通过' }
  return { type: 'info', label: '不适用' }
}

function getSeverityInfo(severity) {
  return severityMap.value[severity] || severityMap.value['info'] || { label: severity, type: 'info', icon: 'InfoFilled' }
}

function getScoreColor(score) {
  if (score >= 85) return '#10b981'
  if (score >= 70) return '#f59e0b'
  return '#ef4444'
}

function toggleRow(row) {
  const idx = expandedRows.value.indexOf(row.id)
  if (idx > -1) {
    animateCollapse(row.id)
  } else {
    expandedRows.value.push(row.id)
  }
}

function getStatusTag(status) {
  switch (status) {
    case 'passed':   return { type: 'success', label: '已通过' }
    case 'rejected': return { type: 'danger',  label: '已打回' }
    case 'pending':  return { type: 'warning', label: '待审核' }
    default:        return { type: 'info',    label: status }
  }
}

function getPriorityTag(priority) {
  switch (priority) {
    case 'urgent':  return { type: 'danger',  label: '紧急' }
    case 'high':    return { type: 'warning', label: '高优' }
    default:        return null
  }
}

// ─── 数据加载 ───
async function loadData() {
  loading.value = true
  try {
    const [reportsData, statsData, qcItemsData, severityData] = await Promise.all([
      fetchReports(),
      fetchStats(),
      fetchQcItems(),
      fetchSeverityMap(),
    ])
    reports.value = reportsData
    stats.value = statsData
    qcItems.value = qcItemsData
    severityMap.value = severityData
  } catch (e) {
    ElMessage.error('数据加载失败：' + e.message)
  } finally {
    loading.value = false
  }
}

// ─── GSAP 动画 ───

// 1. 展开/收起动画
const expandAnimations = {}

function animateExpand(rowId) {
  nextTick(() => {
    const row = document.querySelector(`tr[data-row-key="${rowId}"]`)
    if (!row) return
    const content = row.querySelector('.expanded-content')
    if (!content) return

    const icon = row.querySelector('.el-table__expand-icon')
    if (icon) gsap.to(icon, { rotation: 180, duration: 0.3, ease: 'power2.out' })

    gsap.set(content, { height: 0, overflow: 'hidden' })
    const fullHeight = content.scrollHeight
    gsap.to(content, {
      height: fullHeight,
      duration: 0.4,
      ease: 'power2.out',
      onComplete: () => {
        gsap.set(content, { height: 'auto', overflow: 'visible' })
        animateIssues(rowId)
      },
    })
  })
}

function animateCollapse(rowId) {
  nextTick(() => {
    const row = document.querySelector(`tr[data-row-key="${rowId}"]`)
    if (!row) return
    const content = row.querySelector('.expanded-content')
    const icon = row.querySelector('.el-table__expand-icon')
    if (icon) gsap.to(icon, { rotation: 0, duration: 0.3, ease: 'power2.out' })

    if (content) {
      gsap.set(content, { height: content.scrollHeight, overflow: 'hidden' })
      gsap.to(content, {
        height: 0,
        duration: 0.3,
        ease: 'power2.in',
        onComplete: () => {
          const idx = expandedRows.value.indexOf(rowId)
          if (idx > -1) expandedRows.value.splice(idx, 1)
        },
      })
    } else {
      const idx = expandedRows.value.indexOf(rowId)
      if (idx > -1) expandedRows.value.splice(idx, 1)
    }
  })
}

// 2. 质控问题逐条弹入动画
function animateIssues(rowId) {
  nextTick(() => {
    const row = document.querySelector(`tr[data-row-key="${rowId}"]`)
    if (!row) return
    const cards = row.querySelectorAll('.issue-card')
    if (!cards.length) return

    gsap.fromTo(cards,
      { opacity: 0, y: 12, scale: 0.97 },
      {
        opacity: 1, y: 0, scale: 1,
        duration: 0.35,
        stagger: 0.08,
        ease: 'back.out(1.2)',
      }
    )

    const qcItems = row.querySelectorAll('.qc-item')
    if (qcItems.length) {
      gsap.fromTo(qcItems,
        { opacity: 0, x: -8 },
        { opacity: 1, x: 0, duration: 0.25, stagger: 0.03, ease: 'power2.out' }
      )
    }
  })
}

// 3. 页面入场动画
function animateEntrance() {
  const statCards = document.querySelectorAll('.stat-card-compact')
  gsap.fromTo(statCards,
    { opacity: 0, y: 20 },
    { opacity: 1, y: 0, duration: 0.5, stagger: 0.1, ease: 'power2.out', delay: 0.2 }
  )

  const tableRows = document.querySelectorAll('.el-table__body-wrapper .el-table__row')
  gsap.fromTo(tableRows,
    { opacity: 0, x: -15 },
    { opacity: 1, x: 0, duration: 0.4, stagger: 0.06, ease: 'power2.out', delay: 0.4 }
  )
}

// 4. 质控得分数字滚动动画
const scoreAnimations = {}

function animateScore(element, targetScore) {
  if (!element) return
  const obj = { val: 0 }
  gsap.to(obj, {
    val: targetScore,
    duration: 1.2,
    ease: 'power2.out',
    delay: 0.6,
    onUpdate: () => {
      element.textContent = Math.round(obj.val)
    },
  })
}

onMounted(async () => {
  await loadData()
  // 入场动画（数据加载完成后）
  nextTick(() => animateEntrance())
})

onUnmounted(() => {
  Object.values(expandAnimations).forEach(tl => tl.kill())
})
</script>

<template>
  <div class="dashboard">
    <div class="page-header">
      <h1 class="page-title">质控工作台</h1>
      <p class="page-subtitle">放射科报告质控审核</p>
    </div>

    <!-- 质控检查总览表（核心内容，优先显示） -->
    <el-card shadow="never" class="main-card">
      <template #header>
        <div class="card-header">
          <span class="card-title">质控检查总览</span>
          <div class="header-actions">
            <el-button text type="primary" @click="goToReview">查看全部 →</el-button>
          </div>
        </div>
      </template>

      <el-table :data="reports" style="width: 100%" :expand-row-keys="expandedRows" row-key="id">
        <el-table-column type="expand" width="50">
          <template #default="{ row }">
            <div class="expanded-content">
              <el-row :gutter="16">
                <!-- 患者基本信息 + 影像描述 + 影像诊断 -->
                <el-col :xs="24" :lg="12">
                  <div class="expand-section">
                    <div class="expand-section-title">
                      <el-icon><User /></el-icon> 患者基本信息
                    </div>
                    <el-descriptions :column="2" border size="small" direction="vertical">
                      <el-descriptions-item label="姓名">{{ row.patientName }}</el-descriptions-item>
                      <el-descriptions-item label="性别">
                        <el-tag :type="row.patientSex === '男' ? 'primary' : 'danger'" size="small">{{ row.patientSex }}</el-tag>
                      </el-descriptions-item>
                      <el-descriptions-item label="年龄">{{ row.patientAge }} 岁</el-descriptions-item>
                      <el-descriptions-item label="患者 ID">{{ row.patientId }}</el-descriptions-item>
                      <el-descriptions-item label="检查模态">{{ row.modality }}</el-descriptions-item>
                      <el-descriptions-item label="检查部位">{{ row.bodyPart }}</el-descriptions-item>
                      <el-descriptions-item label="检查号">{{ row.accession }}</el-descriptions-item>
                      <el-descriptions-item label="检查日期">{{ row.studyDate }}</el-descriptions-item>
                      <el-descriptions-item label="报告日期">{{ row.reportDate }}</el-descriptions-item>
                      <el-descriptions-item label="质控得分">
                        <span :style="{ color: getScoreColor(row.score), fontWeight: 600 }">{{ row.score }} 分</span>
                      </el-descriptions-item>
                    </el-descriptions>
                  </div>

                  <div class="expand-section">
                    <div class="expand-section-title">
                      <el-icon><Document /></el-icon> 影像描述
                    </div>
                    <div class="desc-text">{{ row.description }}</div>
                  </div>

                  <div class="expand-section">
                    <div class="expand-section-title">
                      <el-icon><Stamp /></el-icon> 影像诊断
                    </div>
                    <div class="diag-text">{{ row.diagnosis }}</div>
                  </div>
                </el-col>

                <!-- 质控检查项 -->
                <el-col :xs="24" :lg="12">
                  <div class="expand-section">
                    <div class="expand-section-title">
                      <el-icon><List /></el-icon> 质控检查
                      <el-progress
                        type="circle"
                        :percentage="getQcPassRate(row.qcChecks)"
                        :stroke-width="8"
                        :width="70"
                        :color="getQcPassRate(row.qcChecks) >= 80 ? '#10b981' : getQcPassRate(row.qcChecks) >= 60 ? '#f59e0b' : '#ef4444'"
                      />
                    </div>
                    <div v-for="(items, groupName) in qcGroups" :key="groupName" class="qc-group">
                      <div class="qc-group-title">{{ groupName }}</div>
                      <div class="qc-items">
                        <div v-for="item in items" :key="item.key" class="qc-item">
                          <span class="qc-label">{{ item.label }}</span>
                          <el-tag :type="getQcCheckStatus(row.qcChecks, item.key).type" size="small">
                            {{ getQcCheckStatus(row.qcChecks, item.key).label }}
                          </el-tag>
                        </div>
                      </div>
                    </div>
                  </div>
                </el-col>
              </el-row>

              <!-- 质控问题 -->
              <div v-if="row.issues.length" class="expand-section issues-section">
                <div class="expand-section-title">
                  <el-icon><WarningFilled /></el-icon> 质控问题
                  <el-tag :type="row.issues.some(i => i.severity === 'critical' || i.severity === 'error') ? 'danger' : 'warning'" size="small">
                    {{ row.issues.length }} 项
                  </el-tag>
                </div>
                <div class="issue-list">
                  <div v-for="(issue, i) in row.issues" :key="i" class="issue-card">
                    <div class="issue-title-row">
                      <el-tag :type="getSeverityInfo(issue.severity).type" size="small" effect="dark">
                        <el-icon style="margin-right: 4px"><component :is="getSeverityInfo(issue.severity).icon" /></el-icon>
                        {{ getSeverityInfo(issue.severity).label }}
                      </el-tag>
                      <span class="issue-rule">{{ issue.rule }}</span>
                    </div>
                    <div class="issue-detail">{{ issue.detail }}</div>
                  </div>
                </div>
              </div>
            </div>
          </template>
        </el-table-column>

        <el-table-column prop="id" label="报告编号" width="160" show-overflow-tooltip fixed />
        <el-table-column label="患者" width="110">
          <template #default="{ row }">
            <span style="font-weight: 500">{{ row.patientName }}</span>
            <span style="color: var(--text-muted); font-size: 12px; margin-left: 4px">{{ row.patientAge }}岁/{{ row.patientSex }}</span>
          </template>
        </el-table-column>
        <el-table-column label="模态" width="70" align="center">
          <template #default="{ row }">
            <el-tag :type="row.modality === 'CT' ? 'primary' : row.modality === 'MR' ? 'success' : 'info'" size="small" effect="plain">
              {{ row.modality }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="bodyPart" label="检查部位" min-width="100" show-overflow-tooltip />
        <el-table-column prop="accession" label="检查号" width="130" show-overflow-tooltip />
        <el-table-column prop="studyDate" label="检查日期" width="110" />
        <el-table-column label="质控得分" width="100" align="center">
          <template #default="{ row }">
            <div class="score-cell">
              <el-progress
                type="circle"
                :percentage="row.score"
                :stroke-width="6"
                :width="44"
                :color="getScoreColor(row.score)"
              />
            </div>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="120" align="center">
          <template #default="{ row }">
            <div style="display: flex; flex-direction: column; gap: 2px; align-items: center">
              <el-tag v-if="getPriorityTag(row.priority)" :type="getPriorityTag(row.priority).type" size="small" effect="plain">
                {{ getPriorityTag(row.priority).label }}
              </el-tag>
              <el-tag :type="getStatusTag(row.status).type" size="small">
                {{ getStatusTag(row.status).label }}
              </el-tag>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="100" align="center" fixed="right">
          <template #default="{ row }">
            <el-button type="primary" size="small" text @click.stop="viewReport(row.id)">
              审核
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- 统计卡片 + 高频问题 -->
    <el-row :gutter="16" class="bottom-section">
      <el-col :xs="24" :lg="16">
        <div class="stats-row-compact">
          <el-card v-for="card in statsCards" :key="card.label" shadow="never" class="stat-card-compact">
            <div class="stat-compact-content">
              <div class="stat-compact-label">{{ card.label }}</div>
              <div class="stat-compact-value" :style="{ color: card.color }">
                {{ card.value }}<span v-if="card.suffix" class="stat-suffix">{{ card.suffix }}</span>
              </div>
              <div class="stat-compact-sub">{{ card.sub }}</div>
            </div>
          </el-card>
        </div>
      </el-col>

      <el-col :xs="24" :lg="8">
        <el-card shadow="never" class="content-card">
          <template #header>
            <div class="card-header">
              <span class="card-title">高频问题 TOP5</span>
            </div>
          </template>
          <div class="issue-list">
            <div v-for="(issue, i) in (stats?.commonIssues || [])" :key="issue.rule" class="issue-item">
              <div class="issue-rank">{{ i + 1 }}</div>
              <div class="issue-info">
                <div class="issue-rule">{{ issue.rule }}</div>
                <div class="issue-count">出现 {{ issue.count }} 次</div>
              </div>
              <el-progress :percentage="Math.round(issue.count / (stats?.commonIssues?.[0]?.count || 1) * 100)" :stroke-width="6" :show-text="false" />
            </div>
          </div>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<style scoped>
.dashboard {
  max-width: 1400px;
}

.page-header {
  margin-bottom: 16px;
}

.page-title {
  font-size: 26px;
  font-weight: 600;
  color: var(--text-primary);
}

.page-subtitle {
  font-size: 14px;
  color: var(--text-muted);
  margin-top: 4px;
}

.main-card {
  margin-bottom: 16px;
}

.card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.card-title {
  font-size: 15px;
  font-weight: 600;
  color: var(--text-primary);
  display: flex;
  align-items: center;
  gap: 8px;
}

/* 展开行 */
.expanded-content {
  padding: 16px 20px;
  background: var(--bg-primary);
  border-top: 1px solid var(--border-color);
}

.expand-section {
  margin-bottom: 16px;
}

.expand-section:last-child {
  margin-bottom: 0;
}

.expand-section-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
  margin-bottom: 10px;
  display: flex;
  align-items: center;
  gap: 6px;
}

.desc-text, .diag-text {
  font-size: 14px;
  line-height: 1.8;
  color: var(--text-primary);
  white-space: pre-wrap;
  padding: 12px;
  background: var(--bg-secondary);
  border-radius: 6px;
  border: 1px solid var(--border-color);
}

.diag-text {
  color: var(--accent-light);
  font-weight: 500;
}

/* 质控检查项 */
.qc-group {
  margin-bottom: 12px;
}

.qc-group:last-child {
  margin-bottom: 0;
}

.qc-group-title {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-secondary);
  margin-bottom: 8px;
  padding-left: 4px;
}

.qc-items {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.qc-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 6px 12px;
  background: var(--bg-secondary);
  border-radius: 6px;
  border: 1px solid var(--border-color);
}

.qc-label {
  font-size: 13px;
  color: var(--text-primary);
}

/* 质控问题 */
.issues-section {
  margin-top: 16px;
  padding-top: 16px;
  border-top: 1px solid var(--border-color);
}

.issue-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.issue-card {
  background: var(--bg-secondary);
  border: 1px solid var(--border-color);
  border-radius: 6px;
  padding: 12px;
}

.issue-title-row {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 6px;
}

.issue-rule {
  font-size: 14px;
  font-weight: 500;
  color: var(--text-primary);
}

.issue-detail {
  font-size: 13px;
  color: var(--text-secondary);
  line-height: 1.6;
  padding-left: 24px;
}

.score-cell {
  display: flex;
  align-items: center;
  justify-content: center;
}

/* 底部区域 */
.bottom-section {
  margin-top: 0;
}

/* 紧凑统计卡片 */
.stats-row-compact {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 12px;
}

.stat-card-compact {
  cursor: default;
}

.stat-compact-content {
  text-align: center;
  padding: 4px 0;
}

.stat-compact-label {
  font-size: 12px;
  color: var(--text-muted);
  margin-bottom: 4px;
}

.stat-compact-value {
  font-size: 22px;
  font-weight: 700;
  line-height: 1.2;
}

.stat-compact-sub {
  font-size: 11px;
  color: var(--text-muted);
  margin-top: 2px;
}

.content-card {
  margin-bottom: 16px;
}

.issue-list {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.issue-item {
  display: flex;
  align-items: center;
  gap: 12px;
}

.issue-rank {
  width: 24px;
  height: 24px;
  border-radius: 6px;
  background: var(--bg-tertiary);
  color: var(--text-secondary);
  font-size: 12px;
  font-weight: 600;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.issue-info {
  flex: 1;
  min-width: 0;
}

.issue-rule {
  font-size: 13px;
  color: var(--text-primary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.issue-count {
  font-size: 12px;
  color: var(--text-muted);
  margin-top: 2px;
}
</style>
