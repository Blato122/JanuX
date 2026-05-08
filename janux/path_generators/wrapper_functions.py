import networkx as nx
import pandas as pd

from typing import Callable

########################## Basic Path Generator ##########################

from .basic_generator import BasicPathGenerator

def basic_generator(network: nx.DiGraph,
                    origins: list[str], 
                    destinations: list[str],
                    as_df: bool = False,
                    calc_free_flow: bool = False,
                    **kwargs) -> pd.DataFrame:
    generator = BasicPathGenerator(network, origins, destinations, **kwargs)
    return generator.generate_routes(as_df=as_df, calc_free_flow=calc_free_flow)

###########################################################################

######################### Extended Path Generator #########################

from .extended_generator import ExtendedPathGenerator

def extended_generator(network: nx.DiGraph,
                       origins: list[str],
                       destinations: list[str],
                       as_df: bool = False,
                       calc_free_flow: bool = False,
                       **kwargs) -> pd.DataFrame:
    generator = ExtendedPathGenerator(network, origins, destinations, **kwargs)
    return generator.generate_routes(as_df=as_df, calc_free_flow=calc_free_flow)

###########################################################################

######################### Clustering Path Generator #########################

from .clustering_generator import ClusteringPathGenerator

def clustering_generator(network: nx.DiGraph,
                         origins: list[str],
                         destinations: list[str],
                         as_df: bool = False,
                         calc_free_flow: bool = False,
                         **kwargs) -> pd.DataFrame:
    generator = ClusteringPathGenerator(network, origins, destinations, **kwargs)
    return generator.generate_routes(as_df=as_df, calc_free_flow=calc_free_flow)
###########################################################################

######################### Heuristic Path Generator ########################

from .heuristic_based_generator import HeuristicPathGenerator

def heuristic_generator(network: nx.DiGraph,
                        origins: list[str],
                        destinations: list[str],
                        heuristics: list[Callable],
                        heur_weights: list[float],
                        as_df: bool = False,
                        calc_free_flow: bool = False,
                        **kwargs) -> pd.DataFrame:
    generator = HeuristicPathGenerator(network, origins, destinations, heuristics, heur_weights, **kwargs)
    return generator.generate_routes(as_df=as_df, calc_free_flow=calc_free_flow)

###########################################################################