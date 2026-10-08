# Extend the ontology

The canonical model is `wontology.ontology.models.OntologySnapshot`. It contains resources, typed directional relationships, coverage, and unresolved references.

## Add a resource mapping

Edit `src/wontology/ontology/specs/<provider>.yaml`. Match the inventory bucket emitted by the connector, specify native identity fields, and preserve provider-native identifiers. Prefer full resource addresses over names. Add collection separately when the provider inventory does not already return that resource.

```yaml
resources:
  subnets:
    type: Microsoft.Network/virtualNetworks/subnets
    id_fields: [id]
    name_fields: [name]
```

## Add an observed relationship

Use a JMESPath expression over the original provider metadata. The reference must resolve to a discovered resource. Every rule needs a stable unique ID.

```yaml
relationships:
  - source: network_interfaces
    path: properties.ipConfigurations[].properties.subnet.id
    kind: deployed_in
    id: azure.nic-subnet
```

`reverse: true` reverses the relationship direction, useful for container-to-child edges when the parent ID appears on the child. Do not create `depends_on`, `reads_from`, or `writes_to` from shared placement or IAM permissions. Those claims require their own evidence.

## Classification and presentation

`ontology/bundles/core/taxonomy.yaml` defines shared semantic types. Provider `semantics.yaml` rules map native types to semantic types and capabilities. Presentation and authoring bundles expose a reusable provider-neutral catalog. Unknown types stay visible.

Change bundle versions when semantics change, add fixtures with expected relationships and unresolved references, and run the test suite. Reinstall the Python package after changing installed bundles, or use editable installation. New scans use the updated rules. Existing saved snapshots remain immutable.

## Export and reuse

Download JSON from the explorer to use the ontology in other tools. Import accepts the same validated snapshot model. The graph is a typed property graph serialized as JSON; this release does not claim RDF/OWL interchange support. The JSON model can be inspected in Python:

```python
from wontology.ontology.models import OntologySnapshot

with open("snapshot.json") as source:
    snapshot = OntologySnapshot.model_validate_json(source.read())

for edge in snapshot.relationships:
    print(edge.source_id, edge.kind.value, edge.target_id)
```
