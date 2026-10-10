<template>
  <div class="graph-page">
    <div class="graph-header">
      <h4>知识图谱</h4>
      <el-select v-model="knowledgeId" filterable placeholder="选择知识库" style="width: 280px" @change="loadGraph">
        <el-option v-for="k in knowledgeList" :key="k.id" :label="k.name" :value="k.id" />
      </el-select>
      <el-button type="primary" :loading="building" :disabled="!knowledgeId" @click="build">
        生成图谱（抽取实体/关系）
      </el-button>
      <span v-if="stats" class="graph-stats">节点 {{ stats.nodes }} · 关系 {{ stats.edges }}</span>
    </div>
    <div class="graph-legend">
      <span v-for="(color, type) in typeColors" :key="type" class="legend-item">
        <span class="legend-dot" :style="{ background: color }" />{{ type }}
      </span>
    </div>
    <div ref="container" class="graph-canvas" v-loading="loading" element-loading-text="图谱加载中" />
    <div v-if="selected" class="graph-detail">
      <h5>{{ selected.name }} <el-tag size="small">{{ selected.type }}</el-tag></h5>
      <p>{{ selected.description || '（无描述）' }}</p>
      <p class="graph-meta">提及 {{ selected.mentions }} 次 · 关联段落 {{ (selected.sources || []).length }}</p>
    </div>
  </div>
</template>

<script setup lang="ts">
import { nextTick, onBeforeUnmount, onMounted, ref } from 'vue'
import cytoscape from 'cytoscape'
import { buildKnowledgeGraph, getKnowledgeGraph } from '@/api/graph'
import knowledgeApi from '@/api/knowledge/knowledge'

const container = ref<HTMLDivElement>()
const knowledgeId = ref('')
const knowledgeList = ref<any[]>([])
const loading = ref(false)
const building = ref(false)
const selected = ref<any>(null)
const stats = ref<{ nodes: number; edges: number } | null>(null)
let cy: any = null

// 实体类型配色（混沌海主题：深海+暖金）
const typeColors: Record<string, string> = {
  人物: '#E8A33D',
  组织: '#5FA8B8',
  地点: '#7BC496',
  器物: '#C97BA0',
  概念: '#8F8AE8',
  事件: '#D97070',
  规则: '#66B8CB',
  其他: '#9AA7B5',
}

const loadList = async () => {
  const res: any = await knowledgeApi.getKnowledgeList?.() ?? []
  knowledgeList.value = Array.isArray(res) ? res : res?.data || []
  if (knowledgeId.value === '' && knowledgeList.value.length > 0) {
    knowledgeId.value = knowledgeList.value[0].id
  }
}

const render = (data: { nodes: any[]; edges: any[] }) => {
  if (cy) {
    cy.destroy()
    cy = null
  }
  if (!container.value) return
  const elements = [
    ...data.nodes.map((n: any) => ({
      data: {
        id: n.id,
        label: n.name,
        type: n.type || '其他',
        description: n.description,
        mentions: n.mentions,
        sources: n.sources,
      },
    })),
    ...data.edges.map((e: any) => ({
      data: { id: `${e.source}->${e.target}->${e.relation}`, source: e.source, target: e.target, label: e.relation },
    })),
  ]
  cy = cytoscape({
    container: container.value,
    elements,
    style: [
      {
        selector: 'node',
        style: {
          label: 'data(label)',
          'background-color': (ele: any) => typeColors[ele.data('type')] || typeColors['其他'],
          'font-size': 12,
          color: '#1f2d3d',
          'text-valign': 'bottom',
          'text-margin-y': 6,
          width: (ele: any) => 24 + Math.min(ele.data('mentions') || 1, 8) * 4,
          height: (ele: any) => 24 + Math.min(ele.data('mentions') || 1, 8) * 4,
          'border-width': 2,
          'border-color': '#ffffff',
        },
      },
      {
        selector: 'edge',
        style: {
          label: 'data(label)',
          'font-size': 9,
          color: '#7f8b99',
          width: 1.5,
          'line-color': '#B9C4CE',
          'target-arrow-color': '#B9C4CE',
          'target-arrow-shape': 'triangle',
          'curve-style': 'bezier',
          'text-background-color': '#ffffff',
          'text-background-opacity': 0.85,
          'text-background-padding': 2,
        },
      },
    ],
    layout: { name: 'cose', animate: true, padding: 40, nodeOverlap: 30, idealEdgeLength: 90 },
    wheelSensitivity: 0.2,
  })
  cy.on('tap', 'node', (evt: any) => {
    selected.value = evt.target.data()
  })
  cy.on('tap', (evt: any) => {
    if (evt.target === cy) selected.value = null
  })
}

const loadGraph = async () => {
  if (!knowledgeId.value) return
  loading.value = true
  try {
    const res: any = await getKnowledgeGraph(knowledgeId.value)
    const data = res?.data || { nodes: [], edges: [] }
    stats.value = { nodes: data.nodes.length, edges: data.edges.length }
    await nextTick()
    render(data)
  } finally {
    loading.value = false
  }
}

const build = async () => {
  if (!knowledgeId.value) return
  building.value = true
  try {
    await buildKnowledgeGraph(knowledgeId.value, 40)
    await loadGraph()
  } finally {
    building.value = false
  }
}

onMounted(async () => {
  await loadList()
  await loadGraph()
})
onBeforeUnmount(() => {
  if (cy) cy.destroy()
})
</script>

<style lang="scss" scoped>
.graph-page {
  display: flex;
  flex-direction: column;
  height: calc(100vh - 56px);
  padding: 16px;
  background: var(--el-bg-color);
}
.graph-header {
  display: flex;
  gap: 12px;
  align-items: center;
  h4 {
    margin: 0 8px 0 0;
  }
}
.graph-stats {
  color: var(--el-text-color-secondary);
  font-size: 13px;
}
.graph-legend {
  display: flex;
  gap: 14px;
  margin: 8px 0;
  .legend-item {
    display: inline-flex;
    gap: 4px;
    align-items: center;
    font-size: 12px;
    color: var(--el-text-color-regular);
  }
  .legend-dot {
    width: 10px;
    height: 10px;
    border-radius: 50%;
  }
}
.graph-canvas {
  flex: 1;
  min-height: 400px;
  border: 1px solid var(--el-border-color-light);
  border-radius: 8px;
  background: #fafbfd;
}
.graph-detail {
  margin-top: 8px;
  padding: 10px 14px;
  border: 1px solid var(--el-border-color-light);
  border-radius: 8px;
  h5 {
    margin: 0 0 4px;
    display: flex;
    gap: 8px;
    align-items: center;
  }
  p {
    margin: 0 0 2px;
    font-size: 13px;
    color: var(--el-text-color-regular);
  }
  .graph-meta {
    color: var(--el-text-color-secondary);
    font-size: 12px;
  }
}
</style>
