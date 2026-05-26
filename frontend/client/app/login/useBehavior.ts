// useBehavior.ts
// Tracks mouse, keyboard, and paste behavior during the login form session.
// Returns a snapshot function that produces the BehavioralSignals object.

import { useCallback, useEffect, useRef } from "react";

export interface BehavioralSignals {
  form_time_ms: number;
  password_pasted: boolean;
  username_pasted: boolean;
  avg_dwell_time_ms: number;
  avg_flight_time_ms: number;
  keystroke_variance: number;
  typo_count: number;
  mouse_event_count: number;
  mouse_linearity: number;
  mouse_avg_speed: number;
  used_tab_to_navigate: boolean;
}

interface KeyEvent {
  key: string;
  downAt: number;
  upAt?: number;
}

interface MousePoint {
  x: number;
  y: number;
  t: number;
}

export function useBehavior() {
  // ── Timing ───────────────────────────────────────────────────────────────
  const firstFocusAt = useRef<number | null>(null);

  // ── Keystroke ────────────────────────────────────────────────────────────
  const keyBuffer = useRef<KeyEvent[]>([]);
  const typoCount = useRef(0);

  // ── Paste ────────────────────────────────────────────────────────────────
  const usernamePasted = useRef(false);
  const passwordPasted = useRef(false);

  // ── Tab navigation ───────────────────────────────────────────────────────
  const usedTab = useRef(false);

  // ── Mouse ────────────────────────────────────────────────────────────────
  const mousePoints = useRef<MousePoint[]>([]);
  const mouseEventCount = useRef(0);

  /* ── Global listeners ──────────────────────────────────────────────────── */

  useEffect(() => {
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Tab") usedTab.current = true;
      if (e.key === "Backspace") typoCount.current++;
      keyBuffer.current.push({ key: e.key, downAt: performance.now() });
    };

    const onKeyUp = (e: KeyboardEvent) => {
      const last = [...keyBuffer.current].reverse().find((k) => k.key === e.key && !k.upAt);
      if (last) last.upAt = performance.now();
    };

    const onMouseMove = (e: MouseEvent) => {
      mouseEventCount.current++;
      mousePoints.current.push({ x: e.clientX, y: e.clientY, t: performance.now() });
      // cap buffer to last 500 points for memory
      if (mousePoints.current.length > 500) mousePoints.current.shift();
    };

    const onFocus = () => {
      if (firstFocusAt.current === null) firstFocusAt.current = performance.now();
    };

    window.addEventListener("keydown", onKeyDown, true);
    window.addEventListener("keyup", onKeyUp, true);
    window.addEventListener("mousemove", onMouseMove, { passive: true });
    window.addEventListener("focusin", onFocus, true);

    return () => {
      window.removeEventListener("keydown", onKeyDown, true);
      window.removeEventListener("keyup", onKeyUp, true);
      window.removeEventListener("mousemove", onMouseMove);
      window.removeEventListener("focusin", onFocus, true);
    };
  }, []);

  /* ── Field-level paste handlers (attached per input) ────────────────────── */

  const onUsernamePaste = useCallback(() => {
    usernamePasted.current = true;
  }, []);

  const onPasswordPaste = useCallback(() => {
    passwordPasted.current = true;
  }, []);

  /* ── Snapshot calculator ──────────────────────────────────────────────────*/

  const snapshot = useCallback((): BehavioralSignals => {
    const now = performance.now();
    const formTimeMs = firstFocusAt.current !== null ? Math.round(now - firstFocusAt.current) : 0;

    // Keystroke metrics
    const completedKeys = keyBuffer.current.filter((k) => k.upAt !== undefined);
    const dwellTimes = completedKeys.map((k) => k.upAt! - k.downAt);

    // Flight time = gap between keyUp[i] and keyDown[i+1]
    const flightTimes: number[] = [];
    for (let i = 0; i < completedKeys.length - 1; i++) {
      const gap = keyBuffer.current[i + 1]?.downAt - completedKeys[i].upAt!;
      if (gap >= 0 && gap < 5000) flightTimes.push(gap);
    }

    const avg = (arr: number[]) => arr.length ? arr.reduce((a, b) => a + b, 0) / arr.length : 0;
    const variance = (arr: number[]) => {
      if (!arr.length) return 0;
      const m = avg(arr);
      return avg(arr.map((v) => (v - m) ** 2));
    };

    // Mouse metrics
    const pts = mousePoints.current;
    let mouseLinearity = 1;
    let mouseAvgSpeed = 0;

    if (pts.length >= 2) {
      let totalPathLen = 0;
      let totalSpeeds: number[] = [];

      for (let i = 1; i < pts.length; i++) {
        const dx = pts[i].x - pts[i - 1].x;
        const dy = pts[i].y - pts[i - 1].y;
        const dt = (pts[i].t - pts[i - 1].t) / 1000; // seconds
        const dist = Math.sqrt(dx * dx + dy * dy);
        totalPathLen += dist;
        if (dt > 0) totalSpeeds.push(dist / dt);
      }

      const first = pts[0];
      const last = pts[pts.length - 1];
      const straightLine = Math.sqrt(
        (last.x - first.x) ** 2 + (last.y - first.y) ** 2
      );

      mouseLinearity = totalPathLen > 0 ? Math.min(1, straightLine / totalPathLen) : 1;
      mouseAvgSpeed = avg(totalSpeeds);
    }

    return {
      form_time_ms: formTimeMs,
      password_pasted: passwordPasted.current,
      username_pasted: usernamePasted.current,
      avg_dwell_time_ms: avg(dwellTimes),
      avg_flight_time_ms: avg(flightTimes),
      keystroke_variance: variance(dwellTimes),
      typo_count: typoCount.current,
      mouse_event_count: mouseEventCount.current,
      mouse_linearity: parseFloat(mouseLinearity.toFixed(4)),
      mouse_avg_speed: parseFloat(mouseAvgSpeed.toFixed(4)),
      used_tab_to_navigate: usedTab.current,
    };
  }, []);

  return { snapshot, onUsernamePaste, onPasswordPaste };
}
