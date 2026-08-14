<script setup>
import { ref, computed, onMounted, nextTick } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import gsap from 'gsap'
import { fetchReports } from '../api/index.js'

const router = useRouter()

const reports = ref([])
const searchQuery = ref('')
const filterModality = ref('')
const filterStatus = ref('')
const currentPage = ref(1)
const pageSize = 10

const modalities = computed(() => {
  const set = new Set(reports.value.map(r => r.modality))
  return [...set].sort()
})

const statusOptions = [
  { label: '待审核', value: 'pending' },
  { label: '已通过', value: 'passed' },
  { label: '已打回', value: 'rejected' },
]

const filteredReports = computed(() => {
  return reports.value.filter(r => {
    const q = searchQuery.value.toLowerCase()
    const matchQ = !q ||
      r.patientName.includes(q) ||
      r.accession.toLowerCase().includes(q) ||
      r.id.toLowerCase().includes(q) ||
      r.bodyPart.includes(q)
    const matchMod = !filterModality.value || r.modality === filterModality.value
    const matchStatus = !filterStatus.value || r.status === filterStatus.value
    return matchQ && matchMod && matchStatus
  })
})

const paginatedReports = computed(() => {
  const start = (currentPage.value - 1) * pageSize
  return filteredReports.value.slice(start, start + pageSize)
})

const totalFiltered = computed(() => filteredReports.value.length)

function viewReport(id) {
  router.push(`/report?id=${id}`)
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

function getScoreColor(score) {
  if (score >= 85) return '#10b981'
  if (score >= 70) return '#f59e0b'
  return '#ef4444'
}

async function loadReports() {
  try {
    reports.value = await fetchReports()
  } catch (e) {
    ElMessage.error('加载报告失败：' + e.message)
  }
}

onMounted(async () => {
  await loadReports()
  nextTick(() => {
    gsap.fromTo('.filter-card', { opacity: 0, y: 15 }, { opacity: 1, y: 0, duration: 0.4, ease: 'power2.out' })
    gsap.fromTo('.list-card', { opacity: 0, y: 15 }, { opacity: 1, y: 0, duration: 0.4, ease: 'power2.out', delay: 0.15 })
    gsap.fromTo('.el-table__body-wrapper .el-table__row',
      { opacity: 0, x: -10 },
      { opacity: 1, x: 0, duration: 0.35, stagger: 0.05, ease: 'power2.out', delay: 0.3 }
    )
  })
})
</script>

<template>
  <div class="review-page">
    <div class="page-header">
      <h1 class="page-title">报告审核</h1>
      <p class="page-subtitle">{{ totalFiltered }} 份报告</p>
    </div>

    <!-- 筛选栏 -->
    <el-card shadow="never" class="filter-card">
      <el-row :gutter="12" align="middle">
        <el-col :xs="24" :sm="12" :md="8" :lg="6">
          <el-input
            v-model="searchQuery"
            placeholder="搜索患者/检查号/报告编号"
            clearable
            prefix-icon="Search"
          />
        </el-col>
        <el-col :xs="12" :sm="6" :md="4" :lg="3">
          <el-select v-model="filterModality" placeholder="模态" clearable style="width: 100%">
            <el-option v-for="m in modalities" :key="m" :label="m" :value="m" />
          </el-select>
        </el-col>
        <el-col :xs="12" :sm="6" :md="4" :lg="3">
          <el-select v-model="filterStatus" placeholder="状态" clearable style="width: 100%">
            <el-option v-for="s in statusOptions" :key="s.value" :label="s.label" :value="s.value" />
          </el-select>
        </el-col>
        <el-col :xs="24" :sm="24" :md="8" :lg="12" style="text-align: right">
          <el-button type="primary" @click="currentPage = 1">
            <el-icon><Search /></el-icon> 查询
          </el-button>
          <el-button @click="searchQuery = ''; filterModality = ''; filterStatus = ''; currentPage = 1">
            重置
          </el-button>
        </el-col>
      </el-row>
    </el-card>

    <!-- 报告列表 -->
    <el-card shadow="never" class="list-card">
      <el-table :data="paginatedReports" style="width: 100%" @row-click="viewReport">
        <el-table-column prop="id" label="报告编号" width="160" show-overflow-tooltip fixed />
        <el-table-column label="患者" width="100">
          <template #default="{ row }">
            <span style="font-weight: 500">{{ row.patientName }}</span>
          </template>
        </el-table-column>
        <el-table-column label="模态" width="70" align="center">
          <template #default="{ row }">
            <el-tag :type="row.modality === 'CT' ? 'primary' : row.modality === 'MR' ? 'success' : 'info'" size="small" effect="plain">
              {{ row.modality }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="bodyPart" label="检查部位" min-width="120" show-overflow-tooltip />
        <el-table-column prop="accession" label="检查号" width="130" show-overflow-tooltip />
        <el-table-column prop="studyDate" label="检查日期" width="110" />
        <el-table-column label="问题数" width="80" align="center">
          <template #default="{ row }">
            <span :style="{ color: row.issues.length > 0 ? '#ef4444' : '#10b981', fontWeight: 600 }">
              {{ row.issues.length }}
            </span>
          </template>
        </el-table-column>
        <el-table-column label="得分" width="90" align="center">
          <template #default="{ row }">
            <span :style="{ color: getScoreColor(row.score), fontWeight: 600 }">{{ row.score }}</span>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="100" align="center">
          <template #default="{ row }">
            <el-tag v-if="getPriorityTag(row.priority)" :type="getPriorityTag(row.priority).type" size="small" effect="plain" style="margin-right: 4px">
              {{ getPriorityTag(row.priority).label }}
            </el-tag>
            <el-tag :type="getStatusTag(row.status).type" size="small">
              {{ getStatusTag(row.status).label }}
            </el-tag>
          </template>
        </el-table-column>
      </el-table>

      <div class="pagination-wrap">
        <el-pagination
          v-model:current-page="currentPage"
          :page-size="pageSize"
          :total="totalFiltered"
          layout="total, prev, pager, next"
          background
        />
      </div>
    </el-card>
  </div>
</template>

<style scoped>
.review-page {
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

.filter-card {
  margin-bottom: 16px;
}

.list-card {
  margin-bottom: 16px;
}

.el-table :deep(td.el-table__cell) {
  cursor: pointer;
}

.el-table :deep(tr:hover > td.el-table__cell) {
  background: var(--bg-tertiary) !important;
}

.pagination-wrap {
  display: flex;
  justify-content: flex-end;
  padding-top: 16px;
}
</style>
