# import os
# import sys

# sys.path.append(os.path.abspath(os.path.join(os.getcwd(), './')))

# import matplotlib.pyplot as plt
# import networkx as nx

# from typing import Union, Tuple

# from janux.visualizers.visualization_utils import create_graph
# from janux.visualizers.visualization_utils import get_colors
# from janux.visualizers.visualization_utils import parse_network_files
# from janux.visualizers.visualization_utils import shift_edge_by_offset


# #################################################

# def show_multi_routes(nod_file_path: str, 
#                       edg_file_path: str, 
#                       paths: list[list[str]], 
#                       origin: str, 
#                       destination: str, 
#                       **kwargs):
#     """
#     Displays a visualization of multiple routes on a graph derived from the given node and edge files.

#     Parameters:
#     -----------
#     nod_file_path : str
#         Path to the node file containing node definitions in XML format.
#     edg_file_path : str
#         Path to the edge file containing edge definitions in XML format.
#     paths : list[list[str]]
#         A list of routes, where each route is a list of edge IDs to be visualized.
#     origin : str
#         The edge ID for the origin of the routes.
#     destination : str
#         The edge ID for the destination of the routes.
#     **kwargs : dict
#         Additional keyword arguments passed to `visualize_paths` for customization.

#     Keyword Arguments (`kwargs`):
#     -----------------------------
#     show : bool, default=True
#         Whether to display the plot.
#     save_file_path : str | None, default=None
#         File path to save the generated plot as an image. If None, the plot is not saved.
#     title : str, default="Path Visualization"
#         Title of the plot window and saved figure.
#     cmap_names : list[str], default=['Reds', 'Blues', 'Greens', 'Oranges', 'Greys', 'Purples', 'copper', 'pink']
#         List of colormap names used to color the paths. Each path will use a different colormap.
#     offsets : list | None, default=None
#         List of offsets to shift each route for better visualization. If None, offsets are calculated automatically (recommended).
#     fig_size : tuple[int], default=(12, 8)
#         Size of the figure (width, height) in inches.
#     autocrop : bool, default=True
#         Whether to crop the figure to focus on the paths and reduce unnecessary whitespace.
#     autocrop_margin : float, default=10
#         Margin in data units to add around the autocropped view.
#     xcrop : tuple[float, float] | None, default=None
#         Fixed x-axis range for the plot. Overriden by `autocrop`.
#     ycrop : tuple[float, float] | None, default=None
#         Fixed y-axis range for the plot. Overriden by `autocrop`.
#     node_size : int, default=10
#         Size of the nodes in the plot.
#     node_color : str, default='lightblue'
#         Color of the nodes in the plot.
#     path_width : int, default=4
#         Width of the edges that represent the paths in the plot.

#     Returns:
#     --------
#     None
#         Displays the visualization of the routes and optionally saves it to a file.

#     Notes:
#     ------
#     - The function parses the given node and edge files to create a graph representation.
#     - The `visualize_paths` function is used internally to handle the visualization.
#     - The origin and destination edges are highlighted in the plot.
#     """
#     # Parse the network
#     nodes, edges = parse_network_files(nod_file_path, edg_file_path)
#     graph = create_graph(nodes, edges)
#     # Visualize the path
#     visualize_paths(graph, paths, origin, destination, **kwargs)
    
# #################################################


# def visualize_paths(graph: nx.DiGraph, paths: list[list[str]], origin_edge: str, destination_edge: str,
#                    show: bool = True,
#                    save_file_path: Union[str, None] = None,
#                    title: str = "Path Visualization",
#                    cmap_names: list[str] = ['Reds', 'Blues', 'Greens', 'Oranges', 'Greys', 'Purples', 'copper', 'pink'],
#                    offsets: Union[list, None] = None,
#                    fig_size: tuple[int] = (12, 8),
#                    autocrop: bool = True,
#                    autocrop_margin: float = 10,
#                    xcrop: Union[Tuple[float, float], None] = None,
#                    ycrop: Union[tuple[float, float], None] = None,
#                    node_size: int = 10,
#                    node_color: str = 'lightblue',
#                    path_width: int = 4) -> None:
    
#     if offsets is None:
#         margin_between_paths = path_width/5
#         offsets = [((path_width/2)+margin_between_paths) + ((path_width+margin_between_paths) * i) for i in range(len(paths))]
    
#     # Initilize the figure
#     plt.figure(figsize=fig_size)
    
#     # Get node positions
#     node_positions = nx.get_node_attributes(graph, 'pos')
    
#     # Draw the full network
#     nx.draw(graph, node_positions, node_size=node_size, node_color=node_color, style='--', edge_color='gray', arrows=False)

