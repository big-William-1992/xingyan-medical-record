<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { fetchReport, fetchQcItems, fetchSeverityMap, updateReport as apiUpdateReport } from '../api/index.js'

const route = useRoute()
const router = useRouter()

const report = ref(null)
const qcResults = ref({})
const reviewComment = ref('')
const qcItems = ref([])
const severityMap = ref({})

async function loadReport() {
  const id = route.query.id
  if (!id) {
    ElMessage.error('缺少报告 ID')
    router.push('/review')
    return
  }
  try {
    const [reportData, qcData, severityData] = await Promise.all([
      fetchReport(id),
      fetchQcItems(),
      fetchSeverityMap(),
    ])
    report.value = reportData
    qcResults.value = { ...(reportData.qcChecks || {}) }
    reviewComment.value = reportData.reviewComment || ''
    qcItems.value = qcData
    severityMap.value = severityData
  } catch (e) {
    ElMessage.error('加载报告失败：' + e.message)
    router.push('/review')
  }
}

onMounted(loadReport)

function goBack() {
  router.push('/review')
}

async function approve() {
  if (!report.value) return
  try {
    const updated = await apiUpdateReport(report.value.id, {
      status: 'passed',
      reviewer: '张医生',
      reviewComment: reviewComment.value,
    })
    report.value = updated
    ElMessage.success('已通过审核')
  } catch (e) {
    ElMessage.error('操作失败：' + e.message)
  }
}

async function reject() {
  if (!report.value) return
  try {
    const updated = await apiUpdateReport(report.value.id, {
      status: 'rejected',
      reviewer: '张医生',
      reviewComment: reviewComment.value,
    })
    report.value = updated
    ElMessage.warning('已打回修改')
  } catch (e) {
    ElMessage.error('操作失败：' + e.message)
  }
}

