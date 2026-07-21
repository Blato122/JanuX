import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.getcwd(), './')))

from typing import List, Union

import networkx as nx
import pandas as pd
import numpy as np

from janux.path_generators import calculate_free_flow_time
from janux.path_generators import iterable_to_string
from janux.path_generators import paths_to_df
from janux.path_generators.extended_generator import ExtendedPathGenerator

class ClusteringPathGenerator(ExtendedPathGenerator):

    """
    Route generator used by the clustering pipeline with extra functionalities:
    - block repeated undirected segments revisits
    - block junction revisits
    - origin/destination collapse
    - diverse selection mode (choosing subsequent paths not based on their sample counts but on their similarity to previously chosen ones - least similar are prioritized)
    - max_resample_iterations eliminates route generation stalling by allowing to terminate early and return less paths than requested
    
    Mainly meant to be used with the path clustering pipeline.
    """

    def __init__(
        self,
        network: nx.DiGraph,
        origins: list[str],
        destinations: list[str],
        **kwargs,
    ):
        """
        Initialize the clustering generator.

        Args:
            network (nx.DiGraph): Directed traffic graph built from SUMO files.
            origins (list[str]): Ordered list of origin nodes/edges used as OD inputs.
            destinations (list[str]): Ordered list of destination nodes/edges used as OD inputs.
            **kwargs: Optional generator parameters forwarded to the extended base class.

        Notes:
            The clustering workflow uses a dedicated generator path.
            Any clustering-specific defaults should be centralized here so the
            classic generators remain untouched.
        """
        kwargs = dict(kwargs)

        # NEW: cluster-only defaults mirror the forked generator behavior while
        # leaving the classic generators unchanged.
        kwargs.setdefault("max_resample_iterations", 50)
        kwargs.setdefault("diverse_selection", False)
        kwargs.setdefault("keep_generating", False)
        kwargs.setdefault("min_difference_jaccard", 0.1)

        # NEW: route traversal constraints used by the forked clustered generator.
        kwargs.setdefault("forbid_abs_reuse", True)
        kwargs.setdefault("collapse_destination", True)
        kwargs.setdefault("collapse_origin", True)
        kwargs.setdefault("forbid_junction_revisit", True)
        kwargs.setdefault("collapse_internal_junctions", True)

        super().__init__(network, origins, destinations, **kwargs)

        self.max_resample_iterations = kwargs["max_resample_iterations"]
        self.diverse_selection = kwargs["diverse_selection"]
        self.keep_generating = kwargs["keep_generating"]
        self.min_difference_jaccard = kwargs["min_difference_jaccard"]
        self.forbid_abs_reuse = kwargs["forbid_abs_reuse"]
        self.collapse_destination = kwargs["collapse_destination"]
        self.collapse_origin = kwargs["collapse_origin"]
        self.forbid_junction_revisit = kwargs["forbid_junction_revisit"]
        self.collapse_internal_junctions = kwargs["collapse_internal_junctions"]
        self.stats = {"dead_end": 0, "max_length": 0, "no_potential": 0}

        # Keep the clustered generator logging local to this instance.
        self.logger.propagate = False

    def generate_routes(
        self,
        as_df: bool = True,
        calc_free_flow: bool = False,
    ) -> Union[pd.DataFrame, dict]:
        """
        Generates routes between origin-destination pairs in the network.

        Args:
            as_df (bool): Return a DataFrame when True, otherwise return the raw route dict.
            calc_free_flow (bool): Include free-flow travel times when True.

        Returns:
            pd.DataFrame | dict: Generated routes in the same shape as the base generators.
        """
        assert self.num_samples >= self.number_of_paths, (
            f"Number of samples ({self.num_samples}) should be "
            f"at least equal to the number of routes ({self.number_of_paths})"
        )
        assert self.max_path_length > 0, f"Maximum path length should be greater than 0"
        assert self.beta < 0, f"Beta should be less than 0"
        assert self.shift_parameters_by > 0, f"Shift parameters should be greater than 0"
        assert self.params_to_shift in ["beta", "max_path_length", "both", "none"], f"Invalid parameter to shift: {self.params_to_shift}. Choose from 'beta', 'max_path_length', 'both', 'none'."

        routes = dict()   # Tuple<od_id, dest_id> : List<routes>
        for dest_idx, dest_name in self.destinations.items():
            node_potentials = dict(nx.shortest_path_length(self.network, target=dest_name, weight=self.weight))

            for origin_idx, origin_name in self.origins.items():
                self.stats = {k: 0 for k in self.stats}
                sampled_routes = list()
                iteration_count = 0
                total_iterations = 0
                initial_beta, initial_max_path_len = self.beta, self.max_path_length

                while (len(sampled_routes) < self.num_samples) or (len(set(sampled_routes)) < self.number_of_paths):

                    if total_iterations > self.max_resample_iterations + self.num_samples:
                        self.logger.warning(
                            f"Hit max iterations for {origin_idx} -> {dest_idx}. Returning {len(set(sampled_routes))} unique paths."
                        )
                        break

                    if (self.adaptive) and (iteration_count > self.tolerate_num_iterations):
                        self.logger.warning(f"Exceeded tolerance for {origin_idx} -> {dest_idx}.")
                        self.beta, self.max_path_length = self._shift_parameters(self.beta, self.max_path_length)
                        self.logger.info(f"Beta: {self.beta}, Max Path Length: {self.max_path_length}")
                        iteration_count = 0

                    path = self._sample_single_route(origin_name, dest_name, node_potentials)
                    if path is not None:
                        sampled_routes.append(tuple(path))
                    iteration_count += 1
                    total_iterations += 1

                self.beta, self.max_path_length = initial_beta, initial_max_path_len
                self.logger.info(f"Sampled {len(sampled_routes)} paths for {origin_idx} -> {dest_idx}")
                routes[(origin_idx, dest_idx)] = self._pick_routes_from_samples(sampled_routes)
                self.logger.info(f"Selected {len(set(routes[(origin_idx, dest_idx)]))} paths for {origin_idx} -> {dest_idx}")

        if as_df:
            free_flows = None
            if calc_free_flow:
                free_flows = {od: [calculate_free_flow_time(route, self.network) for route in routes[od]] for od in routes}
            routes_df = paths_to_df(routes, self.origins, self.destinations, free_flows)
            return routes_df
        else:
            return routes

    def _sample_single_route(
        self,
        origin: str,
        destination: str,
        node_potentials: dict,
    ) -> Union[List[str], None]:
        """
        Samples a single route between an origin and a destination in the network.
                
        Args:
            origin (str): Start node/edge for the OD pair.
            destination (str): Target node/edge for the OD pair.
            node_potentials (dict): Reverse shortest-path potential map for the target.

        Returns:
            list[str] | None: A sampled route or `None` when no valid route can be built.
        """
        path = []
        visited_edges = set()
        visited_undir = set()
        visited_junctions = set()
        current_node = origin

        def junction_id(node_id: str | None) -> str | None:
            if node_id is None: 
                return None
            s = str(node_id)
            if self.collapse_internal_junctions and s.startswith(":"):
                return s[1:].split("_")[0]
            return s

        def get_junc(eid: str, attr: str) -> str | None:
            # attr is "from_node" or "to_node"
            val = self.network.nodes.get(eid, {}).get(attr)
            return junction_id(val)

        def undir_key(eid: str) -> tuple[str, str] | None:
            d = self.network.nodes.get(eid, {})
            return d.get("undir_key")

        ######
        ### STARTING DIRECTION CHOICE:
        ######

        origin_key = undir_key(origin)
        start_candidates = [origin]
        
        if self.collapse_origin and origin_key:
            # Find the directed edge going the other way on the same road
            for node, data in self.network.nodes(data=True):
                if node == origin: continue
                if data.get("undir_key") == origin_key:
                    start_candidates.append(node)
                    break

        # Choose the optimal starting direction based on the potentials; avoids U-turns
        current_node = self._logit(start_candidates, node_potentials)

        dest_key = undir_key(destination) if self.collapse_destination else None

        ######
        ### PATH CREATION:
        ######

        while True:
            path.append(current_node)
            visited_edges.add(current_node)

            # Mark the junction we just arrived at as visited
            j_arrival = get_junc(current_node, "to_node")
            if self.forbid_junction_revisit and j_arrival:
                visited_junctions.add(j_arrival)

            # Mark the undirected (!) edge we just arrived at as visited
            k = undir_key(current_node)
            if self.forbid_abs_reuse and k is not None:
                # Don't "consume" the origin segment immediately so that we can turn around
                # ~(p && q) <=> ~p || ~q
                if not (self.collapse_origin and k == origin_key):
                    visited_undir.add(k)

            # Success - collapsed destination - early exit
            if self.collapse_destination and dest_key is not None:
                if k == dest_key:
                    return path

            ######
            ### STEP SELECTION:
            ######

            options = sorted(self.network.neighbors(current_node))
            
            # Exact finish
            # if destination in options:
            #     dk = undir_key(destination)
            #     # Allow if not blocking segment OR if it's a tiny 1-edge road we just started on
            #     if not self.forbid_abs_reuse or (dk not in visited_undir) or (len(path) == 1 and dk == origin_key):
            #         return path + [destination]

            if destination in options:
                return path + [destination]

            if len(path) > self.max_path_length:
                self.stats["max_length"] += 1 # NEW
                return None

            candidates = []

            for opt in options:
                if opt in visited_edges:
                    continue

                p_opt = node_potentials.get(opt, float("inf"))
                if not np.isfinite(p_opt):
                    continue

                # Junction-revisit block
                if self.forbid_junction_revisit:
                    j_next = get_junc(opt, "to_node")
                    if j_next and (j_next in visited_junctions):
                        continue # destination already handled above

                # Undirected segment block
                if self.forbid_abs_reuse:
                    ok_key = undir_key(opt)
                    if ok_key and ok_key in visited_undir:
                        continue # destination already handled above

                candidates.append(opt)

            # collapsed-destination "hit" via any candidate
            if self.collapse_destination and dest_key is not None:
                dest_cands = [c for c in candidates if undir_key(c) == dest_key]
                if dest_cands:
                    best = min(dest_cands, key=lambda x: node_potentials.get(x, float("inf")))
                    return path + [best]

            if not candidates:
                self.stats["dead_end"] += 1    # NEW
                # try:
                #     fallback = nx.shortest_path(self.network, origin, destination)
                #     # print(fallback)
                #     return fallback
                # except nx.NetworkXNoPath:
                #     pass
                return None  # truly unreachable

            cur_p = node_potentials.get(current_node, float("inf"))
            if not np.isfinite(cur_p):
                self.stats["no_potential"] += 1 # NEW
                return None

            current_node = self._logit(candidates, node_potentials)

    def _pick_routes_from_samples(self, sampled_routes: list[tuple]) -> list[tuple]:
        """
        Select the final route set for an OD pair.

        Args:
            sampled_routes (list[tuple]): Sampled candidate routes for one OD pair.

        Returns:
            list[tuple]: The selected route set.
        """
        assert self.number_of_paths > 0, f"Number of paths should be greater than 0"

        if not sampled_routes:
            return []

        if self.diverse_selection:
            route_counts = pd.Series(sampled_routes).value_counts()
            unique_routes = route_counts.index.tolist()

            shortest_route_len = min(len(r) for r in unique_routes)
            max_allowed_len = 10 * shortest_route_len
            candidates = [r for r in unique_routes if len(r) <= max_allowed_len]

            num_too_long = len(unique_routes) - len(candidates)
            if not candidates:
                return []

            picked_routes = []
            rejected_jaccard = 0

            for candidate in candidates:
                if not self.keep_generating and len(picked_routes) >= self.number_of_paths:
                    break

                if all(self._jaccard_distance(candidate, picked) >= self.min_difference_jaccard for picked in picked_routes):
                    picked_routes.append(candidate)
                else:
                    rejected_jaccard += 1

            surplus = len(candidates) - len(picked_routes) - rejected_jaccard
            self.logger.info(
                f"Selection: {len(picked_routes)} kept, {num_too_long} too long, "
                f"{rejected_jaccard} too similar, {surplus} surplus unique paths."
            )
            return picked_routes

        sampled_routes_by_str = np.array([iterable_to_string(route, ",") for route in sampled_routes])
        unique_routes, route_counts = np.unique(sampled_routes_by_str, return_counts=True)
        sampling_probabilities = route_counts / route_counts.sum()

        n_to_pick = min(self.number_of_paths, len(unique_routes))
        if n_to_pick == 0:
            return []

        if n_to_pick < self.number_of_paths and self.verbose:
            self.logger.warning(
                f"Requested {self.number_of_paths} unique paths but only {len(unique_routes)} found; returning {n_to_pick}."
            )

        picked_routes = self.rng.choice(unique_routes, size=n_to_pick, p=sampling_probabilities, replace=False)
        return [tuple(route.split(",")) for route in picked_routes]

    def _jaccard_distance(self, route_A: tuple[str], route_B: tuple[str]) -> float:
        route_A_edges = set(route_A)
        route_B_edges = set(route_B)
        return 1 - len(route_A_edges & route_B_edges) / len(route_A_edges | route_B_edges)