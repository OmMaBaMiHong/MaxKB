<template>
  <div class="graph-page">
    <div class="graph-header">
      <h4>知识图谱</h4>
      <span class="graph-kb">{{ knowledgeName }}</span>
      <el-button type="primary" :loading="building" @click="build">重新生成图谱</el-button>
      <span v-if="stats" class="graph-stats">节点 {{ stats.nodes }} · 关系 {{ stats.edges }}</span>
    </div>
    <div class="graph-legend">
      <span v-for="(color, type) in typeColors" :key="type" class="legend-item">
        <span class="legend-dot" :style="{ background: color }" />{{ type }}
      </span>
      <span class="graph-tip">滚轮缩放 · 拖拽移动 · 点节点看详情</span>
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
import { useRoute } from 'vue-router'
import cytoscape from 'cytoscape'
import { buildKnowledgeGraph, getKnowledgeGraph } from '@/api/graph'
import knowledgeApi from '@/api/knowledge/knowledge'

const route = useRoute()
const knowledgeId = route.params.id as string
const container = ref<HTMLDivElement>()
const knowledgeName = ref('')
const loading = ref(false)
const building = ref(false)
const selected = ref<any>(null)
const stats = ref<{ nodes: number; edges: number } | null>(null)
let cy: any = null

const typeColors: Record<string, string> = {
  人物: '#E8A33D',
  Character: '#E8A33D',
  组织: '#5FA8B8',
  Organization: '#5FA8B8',
  地点: '#7BC496',
  Location: '#7BC496',
  器物: '#C97BA0',
  Artifact: '#C97BA0',
  概念: '#8F8AE8',
  Concept: '#8F8AE8',
  事件: '#D97070',
  Event: '#D97070',
  规则: '#66B8CB',
  Rule: '#66B8CB',
  Creature: '#B5A642',
  Resource: '#9AA7B5',
  其他: '#9AA7B5',
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
          width: (ele: any) => 22 + Math.min(ele.data('mentions') || 1, 10) * 3,
          height: (ele: any) => 22 + Math.min(ele.data('mentions') || 1, 10) * 3,
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
  loading.value = true
  try {
    const detail: any = await knowledgeApi.getKnowledgeDetail(knowledgeId)
    knowledgeName.value = detail?.data?.name || detail?.name || ''
    const res: any = await getKnowledgeGraph(knowledgeId, 400)
    const data = res?.data || { nodes: [], edges: [] }
    stats.value = { nodes: data.nodes.length, edges: data.edges.length }
    await nextTick()
    render(data)
  } finally {
    loading.value = false
  }
}

const build = async () => {
  building.value = true
  try {
    await buildKnowledgeGraph(knowledgeId, 40)
    await loadGraph()
  } finally {
    building.value = false
  }
}

onMounted(loadGraph)
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
    margin: 0;
  }
}
.graph-kb {
  color: var(--el-text-color-secondary);
  font-size: 13px;
  margin-right: 8px;
}
.graph-stats {
  color: var(--el-text-color-secondary);
  font-size: 13px;
}
.graph-legend {
  display: flex;
  gap: 14px;
  margin: 8px 0;
  align-items: center;
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
  .graph-tip {
    margin-left: auto;
    font-size: 12px;
    color: var(--el-text-color-secondary);
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
