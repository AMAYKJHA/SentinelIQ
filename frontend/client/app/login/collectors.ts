// collectors.ts
// Scrapes DeviceSpec, NetworkContext, and SessionMetadata from the browser.
// All functions are async-safe and degrade gracefully when APIs are unavailable.

/* ─── helpers ─────────────────────────────────────────────────────────────── */

/** Simple djb2 hash → hex string */
function djb2(str: string): string {
  let hash = 5381;
  for (let i = 0; i < str.length; i++) {
    hash = ((hash << 5) + hash) ^ str.charCodeAt(i);
    hash = hash & hash; // keep 32-bit
  }
  return (hash >>> 0).toString(16).padStart(8, "0");
}

/* ─── Canvas fingerprint ──────────────────────────────────────────────────── */

function getCanvasHash(): string {
  try {
    const canvas = document.createElement("canvas");
    canvas.width = 200;
    canvas.height = 50;
    const ctx = canvas.getContext("2d");
    if (!ctx) return "no-ctx";

    ctx.textBaseline = "top";
    ctx.font = "14px Arial";
    ctx.fillStyle = "#f60";
    ctx.fillRect(125, 1, 62, 20);
    ctx.fillStyle = "#069";
    ctx.fillText("SentinelIQ🔐", 2, 15);
    ctx.fillStyle = "rgba(102,204,0,0.7)";
    ctx.fillText("SentinelIQ🔐", 4, 17);

    return djb2(canvas.toDataURL());
  } catch {
    return "canvas-blocked";
  }
}

/* ─── WebGL renderer ─────────────────────────────────────────────────────── */

function getWebGLRenderer(): string {
  try {
    const canvas = document.createElement("canvas");
    const gl =
      (canvas.getContext("webgl") as WebGLRenderingContext | null) ??
      (canvas.getContext("experimental-webgl") as WebGLRenderingContext | null);
    if (!gl) return "no-webgl";

    const ext = gl.getExtension("WEBGL_debug_renderer_info");
    if (ext) {
      return gl.getParameter(ext.UNMASKED_RENDERER_WEBGL) as string;
    }
    return gl.getParameter(gl.RENDERER) as string;
  } catch {
    return "webgl-blocked";
  }
}

/* ─── Plugins hash ───────────────────────────────────────────────────────── */

function getPluginsHash(): string {
  try {
    const names = Array.from(navigator.plugins)
      .map((p) => p.name)
      .sort()
      .join("|");
    return djb2(names);
  } catch {
    return "plugins-blocked";
  }
}

/* ─── Platform label ─────────────────────────────────────────────────────── */

function getPlatformLabel(): string {
  const p = navigator.platform?.toLowerCase() ?? "";
  const ua = navigator.userAgent.toLowerCase();
  if (p.includes("win")) return "windows";
  if (p.includes("mac")) return "mac";
  if (p.includes("linux") && !ua.includes("android")) return "linux";
  if (ua.includes("android")) return "android";
  if (/iphone|ipad|ipod/.test(ua)) return "ios";
  return "other";
}

/* ─── Device fingerprint (composite) ─────────────────────────────────────── */

function getDeviceFingerprint(
  canvasHash: string,
  webglRenderer: string,
  pluginsHash: string,
): string {
  const parts = [
    canvasHash,
    webglRenderer,
    pluginsHash,
    screen.width,
    screen.height,
    screen.colorDepth,
    navigator.hardwareConcurrency,
    (navigator as Navigator & { deviceMemory?: number }).deviceMemory ?? 0,
    navigator.platform,
  ].join("::");
  return djb2(parts);
}

/* ─── WebRTC local IP ────────────────────────────────────────────────────── */

async function getWebRTCLocalIP(): Promise<string | null> {
  return new Promise((resolve) => {
    try {
      const pc = new RTCPeerConnection({ iceServers: [] });
      pc.createDataChannel("");
      pc.createOffer().then((offer) => pc.setLocalDescription(offer));

      const timeout = setTimeout(() => {
        pc.close();
        resolve(null);
      }, 1000);

      pc.onicecandidate = (e) => {
        if (!e.candidate) return;
        const match = /([0-9]{1,3}(\.[0-9]{1,3}){3})/.exec(
          e.candidate.candidate,
        );
        if (match) {
          clearTimeout(timeout);
          pc.close();
          resolve(match[1]);
        }
      };
    } catch {
      resolve(null);
    }
  });
}

