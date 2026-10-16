/**
 * 2G/Offline Outbox Queue for `apps/web` PWA (Section 9.2, 11, ADR-011).
 *
 * Security Invariants:
 * 1. Only anonymous `T0` public questions may be queued in the offline outbox on shared devices.
 * 2. Any `T1`–`T4` personal query or message containing a 9–12 digit TIN is rejected from client storage.
 * 3. Bounded capacity (`maxItems = 25`) prevents unbounded memory/storage growth.
 */

import type { LocaleCode, RiskTier } from "@ssra/contracts";

export interface QueuedOutboxMessage {
  readonly id: string;
  readonly message: string;
  readonly locale: LocaleCode;
  readonly tier: RiskTier;
  readonly queuedAtIso: string;
}

const UNMASKED_TIN_PATTERN = /\b\d{9,12}\b/;

export class OfflineOutboxQueue {
  private readonly items: QueuedOutboxMessage[] = [];
  private readonly maxItems: number;

  public constructor(maxItems = 25) {
    this.maxItems = maxItems;
  }

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
    if (UNMASKED_TIN_PATTERN.test(item.message)) {
      return {
        queued: false,
        reason: "SECURITY_POLICY_PII_REJECTED_FROM_OFFLINE_QUEUE",
      };
    }
    if (this.items.length >= this.maxItems) {
      return {
        queued: false,
        reason: "OFFLINE_OUTBOX_CAPACITY_EXCEEDED",
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
