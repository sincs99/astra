import { account } from "./de/account";
import { auth } from "./de/auth";
import { common } from "./de/common";
import { dash } from "./de/dash";
import { landing } from "./de/landing";
import { nav } from "./de/nav";
import { orders } from "./de/orders";
import { shop } from "./de/shop";
import { srv } from "./de/srv";
import { susers } from "./de/susers";
import { sroutines } from "./de/sroutines";
import { sbackups } from "./de/sbackups";
import { sfiles } from "./de/sfiles";
import { sconsole } from "./de/sconsole";
import { ssh } from "./de/ssh";

export const de = {
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
} as const;

export type MessageKey = keyof typeof de;
