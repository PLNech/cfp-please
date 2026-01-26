"""Discovery module for speaker-aware talk discovery."""

from cfp_pipeline.discovery.graph import (
    DiscoveryGraph,
    DiscoveredConference,
    DiscoveredSpeaker,
    DiscoveredTalk,
    load_graph,
    save_graph,
    load_discovery_list,
    save_discovery_list,
    clear_discovery_graph,
    print_discovery_summary,
)

from cfp_pipeline.discovery.engine import (
    DiscoveryEngine,
    DiscoveryChannel,
    DiscoverySpeaker,
    DiscoveryTalk,
    load_discovery_list,
)

__all__ = [
    "DiscoveryGraph",
    "DiscoveredConference",
    "DiscoveredSpeaker",
    "DiscoveredTalk",
    "load_graph",
    "save_graph",
    "load_discovery_list",
    "save_discovery_list",
    "clear_discovery_graph",
    "print_discovery_summary",
    "DiscoveryEngine",
    "DiscoveryChannel",
    "DiscoverySpeaker",
    "DiscoveryTalk",
]