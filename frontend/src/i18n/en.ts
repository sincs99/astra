import type { MessageKey } from "./de";
import { account } from "./en/account";
import { auth } from "./en/auth";
import { common } from "./en/common";
import { dash } from "./en/dash";
import { nav } from "./en/nav";
import { orders } from "./en/orders";
import { shop } from "./en/shop";
import { ssh } from "./en/ssh";

export const en: Record<MessageKey, string> = {
  ...account,
  ...auth,
  ...common,
  ...dash,
  ...nav,
  ...orders,
  ...shop,
  ...ssh,
};