function getSeverityInfo(severity) {
  return severityMap.value[severity] || severityMap.value['info'] || { label: severity, type: 'info', icon: 'InfoFilled' }
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

function getQcPassRate() {
  if (!report.value?.qcChecks) return 0
  const checks = report.value.qcChecks
  const total = Object.values(checks).filter(v => v !== null).length
  const passed = Object.values(checks).filter(v => v === true).length
  return total > 0 ? Math.round(passed / total * 100) : 0
}

const sexLabel = { '男': 'male', '女': 'female' }
</script>

<template>
  <div v-if="report" class="detail-page">
    <!-- 顶部导航 -->
    <div class="top-bar">
      <el-button @click="goBack" plain size="default">
        <el-icon><ArrowLeft /></el-icon> 返回列表
      </el-button>
      <div class="top-actions">
        <el-button @click="reject" type="danger" plain>打回修改</el-button>
        <el-button @click="approve" type="primary">通过审核</el-button>
      </div>
    </div>

    <el-row :gutter="16">
      <!-- 左侧：患者信息 + 影像描述 + 影像诊断 + 质控检查 -->
      <el-col :xs="24" :lg="12">
        <!-- 患者基本信息 -->
        <el-card shadow="never" class="info-card">
          <template #header>
            <div class="card-header">
              <el-icon><User /></el-icon>
              <span class="card-title">患者基本信息</span>
            </div>
          </template>
          <el-descriptions :column="2" border size="small">
            <el-descriptions-item label="姓名">{{ report.patientName }}</el-descriptions-item>
            <el-descriptions-item label="性别">
              <el-tag :type="report.patientSex === '男' ? 'primary' : 'danger'" size="small">{{ report.patientSex }}</el-tag>
            </el-descriptions-item>
            <el-descriptions-item label="年龄">{{ report.patientAge }} 岁</el-descriptions-item>
            <el-descriptions-item label="患者 ID">{{ report.patientId }}</el-descriptions-item>
            <el-descriptions-item label="检查模态">{{ report.modality }}</el-descriptions-item>
            <el-descriptions-item label="检查部位">{{ report.bodyPart }}</el-descriptions-item>
            <el-descriptions-item label="检查号">{{ report.accession }}</el-descriptions-item>
            <el-descriptions-item label="检查日期">{{ report.studyDate }}</el-descriptions-item>
            <el-descriptions-item label="报告日期">{{ report.reportDate }}</el-descriptions-item>
            <el-descriptions-item label="质控得分">
              <span :style="{ color: report.score >= 85 ? '#10b981' : report.score >= 70 ? '#f59e0b' : '#ef4444', fontWeight: 600 }">
                {{ report.score }} 分
              </span>
            </el-descriptions-item>
          </el-descriptions>
        </el-card>

        <!-- 影像描述 -->
        <el-card shadow="never" class="content-card desc-card">
          <template #header>
            <div class="card-header">
              <el-icon><Document /></el-icon>
              <span class="card-title">影像描述</span>
            </div>
          </template>
          <div class="desc-text">{{ report.description }}</div>
        </el-card>

        <!-- 影像诊断 -->
        <el-card shadow="never" class="content-card diag-card">
          <template #header>
            <div class="card-header">
              <el-icon><Stamp /></el-icon>
              <span class="card-title">影像诊断</span>
            </div>
          </template>
          <div class="diag-text">{{ report.diagnosis }}</div>
        </el-card>

        <!-- 质控检查项 -->
        <el-card shadow="never" class="content-card qc-card">
          <template #header>
            <div class="card-header">
              <el-icon><List /></el-icon>
              <span class="card-title">质控检查</span>
              <el-progress
                :percentage="getQcPassRate()"
                :stroke-width="8"
                :width="80"
                type="circle"
                :color="getQcPassRate() >= 80 ? '#10b981' : getQcPassRate() >= 60 ? '#f59e0b' : '#ef4444'"
              />
            </div>
          </template>
          <div v-for="(items, groupName) in qcGroups" :key="groupName" class="qc-group">
            <div class="qc-group-title">{{ groupName }}</div>
            <div class="qc-items">
              <div v-for="item in items" :key="item.key" class="qc-item">
                <span class="qc-label">{{ item.label }}</span>
                <el-radio-group v-model="qcResults[item.key]" size="small">
                  <el-radio-button label="pass" type="success">通过</el-radio-button>
                  <el-radio-button label="fail" type="danger">不通过</el-radio-button>
                  <el-radio-button label="null" type="info">不适用</el-radio-button>
                </el-radio-group>
              </div>
            </div>
          </div>
        </el-card>
      </el-col>

      <!-- 右侧：质控问题 + 审核意见 -->
      <el-col :xs="24" :lg="12">
        <!-- 质控问题 -->
        <el-card shadow="never" class="content-card issues-card">
          <template #header>
            <div class="card-header">
              <el-icon><WarningFilled /></el-icon>
              <span class="card-title">
                质控问题
                <el-tag v-if="report.issues.length" :type="report.issues.some(i => i.severity === 'critical' || i.severity === 'error') ? 'danger' : 'warning'" size="small">
                  {{ report.issues.length }} 项
                </el-tag>
                <span v-else class="no-issues">无问题</span>
              </span>
            </div>
          </template>

          <div v-if="report.issues.length === 0" class="empty-issues">
            <el-icon :size="48" color="#10b981"><CircleCheckFilled /></el-icon>
            <p>该报告未发现质控问题</p>
          </div>

          <div v-else class="issue-list">
            <div v-for="(issue, i) in report.issues" :key="i" class="issue-card">
              <div class="issue-header">
                <div class="issue-title-row">
                  <el-tag :type="getSeverityInfo(issue.severity).type" size="small" effect="dark">
                    <el-icon style="margin-right: 4px"><component :is="getSeverityInfo(issue.severity).icon" /></el-icon>
                    {{ getSeverityInfo(issue.severity).label }}
                  </el-tag>
                  <span class="issue-rule">{{ issue.rule }}</span>
                </div>
              </div>
              <div class="issue-detail">{{ issue.detail }}</div>
            </div>
          </div>
        </el-card>

        <!-- 审核意见 -->
        <el-card shadow="never" class="content-card comment-card">
          <template #header>
            <div class="card-header">
              <el-icon><EditPen /></el-icon>
              <span class="card-title">审核意见</span>
            </div>
          </template>
          <el-input
            v-model="reviewComment"
            type="textarea"
            :rows="6"
            placeholder="请输入审核意见（选填）"
            maxlength="500"
            show-word-limit
          />
        </el-card>

        <!-- 审核记录 -->
        <el-card shadow="never" class="content-card history-card">
          <template #header>
            <div class="card-header">
              <el-icon><Clock /></el-icon>
              <span class="card-title">审核记录</span>
            </div>
          </template>
          <el-timeline>
            <el-timeline-item
              v-if="report.reviewer"
              type="primary"
              :timestamp="report.reportDate"
              placement="top"
            >
              <div class="history-item">
                <span class="history-reviewer">{{ report.reviewer }}</span>
                <span class="history-action" :class="'history-' + report.status">
                  {{ report.status === 'passed' ? '通过审核' : '打回修改' }}
                </span>
              </div>
              <div v-if="report.reviewComment" class="history-comment">{{ report.reviewComment }}</div>
            </el-timeline-item>
            <el-timeline-item type="gray" :timestamp="report.reportDate" placement="top">
              <div class="history-item">
                <span class="history-reviewer">系统</span>
                <span class="history-action history-auto">AI 质控初筛</span>
              </div>
              <div class="history-comment">发现 {{ report.issues.length }} 项问题，得分 {{ report.score }} 分</div>
            </el-timeline-item>
          </el-timeline>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<style scoped>
.detail-page {
  max-width: 1400px;
}

.top-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 16px;
}

