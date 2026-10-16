/**
 * Next.js 16 Shared Valkey Cache Handler for Multi-Instance Deployments
 * (`apps/web/src/lib/valkey-cache-handler.ts` — Section 9.1, ADR-010).
 *
 * Security Invariant: Caches ONLY public T0 Cache Components and static routes,
 * tagged by `KnowledgeSnapshot` version so publishing or rolling back a snapshot
 * atomically invalidates all stale cached entries across all Next.js replicas.
 */

export interface ValkeyCacheEntry {
  readonly key: string;
  readonly value: string;
  readonly tags: readonly string[];
  readonly snapshotVersion: string;
  readonly cachedAtMs: number;
}

export class SharedValkeyCacheHandler {
  private readonly store = new Map<string, ValkeyCacheEntry>();

  public get(key: string, activeSnapshotVersion: string): ValkeyCacheEntry | null {
    const entry = this.store.get(key);
    if (!entry || entry.snapshotVersion !== activeSnapshotVersion) {
      return null;
    }
    return entry;
  }

  public set(
    key: string,
    value: string,
    options: {
      readonly tags: readonly string[];
      readonly snapshotVersion: string;
      readonly isPersonalAuthenticatedRoute?: boolean;
    },
  ): boolean {
    // Hard rule: never store authenticated T1-T3 responses in shared page/component cache
    if (options.isPersonalAuthenticatedRoute) {
      return false;
    }
    this.store.set(key, {
      key,
      value,
      tags: options.tags,
      snapshotVersion: options.snapshotVersion,
      cachedAtMs: Date.now(),
    });
    return true;
  }

  public revalidateTag(tag: string): number {
    let evicted = 0;
    for (const [k, entry] of this.store.entries()) {
      if (entry.tags.includes(tag)) {
        this.store.delete(k);
        evicted += 1;
      }
    }
    return evicted;
  }
}
