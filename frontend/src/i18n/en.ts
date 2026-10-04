import type { MessageKey } from "./de";
import { account } from "./en/account";
import { auth } from "./en/auth";
import { common } from "./en/common";
import { dash } from "./en/dash";
import { landing } from "./en/landing";
import { nav } from "./en/nav";
import { orders } from "./en/orders";
import { shop } from "./en/shop";
import { srv } from "./en/srv";
import { susers } from "./en/susers";
import { sroutines } from "./en/sroutines";
import { sbackups } from "./en/sbackups";
import { sfiles } from "./en/sfiles";
import { sconsole } from "./en/sconsole";
import { ssh } from "./en/ssh";

export const en: Record<MessageKey, string> = {
  ...account,
  ...auth,
  ...common,
  ...dash,
  ...landing,
  ...nav,
  ...orders,
  ...shop,
  ...srv,
  ...susers,
  ...sroutines,
  ...sbackups,
  ...sfiles,
  ...sconsole,
  ...ssh,
};
