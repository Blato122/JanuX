from __future__ import annotations

import logging
from dataclasses import dataclass
from itertools import islice
from typing import Callable, Iterable, Optional, Union

import networkx as nx
import pandas as pd
from networkx.exception import NetworkXNoPath, NodeNotFound

from janux.path_generators import calculate_free_flow_time
from janux.path_generators import check_od_integrity
from janux.path_generators import paths_to_df
from janux.path_generators.base_generator import PathGenerator


@dataclass
class AlternativeRouteConfig:
    """
    Parameters for the alternative-route generator.

    The defaults are intentionally conservative: the generator should return
    fewer than N routes rather than forcing strange detours into the action set.
    """

    number_of_paths: int = 3

    # travel_time vs time!
    weight: str = "travel_time"

    # Maximum number of raw candidates to keep from each generation method.
    candidate_pool_size: int = 150

    # Candidate generation controls.
    via_stretch: float = 1.30
    link_penalty: float = 0.30
    penalty_iterations: int = 25
    k_shortest_limit: int = 80

    # Quality filters.
    max_time_stretch: float = 1.30
    max_distance_stretch: float = 1.50

    # Diversity filters.
    max_overlap_with_shortest: float = 0.85
    max_pairwise_overlap: float = 0.70
    min_jaccard_distance: float = 0.20
    overlap_relaxation_per_route: float = 0.05
    jaccard_relaxation_per_route: float = 0.05
    diversity_violation_weight: float = 2.0

    # Return every filtered candidate for downstream clustering instead of
    # limiting the result to number_of_paths.
    keep_all_filtered: bool = False
    max_filtered_candidates: Optional[int] = 100
    max_routes_per_od: Optional[int] = 20

    # Via edges very close to the origin/destination often just reproduce
    # tiny variants of the shortest route, so we skip them.
    min_via_position: float = 0.10

    # Local optimality catches "go around the block for no reason" behavior.
    # If edge lengths are available, windows are measured in meters.
    # Otherwise, local_window_edges is used as a fallback.
    local_optimality_epsilon: float = 0.10
    local_window_m: float = 500.0
    local_window_edges: int = 8
    local_check_stride: int = 3

    # These filters use attributes that may or may not exist yet.
    # If the required attributes are missing, the check becomes harmless.
    forbid_repeated_edges: bool = True
    forbid_repeated_junctions: bool = True
    forbid_u_turns: bool = True

    # Origin/destination collapse.
    # If enabled, an OD endpoint can match any SUMO edge with the same undirected road key.
    collapse_origin: bool = True
    collapse_destination: bool = True

    verbose: bool = False


