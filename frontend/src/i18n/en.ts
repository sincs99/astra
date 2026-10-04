import type { MessageKey } from "./de";
import { auth } from "./en/auth";
import { common } from "./en/common";

export const en: Record<MessageKey, string> = {
  ...auth,
  ...common,
};
