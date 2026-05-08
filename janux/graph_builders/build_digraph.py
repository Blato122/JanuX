import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.getcwd(), './')))

import lxml
import networkx as nx
import pandas as pd

from bs4 import BeautifulSoup
from typing import Tuple

from janux.utils import remove_double_quotes


#################################################

def build_digraph(connection_file: str, edge_file: str, route_file: str, use_clustered_routes : bool = False) -> nx.DiGraph:
    """
    Generates a traffic network graph from XML files.

    Args:
        connection_file (str): Path to the connection XML file.
        edge_file (str): Path to the edge XML file.
        route_file (str): Path to the route XML file.
        use_clustered_routes (bool): Whether to use clustering-routes-compatible version.

    Returns:
        nx.DiGraph: A directed graph representing the traffic network.

    Raises:
        FileNotFoundError: If any of the input files are not found.
        ValueError: If required data is missing in the input files.
    """
    try:
        # Process connections
        if use_clustered_routes:
            connections_df = _process_connection_file_clustering(connection_file)
        else:
            connections_df = _process_connection_file(connection_file)

        # Process edge attributes
        if use_clustered_routes:
            edge_attributes_df = _process_edge_file_clustering(edge_file)
        else:
            edge_attributes_df = _process_edge_file(edge_file)

        # Process route attributes
        route_attributes_df = _process_route_file(route_file)

        # Merge all DataFrames and calculate travel times
        network_df = _merge_network_data(connections_df, edge_attributes_df, route_attributes_df)
        network_df = network_df.mask(network_df.astype(object).eq('None')).dropna()

        # Create and return directed graph
        traffic_network_graph = nx.from_pandas_edgelist(
            network_df,
            source='source_edge',
            target='target_edge',
            edge_attr='travel_time',
            create_using=nx.DiGraph()
        )

        if use_clustered_routes:
            def junction_id(node_id: str | None) -> str | None:
                if node_id is None:
                    return None
                node_id = str(node_id)
                if node_id.startswith(":"):
                    # internal SUMO node/junction id like ":123_0" -> "123"
                    return node_id[1:].split("_")[0]            
                return node_id

            node_attrs = {}
            for row in edge_attributes_df.itertuples(index=False):
                if row.edge_id not in traffic_network_graph:
                    continue

                # There might be multiple connections between nodes. Currently, all are blocked
                segment_key = (min(row.from_node, row.to_node), max(row.from_node, row.to_node))

                node_attrs[row.edge_id] = {
                    "from_node": row.from_node,
                    "to_node": row.to_node,
                    "segment_key": segment_key,
                    "undir_key": segment_key,
                    "junction_from": junction_id(row.from_node),
                    "junction_to": junction_id(row.to_node),
                    "is_internal_edge": str(row.edge_id).startswith(":"),
                    "is_cluster_edge": str(row.edge_id).startswith("cluster"),
                }
            
            nx.set_node_attributes(traffic_network_graph, node_attrs)

        return traffic_network_graph

    except FileNotFoundError as e:
        print(f"File not found: {e}")
        raise
    except Exception as e:
        print(f"An error occurred: {e}")
        raise
    
#################################################


def _process_connection_file(connection_file: str) -> pd.DataFrame:
    """Parses the connection XML file and returns a DataFrame."""
    from_df, to_df = _read_xml_file(connection_file, 'connection', 'from', 'to')
    connections_df = pd.merge(from_df, to_df, left_index=True, right_index=True)
    connections_df = connections_df.rename(columns={'0_x': 'source_edge', '0_y': 'target_edge'})
    return connections_df

def _process_edge_file_clustering(edge_file: str) -> pd.DataFrame:
    """Parses the edge XML file and returns a DataFrame with edge attributes."""
    # uses new read xml file function and new column names (instead of 0x and 0y)
    df = _read_xml_file_clustering(edge_file, 'edge', 'id', 'from', 'to')
    return df.rename(columns={'id': 'edge_id', 'from': 'from_node', 'to': 'to_node'})

def _process_edge_file(edge_file: str) -> pd.DataFrame:
    """Parses the edge XML file and returns a DataFrame with edge attributes."""
    edge_ids_df, edge_sources_df = _read_xml_file(edge_file, 'edge', 'id', 'from')
    edge_attributes_df = pd.merge(edge_sources_df, edge_ids_df, right_index=True, left_index=True)
    edge_attributes_df = edge_attributes_df.rename(columns={'0_x': 'source_node', '0_y': 'edge_id'})
    edge_attributes_df['source_node'] = edge_attributes_df['source_node'].apply(remove_double_quotes)
    edge_attributes_df['edge_id'] = edge_attributes_df['edge_id'].apply(remove_double_quotes)
    return edge_attributes_df

def _process_connection_file_clustering(connection_file: str) -> pd.DataFrame:
    """Parses the connection XML file and returns a DataFrame."""
    df = _read_xml_file_clustering(connection_file, 'connection', 'from', 'to')
    return df.rename(columns={'from': 'source_edge', 'to': 'target_edge'})

def _process_route_file(route_file: str) -> pd.DataFrame:
    """Parses the route XML file and returns a DataFrame with route attributes."""
    with open(route_file, 'r') as route_file_obj:
        route_xml_data = route_file_obj.read()
    route_xml_parsed = BeautifulSoup(route_xml_data, "xml")
    edges = route_xml_parsed.find_all('edge', {'to': True})

    # Extract attributes from route XML
    route_attributes_df = pd.DataFrame({
        'edge_id': [edge.get('id') for edge in edges],
        'length': [edge.find('lane').get('length') for edge in edges],
        'speed': [edge.find('lane').get('speed') for edge in edges]
    })
    return route_attributes_df


def _merge_network_data(
    connections_df: pd.DataFrame,
    edge_attributes_df: pd.DataFrame,
    route_attributes_df: pd.DataFrame
) -> pd.DataFrame:
    """Merges connection, edge, and route DataFrames and calculates travel times."""
    edge_route_merged_df = pd.merge(edge_attributes_df, route_attributes_df, on='edge_id', how='inner')
    network_df = pd.merge(edge_route_merged_df, connections_df, left_on='edge_id', right_on='source_edge', how='inner')

    # Calculate travel time (in minutes)
    network_df['travel_time'] = (network_df['length'].astype(float) / network_df['speed'].astype(float)) / 60
    network_df = network_df[['source_edge', 'target_edge', 'travel_time']]  # Keep only required columns
    return network_df


def _read_xml_file(file_path: str, element_name: str, attr1: str, attr2: str) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """Reads an XML file and extracts two specified attributes."""
    with open(file_path, 'r') as f:
        data = f.read()
    parsed_xml = BeautifulSoup(data, "xml")
    elements = parsed_xml.find_all(element_name)

    attr1_values = [el.get(attr1) for el in elements]
    attr2_values = [el.get(attr2) for el in elements]

    return pd.DataFrame(attr1_values), pd.DataFrame(attr2_values)

def _read_xml_file_clustering(file_path: str, element_name: str, *attributes: str) -> pd.DataFrame:
    """Reads an XML file and extracts specified attributes into a Dataframe"""
    # 1+ attrs instead of 2, applies remove double quotes, returns 1 df
    with open(file_path, 'r') as f:
        data = f.read()
    parsed_xml = BeautifulSoup(data, "xml")
    elements = parsed_xml.find_all(element_name)

    data_map = {}
    for attr in attributes:
        data_map[attr] = [remove_double_quotes(el.get(attr)) for el in elements]

    return pd.DataFrame(data_map).dropna()