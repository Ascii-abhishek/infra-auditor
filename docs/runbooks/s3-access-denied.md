# Diagnose and fix schema-3 S3 access

## Observed on 2026-09-08

The owner completed database permission updates and ran Sync all. The screenshot
shows AccessDenied writing the first PostgreSQL findings object beneath
`reports/snapshots/schema=3/` in `infra-audit-rl-dev`.

Read-only probes with the configured `infra-auditor` profile confirmed:

| Operation | Result |
| --- | --- |
| STS identity | IAM Identity Center role for `prm_rl_infra_auditor` |
| List raw schema-3 objects | Allowed, objects present |
| Read a byte from an existing raw schema-3 object | Allowed; content not printed |
| List canonical PostgreSQL report prefix, both aliases | AccessDenied |
| List canonical run-manifest prefix, both aliases | AccessDenied |
| Inspect role inline policies | AccessDenied; exact policy contents unverified |

No S3 write probe, database collection, grants or IAM changes were performed in
this diagnosis. The denied PutObject is from the owner's screenshot. The strongest
explanation is a prefix-scoped policy that still allows only the old raw layout;
an explicit deny or other policy layer cannot be excluded without policy access.

The reader calls S3 ListObjectsV2/GetObject directly. Earlier evidence/report reads
were not served from a local evidence store. Before the purpose split, evidence,
findings and manifests all lived beneath `raw/snapshots/`. Schema 3 added sibling
`reports/` and `runs/` prefixes. PostgreSQL grants do not change AWS permissions.

The writer stores seven raw objects before the first findings object. For the
reported failure those earlier writes completed, but the run manifest was never
written. This is an incomplete stored family, so Reports cannot treat it as a
completed run. A fresh latest sync after fixing IAM creates a new timestamped run;
no bucket cleanup is needed to retry.

## Fix in IAM Identity Center as an administrator

1. Open **IAM Identity Center → Permission sets → prm_rl_infra_auditor**.
   `infra-auditor` is the local AWS profile; the permission set has a different name.
2. Edit its inline policy. Merge the two `Statement` entries from
   [the dev S3 policy](../iam/infra-auditor-dev-s3.json) into the existing policy,
   or replace the existing S3 statements with them. Preserve the unrelated
   RDS, EC2, CloudWatch and Secrets Manager permissions. This JSON is the S3
   portion only, not a replacement for the entire auditor policy.
3. Save and update/reprovision the permission set to the assigned target AWS
   account. Confirm provisioning succeeded. Update the permission set rather
   than hand-editing the generated `AWSReservedSSO_...` IAM role.
4. Refresh the local login with `aws sso login --profile infra-auditor`, then
   restart the local console. Refresh is not a substitute for provisioning.
5. Run the two read-only checks below. Success may return an empty listing;
   that is expected before the first report/manifest write succeeds.
6. Run **Sync all** again. Confirm both aliases finish and Reports loads. Review
   collector gaps independently; successful storage does not prove every database
   collector succeeded.

```bash
aws s3api list-objects-v2 --profile infra-auditor --bucket infra-audit-rl-dev --prefix reports/snapshots/schema=3/ --max-keys 1
aws s3api list-objects-v2 --profile infra-auditor --bucket infra-audit-rl-dev --prefix runs/schema=3/ --max-keys 1
```

S3 has separate permissions for each operation: `s3:PutObject` writes artifacts,
`s3:GetObject` reads them, and `s3:ListBucket` discovers keys. ListBucket uses the
bucket ARN plus a prefix condition; GetObject/PutObject use object ARNs. Adding
only GetObject cannot repair the observed upload failure. No DeleteObject,
ListAllMyBuckets, or S3FullAccess is required by this fix.

If denied after successful provisioning, have the administrator check the
permission set's effective policies and permissions boundary, bucket policy,
organization SCPs, and any S3 VPC endpoint policy for explicit denies or prefix
restrictions. Do not broaden access merely because one of those layers denies it.

Sources: [AWS permission set updates](https://docs.aws.amazon.com/singlesignon/latest/userguide/howtoviewandchangepermissionset.html)
and [S3 prefix conditions](https://docs.aws.amazon.com/AmazonS3/latest/userguide/amazon-s3-policy-keys.html).
