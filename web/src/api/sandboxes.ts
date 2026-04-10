import client from './client'
import type {
  SandboxListItem,
  SandboxDetail,
  ConnectInfo,
  CreateSandboxRequest,
  SaveTemplateRequest,
  ApiResponse,
  BatchDeleteResponse,
  HealthResponse,
  SystemStatus,
} from './types'

/** 获取沙盒列表 */
export async function getSandboxes(): Promise<SandboxListItem[]> {
  const { data } = await client.get<SandboxListItem[]>('/sandboxes')
  return data
}

/** 获取沙盒详情 */
export async function getSandboxDetail(id: string): Promise<SandboxDetail> {
  const { data } = await client.get<SandboxDetail>(`/sandboxes/${id}`)
  return data
}

/** 创建沙盒 */
export async function createSandbox(req: CreateSandboxRequest): Promise<SandboxDetail> {
  const { data } = await client.post<SandboxDetail>('/sandboxes', req)
  return data
}

/** 删除沙盒 */
export async function deleteSandbox(id: string): Promise<ApiResponse> {
  const { data } = await client.delete<ApiResponse>(`/sandboxes/${id}`)
  return data
}

/** 批量删除所有沙盒 */
export async function deleteAllSandboxes(): Promise<BatchDeleteResponse> {
  const { data } = await client.delete<BatchDeleteResponse>('/sandboxes?all=true')
  return data
}

/** 暂停沙盒 */
export async function pauseSandbox(id: string): Promise<ApiResponse> {
  const { data } = await client.post<ApiResponse>(`/sandboxes/${id}/pause`)
  return data
}

/** 恢复沙盒 */
export async function resumeSandbox(id: string): Promise<ApiResponse> {
  const { data } = await client.post<ApiResponse>(`/sandboxes/${id}/resume`)
  return data
}

/** 获取沙盒连接信息 */
export async function getConnectInfo(id: string): Promise<ConnectInfo> {
  const { data } = await client.get<ConnectInfo>(`/sandboxes/${id}/connect-info`)
  return data
}

/** 保存沙盒为模板（快照） */
export async function saveAsTemplate(
  id: string,
  req: SaveTemplateRequest,
): Promise<ApiResponse> {
  const { data } = await client.post<ApiResponse>(`/sandboxes/${id}/save-template`, req)
  return data
}

/** 健康检查 */
export async function getHealth(): Promise<HealthResponse> {
  const { data } = await client.get<HealthResponse>('/health')
  return data
}

/** 系统状态 */
export async function getSystemStatus(): Promise<SystemStatus> {
  const { data } = await client.get<SystemStatus>('/status')
  return data
}
