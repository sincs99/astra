import type { MessageKey } from "./de";
import { auth } from "./en/auth";
import { common } from "./en/common";
import { nav } from "./en/nav";
import { orders } from "./en/orders";
import { shop } from "./en/shop";

export const en: Record<MessageKey, string> = {
  ...auth,
  ...common,
  ...nav,
  ...orders,
  ...shop,
};
