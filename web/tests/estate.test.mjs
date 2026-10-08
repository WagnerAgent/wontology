import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { toEstate } from "../.test/estate.mjs";

const example = (provider) =>
  JSON.parse(
    readFileSync(new URL(`../../examples/${provider}.json`, import.meta.url)),
  );

for (const provider of ["aws", "azure", "gcp"]) {
  test(`${provider}: every resource is navigable exactly once and edges retain direction`, () => {
    const snapshot = example(provider),
      estate = toEstate(snapshot);
    assert.equal(estate.total, snapshot.resources.length);
    assert.equal(
      new Set(estate.resources.map((r) => r.id)).size,
      snapshot.resources.length,
    );
    assert.equal(
      estate.groups.reduce((n, g) => n + g.count, 0),
      estate.total,
    );
    const group = new Map(estate.resources.map((r) => [r.id, r.groupId]));
    for (const [source, target] of estate.deps) {
      assert.ok(
        snapshot.relationships.some(
          (e) =>
            group.get(e.source_id) === source &&
            group.get(e.target_id) === target,
        ),
      );
    }
    for (const resource of snapshot.resources) {
      if (resource.health.state === "unknown") {
        assert.equal(
          estate.resources.find((r) => r.id === resource.canonical_id).status,
          "unknown",
        );
      }
    }
  });
}

test("Azure VM inherits observed network membership through its NIC and subnet", () => {
  const estate = toEstate(example("azure"));
  const vm = estate.resources.find((r) => r.type.includes("virtualMachines"));
  assert.equal(vm.vpcLabel, "Production network");
});

test("GCP zones normalize to regions, and attached disks follow their instance", () => {
  const estate = toEstate(example("gcp"));
  const disk = estate.resources.find((r) => r.type.endsWith("/Disk"));
  assert.equal(disk.region, "us-central1");
  assert.equal(disk.vpcLabel, "Production network");
});

test("filtering compute retains full-snapshot network evidence", () => {
  const snapshot = example("aws");
  const estate = toEstate(
    snapshot,
    snapshot.resources.filter((r) => r.category === "compute"),
  );
  assert.ok(estate.resources.length > 0);
  assert.ok(estate.resources.every((r) => r.vpcLabel === "Production network"));
});

test("multiple network memberships stay explicit rather than picking one", () => {
  const snapshot = example("aws");
  const network = snapshot.resources.find(
    (r) => r.semantic_type === "network.boundary",
  );
  const instance = snapshot.resources.find(
    (r) => r.semantic_type === "compute.instance",
  );
  const other = {
    ...network,
    canonical_id: `${network.canonical_id}-other`,
    name: "Other network",
  };
  snapshot.resources.push(other);
  snapshot.relationships.push({
    source_id: instance.canonical_id,
    target_id: other.canonical_id,
    kind: "deployed_in",
  });
  assert.equal(
    toEstate(snapshot).resources.find((r) => r.id === instance.canonical_id)
      .vpcLabel,
    "Multiple networks",
  );
});

test("resources with no containment evidence remain outside / unassigned", () => {
  const snapshot = example("aws");
  const estate = toEstate(snapshot);
  const bucket = estate.resources.find((r) => r.type.includes("S3"));
  assert.equal(bucket.vpcLabel, "Outside / unassigned network");
});
