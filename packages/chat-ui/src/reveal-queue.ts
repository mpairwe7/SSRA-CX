/**
 * Word-Boundary Paced Reveal Queue (`packages/chat-ui/src/reveal-queue.ts`).
 *
 * Paces bursty SSE token frames onto the screen snapped to word boundaries so
 * replies read as typed rather than pasted, while respecting `prefers-reduced-motion`
 * (`instant: true`) and keeping a single complete string in the store on `finish()`.
 */

const TICK_MS = 30;
const MIN_CHARS = 2;
const MAX_CHARS = 100;
const BACKLOG_DIVISOR = 20;

export function nextRevealIndex(target: string, shown: number, budget: number): number {
  if (shown >= target.length) return target.length;
  const raw = Math.min(target.length, shown + Math.max(1, budget));
  if (raw >= target.length) return target.length;

  const nextBreak = target.slice(raw).search(/[\s\n]/);
  if (nextBreak === -1) return target.length;
  return raw + nextBreak + 1;
}

export function revealBudget(remaining: number): number {
  return Math.max(MIN_CHARS, Math.min(MAX_CHARS, Math.ceil(remaining / BACKLOG_DIVISOR)));
}

export interface RevealQueue {
  push(chunk: string): void;
  set(text: string): void;
  getTarget(): string;
  finish(): Promise<void>;
  stop(): void;
}

export interface RevealQueueOptions {
  readonly onCommit: (text: string) => void;
  readonly instant?: boolean | undefined;
  readonly tickMs?: number | undefined;
}

export function createRevealQueue({
  onCommit,
  instant = false,
  tickMs = TICK_MS,
}: RevealQueueOptions): RevealQueue {
  let target = "";
  let shown = 0;
  let timer: ReturnType<typeof setInterval> | null = null;
  let done = false;
  const waiters: Array<() => void> = [];

  const clear = () => {
    if (timer !== null) {
      clearInterval(timer);
      timer = null;
    }
  };

  const settle = () => {
    if (shown < target.length) return;
    clear();
    while (waiters.length > 0) {
      const w = waiters.shift();
      w?.();
    }
  };

  const commitAll = () => {
    if (shown !== target.length) {
      shown = target.length;
      onCommit(target);
    }
    settle();
  };

  const tick = () => {
    if (shown >= target.length) {
      settle();
      return;
    }
    shown = nextRevealIndex(target, shown, revealBudget(target.length - shown));
    onCommit(target.slice(0, shown));
    if (shown >= target.length) settle();
  };

  const ensureRunning = () => {
    if (instant || done) {
      commitAll();
      return;
    }
    if (timer === null && shown < target.length) {
      timer = setInterval(tick, tickMs);
    }
  };

  return {
    push(chunk: string) {
      if (!chunk) return;
      target += chunk;
      ensureRunning();
    },
    set(text: string) {
      const isPrefixContinuation = text.startsWith(target.slice(0, shown));
      target = text;
      if (!isPrefixContinuation || instant || done) {
        commitAll();
        return;
      }
      ensureRunning();
    },
    getTarget() {
      return target;
    },
    finish() {
      done = true;
      commitAll();
      return Promise.resolve();
    },
    stop() {
      done = true;
      clear();
      commitAll();
    },
  };
}
