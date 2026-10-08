/** Provider-neutral view model consumed by the existing estate canvas. */

export type Status = "ok" | "warn" | "bad" | "unknown" | "na";
export type Tier = string;

export interface EstateLane {
  id: string;
  label: string;
  order: number;
}

export interface EstateResource {
  searchText?: string;
  id: string;
  name: string;
  type: string;
  typeLabel: string;
  icon: string;
  unit: string;
  vpc: string;
  vpcLabel: string;
  region: string;
  tier: Tier;
  group: string;
  groupId: string;
  status: Status;
}

export interface EstateGroup {
  id: string;
  name: string;
  type: string;
  typeLabel: string;
  icon: string;
  unit: string;
  tier: Tier;
  tierLabel: string;
  vpc: string;
  vpcLabel: string;
  region: string;
  count: number;
  ok: number;
  warn: number;
  bad: number;
  unknown: number;
  na: number;
  status: Status;
}

export interface EstateVpc {
  key: string;
  label: string;
  region: string;
  kind?: string;
}

export interface Estate {
  vpcs: EstateVpc[];
  groups: EstateGroup[];
  resources: EstateResource[];
  deps: Array<[string, string]>;
  regions: string[];
  lanes: EstateLane[];
  total: number;
  counts: {
    ok: number;
    warn: number;
    bad: number;
    unknown: number;
    na: number;
  };
}

export interface Rollup {
  count: number;
  ok: number;
  warn: number;
  bad: number;
  unknown: number;
  na: number;
}

export function rollup(groups: EstateGroup[]): Rollup {
  return groups.reduce<Rollup>(
    (acc, group) => ({
      count: acc.count + group.count,
      ok: acc.ok + group.ok,
      warn: acc.warn + group.warn,
      bad: acc.bad + group.bad,
      unknown: acc.unknown + group.unknown,
      na: acc.na + group.na,
    }),
    { count: 0, ok: 0, warn: 0, bad: 0, unknown: 0, na: 0 },
  );
}

export function worstStatus(
  value: Pick<Rollup, "bad" | "warn" | "unknown" | "ok" | "na">,
): Status {
  if (value.bad > 0) return "bad";
  if (value.warn > 0) return "warn";
  if (value.unknown > 0) return "unknown";
  if (value.ok > 0) return "ok";
  return "na";
}
