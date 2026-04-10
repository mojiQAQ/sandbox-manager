import client from './client'
import type {
  TemplateListItem,
  TemplateDetail,
  TemplateBuildStatus,
  ApiResponse,
} from './types'

/** 获取模板列表 */
export async function getTemplates(): Promise<TemplateListItem[]> {
  const { data } = await client.get<TemplateListItem[]>('/templates')
  return data
}

/** 获取模板详情 */
export async function getTemplateDetail(name: string): Promise<TemplateDetail> {
  const { data } = await client.get<TemplateDetail>(`/templates/${encodeURIComponent(name)}`)
  return data
}

/** 构建模板 */
export async function buildTemplate(name: string): Promise<ApiResponse> {
  const { data } = await client.post<ApiResponse>(`/templates/${encodeURIComponent(name)}/build`)
  return data
}

/** 获取模板构建状态 */
export async function getTemplateBuildStatus(name: string): Promise<TemplateBuildStatus> {
  const { data } = await client.get<TemplateBuildStatus>(
    `/templates/${encodeURIComponent(name)}/build-status`,
  )
  return data
}

/** 删除模板 */
export async function deleteTemplate(name: string): Promise<ApiResponse> {
  const { data } = await client.delete<ApiResponse>(`/templates/${encodeURIComponent(name)}`)
  return data
}