/* ─── Headless detection ─────────────────────────────────────────────────── */

function detectHeadlessSignals(): {
  headless_signals: string;
  webdriver: boolean;
  chrome_headless: boolean;
  no_plugins: boolean;
} {
  const signals: string[] = [];

  const webdriver = !!navigator.webdriver;
  if (webdriver) signals.push("webdriver");

  // @ts-expect-error — non-standard
  const phantom = !!window._phantom || !!window.callPhantom;
  if (phantom) signals.push("phantom");

  // @ts-expect-error — non-standard
  const nightmare = !!window.__nightmare;
  if (nightmare) signals.push("nightmare");

  const noPlugins = navigator.plugins.length === 0;
  if (noPlugins) signals.push("no-plugins");

  const ua = navigator.userAgent;
  const chrome_headless = /HeadlessChrome/.test(ua);
  if (chrome_headless) signals.push("headless-chrome");

  // Broken Image dimensions trick — real browsers always return 0 for unloaded images
  try {
    const img = new Image();
    if (typeof img.width === "undefined") signals.push("broken-img-dims");
  } catch {}

  return {
    headless_signals: signals.join(",") || "none",
    webdriver,
    chrome_headless,
    no_plugins: noPlugins,
  };
}

/* ─── Public collectors ──────────────────────────────────────────────────── */

export interface DeviceSpec {
  device_fingerprint: string;
  hardware_concurrency: number;
  device_memory: number | null;
  screen_width: number;
  screen_height: number;
  pixel_ratio: number;
  is_touch: boolean;
  platform: string;
  user_agent: string;
  color_depth: string;
  plugins_hash: string | null;
  canvas_hash: string | null;
  webgl_renderer: string | null;
}

export interface NetworkContext {
  timezone: string;
  language: string;
  languages: string[];
  connection_type: string;
  webrtc_local_ip: string | null;
  do_not_track: string | null;
}

export interface SessionMetadata {
  session_id: string;
  referrer: string | null;
  cookies_enabled: boolean;
  webdriver: boolean;
  chrome_headless: boolean;
  no_plugins: boolean;
}

export function collectDeviceSpec(): DeviceSpec {
  const canvasHash = getCanvasHash();
  const webglRenderer = getWebGLRenderer();
  const pluginsHash = getPluginsHash();

  return {
    device_fingerprint: getDeviceFingerprint(
      canvasHash,
      webglRenderer,
      pluginsHash,
    ),
    hardware_concurrency: navigator.hardwareConcurrency ?? 0,
    device_memory:
      (navigator as Navigator & { deviceMemory?: number }).deviceMemory ?? null,
    screen_width: screen.width,
    screen_height: screen.height,
    pixel_ratio: devicePixelRatio,
    is_touch: navigator.maxTouchPoints > 0,
    platform: getPlatformLabel(),
    user_agent: navigator.userAgent,
    color_depth: String(screen.colorDepth),
    plugins_hash: pluginsHash,
    canvas_hash: canvasHash,
    webgl_renderer: webglRenderer,
  };
}

interface NetConnection {
  effectiveType?: string;
  type?: string;
}
type NavigatorWithConn = Navigator & {
  connection?: NetConnection;
  mozConnection?: NetConnection;
  webkitConnection?: NetConnection;
};

export async function collectNetworkContext(): Promise<NetworkContext> {
  const nav = navigator as NavigatorWithConn;
  const conn = nav.connection ?? nav.mozConnection ?? nav.webkitConnection;

  return {
    timezone: Intl.DateTimeFormat().resolvedOptions().timeZone,
    language: navigator.language,
    languages: Array.from(navigator.languages),
    connection_type: conn?.effectiveType ?? conn?.type ?? "unknown",
    webrtc_local_ip: await getWebRTCLocalIP(),
    do_not_track: navigator.doNotTrack ?? null,
  };
}

export function collectSessionMetadata(): SessionMetadata {
  const { webdriver, chrome_headless, no_plugins } = detectHeadlessSignals();
  return {
    session_id: crypto.randomUUID(),
    referrer: document.referrer || null,
    cookies_enabled: navigator.cookieEnabled,
    webdriver,
    chrome_headless,
    no_plugins,
  };
}
