"""Azure ontology normalization backed by the reviewed Azure spec bundle."""

from wontology.ontology.spec_engine import SpecOntologyAdapter


class AzureOntologyAdapter(SpecOntologyAdapter):
    def __init__(self) -> None:
        super().__init__("azure")


__all__ = ["AzureOntologyAdapter"]
