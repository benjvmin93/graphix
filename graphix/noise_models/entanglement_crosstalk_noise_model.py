from __future__ import annotations

import warnings
from itertools import combinations
from typing import TYPE_CHECKING

import networkx as nx
import typing_extensions

from graphix.channels import KrausChannel
from graphix.command import Command, CommandKind
from graphix.noise_models.noise_model import Noise, NoiseModel
from graphix.rng import ensure_rng

if TYPE_CHECKING:
    from numpy.random import Generator


class EntanglementCrossTalkNoiseModel(NoiseModel):
    """Entanglement cross talk noise model.

    Tracks the entangled neighbors of each node using a state graph.
    Apply channels specified in `channel_selector`. Each channel must be a 1 qubit channel.
    The entries within `channel_selector` are CommandKind and the `input` literal.
    """

    def __init__(
        self,
        channel_specifier: dict[Literal["input"] | CommandKind, KrausChannel],
        rng: Generator = None,
        input_graph: nx.Graph = None,
    ) -> None:
        self._state_graph: nx.Graph = (
            input_graph if input_graph is not None else nx.Graph()
        )  # Global tracking of the neighbors (entanglement)
        self.rng = ensure_rng(rng)

        for key, channel in channel_specifier.items():
            if channel.nqubit != 1:
                raise AttributeError(f"Cannot instantiate entanglement cross talk with channels for more than 1 qubit.")
        self.channel_specifier = channel_specifier

    def input_nodes(
        self,
        nodes: list[int],
    ) -> Noise:
        """Return the noise to apply to the input's neighbors.

        For each nodes, check if they have neighbors and
        compose the noise with the channel applied on each of these nodes.
        """
        self._state_graph.add_nodes_from(nodes)
        noise = Noise()
        channel = self.channel_specifier.get("input")
        if channel == None: # Channel is not specified in the channel_specifier
            return noise

        for n in nodes:  # Iterate through each nodes
            neighbors = list(self._state_graph.neighbors(n))
            noise.extend([(channel, neighb) for neighb in neighbors])

        return noise

    def command(self, cmd: Command) -> Noise:
        """Return the noise to apply to the command `cmd`.

        N: adds a node to the state graph.
        E: adds an edge to the state graph returns noise applied to each neighbors.
        M: removes a node from the state graph and returns noise applied to each neighbors.
        other commands: returns noise applied to each neighbors.
        """
        kind = cmd.kind
        channel = self.channel_specifier.get(kind)
        if channel == None: # Channel is not specified in the channel_specifier
            return Noise()

        neighbors = []

        if kind == CommandKind.N:
            self._state_graph.add_node(cmd.node)
            return Noise()  # Return empty noise since we just prepared this node. Thus, it is not entangled with any other node.

        elif kind == CommandKind.E:
            self._state_graph.add_edge(cmd.nodes[0], cmd.nodes[1])  # Update entanglement state graph.

            neighbors_first = set(self._state_graph.neighbors(cmd.nodes[0]))
            neighbors_second = set(self._state_graph.neighbors(cmd.nodes[1]))
            neighbors += list(neighbors_first | neighbors_second)   # Union of the sets turned into a list.

        else:  # M, X, Z, C, T commands
            neighbors = self._state_graph.neighbors(cmd.node)

            if kind == CommandKind.M:
                self._state_graph.remove_node(cmd.node) # Remove the node if measurement command.

        return Noise([(channel, neighb) for neighb in neighbors])

    def confuse_result(self, result: bool) -> bool:
        """Assign wrong measurement result."""
        return result
