import { useEffect, useRef, useCallback } from 'react'

/**
 * 定时轮询 hook
 * @param callback 轮询回调函数
 * @param interval 轮询间隔（毫秒），传 null 暂停轮询
 * @param immediate 是否立即执行一次
 */
export default function usePolling(
  callback: () => void | Promise<void>,
  interval: number | null = 5000,
  immediate = true,
) {
  const savedCallback = useRef(callback)
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null)

  useEffect(() => {
    savedCallback.current = callback
  }, [callback])

  const tick = useCallback(async () => {
    try {
      await savedCallback.current()
    } catch (err) {
      console.error('[Polling]', err)
    }
  }, [])

  useEffect(() => {
    if (immediate) {
      tick()
    }

    if (interval !== null && interval > 0) {
      timerRef.current = setInterval(tick, interval)
    }

    return () => {
      if (timerRef.current) {
        clearInterval(timerRef.current)
        timerRef.current = null
      }
    }
  }, [interval, immediate, tick])
}
