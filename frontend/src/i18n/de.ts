import { auth } from "./de/auth";
import { common } from "./de/common";
import { nav } from "./de/nav";
import { orders } from "./de/orders";
import { shop } from "./de/shop";

export const de = {
  ...auth,
  ...common,
  ...nav,
  ...orders,
  ...shop,
} as const;

export type MessageKey = keyof typeof de;
