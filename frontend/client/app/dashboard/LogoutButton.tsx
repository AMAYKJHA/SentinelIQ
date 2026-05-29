"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";

import { api } from "../lib/api";

export default function LogoutButton({ className }: { className?: string }) {
  const router = useRouter();
  const [busy, setBusy] = useState(false);

  const handleClick = async () => {
    if (busy) return;
    setBusy(true);
    try {
      await api.logout();
    } catch {
      /* even on failure we want to leave the dashboard */
    }
    router.replace("/login");
    router.refresh();
  };

  return (
    <button
      type="button"
      onClick={handleClick}
      className={className}
      disabled={busy}
    >
      {busy ? "Logging out…" : "Log out"}
    </button>
  );
}
