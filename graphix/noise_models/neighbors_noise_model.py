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


class NeighborsNoiseModel(NoiseModel):
    """Neighbor noise model.

    Tracks the entangled neighbors of each node using a state graph.
    Apply channels specified in `channel_selector`.
    The entries within `channel_selector` are CommandKind.
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
        self.channel_specifier = channel_specifier

    def _noise_with_combinations(
        self, neighbors: list[int], channel: KraussChannel, noise: Noise | None = None
    ) -> Noise:
        """Return a noise applied on every combinations of the neighbors.

        If noise is defined, it will be extended. Otherwise it will be newly created.
        """
        if noise is None:
            noise = Noise()

        if channel.nqubit < len(neighbors):
            warnings.warn(f"Krauss channel with {channel.nqubit} qubits can not be applied to {len(neighbors)} qubits.")
            return noise

        neighbor_combinations = list(combinations(neighbors, channel.nqubit))  # Get all combinations of the neighbor nodes
        # print(f"neighbor combinations = {neighbor_combinations}")
        noise.extend(
            [(channel, list(comb)) for comb in neighbor_combinations]
        )  # Update noise by adding the channel with each combination

        return noise

    def input_nodes(
        self,
        nodes: list[int],
    ) -> Noise:
        """Return the noise to apply to the input nodes neighbors.

        For each nodes, check if they have neighbors.
        If so, compose the nodes on which the channel will be applied
        according to its number of qubits.
        """
        self._state_graph.add_nodes_from(nodes)
        channel = getattr(self.channel_specifier, "input", None)
        noise = Noise()

        if channel == None:
            return noise
        for n in nodes:  # ITerate through each nodes
            neighbors = list(self._state_graph.neighbors(n))

            if len(neighbors) == 0:
                continue

            noise = self._noise_with_combinations(neighbors, channel, noise)

        return noise

    def command(self, cmd: Command) -> Noise:
        """Return the noise to apply to the command `cmd`.

        N: adds a node to the state graph.
        E: adds an edge to the state graph.
        M: removes a node from the state graph.
        """
        kind = cmd.kind
        # print(f"NEIHBORS NOISE MODEL:")
        # print(f"{self.channel_specifier}")
        # print(f"CMD: {cmd}")
        # print(f"KIND: {cmd.kind}")


        channel = self.channel_specifier.get(kind)        
        
        # print(f"Channel = {channel}")

        
        if kind == CommandKind.N:
            # print(f"===============================")
            self._state_graph.add_node(
                cmd.node
            )  # Update state_graph. No need to check if the node already in the state graph because we can't prepare a node twice.
            if channel == None:
                return Noise()
            if channel.nqubit != 1:
                warnings.warn(f"Krauss channel with {channel_nqubits} qubits can not be applied to 1 qubit.")
                return Noise()
            else:
                return Noise([(channel, [cmd.node])])

        elif kind == CommandKind.E:
            self._state_graph.add_edge(cmd.nodes[0], cmd.nodes[1])
            if channel == None:
                return Noise()
            neighbors_first = list(self._state_graph.neighbors(cmd.nodes[0]))
            neighbors_second = list(self._state_graph.neighbors(cmd.nodes[1]))

            # Question: should we take into account that two nodes could have the same neighbors
            # Or only consider each neighbors once even if they are common neighbors of the two node to intricate?
            # For now, creates a set containing each neighbor once even if they are common to the two nodes to intricate.
            neighbors = set(neighbors_first + neighbors_second)

            # print(list(neighbors))
            # print(f"===============================")
            noise_with_combinations = self._noise_with_combinations(list(neighbors), channel)
            # print(noise_with_combinations)
            # return noise_with_combinations

        else:  # M, X, Z, C, T commands
            neighbors = self._state_graph.neighbors(cmd.node)

            if kind == CommandKind.M:
                self._state_graph.remove_node(cmd.node)
            if channel == None:
                return Noise()

            return self._noise_with_combinations(neighbors, channel)

        typing_extensions.assert_never(kind)

    def confuse_result(self, result: bool) -> bool:
        """Assign wrong measurement result."""
        return result
