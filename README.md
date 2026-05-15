[![DOI](https://zenodo.org/badge/889013393.svg)](https://doi.org/10.5281/zenodo.20204628)
![PyPI - Version](https://img.shields.io/pypi/v/janux)
![GitHub License](https://img.shields.io/github/license/COeXISTENCE-PROJECT/janux)
![GitHub Release](https://img.shields.io/github/v/release/COeXISTENCE-PROJECT/janux)
![PyPI - Downloads](https://img.shields.io/pypi/dm/janux)


# Welcome to JanuX. Routing starts here.

<img src="https://raw.githubusercontent.com/COeXISTENCE-PROJECT/JanuX/refs/heads/main/graphics/janux_logo_bg.png" alt="JanuX Logo" align="right" width="200">

**Janus**, the Roman god of beginnings, transitions and duality, is known for his two faces. In Roman mythology, he symbolizes direction, beginnings, ends and contrasts.

---

**JanuX** is not a Roman god, but it is a robust yet simple tool for generating a set of path options in directed [NetworkX](https://networkx.org/en/) graphs. It is designed for efficient routing or creating path options for custom requirements.

---

## Installation

JanuX works with Python 3.6+.

- Install from PyPI:

```bash
pip install janux
```

- Or install from source:

```bash
git clone https://github.com/COeXISTENCE-PROJECT/JanuX.git
cd JanuX
pip install -r requirements.txt
pip install -e .
```

---

## Repository Layout

```text
JanuX/
|-- janux/                         
|   |-- graph_builders/            build directed graphs from SUMO network files
|   |-- path_generators/           path generators, wrappers, and helper utilities
|   |-- visualizers/               plotting and animation tools
|   |-- utils.py                   shared helpers
|-- examples/
|   |-- network_files/             sample SUMO networks and OD data for Cologne, Csomor, and Ingolstadt
|   |-- path_generation_examples/  runnable path-generation scripts
|   |-- visualization_examples/    runnable plotting and animation scripts
|-- graphics/                      docs assets
|-- pyproject.toml                 package metadata and build configuration
|-- requirements.txt               dependency list for source installs
|-- CITATION.cff                   citation metadata
|-- LICENSE.txt                    MIT license
|-- README.md                      project overview, installation, and usage notes
```

---

### Path Generators

The [`janux/path_generators`](janux/path_generators) package includes four route-generation strategies:

| Generator | Best for | What it adds |
| --- | --- | --- |
| [`basic_generator`](janux/path_generators/basic_generator.py) | getting started with candidate route sampling | logit-style probabilistic path generation |
| [`extended_generator`](janux/path_generators/extended_generator.py) | adding more control to sampled routes | loop handling, path-length limits, and adaptive parameter shifting |
| [`heuristic_generator`](janux/path_generators/heuristic_based_generator.py) | choosing route sets with custom criteria | scores sampled route sets with user-defined heuristics and weights |
| [`clustering_generator`](janux/path_generators/clustering_generator.py) | building structurally distinct alternatives | avoids repeated road segments and junction revisits, and can favor less similar routes |

All generators share a similar interface and can return either raw route sets or DataFrame outputs, with optional free-flow travel times.

---

### Usage

Here is a minimal example using [`extended_generator`](janux/path_generators/extended_generator.py):

```python
import janux as jx

network = jx.build_digraph(
    "path/to/network.con.xml",
    "path/to/network.edg.xml",
    "path/to/network.rou.xml",
)

origins = ["origin_edge_id"]
destinations = ["destination_edge_id"]

routes = jx.extended_generator(
    network,
    origins,
    destinations,
    as_df=True,
    calc_free_flow=True,
    number_of_paths=3,
    num_samples=300,
    beta=-3,
    adaptive=True,
)

print(routes[["origins", "destinations", "path"]].head())
```

This returns a pandas DataFrame with `origins`, `destinations`, `path`, and optionally `free_flow_time`. Set `as_df=False` if you prefer the raw route dictionary instead. For a fuller runnable example using the bundled sample networks, see [`extended_example.py`](examples/path_generation_examples/extended_example.py).

---

## Examples

Two small scripts are a good starting point:

##### Path generation: 
```bash
python examples/path_generation_examples/basic_example.py
```
- Builds a sample network, generates multiple candidate paths for each origin-destination pair, saves the routes as CSV, and can also write route plots to `examples/figures/`.

##### Visualization: 
```bash
python examples/visualization_examples/single_route_visualization.py
```
  - Draws one route on top of a sample network and saves the figure to `examples/figures/`.

Both scripts use the sample files in `examples/network_files/`, so they should run directly after installing the package.

## Gallery

| ![Image1](https://raw.githubusercontent.com/COeXISTENCE-PROJECT/JanuX/refs/heads/main/graphics/gallery/a.png) | ![Image2](https://raw.githubusercontent.com/COeXISTENCE-PROJECT/JanuX/refs/heads/main/graphics/gallery/b.png) |
|------------------------|-----------------------|
| ![Image3](https://raw.githubusercontent.com/COeXISTENCE-PROJECT/JanuX/refs/heads/main/graphics/gallery/c.png) | ![Image4](https://raw.githubusercontent.com/COeXISTENCE-PROJECT/JanuX/refs/heads/main/graphics/gallery/d.png) |

---

![Image5](https://raw.githubusercontent.com/COeXISTENCE-PROJECT/JanuX/refs/heads/main/graphics/gallery/e.gif)

---

### JanuX appears in

<p align="center">
  <a href="https://github.com/COeXISTENCE-PROJECT/RouteRL">
    <img src="https://raw.githubusercontent.com/aonurakman/assets/refs/heads/main/icons/routerl_modern_cropped.png" alt="RouteRL" height="50"/>
  </a>
  &nbsp;&nbsp;&nbsp;&nbsp;
  <a href="https://github.com/COeXISTENCE-PROJECT/URB">
    <img src="https://raw.githubusercontent.com/COeXISTENCE-PROJECT/URB/main/docs/urb.png" alt="URB" height="60"/>
  </a>
</p>

<p align="center">
  JanuX supports
  <a href="https://github.com/COeXISTENCE-PROJECT/RouteRL"><strong>RouteRL</strong></a>
  and
  <a href="https://github.com/COeXISTENCE-PROJECT/URB"><strong>URB</strong></a>,
  with accompanying papers in
  <a href="https://www.sciencedirect.com/science/article/pii/S2352711025002468"><em>SoftwareX</em></a>
  and
  <a href="https://proceedings.neurips.cc/paper_files/paper/2025/hash/77e5b98de7d7060bc7c57d7943b53d8f-Abstract-Datasets_and_Benchmarks_Track.html"><em>NeurIPS</em></a>.
</p>

---

### Citation

If you use this repository, please cite it using the following BibTeX:

```bibtex
@software{JanuX,
  author = {Akman, Ahmet Onur and Torbus, Błażej},
  title = {{JanuX}},
  doi = {https://doi.org/10.5281/zenodo.20204628},
  url = {https://github.com/COeXISTENCE-PROJECT/JanuX},
  version = {1.1.0},
  month = may,
  year = {2026}
}