#     # Highlight OD edges with bold black arrows
#     origin_coords, dest_coords = None, None
#     for source_node, target_node, edge_id in graph.edges(data=True):
#         if edge_id['edge_id'] == origin_edge:
#             origin_coords = (source_node, target_node)
#             if dest_coords is not None: break
#         elif edge_id['edge_id'] == destination_edge:
#             dest_coords = (source_node, target_node)
#             if origin_coords is not None: break  
#     assert origin_coords is not None, f"Origin {origin_edge} is not found in the network."
#     assert dest_coords is not None, f"Destination {destination_edge} is not found in the network."
    
#     # Autocropping limits
#     x_max, x_min, y_max, y_min = float('-inf'), float('inf'), float('-inf'), float('inf')
    
#     # Legend artists
#     artists = []
    
#     # Draw the paths
#     for path_idx, path_edges in enumerate(paths):
#         # Get the edge IDs and source-target nodes in the path
#         path_edges_graph = {data_dict['edge_id']: (source, target) for source, target, data_dict in graph.edges(data=True)
#                             if data_dict['edge_id'] in path_edges}
#         # Get colormap
#         cmap_name = cmap_names[path_idx % len(cmap_names)]
#         colors = get_colors(len(path_edges), cmap_name)
        
#         # Draw the path edges one by one
#         for edge_id, (source_node, target_node) in path_edges_graph.items():
#             # Shift the edge by the offset
#             new_pos = shift_edge_by_offset(node_positions, source_node, target_node, offsets[path_idx])
#             # Draw the edge
#             color = colors[path_edges.index(edge_id)]
#             # Draw the lane
#             nx.draw_networkx_edges(graph, new_pos, edgelist=[(source_node, target_node)], edge_color=[color], width=path_width)
            
#             if autocrop:
#                 # Update the cropping limits
#                 x_max = max(x_max, new_pos[source_node][0], new_pos[target_node][0])
#                 x_min = min(x_min, new_pos[source_node][0], new_pos[target_node][0])
#                 y_max = max(y_max, new_pos[source_node][1], new_pos[target_node][1])
#                 y_min = min(y_min, new_pos[source_node][1], new_pos[target_node][1])
        
#         # Create a legend artist with representative color from the path
#         artist = plt.Line2D([0], [0], color=colors[len(colors)//2], lw=path_width, label=f"Path {path_idx}")
#         artists.append(artist)
        
#     # Crop the figure if requested
#     if autocrop:
#         # Determine the aspect ratio of the ranges
#         x_range_length = x_max - x_min
#         y_range_length = y_max - y_min
#         cropped_aspect_ratio = y_range_length / x_range_length
        
#         fig_width, fig_height = fig_size  # Base figure size
#         fig_aspect_ratio = fig_height / fig_width
#         if cropped_aspect_ratio > fig_aspect_ratio:
#             # Cropped aspect ratio is taller than the base aspect ratio
#             x_range_length_new = (cropped_aspect_ratio / fig_aspect_ratio) * x_range_length
#             difference = x_range_length_new - x_range_length
#             # Expand the image on x axis
#             x_max += difference / 2
#             x_min -= difference / 2
#         else:
#             # Cropped aspect ratio is wider than the base aspect ratio
#             y_range_length_new = (fig_aspect_ratio / cropped_aspect_ratio) * y_range_length
#             difference = y_range_length_new - y_range_length
#             # Expand the image on y axis
#             y_max += difference / 2
#             y_min -= difference / 2

#         # Set plot limits
#         plt.xlim(x_min - autocrop_margin, x_max + autocrop_margin)
#         plt.ylim(y_min - autocrop_margin, y_max+autocrop_margin)
#     else:    
#         if xcrop is not None:
#             plt.xlim(xcrop)
#         if ycrop is not None:
#             plt.ylim(ycrop)
            
#     # Set the title and show the plot
#     plt.title(title)
#     plt.legend(handles=artists)
#     fig = plt.gcf()   # Get the current figure
#     fig.canvas.manager.set_window_title(title)
    
#     # Save the plot if requested
#     if save_file_path is not None:
#         plt.savefig(save_file_path, bbox_inches='tight', dpi=300)
        
#     if show:
#         plt.show()
        
#     plt.close()

import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.getcwd(), './')))

import matplotlib.pyplot as plt
import networkx as nx

from typing import Union, Tuple

from janux.visualizers.visualization_utils import create_graph
from janux.visualizers.visualization_utils import get_colors
from janux.visualizers.visualization_utils import parse_network_files
from janux.visualizers.visualization_utils import shift_edge_by_offset


#################################################

