"use client";

import { Suspense, useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";

import styles from "../../login/page.module.css";
import { api } from "../../lib/api";

function ConfirmInner() {
  const params = useSearchParams();
  const token = params.get("token") ?? "";

  const [state, setState] = useState<"loading" | "ok" | "error">("loading");
  const [message, setMessage] = useState("");

  useEffect(() => {
    if (!token) {
      setState("error");
      setMessage("Missing token.");
      return;
    }
    (async () => {
      try {
        const r = await api.securityConfirm(token);
        setState("ok");
        setMessage(r.message);
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
                ? "Confirming…"
                : state === "ok"
                  ? "Device trusted"
                  : "Link invalid"}
            </h1>
            <p className={styles.subtitle}>
              {state === "loading" ? "Please wait." : message}
            </p>
          </div>
          {state !== "loading" && (
            <a
              href="/login"
              className={styles.submitBtn}
              style={{ textAlign: "center", textDecoration: "none" }}
            >
              Continue to sign in
            </a>
          )}
        </div>
      </main>
    </div>
  );
}

export default function ConfirmPage() {
  return (
    <Suspense fallback={null}>
      <ConfirmInner />
    </Suspense>
  );
}