class AlternativePathGenerator(PathGenerator):
    """
    Generate plausible and diverse route alternatives.

    This generator is path-level rather than random-walk-based.
    It first creates a pool of reasonable candidates using:
      1. via-edge shortest paths,
      2. link-penalty shortest paths,
      3. capped k-shortest paths.

    Then it removes implausible routes and greedily selects routes that are
    both good and meaningfully different from each other.
    """

    def __init__(
        self,
        network: nx.DiGraph,
        origins: list[str],
        destinations: list[str],
        **kwargs,
    ) -> None:
        super().__init__(network)

        check_od_integrity(self.network, origins, destinations)

        self.origins = dict(enumerate(origins))
        self.destinations = dict(enumerate(destinations))
        self.cfg = AlternativeRouteConfig(**kwargs)

        self.edges_by_undir_key = {}
        for node, data in self.network.nodes(data=True):
            key = data.get("undir_key")
            if key is not None:
                self.edges_by_undir_key.setdefault(key, []).append(node)

        self.logger = logging.getLogger(__name__)
        if self.cfg.verbose:
            self.logger.setLevel(logging.INFO)
        else:
            self.logger.addHandler(logging.NullHandler())

    def generate_routes(
        self,
        as_df: bool = True,
        calc_free_flow: bool = False,
    ) -> Union[pd.DataFrame, dict]:
        """
        Generates routes between origin-destination pairs in the network.
        """
        routes = {}

        for dest_idx, destination in self.destinations.items():
            for origin_idx, origin in self.origins.items():
                selected = self._generate_for_od(origin, destination)
                routes[(origin_idx, dest_idx)] = [tuple(path) for path in selected]

                self.logger.info(
                    "Generated %s routes for %s -> %s",
                    len(selected),
                    origin,
                    destination,
                )

        if not as_df:
            return routes

        free_flows = None
        if calc_free_flow:
            free_flows = {
                od: [calculate_free_flow_time(route, self.network) for route in routes[od]]
                for od in routes
            }

        return paths_to_df(routes, self.origins, self.destinations, free_flows)

    def _endpoint_options(self, edge_id: str, collapse: bool) -> list[str]:
        """
        Return equivalent endpoint edges.

        In this graph, nodes are SUMO edge IDs. If collapse is enabled and the
        edge has an undirected key, both directions of the same physical road
        segment can be used as equivalent OD endpoints.
        """
        if not collapse:
            return [edge_id]

        key = self.network.nodes.get(edge_id, {}).get("undir_key")
        if key is None:
            return [edge_id]

        options = self.edges_by_undir_key.get(key, [edge_id])

        # Keep the requested endpoint first for stable behavior
        return [edge_id] + sorted(e for e in options if e != edge_id)

    def _generate_for_od(self, origin: str, destination: str) -> list[list[str]]:
        """
        Generate alternatives for one OD pair.

        This is the main algorithm in one place:
          1. shortest route,
          2. via-edge candidates,
          3. link-penalty candidates,
          4. k-shortest candidates,
          5. hard filtering,
          6. diversity-aware selection.

        If origin/destination collapse is enabled, candidate generation is run
        over equivalent endpoint edges that share the same undirected road key.
        """
        origin_options = self._endpoint_options(origin, self.cfg.collapse_origin)
        destination_options = self._endpoint_options(destination, self.cfg.collapse_destination)

        endpoint_pairs = []

        for start in origin_options:
            for end in destination_options:
                if start == end:
                    continue

                shortest = self._shortest_path(start, end)
                if shortest is None:
                    continue

                endpoint_pairs.append((start, end, shortest, self._path_cost(shortest)))

        if not endpoint_pairs:
            return []

        # Use the best collapsed-endpoint shortest path as the reference route.
        _, _, reference_shortest, reference_cost = min(endpoint_pairs, key=lambda x: x[3])

        candidates = []

        for start, end, shortest, shortest_cost in endpoint_pairs:
            candidates.append(shortest)
            candidates.extend(self._via_edge_candidates(start, end, shortest, shortest_cost))
            candidates.extend(self._penalty_candidates(start, end, shortest))
            candidates.extend(self._k_shortest_candidates(start, end, shortest_cost))

        candidates = self._deduplicate(candidates)

        # Filter all candidates against the best collapsed shortest route.
        # This keeps stretch comparisons consistent across endpoint variants.
        candidates = self._filter_candidates(candidates, reference_shortest)
        candidates = self._limit_filtered_candidates(candidates, reference_shortest)

        return self._select_diverse(candidates, reference_shortest)

    def _limit_filtered_candidates(
        self,
        candidates: list[list[str]],
        shortest: list[str],
    ) -> list[list[str]]:
        limit = self.cfg.max_filtered_candidates
        if limit is None or len(candidates) <= limit:
            return candidates

        shortest_cost = max(self._path_cost(shortest), 1e-9)
        ranked = sorted(
            candidates,
            key=lambda path: (
                self._path_cost(path) / shortest_cost - 1.0
                + 0.5 * self._overlap(path, shortest)
            ),
        )
        return ranked[:limit]

    def _via_edge_candidates(
        self,
        origin: str,
        destination: str,
        shortest: list[str],
        shortest_cost: float,
    ) -> list[list[str]]:
        """
        Generate routes through promising via edges.

        A via edge v is accepted only if:
        cost(origin -> v) + cost(v -> destination) <= via_stretch * cost(shortest route)

        This gives alternatives that have a clear reason to exist: they go
        through a different plausible corridor, instead of wandering randomly.
        """
        try:
            dist_o, paths_o = nx.single_source_dijkstra(
                self.network,
                origin,
                weight=self._base_weight,
            )

            reversed_network = self.network.reverse(copy=False)

            dist_d_rev, paths_d_rev = nx.single_source_dijkstra(
                reversed_network,
                destination,
                weight=self._base_weight,
            )

        except (NetworkXNoPath, NodeNotFound):
            return []

        shortest_set = set(shortest)
        via_routes = []

        # dist_o[v]: cost(origin -> v)
        # dist_d_rev[v]: cost(destination -> v in reversed graph) == cost(v -> destination in original graph)
        # Consider every edge that:
        # 1. can be reached from origin
        # 2. can reach destination
        reachable_from_origin = set(dist_o.keys())
        can_reach_destination = set(dist_d_rev.keys())
        possible_via_nodes = reachable_from_origin & can_reach_destination

        for via in possible_via_nodes:

            # Not a meaningful candidate
            if via == origin or via == destination:
                continue

            # Via edges already on the shortest route usually create duplicates
            if via in shortest_set:
                continue

            via_cost = dist_o[via] + dist_d_rev[via]
            if via_cost > self.cfg.via_stretch * shortest_cost:
                continue

            # Skip edges too close to the origin or destination
            # pos is an estimate of where the via node sits along the full candidate route
            # pos = cost(origin -> via) / cost(origin -> via -> destination) <- full route
            # If min_via_position is e.g. 0.15, then only via nodes between 15% and 85% of the route are kept
            pos = dist_o[via] / max(via_cost, 1e-9)
            if pos < self.cfg.min_via_position or pos > 1.0 - self.cfg.min_via_position:
                continue

            # paths_d_rev[via] is destination -> via in the reversed graph,
            # so reversing it gives via -> destination in the original graph.
            path_o_v = paths_o[via]
            path_v_d = list(reversed(paths_d_rev[via]))
            candidate = path_o_v + path_v_d[1:]

            # Rank candidates by "not too much detour" and "not too much overlap".
            score = (
                self._path_cost(candidate) / max(shortest_cost, 1e-9)
                + 0.30 * self._overlap(candidate, shortest)
            )
            via_routes.append((score, candidate))

        via_routes.sort(key=lambda x: x[0])
        return [path for _, path in via_routes[: self.cfg.candidate_pool_size]]

    def _penalty_candidates(
        self,
        origin: str,
        destination: str,
        shortest: list[str],
    ) -> list[list[str]]:
        """
        Generate alternatives by repeatedly penalizing already-used road segments.

        The idea is simple:
          - first, the shortest route is cheap;
          - then, edges used by previous routes become slightly more expensive;
          - shortest path is recomputed;
          - this often reveals nearby alternative corridors.

        Only the middle part of each route is penalized heavily. Origin and
        destination access roads are often unavoidable, especially in urban
        networks, so punishing them too much creates weird behavior.
        """
        candidates = []
        usage_count = {}

        for node in self._middle_of_route(shortest):
            usage_count[node] = usage_count.get(node, 0) + 1

        for _ in range(self.cfg.penalty_iterations):
            weight = self._penalized_weight(usage_count)
            path = self._shortest_path(origin, destination, weight=weight)

            if path is None:
                break

            candidates.append(path)

            for node in self._middle_of_route(path):
                usage_count[node] = usage_count.get(node, 0) + 1

            if len(candidates) >= self.cfg.candidate_pool_size:
                break

        return candidates

    def _k_shortest_candidates(
        self,
        origin: str,
        destination: str,
        shortest_cost: float,
    ) -> list[list[str]]:
        """
        Generate a capped list of k-shortest simple paths.

        Plain k-shortest paths are not enough by themselves: they often produce
        tiny variants of the same route, then increasingly ugly detours.

        Here they are just one candidate source. The stretch, loop, local
        optimality, and diversity filters later decide whether they survive.
        """
        candidates = []

        try:
            path_iter = nx.shortest_simple_paths(
                self.network,
                origin,
                destination,
                weight=self._base_weight,
            )
        except (NetworkXNoPath, NodeNotFound):
            return []

        for path in islice(path_iter, self.cfg.k_shortest_limit):
            cost = self._path_cost(path)

            # Since paths are yielded in increasing cost order, once we are
            # past the stretch limit, later paths are unlikely to help.
            if cost > self.cfg.max_time_stretch * shortest_cost:
                break

            candidates.append(path)

            if len(candidates) >= self.cfg.candidate_pool_size:
                break

        return candidates

    def _filter_candidates(
        self,
        candidates: list[list[str]],
        shortest: list[str],
    ) -> list[list[str]]:
        """
        Remove candidates that are mathematically valid but behaviorally bad.

        This is where "plausibility" is enforced:
          - no repeated SUMO edge IDs,
          - no repeated junctions when junction attributes exist,
          - no U-turns when attributes allow detection,
          - not much slower/longer than the shortest route,
          - no locally silly subroute.
        """
        shortest_cost = self._path_cost(shortest)
        shortest_length = self._path_length(shortest)

        accepted = []

        for path in candidates:
            if len(path) < 2:
                continue

            if self.cfg.forbid_repeated_edges and len(path) != len(set(path)):
                continue

            if self.cfg.forbid_repeated_junctions and self._has_repeated_junction(path):
                continue

            if self.cfg.forbid_u_turns and self._has_forbidden_u_turn(path):
                continue

            cost = self._path_cost(path)
            if cost > self.cfg.max_time_stretch * shortest_cost:
                continue

            length = self._path_length(path)
            if shortest_length > 0 and length > self.cfg.max_distance_stretch * shortest_length:
                continue

            if not self._local_optimality_ok(path):
                continue

            accepted.append(path)

        # The shortest route should always be present if it passed basic routing.
        # It can be missing only due to an overly strict attribute-based check.
        if tuple(shortest) not in {tuple(p) for p in accepted}:
            accepted.insert(0, shortest)

        return self._deduplicate(accepted)

    def _select_diverse(
        self,
        candidates: list[list[str]],
        shortest: list[str],
    ) -> list[list[str]]:
        """
        Rank routes by quality and diversity, with progressively relaxed targets.

        Diversity thresholds are soft: exceeding one adds a score penalty
        instead of discarding the route. This avoids returning too few routes
        when an OD has limited genuinely distinct alternatives.
        """
        if not candidates:
            return []

        candidates = sorted(candidates, key=self._path_cost)

        selected = [shortest]
        remaining = [p for p in candidates if tuple(p) != tuple(shortest)]
        target_count = min(self.cfg.number_of_paths, len(candidates))
        shortest_cost = max(self._path_cost(shortest), 1e-9)

        while len(selected) < target_count and remaining:
            relaxation_step = max(0, len(selected) - 1)
            allowed_shortest_overlap = min(
                1.0,
                self.cfg.max_overlap_with_shortest
                + relaxation_step * self.cfg.overlap_relaxation_per_route,
            )
            allowed_pairwise_overlap = min(
                1.0,
                self.cfg.max_pairwise_overlap
                + relaxation_step * self.cfg.overlap_relaxation_per_route,
            )
            required_jaccard_distance = max(
                0.0,
                self.cfg.min_jaccard_distance
                - relaxation_step * self.cfg.jaccard_relaxation_per_route,
            )
            scored = []

            for path in remaining:
                max_overlap = max(self._overlap(path, old) for old in selected)
                min_jaccard_dist = min(self._jaccard_distance(path, old) for old in selected)
                shortest_overlap = self._overlap(path, shortest)
                excess = self._path_cost(path) / shortest_cost - 1.0

                violation = (
                    max(0.0, shortest_overlap - allowed_shortest_overlap)
                    + max(0.0, max_overlap - allowed_pairwise_overlap)
                    + max(0.0, required_jaccard_distance - min_jaccard_dist)
                )
                score = (
                    excess
                    + 0.50 * max_overlap
                    + 0.25 * shortest_overlap
                    - 0.25 * min_jaccard_dist
                    + self.cfg.diversity_violation_weight * violation
                )
                scored.append((score, path))

            scored.sort(key=lambda x: x[0])
            chosen = scored[0][1]

            selected.append(chosen)
            remaining = [p for p in remaining if tuple(p) != tuple(chosen)]

        if self.cfg.keep_all_filtered:
            selected.extend(sorted(remaining, key=self._path_cost))

        if self.cfg.max_routes_per_od is not None:
            selected = selected[: self.cfg.max_routes_per_od]

        return selected

    def _shortest_path(
        self,
        origin: str,
        destination: str,
        weight: Optional[Callable] = None,
    ) -> Optional[list[str]]:
        """
        Safe shortest-path wrapper.

        Returns None instead of crashing when an OD pair becomes unreachable
        under a custom penalized weight.
        """
        try:
            return nx.shortest_path(
                self.network,
                origin,
                destination,
                weight=weight or self._base_weight,
            )
        except (NetworkXNoPath, NodeNotFound):
            return None

    def _base_weight(self, u: str, v: str, data: dict) -> float:
        """
        Edge cost used by shortest-path methods.

        The current JanuX graph normally uses "travel_time". This helper also
        falls back to "time" and then to 1.0, so the generator does not silently
        fail if a slightly different graph is passed in.
        """
        if self.cfg.weight in data:
            return float(data[self.cfg.weight])

        if "travel_time" in data:
            return float(data["travel_time"])

        if "time" in data:
            return float(data["time"])

        return 1.0

    def _penalized_weight(self, usage_count: dict[str, int]) -> Callable:
        """
        Create a temporary weight function for link-penalty routing.

        In JanuX's graph, nodes are SUMO edges. For transition u -> v, we
        penalize v when v has appeared in previous routes. This encourages the
        shortest-path search to choose a different corridor.
        """

        def weight(u: str, v: str, data: dict) -> float:
            base = self._base_weight(u, v, data)
            penalty = 1.0 + self.cfg.link_penalty * usage_count.get(v, 0)
            return base * penalty

        return weight

    def _path_cost(self, path: list[str]) -> float:
        """
        Sum transition costs along a route.

        This mirrors JanuX's existing route-time logic: cost is accumulated on
        graph edges between consecutive SUMO edge IDs.
        """
        total = 0.0

        for u, v in zip(path[:-1], path[1:]):
            data = self.network.get_edge_data(u, v)

            if data is None:
                return float("inf")

            total += self._base_weight(u, v, data)

        return total

    def _path_length(self, path: list[str]) -> float:
        """
        Sum physical lengths if node lengths exist; otherwise fall back to cost.

        The graph enrichment I suggested would attach "length" to graph nodes,
        because graph nodes are SUMO road edges. Until that exists everywhere,
        this method remains safe by falling back to route cost.
        """
        lengths = []

        for node in path:
            value = self.network.nodes.get(node, {}).get("length")
            if value is not None:
                lengths.append(float(value))

        if lengths:
            return sum(lengths)

        return self._path_cost(path)

    def _middle_of_route(self, path: list[str], trim_fraction: float = 0.15) -> list[str]:
        """
        Return the middle part of a route.

        Used by the penalty method. We avoid penalizing the very beginning and
        end too strongly because many OD pairs have unavoidable access links.
        """
        if len(path) <= 4:
            return path

        trim = int(len(path) * trim_fraction)
        return path[trim : len(path) - trim]


    def _deduplicate(self, paths: Iterable[list[str]]) -> list[list[str]]:
        """
        Remove exact duplicate routes while preserving order.
        """
        seen = set()
        unique = []

        for path in paths:
            key = tuple(path)
            if key in seen:
                continue

            seen.add(key)
            unique.append(path)

        return unique

    def _overlap(self, path_a: list[str], path_b: list[str]) -> float:
        """
        Fraction of the shorter route that is shared by both routes.

        This is stricter than Jaccard for route alternatives: if a candidate
        mostly contains the shortest route plus a detour, the overlap will be
        high and the route will likely be rejected.
        """
        set_a = set(path_a)
        set_b = set(path_b)

        denom = max(1, min(len(set_a), len(set_b)))
        return len(set_a.intersection(set_b)) / denom

    def _jaccard_distance(self, path_a: list[str], path_b: list[str]) -> float:
        """
        Jaccard distance between route edge sets.
        0 means identical edge set, 1 means no shared edges.
        """
        set_a = set(path_a)
        set_b = set(path_b)

        union = set_a.union(set_b)
        if not union:
            return 0.0

        return 1.0 - len(set_a.intersection(set_b)) / len(union)


    def _has_repeated_junction(self, path: list[str]) -> bool:
        """
        Detect loops using junction attributes when available.

        This uses "junction_to" first, then "to_node". These attributes are
        already present only if the graph builder keeps/enriches them. If they
        are missing, the check does nothing rather than rejecting valid routes.
        """
        seen = set()

        for node in path:
            attrs = self.network.nodes.get(node, {})
            junction = attrs.get("junction_to") or attrs.get("to_node")

            if junction is None:
                continue

            if junction in seen:
                return True

            seen.add(junction)

        return False

    def _has_forbidden_u_turn(self, path: list[str]) -> bool:
        """
        Detect obvious U-turns.

        Two mechanisms are used:
          1. transition attribute says dir == "t", which SUMO often uses for turnarounds;
          2. node attributes show that consecutive road edges reverse from/to nodes.

        If those attributes are not available, this returns False.
        """
        for u, v in zip(path[:-1], path[1:]):
            edge_data = self.network.get_edge_data(u, v) or {}

            if str(edge_data.get("dir", "")).lower() == "t":
                return True

            u_attrs = self.network.nodes.get(u, {})
            v_attrs = self.network.nodes.get(v, {})

            u_from = u_attrs.get("from_node")
            u_to = u_attrs.get("to_node")
            v_from = v_attrs.get("from_node")
            v_to = v_attrs.get("to_node")

            if u_from is not None and u_to is not None and v_from is not None and v_to is not None:
                if u_from == v_to and u_to == v_from:
                    return True

        return False

    def _local_optimality_ok(self, path: list[str]) -> bool:
        """
        Reject routes with locally irrational detours.

        For short windows along the route, compare the actual subpath with the
        shortest path between the same endpoints. If the actual local segment
        is much worse, the full route is probably doing a silly neighborhood
        loop even if its total stretch is still acceptable.

        This is intentionally approximate and can be turned off by setting
        local_optimality_epsilon to a very large value.
        """
        if len(path) <= self.cfg.local_window_edges + 1:
            return True

        for i in range(0, len(path) - 2, self.cfg.local_check_stride):
            j = self._local_window_end(path, i)

            if j <= i + 2:
                continue

            actual = self._path_cost(path[i : j + 1])

            try:
                best = nx.shortest_path_length(
                    self.network,
                    path[i],
                    path[j],
                    weight=self._base_weight,
                )
            except (NetworkXNoPath, NodeNotFound):
                continue

            if actual > (1.0 + self.cfg.local_optimality_epsilon) * best:
                return False

        return True

    def _local_window_end(self, path: list[str], start_idx: int) -> int:
        """
        Find the end index for a local-optimality window.

        If node lengths are available, the window is about local_window_m meters.
        Otherwise, it falls back to a fixed number of graph nodes.
        """
        total_length = 0.0
        saw_lengths = False

        for j in range(start_idx + 1, len(path)):
            length = self.network.nodes.get(path[j], {}).get("length")

            if length is not None:
                saw_lengths = True
                total_length += float(length)

                if total_length >= self.cfg.local_window_m:
                    return j

        if saw_lengths:
            return len(path) - 1

        return min(len(path) - 1, start_idx + self.cfg.local_window_edges)