def show_multi_routes(nod_file_path: str, 
                      edg_file_path: str, 
                      paths: list[list[str]], 
                      origin: str, 
                      destination: str, 
                      **kwargs):
    """
    Displays a visualization of multiple routes on a graph derived from the given node and edge files.

    Parameters:
    -----------
    nod_file_path : str
        Path to the node file containing node definitions in XML format.
    edg_file_path : str
        Path to the edge file containing edge definitions in XML format.
    paths : list[list[str]]
        A list of routes, where each route is a list of edge IDs to be visualized.
    origin : str
        The edge ID for the origin of the routes.
    destination : str
        The edge ID for the destination of the routes.
    **kwargs : dict
        Additional keyword arguments passed to `visualize_paths` for customization.

    Keyword Arguments (`kwargs`):
    -----------------------------
    show : bool, default=True
        Whether to display the plot.
    save_file_path : str | None, default=None
        File path to save the generated plot as an image. If None, the plot is not saved.
    title : str, default="Path Visualization"
        Title of the plot window and saved figure.
    cmap_names : list[str], default=['Reds', 'Blues', 'Greens', 'Oranges', 'Greys', 'Purples', 'copper', 'pink']
        List of colormap names used to color the paths. Each path will use a different colormap.
    offsets : list | None, default=None
        List of offsets to shift each route for better visualization. If None, offsets are calculated automatically (recommended).
    fig_size : tuple[int], default=(12, 8)
        Size of the figure (width, height) in inches.
    autocrop : bool, default=True
        Whether to crop the figure to focus on the paths and reduce unnecessary whitespace.
    autocrop_margin : float, default=10
        Margin in data units to add around the autocropped view.
    xcrop : tuple[float, float] | None, default=None
        Fixed x-axis range for the plot. Overriden by `autocrop`.
    ycrop : tuple[float, float] | None, default=None
        Fixed y-axis range for the plot. Overriden by `autocrop`.
    node_size : int, default=10
        Size of the nodes in the plot.
    node_color : str, default='lightblue'
        Color of the nodes in the plot.
    path_width : int, default=4
        Width of the edges that represent the paths in the plot.

    Returns:
    --------
    None
        Displays the visualization of the routes and optionally saves it to a file.

    Notes:
    ------
    - The function parses the given node and edge files to create a graph representation.
    - The `visualize_paths` function is used internally to handle the visualization.
    - The origin and destination edges are highlighted in the plot.
    """
    # Parse the network
    nodes, edges = parse_network_files(nod_file_path, edg_file_path)
    graph = create_graph(nodes, edges)
    # Visualize the path
    visualize_paths(graph, paths, origin, destination, **kwargs)
    
#################################################


