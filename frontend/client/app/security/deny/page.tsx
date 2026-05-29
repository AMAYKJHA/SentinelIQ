"use client";

import { Suspense, useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";

import styles from "../../login/page.module.css";
import { api } from "../../lib/api";

function DenyInner() {
  const params = useSearchParams();
  const token = params.get("token") ?? "";

  const [state, setState] = useState<"loading" | "ok" | "error">("loading");
  const [message, setMessage] = useState("");
  const [revoked, setRevoked] = useState(0);

  useEffect(() => {
    if (!token) {
      setState("error");
      setMessage("Missing token.");
      return;
    }
    (async () => {
      try {
        const r = await api.securityDeny(token);
        setState("ok");
        setMessage(r.message);
        setRevoked(r.sessions_revoked);
      } catch (err) {
        setState("error");
        setMessage(
          err instanceof Error ? err.message : "Invalid or expired link.",
        );
      }
    })();
  }, [token]);

  return (
    <div className={styles.page}>
      <main className={styles.main}>
        <div className={styles.card}>
          <div className={styles.cardHeader}>
            <h1 className={styles.title}>
              {state === "loading"
                ? "Securing your account…"
                : state === "ok"
                  ? "All sessions revoked"
                  : "Link invalid"}
            </h1>
            <p className={styles.subtitle}>
              {state === "loading"
                ? "Please wait."
                : state === "ok"
                  ? `${message} (${revoked} session${revoked === 1 ? "" : "s"} signed out)`
                  : message}
            </p>
          </div>
          {state !== "loading" && (
            <a
              href="/login"
              className={styles.submitBtn}
              style={{ textAlign: "center", textDecoration: "none" }}
            >
              Reset password & sign in
            </a>
          )}
        </div>
      </main>
    </div>
  );
}

export default function DenyPage() {
  return (
    <Suspense fallback={null}>
      <DenyInner />
    </Suspense>
  );
}