.top-actions {
  display: flex;
  gap: 8px;
}

.info-card, .content-card {
  margin-bottom: 16px;
}

.card-header {
  display: flex;
  align-items: center;
  gap: 8px;
}

.card-title {
  font-size: 15px;
  font-weight: 600;
  color: var(--text-primary);
}

/* 影像描述 */
.desc-text, .diag-text {
  font-size: 14px;
  line-height: 1.8;
  color: var(--text-primary);
  white-space: pre-wrap;
}

.diag-text {
  color: var(--accent-light);
  font-weight: 500;
}

/* 质控检查项 */
.qc-group {
  margin-bottom: 16px;
}

.qc-group:last-child {
  margin-bottom: 0;
}

.qc-group-title {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-secondary);
  margin-bottom: 10px;
  padding-left: 4px;
}

.qc-items {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.qc-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8px 12px;
  background: var(--bg-tertiary);
  border-radius: 6px;
}

.qc-label {
  font-size: 13px;
  color: var(--text-primary);
}

/* 审核意见 */
.comment-card {
  margin-bottom: 16px;
}

/* 审核记录 */
.history-item {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 4px;
}

.history-reviewer {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-primary);
}

.history-action {
  font-size: 12px;
  padding: 2px 8px;
  border-radius: 4px;
}

.history-pass {
  background: rgba(16, 185, 129, 0.1);
  color: #10b981;
}

.history-reject {
  background: rgba(239, 68, 68, 0.1);
  color: #ef4444;
}

.history-auto {
  background: rgba(59, 130, 246, 0.1);
  color: #60a5fa;
}

.history-comment {
  font-size: 12px;
  color: var(--text-muted);
  margin-top: 4px;
}

.empty-issues {
  text-align: center;
  padding: 48px 0;
  color: var(--text-muted);
}

.empty-issues p {
  margin-top: 12px;
  font-size: 14px;
}

.issue-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.issue-card {
  background: var(--bg-tertiary);
  border: 1px solid var(--border-color);
  border-radius: 8px;
  padding: 16px;
}

.issue-header {
  margin-bottom: 8px;
}

.issue-title-row {
  display: flex;
  align-items: center;
  gap: 10px;
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
  padding-left: 4px;
}

.no-issues {
  font-size: 14px;
  color: var(--success);
  margin-left: 8px;
}
</style>
