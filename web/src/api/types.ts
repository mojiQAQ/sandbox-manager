/* TypeScript 类型定义 - 对应后端 schemas.py */

// --- 通用 ---

export interface ApiResponse {
  success: boolean
  message: string
  data?: Record<string, unknown> | unknown[] | null
}

export interface ErrorResponse {
  success: boolean
  message: string
  detail?: string | null
}

// --- 模板 ---

export interface TemplateListItem {
  id: string
  name: string
  description: string
  status: 'unbuilt' | 'building' | 'ready' | 'failed'
  source: 'builtin' | 'custom' | 'snapshot'
  connect_type: string
  docker_image: string
  size_bytes: number | null
  created_at: string
  updated_at: string
}

export interface TemplateDetail extends TemplateListItem {
  base_image: string
  docker_image_id: string | null
  entrypoint: string[]
  env: Record<string, string>
  ports: Record<string, number>
  install_commands: string[]
  connect_port: number | null
  build_error: string | null
}

export interface TemplateBuildStatus {
  name: string
  status: string
  build_error: string | null
}

// --- 沙盒 ---

export interface CreateSandboxRequest {
  template_name?: string | null
  image?: string | null
  name?: string | null
  env?: Record<string, string>
}

export interface SandboxListItem {
  id: string
  name: string | null
  template_name: string | null
  status: 'running' | 'paused' | 'stopped'
  image: string
  created_at: string
  connect_type: string | null
  docker_container_name: string
}

export interface SandboxDetail extends SandboxListItem {
  template_id: string | null
}

export interface ConnectInfo {
  connect_type: string
  sandbox_id: string
  container_name: string
  status: string
  command?: string | null
  url?: string | null
  port?: number | null
  ports?: Array<Record<string, unknown>> | null
  message?: string | null
}

export interface BatchDeleteResponse {
  success: boolean
  total: number
  deleted: number
  failed: number
  message: string
}

export interface SaveTemplateRequest {
  name: string
  description?: string
  connect_type?: string | null
  entrypoint?: string[] | null
}

// --- 系统状态 ---

export interface HealthResponse {
  status: string
  version: string
  opensandbox_connected: boolean
  database_ok: boolean
}

export interface SystemStatus {
  api_running: boolean
  opensandbox_connected: boolean
  active_sandboxes: number
  built_templates: number
  total_templates: number
}
