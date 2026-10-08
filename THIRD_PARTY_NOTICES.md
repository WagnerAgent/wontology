# Third-party notices

Wontology is Apache-2.0. Its dependencies retain their own licenses.

The web bundle includes React and React DOM (MIT), React Flow / @xyflow/react (MIT), Lucide (ISC), and their transitive dependencies. The notices emitted by esbuild are distributed in `src/wontology/static/app.js.LEGAL.txt`; full runtime dependency license texts are in `THIRD_PARTY_LICENSES.txt`. React Flow attribution remains visible in the diagram.

Python dependencies are installed from their respective distributions and retain their bundled license notices: Pydantic (MIT), PyYAML (MIT), JMESPath (MIT), Boto3/Botocore (Apache-2.0), Azure Identity/Azure Core (MIT), Google Auth (Apache-2.0), Requests (Apache-2.0), and their transitive dependencies. Development dependencies are not bundled in the application wheel.

The category SVGs extracted from the Wagner ontology bundles are simple project assets. No third-party articles, screenshots of customer infrastructure, official cloud icon packs, or private diagrams were copied into this repository. Bundled open-source fonts are listed below.

## Fonts

Inter, Space Grotesk, and Instrument Serif are bundled locally under the SIL Open Font License 1.1. Their copyright notices and complete license texts are included alongside the fonts in `src/wontology/static/fonts/*-OFL.txt` and in the installed package. Sources: [Inter](https://github.com/google/fonts/tree/main/ofl/inter), [Space Grotesk](https://github.com/google/fonts/tree/main/ofl/spacegrotesk), [Instrument Serif](https://github.com/google/fonts/tree/main/ofl/instrumentserif).