def visualize_paths(graph: nx.DiGraph, paths: list[list[str]], origin_edge: str, destination_edge: str,
                   show: bool = True,
                   save_file_path: Union[str, None] = None,
                   title: str = "Path Visualization",
                   cmap_names: list[str] = ['Reds', 'Blues', 'Greens', 'Oranges', 'Greys', 'Purples', 'copper', 'pink'],
                   offsets: Union[list, None] = None,
                   fig_size: tuple[int, int] = (12, 8),
                   autocrop: bool = True,
                   autocrop_margin: float = 10,
                   xcrop: Union[Tuple[float, float], None] = None,
                   ycrop: Union[tuple[float, float], None] = None,
                   node_size: int = 10,
                   node_color: str = 'lightblue',
                   path_width: int = 4,
                   # NEW:
                   show_edge_ids: bool = True,
                   edge_id_scope: str = "all",   # "all" or "paths"
                   edge_id_fontsize: int = 6,
                   edge_id_color: str = "black",
                   edge_id_alpha: float = 0.5,
                   edge_id_offset: float = 0) -> None:
    
    if offsets is None:
        margin_between_paths = path_width/5
        offsets = [((path_width/2)+margin_between_paths) + ((path_width+margin_between_paths) * i) for i in range(len(paths))]
    
    # Initilize the figure
    plt.figure(figsize=fig_size)
    
    # Get node positions
    node_positions = nx.get_node_attributes(graph, 'pos')
    
    # Draw the full network
    nx.draw(graph, node_positions, node_size=node_size, node_color=node_color, style='--', edge_color='gray', arrows=True) # NEW: arrows=True

    # NEW:
    ax = plt.gca()

    def _annotate_edge(u, v, text: str, offset: float = 0.0):
        (x1, y1) = node_positions[u]
        (x2, y2) = node_positions[v]
        mx, my = (x1 + x2) / 2.0, (y1 + y2) / 2.0

        if offset:
            dx, dy = (x2 - x1), (y2 - y1)
            L = (dx * dx + dy * dy) ** 0.5 or 1.0
            mx += (-dy / L) * offset
            my += ( dx / L) * offset

        ax.text(
            mx, my, text,
            fontsize=edge_id_fontsize,
            color=edge_id_color,
            alpha=edge_id_alpha,
            ha="center", va="center",
            bbox=dict(facecolor="white", edgecolor="none", alpha=0.6, pad=0.2),
            zorder=5,
        )

    if show_edge_ids:
        if edge_id_scope not in ("all", "paths"):
            raise ValueError("edge_id_scope must be 'all' or 'paths'")

        path_edge_ids = set(eid for p in paths for eid in p) if edge_id_scope == "paths" else None

        for u, v, data in graph.edges(data=True):
            eid = data.get("edge_id")
            if not eid:
                continue
            if path_edge_ids is not None and eid not in path_edge_ids:
                continue
            # _annotate_edge(u, v, eid, offset=edge_id_offset)

    # Highlight OD edges with bold black arrows
    origin_coords, dest_coords = None, None
    for source_node, target_node, edge_id in graph.edges(data=True):
        if edge_id['edge_id'] == origin_edge:
            origin_coords = (source_node, target_node)
            if dest_coords is not None: break
        elif edge_id['edge_id'] == destination_edge:
            dest_coords = (source_node, target_node)
            if origin_coords is not None: break  
    assert origin_coords is not None, f"Origin {origin_edge} is not found in the network."
    assert dest_coords is not None, f"Destination {destination_edge} is not found in the network."
    
    # Autocropping limits
    x_max, x_min, y_max, y_min = float('-inf'), float('inf'), float('-inf'), float('inf')
    
    # Legend artists
    artists = []
    
    # Draw the paths
    for path_idx, path_edges in enumerate(paths):
        # Get the edge IDs and source-target nodes in the path
        path_edges_graph = {data_dict['edge_id']: (source, target) for source, target, data_dict in graph.edges(data=True)
                            if data_dict['edge_id'] in path_edges}
        # Get colormap
        cmap_name = cmap_names[path_idx % len(cmap_names)]
        colors = get_colors(len(path_edges), cmap_name)
        
        # Draw the path edges one by one
        for edge_id, (source_node, target_node) in path_edges_graph.items():
            # Shift the edge by the offset
            new_pos = shift_edge_by_offset(node_positions, source_node, target_node, offsets[path_idx])
            # Draw the edge
            color = colors[path_edges.index(edge_id)]
            # Draw the lane
            nx.draw_networkx_edges(graph, new_pos, edgelist=[(source_node, target_node)], edge_color=[color], width=path_width)
            
            if autocrop:
                # Update the cropping limits
                x_max = max(x_max, new_pos[source_node][0], new_pos[target_node][0])
                x_min = min(x_min, new_pos[source_node][0], new_pos[target_node][0])
                y_max = max(y_max, new_pos[source_node][1], new_pos[target_node][1])
                y_min = min(y_min, new_pos[source_node][1], new_pos[target_node][1])
        
        # Create a legend artist with representative color from the path
        artist = plt.Line2D([0], [0], color=colors[len(colors)//2], lw=path_width, label=f"Path {path_idx}")
        artists.append(artist)
        
    # Crop the figure if requested
    if autocrop:
        # Determine the aspect ratio of the ranges
        x_range_length = x_max - x_min
        y_range_length = y_max - y_min
        cropped_aspect_ratio = y_range_length / x_range_length
        
        fig_width, fig_height = fig_size  # Base figure size
        fig_aspect_ratio = fig_height / fig_width
        if cropped_aspect_ratio > fig_aspect_ratio:
            # Cropped aspect ratio is taller than the base aspect ratio
            x_range_length_new = (cropped_aspect_ratio / fig_aspect_ratio) * x_range_length
            difference = x_range_length_new - x_range_length
            # Expand the image on x axis
            x_max += difference / 2
            x_min -= difference / 2
        else:
            # Cropped aspect ratio is wider than the base aspect ratio
            y_range_length_new = (fig_aspect_ratio / cropped_aspect_ratio) * y_range_length
            difference = y_range_length_new - y_range_length
            # Expand the image on y axis
            y_max += difference / 2
            y_min -= difference / 2

        # Set plot limits
        plt.xlim(x_min - autocrop_margin, x_max + autocrop_margin)
        plt.ylim(y_min - autocrop_margin, y_max+autocrop_margin)
    else:    
        if xcrop is not None:
            plt.xlim(xcrop)
        if ycrop is not None:
            plt.ylim(ycrop)
            
    # Set the title and show the plot
    plt.title(title)
    plt.legend(handles=artists)
    fig = plt.gcf()   # Get the current figure
    fig.canvas.manager.set_window_title(title)
    
    # Save the plot if requested
    if save_file_path is not None:
        plt.savefig(save_file_path, bbox_inches='tight', dpi=300)
        
    if show:
        plt.show()
        
    plt.close()