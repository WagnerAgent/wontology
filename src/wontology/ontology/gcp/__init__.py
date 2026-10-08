"""GCP ontology normalization backed by the reviewed GCP spec bundle."""

from wontology.ontology.spec_engine import SpecOntologyAdapter


class GcpOntologyAdapter(SpecOntologyAdapter):
    def __init__(self) -> None:
        super().__init__("gcp")


__all__ = ["GcpOntologyAdapter"]
