import { account } from "./de/account";
import { auth } from "./de/auth";
import { common } from "./de/common";
import { dash } from "./de/dash";
import { nav } from "./de/nav";
import { orders } from "./de/orders";
import { shop } from "./de/shop";
import { srv } from "./de/srv";
import { ssh } from "./de/ssh";

export const de = {
  ...account,
  ...auth,
  ...common,
  ...dash,
  ...nav,
  ...orders,
  ...shop,
  ...srv,
  ...ssh,
} as const;

export type MessageKey = keyof typeof de;
