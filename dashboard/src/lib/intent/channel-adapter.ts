import type { GuardrailRolloutStatus } from '@/lib/intent/types'

/**
 * Channel adapter contracts for future multi-channel expansion.
 * Phase 4 Batch D: defines interfaces without forcing immediate rollout.
 */

/** Supported channel identifiers */
export type ChannelId = 'google_ads' | 'microsoft_ads' | 'meta_ads' | 'custom'

/** Channel capability flags */
export interface ChannelCapabilities {
  supportsNegativeKeywords: boolean
  supportsTroas: boolean
  supportsTcpa: boolean
  supportsTierLabels: boolean
  supportsExperiments: boolean
}

/** Channel health status from adapter self-check */
export interface ChannelHealthStatus {
  channel: ChannelId
  healthy: boolean
  lastSyncAt: string | null
  errorMessage: string | null
}

/** Standardized action that an adapter can execute */
export interface ChannelAction {
  actionType: 'add_negative' | 'remove_negative' | 'update_target' | 'set_label' | 'pause' | 'enable'
  entityId: string
  parameters: Record<string, unknown>
}

/** Result of executing a channel action */
export interface ChannelActionResult {
  success: boolean
  actionType: ChannelAction['actionType']
  entityId: string
  errorMessage: string | null
}

/** The adapter contract all channel implementations must satisfy */
export interface ChannelAdapter {
  readonly channelId: ChannelId
  readonly capabilities: ChannelCapabilities

  /** Check adapter health and connectivity */
  checkHealth(): Promise<ChannelHealthStatus>

  /** Execute a batch of actions, returning results per action */
  executeActions(actions: ChannelAction[], guardrailStatus: GuardrailRolloutStatus): Promise<ChannelActionResult[]>
}

/** Registry entry for a registered adapter */
export interface RegisteredAdapter {
  channelId: ChannelId
  adapter: ChannelAdapter
  registeredAt: string
}

/**
 * Channel adapter registry — manages adapter lifecycle.
 */
export class ChannelAdapterRegistry {
  private adapters = new Map<ChannelId, RegisteredAdapter>()

  register(adapter: ChannelAdapter): void {
    this.adapters.set(adapter.channelId, {
      channelId: adapter.channelId,
      adapter,
      registeredAt: new Date().toISOString(),
    })
  }

  unregister(channelId: ChannelId): boolean {
    return this.adapters.delete(channelId)
  }

  get(channelId: ChannelId): ChannelAdapter | undefined {
    return this.adapters.get(channelId)?.adapter
  }

  listRegistered(): ChannelId[] {
    return Array.from(this.adapters.keys())
  }

  async checkAllHealth(): Promise<ChannelHealthStatus[]> {
    const results: ChannelHealthStatus[] = []
    for (const entry of this.adapters.values()) {
      try {
        results.push(await entry.adapter.checkHealth())
      } catch {
        results.push({
          channel: entry.channelId,
          healthy: false,
          lastSyncAt: null,
          errorMessage: 'Health check threw an exception',
        })
      }
    }
    return results
  }

  async executeOnChannel(
    channelId: ChannelId,
    actions: ChannelAction[],
    guardrailStatus: GuardrailRolloutStatus
  ): Promise<ChannelActionResult[]> {
    const adapter = this.get(channelId)
    if (!adapter) {
      return actions.map((a) => ({
        success: false,
        actionType: a.actionType,
        entityId: a.entityId,
        errorMessage: `No adapter registered for channel: ${channelId}`,
      }))
    }

    if (guardrailStatus === 'blocked') {
      return actions.map((a) => ({
        success: false,
        actionType: a.actionType,
        entityId: a.entityId,
        errorMessage: 'Execution blocked: guardrail status is blocked',
      }))
    }

    return adapter.executeActions(actions, guardrailStatus)
  }
}

/**
 * Google Ads adapter stub — implements contract for existing channel.
 * Actual API calls are handled by existing route handlers;
 * this adapter provides the standardized interface.
 */
export function createGoogleAdsAdapterStub(): ChannelAdapter {
  return {
    channelId: 'google_ads',
    capabilities: {
      supportsNegativeKeywords: true,
      supportsTroas: true,
      supportsTcpa: true,
      supportsTierLabels: true,
      supportsExperiments: true,
    },
    async checkHealth(): Promise<ChannelHealthStatus> {
      return {
        channel: 'google_ads',
        healthy: true,
        lastSyncAt: new Date().toISOString(),
        errorMessage: null,
      }
    },
    // eslint-disable-next-line @typescript-eslint/no-unused-vars
    async executeActions(actions: ChannelAction[], _guardrailStatus: GuardrailRolloutStatus): Promise<ChannelActionResult[]> {
      // Stub: delegates to existing route handlers in production
      return actions.map((a) => ({
        success: true,
        actionType: a.actionType,
        entityId: a.entityId,
        errorMessage: null,
      }))
    },
  }
}
