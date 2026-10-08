# Connect your cloud

Wontology has no product login. Your cloud provider still requires authentication and authorization. Establish that session using its own tooling, then select **Connect cloud** in Wontology. Credentials are never pasted into the UI.

## AWS

Use a local AWS SDK profile or the standard credential chain. IAM Identity Center profiles and temporary role credentials are supported by Boto3.

```bash
aws sso login --profile infrastructure-readonly
```

Select that profile and enter comma-separated AWS regions. The default selection is `us-east-1`; Wontology does not silently scan every region. Global S3 and IAM metadata is collected once. SDK credential refresh follows the profile's normal behavior.

[aws-metadata-policy.json](aws-metadata-policy.json) lists the exact metadata operations in the initial connector. Ask your administrator to provision that access if necessary. Wontology does not create roles or attach permissions. Missing access produces coverage gaps while accessible resources remain available.

Reference: [Boto3 credentials](https://docs.aws.amazon.com/boto3/latest/guide/credentials.html).

## Azure

```bash
az login
```

Enter the subscription ID in Wontology. The connector uses Azure Identity's credential chain and queries Azure Resource Graph for that subscription. The identity needs read access to the resources being queried; Reader at the subscription scope is a common starting point. Resource Graph returns resources the identity can see, so restricted resource visibility cannot automatically be distinguished from an empty permitted scope.

No user-assigned managed identity, service principal secret, or application registration is required when using an existing Azure CLI developer session on the host.

References: [local Azure authentication](https://learn.microsoft.com/en-us/azure/developer/python/sdk/authentication/local-development-dev-accounts), [Resource Graph access](https://learn.microsoft.com/en-us/azure/governance/resource-graph/overview).

## Google Cloud

```bash
gcloud auth application-default login
```

Enter a project ID or project number. The project must have Cloud Asset Inventory enabled by an administrator. Wontology never enables APIs. The identity needs the Cloud Asset Inventory resource-list permissions at the selected project scope. `roles/cloudasset.viewer` is a provider-managed starting point; review it against your organization's requirements. A quota project may need `serviceusage.services.use`.

The API requires the `cloud-platform` OAuth scope. IAM must constrain the identity to metadata reads; an OAuth scope by itself is not a least-privilege policy. `gcloud auth login` alone is not equivalent to setting up Application Default Credentials.

References: [Application Default Credentials](https://docs.cloud.google.com/docs/authentication/application-default-credentials), [list assets](https://docs.cloud.google.com/asset-inventory/docs/list-assets), [required OAuth scope](https://docs.cloud.google.com/asset-inventory/docs/reference/rest/v1/assets/list).

## Docker credentials

The default Compose file starts examples only. Prefer host installation when reusing an interactive Azure CLI session. Docker cannot automatically use CLI binaries or credential caches from the host.

For AWS, mount the relevant configuration and cache read-only into `/root/.aws` and select the profile. Renew an expired IAM Identity Center session on the host. For GCP, mount the ADC file read-only and point `GOOGLE_APPLICATION_CREDENTIALS` to the container path. Use Compose overrides kept outside Git; never add credential files to the image or repository.

For Azure containers, configure an existing workload identity or service principal through the Azure Identity environment variables using your secret manager or local environment. Do not commit them. Interactive host Azure CLI authentication is not included in the base image.

Keep the published port bound to `127.0.0.1`. The app is a single-user local tool; Internet-facing deployment and shared remote access are outside the supported security model.
