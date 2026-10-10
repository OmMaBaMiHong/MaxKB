import { Result } from '@/request/Result'
import { get, post } from '@/request/index'
import type { Ref } from 'vue'

/**
 * 混沌海知识图谱（M3）：管理端读图 / 触发抽取
 */
const prefix = '/knowledge'

/**
 * 读图：节点 + 边
 * @param knowledge_id 知识库id
 */
export const getKnowledgeGraph: (knowledge_id: string, limit_nodes?: number) => Promise<Result<Ref<any>>> = (
  knowledge_id,
  limit_nodes,
) => {
  return get(`${prefix}/${knowledge_id}/graph`, undefined, { limit_nodes: limit_nodes ?? 300 })
}

/**
 * 触发图谱抽取（同步，段落数受 limit 限制）
 */
export const buildKnowledgeGraph: (knowledge_id: string, limit?: number) => Promise<Result<Ref<any>>> = (
  knowledge_id,
  limit,
) => {
  return post(`${prefix}/${knowledge_id}/graph/build`, { limit: limit ?? 40 })
}
