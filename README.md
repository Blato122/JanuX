[![DOI](https://zenodo.org/badge/889013393.svg)](https://doi.org/10.5281/zenodo.17422815)
![PyPI - Version](https://img.shields.io/pypi/v/janux)
![GitHub License](https://img.shields.io/github/license/COeXISTENCE-PROJECT/janux)
![GitHub Release](https://img.shields.io/github/v/release/COeXISTENCE-PROJECT/janux)
![PyPI - Downloads](https://img.shields.io/pypi/dm/janux)


# JanuX

<img src="graphics/janux_logo.png" alt="JanuX Logo" align="right" width="200">

**Janus**, the Roman god of beginnings, transitions and duality, is known for his two faces. In Roman mythology, he symbolizes direction, beginnings, ends and contrasts.

---

**JanuX** is not a Roman god, but it is a robust yet simple tool for generating a set of path options in directed graphs. It is designed for efficient routing or creating path options for custom requirements.

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

- `janux/graph_builders`: build directed graphs from SUMO-style network files and edge data.
- `janux/path_generators`: basic, extended, clustering, and heuristic path generators plus OD utilities.
- `janux/visualizers`: visualization scripts for routes, edge attributes, congestion, and animations.
- `examples/path_generation_examples`: small scripts showing how to generate paths.
- `examples/visualization_examples`: scripts for plotting and animation examples.
- `examples/network_files`: sample networks, routes, and OD inputs used by the examples.
- `graphics/`: logo and gallery assets used in this README.

---

## Used By

- [RouteRL](https://github.com/COeXISTENCE-PROJECT/RouteRL) and [URB](https://github.com/COeXISTENCE-PROJECT/URB): use JanuX in a route-generation pipeline for vehicle routing experiments and benchmark scenarios.

<p align="center">
  <a href="https://github.com/COeXISTENCE-PROJECT/RouteRL">
    <img src="https://raw.githubusercontent.com/COeXISTENCE-PROJECT/RouteRL/main/docs/_static/logo.png" alt="RouteRL" width="180"/>
  </a>
  <a href="https://github.com/COeXISTENCE-PROJECT/URB">
    <img src="https://raw.githubusercontent.com/COeXISTENCE-PROJECT/URB/main/docs/urb.png" alt="URB" width="180"/>
  </a>
</p>

---

## Examples

Two small scripts are a good starting point:

- Path generation: `python examples/path_generation_examples/basic_example.py`
  - Builds a sample network, generates multiple candidate paths for each origin-destination pair, saves the routes as CSV, and can also write route plots to `examples/figures/`.
- Visualization: `python examples/visualization_examples/single_route_visualization.py`
  - Draws one route on top of a sample network and saves the figure to `examples/figures/`.

Both scripts use the sample files in `examples/network_files/`, so they should run directly after installing the package.

## Gallery

| ![Image1](graphics/gallery/a.png) | ![Image2](graphics/gallery/b.png) |
|------------------------|-----------------------|
| ![Image3](graphics/gallery/c.png) | ![Image4](graphics/gallery/d.png) |

---

![Image5](graphics/gallery/e.gif)

---

## License

This project is licensed under the [MIT License](LICENSE.txt).

---

## Citation

If you use this repository, please cite it using the following BibTeX:

```bibtex
@software{JanuX,
  author = {Akman, Ahmet Onur and Torbus, Błażej},
  title = {{JanuX}},
  doi = {https://doi.org/10.5281/zenodo.17422816},
  url = {https://github.com/COeXISTENCE-PROJECT/JanuX},
  version = {1.1.0},
  month = may,
  year = {2026}
}
