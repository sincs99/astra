import { useEffect, useState } from "react";
import { api, getAccessToken, type User } from "../services/api";

// Ein Request pro Token, danach aus dem Cache (Navigation + Seiten teilen sich den User).
let cache: { token: string; user: Promise<User> } | null = null;

function loadUser(): Promise<User> | null {
  const token = getAccessToken();
  if (!token) { cache = null; return null; }
  if (!cache || cache.token !== token) {
    const user = api.getCurrentUser();
    cache = { token, user };
    // Fehlgeschlagene Anfragen nicht cachen, damit der naechste Aufruf es erneut versucht
    user.catch(() => { if (cache?.user === user) cache = null; });
  }
  return cache.user;
}

/** Aktueller Benutzer (null waehrend des Ladens oder bei Fehler). */
export function useCurrentUser(): User | null {
  const [user, setUser] = useState<User | null>(null);

  useEffect(() => {
    let cancelled = false;
    loadUser()?.then((u) => { if (!cancelled) setUser(u); }).catch(() => {});
    return () => { cancelled = true; };
  }, []);

  return user;
}

export function resetCurrentUserCache() {
  cache = null;
}
