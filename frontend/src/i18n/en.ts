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
import { ainv } from "./en/ainv";
import { aover } from "./en/aover";
import { sform } from "./en/sform";
import { asys } from "./en/asys";
import { ainst } from "./en/ainst";
import { aagents } from "./en/aagents";
import { aorders } from "./en/aorders";
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
  ...ainv,
  ...aover,
  ...sform,
  ...asys,
  ...ainst,
  ...aagents,
  ...aorders,
  ...susers,
  ...sroutines,
  ...sbackups,
  ...sfiles,
  ...sconsole,
  ...ssh,
};
