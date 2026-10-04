import { auth } from "./de/auth";
import { common } from "./de/common";

export const de = {
  ...auth,
  ...common,
} as const;

export type MessageKey = keyof typeof de;
