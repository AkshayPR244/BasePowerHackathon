import type { Scenario } from "../api/types";

export const HOUSTON_CENTER = { lon: -95.3698, lat: 29.7604 };

const directions: Record<string, string> = {
  N: "North",
  S: "South",
  E: "East",
  W: "West",
};

export const clusterDirection = (clusterId: string, name?: string) =>
  directions[clusterId.toUpperCase()] ?? name ?? clusterId;

export const isHoustonScenario = (scenario: Scenario) =>
  scenario.sites.some((site) => site.load_zone === "LZ_HOUSTON");

export const clusterKey = (scenario: Scenario) =>
  scenario.clusters
    .map(
      (cluster) =>
        `${cluster.cluster_id} ${clusterDirection(cluster.cluster_id, cluster.name)}`,
    )
    .join(" · ");
