"""AWS adapter for the provider-neutral cloud ontology."""

from .builder import AwsOntologyAdapter, build_aws_ontology_snapshot

__all__ = ["AwsOntologyAdapter", "build_aws_ontology_snapshot"]
