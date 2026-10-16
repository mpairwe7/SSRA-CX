/**
 * 2G/Offline Outbox Queue for `apps/web` PWA (Section 9.2, 11, ADR-011).
 *
 * Security Invariant: Only anonymous `T0` public questions may be queued in the offline
 * outbox on potentially shared devices. Any `T1`–`T3` personal query is rejected from
 * client-side offline storage.
 */

import type { LocaleCode, RiskTier } from "@ssra/contracts";

export interface QueuedOutboxMessage {
  readonly id: string;
  readonly message: string;
  readonly locale: LocaleCode;
  readonly tier: RiskTier;
  readonly queuedAtIso: string;
}

export class OfflineOutboxQueue {
  private readonly items: QueuedOutboxMessage[] = [];

  public enqueue(item: QueuedOutboxMessage): {
    readonly queued: boolean;
    readonly reason?: string;
  } {
    if (item.tier !== "T0") {
      return {
        queued: false,
        reason: "SECURITY_POLICY_T0_ONLY_OFFLINE_QUEUE",
      };
    }
    this.items.push(item);
    return { queued: true };
  }

  public drainAll(): QueuedOutboxMessage[] {
    return this.items.splice(0, this.items.length);
  }

  public clearOnLogout(): void {
    this.items.length = 0;
  }

  public get size(): number {
    return this.items.length;
  }
}
