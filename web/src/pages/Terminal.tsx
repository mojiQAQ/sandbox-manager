import { useEffect, useRef, useState, useCallback } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { Button, Space, Tag, message, Typography } from 'antd'
import {
  DisconnectOutlined,
  ArrowLeftOutlined,
} from '@ant-design/icons'
import { Terminal as XTerm } from '@xterm/xterm'
import { FitAddon } from '@xterm/addon-fit'
import '@xterm/xterm/css/xterm.css'
import { getSandboxDetail } from '../api/sandboxes'
import StatusBadge from '../components/StatusBadge'
import type { SandboxDetail } from '../api/types'

const { Text } = Typography

export default function Terminal() {
  const { sandboxId } = useParams<{ sandboxId: string }>()
  const navigate = useNavigate()
  const termRef = useRef<HTMLDivElement>(null)
  const xtermRef = useRef<XTerm | null>(null)
  const wsRef = useRef<WebSocket | null>(null)
  const fitAddonRef = useRef<FitAddon | null>(null)
  const [sandbox, setSandbox] = useState<SandboxDetail | null>(null)
  const [connected, setConnected] = useState(false)

  // 获取沙盒信息
  useEffect(() => {
    if (!sandboxId) return
    getSandboxDetail(sandboxId)
      .then(setSandbox)
      .catch(() => message.error('获取沙盒信息失败'))
  }, [sandboxId])

  // 断开 WebSocket
  const disconnect = useCallback(() => {
    if (wsRef.current) {
      wsRef.current.close()
      wsRef.current = null
    }
    setConnected(false)
  }, [])

  // 初始化终端和 WebSocket
  useEffect(() => {
    if (!termRef.current || !sandboxId) return

    const term = new XTerm({
      theme: {
        background: '#000000',
        foreground: '#e5e7eb',
        cursor: '#06b6d4',
        cursorAccent: '#000000',
        selectionBackground: 'rgba(6, 182, 212, 0.3)',
        black: '#1e293b',
        red: '#ef4444',
        green: '#10b981',
        yellow: '#f59e0b',
        blue: '#3b82f6',
        magenta: '#8b5cf6',
        cyan: '#06b6d4',
        white: '#e5e7eb',
        brightBlack: '#6b7280',
        brightRed: '#f87171',
        brightGreen: '#34d399',
        brightYellow: '#fbbf24',
        brightBlue: '#60a5fa',
        brightMagenta: '#a78bfa',
        brightCyan: '#22d3ee',
        brightWhite: '#f9fafb',
      },
      fontFamily: '"JetBrains Mono", "Fira Code", "Cascadia Code", monospace',
      fontSize: 14,
      cursorBlink: true,
      cursorStyle: 'bar',
      scrollback: 5000,
    })

    const fitAddon = new FitAddon()
    term.loadAddon(fitAddon)
    term.open(termRef.current)

    // 等一帧后 fit，确保 DOM 已渲染
    requestAnimationFrame(() => {
      fitAddon.fit()
    })

    xtermRef.current = term
    fitAddonRef.current = fitAddon

    // WebSocket 连接
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const wsUrl = `${protocol}//${window.location.host}/api/v1/sandboxes/${sandboxId}/terminal`

    term.writeln('\x1b[36m--- Sandbox Terminal ---\x1b[0m')
    term.writeln(`\x1b[90m正在连接到沙盒 ${sandboxId.slice(0, 12)}...\x1b[0m`)
    term.writeln('')

    try {
      const ws = new WebSocket(wsUrl)
      ws.binaryType = 'arraybuffer'
      wsRef.current = ws

      ws.onopen = () => {
        setConnected(true)
        term.writeln('\x1b[32m已连接\x1b[0m')
        term.writeln('')
      }

      ws.onmessage = (event) => {
        if (event.data instanceof ArrayBuffer) {
          term.write(new Uint8Array(event.data))
        } else {
          term.write(event.data)
        }
      }

      ws.onclose = () => {
        setConnected(false)
        term.writeln('')
        term.writeln('\x1b[31m连接已断开\x1b[0m')
      }

      ws.onerror = () => {
        setConnected(false)
        term.writeln('\x1b[31m连接失败 — WebSocket 端点可能尚未启用\x1b[0m')
      }

      // 终端输入 -> WebSocket (以 binary 模式发送)
      const encoder = new TextEncoder()
      term.onData((data) => {
        if (ws.readyState === WebSocket.OPEN) {
          ws.send(encoder.encode(data))
        }
      })
    } catch {
      term.writeln('\x1b[31m无法创建 WebSocket 连接\x1b[0m')
    }

    // 窗口 resize 时重新 fit
    const handleResize = () => {
      fitAddon.fit()
    }
    window.addEventListener('resize', handleResize)

    return () => {
      window.removeEventListener('resize', handleResize)
      disconnect()
      term.dispose()
    }
  }, [sandboxId, disconnect])

  return (
    <div className="terminal-container" style={{ height: 'calc(100vh - 48px)', margin: -24 }}>
      {/* 顶栏 */}
      <div className="terminal-header">
        <Space>
          <Button
            type="text"
            icon={<ArrowLeftOutlined />}
            onClick={() => navigate('/sandboxes')}
            style={{ color: '#9ca3af' }}
          />
          <Text className="mono" style={{ color: '#06b6d4', fontSize: 13 }}>
            {sandboxId?.slice(0, 12)}
          </Text>
          {sandbox?.template_name && (
            <Tag
              style={{
                background: 'rgba(139, 92, 246, 0.1)',
                borderColor: 'rgba(139, 92, 246, 0.2)',
                color: '#8b5cf6',
                fontSize: 11,
              }}
            >
              {sandbox.template_name}
            </Tag>
          )}
          {sandbox && <StatusBadge status={sandbox.status} />}
          <span
            className="indicator-dot"
            style={{
              backgroundColor: connected ? '#10b981' : '#6b7280',
              boxShadow: connected ? '0 0 6px rgba(16,185,129,0.5)' : 'none',
            }}
          />
          <Text style={{ color: '#9ca3af', fontSize: 12 }}>
            {connected ? '已连接' : '未连接'}
          </Text>
        </Space>
        <Button
          size="small"
          icon={<DisconnectOutlined />}
          onClick={disconnect}
          disabled={!connected}
          danger
        >
          断开连接
        </Button>
      </div>

      {/* 终端区域 */}
      <div
        className="terminal-body"
        ref={termRef}
        style={{ flex: 1 }}
      />
    </div>
  )
}
