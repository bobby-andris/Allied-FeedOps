import { describe, expect, it, vi } from 'vitest'
import {
  ChannelAdapterRegistry,
  createGoogleAdsAdapterStub,
  type ChannelAction,
  type ChannelAdapter,
  type ChannelHealthStatus,
} from '@/lib/intent/channel-adapter'

function createMockAdapter(overrides?: Partial<ChannelAdapter>): ChannelAdapter {
  return {
    channelId: 'microsoft_ads',
    capabilities: {
      supportsNegativeKeywords: true,
      supportsTroas: true,
      supportsTcpa: false,
      supportsTierLabels: false,
      supportsExperiments: false,
    },
    checkHealth: vi.fn().mockResolvedValue({
      channel: 'microsoft_ads',
      healthy: true,
      lastSyncAt: '2026-02-20T10:00:00Z',
      errorMessage: null,
    } satisfies ChannelHealthStatus),
    executeActions: vi.fn().mockResolvedValue([]),
    ...overrides,
  }
}

describe('ChannelAdapterRegistry', () => {
  it('registers and retrieves an adapter', () => {
    const registry = new ChannelAdapterRegistry()
    const adapter = createMockAdapter()
    registry.register(adapter)

    expect(registry.get('microsoft_ads')).toBe(adapter)
    expect(registry.listRegistered()).toEqual(['microsoft_ads'])
  })

  it('returns undefined for unregistered channel', () => {
    const registry = new ChannelAdapterRegistry()
    expect(registry.get('meta_ads')).toBeUndefined()
  })

  it('unregisters an adapter', () => {
    const registry = new ChannelAdapterRegistry()
    registry.register(createMockAdapter())
    expect(registry.unregister('microsoft_ads')).toBe(true)
    expect(registry.get('microsoft_ads')).toBeUndefined()
    expect(registry.listRegistered()).toEqual([])
  })

  it('lists multiple registered adapters', () => {
    const registry = new ChannelAdapterRegistry()
    registry.register(createGoogleAdsAdapterStub())
    registry.register(createMockAdapter())
    expect(registry.listRegistered()).toEqual(['google_ads', 'microsoft_ads'])
  })

  it('checks health across all adapters', async () => {
    const registry = new ChannelAdapterRegistry()
    registry.register(createGoogleAdsAdapterStub())
    registry.register(createMockAdapter())

    const results = await registry.checkAllHealth()
    expect(results).toHaveLength(2)
    expect(results.every((r) => r.healthy)).toBe(true)
  })

  it('handles health check failure gracefully', async () => {
    const registry = new ChannelAdapterRegistry()
    registry.register(
      createMockAdapter({
        checkHealth: vi.fn().mockRejectedValue(new Error('connection timeout')),
      })
    )

    const results = await registry.checkAllHealth()
    expect(results).toHaveLength(1)
    expect(results[0].healthy).toBe(false)
    expect(results[0].errorMessage).toBe('Health check threw an exception')
  })

  it('executes actions on a registered channel', async () => {
    const registry = new ChannelAdapterRegistry()
    const adapter = createMockAdapter({
      executeActions: vi.fn().mockResolvedValue([
        { success: true, actionType: 'add_negative', entityId: 'q1', errorMessage: null },
      ]),
    })
    registry.register(adapter)

    const actions: ChannelAction[] = [
      { actionType: 'add_negative', entityId: 'q1', parameters: { term: 'test' } },
    ]

    const results = await registry.executeOnChannel('microsoft_ads', actions, 'go')
    expect(results).toHaveLength(1)
    expect(results[0].success).toBe(true)
  })

  it('returns failure for unregistered channel execution', async () => {
    const registry = new ChannelAdapterRegistry()
    const actions: ChannelAction[] = [
      { actionType: 'add_negative', entityId: 'q1', parameters: {} },
    ]

    const results = await registry.executeOnChannel('meta_ads', actions, 'go')
    expect(results).toHaveLength(1)
    expect(results[0].success).toBe(false)
    expect(results[0].errorMessage).toContain('No adapter registered')
  })

  it('blocks execution when guardrail status is blocked', async () => {
    const registry = new ChannelAdapterRegistry()
    registry.register(createMockAdapter())

    const actions: ChannelAction[] = [
      { actionType: 'update_target', entityId: 'c1', parameters: { target: 3.5 } },
    ]

    const results = await registry.executeOnChannel('microsoft_ads', actions, 'blocked')
    expect(results).toHaveLength(1)
    expect(results[0].success).toBe(false)
    expect(results[0].errorMessage).toContain('blocked')
  })
})

describe('createGoogleAdsAdapterStub', () => {
  it('returns adapter with google_ads channel and full capabilities', () => {
    const adapter = createGoogleAdsAdapterStub()
    expect(adapter.channelId).toBe('google_ads')
    expect(adapter.capabilities.supportsNegativeKeywords).toBe(true)
    expect(adapter.capabilities.supportsTroas).toBe(true)
    expect(adapter.capabilities.supportsTcpa).toBe(true)
    expect(adapter.capabilities.supportsTierLabels).toBe(true)
    expect(adapter.capabilities.supportsExperiments).toBe(true)
  })

  it('reports healthy status', async () => {
    const adapter = createGoogleAdsAdapterStub()
    const health = await adapter.checkHealth()
    expect(health.healthy).toBe(true)
    expect(health.channel).toBe('google_ads')
  })

  it('stub executes actions successfully', async () => {
    const adapter = createGoogleAdsAdapterStub()
    const actions: ChannelAction[] = [
      { actionType: 'add_negative', entityId: 'q1', parameters: {} },
      { actionType: 'update_target', entityId: 'c1', parameters: { target: 4.0 } },
    ]

    const results = await adapter.executeActions(actions, 'go')
    expect(results).toHaveLength(2)
    expect(results.every((r) => r.success)).toBe(true)
  })
})
