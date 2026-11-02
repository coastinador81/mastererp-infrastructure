# Resource ownership

- mastererp-database owns RDS, its networking, migration Lambda, SQL and migration workflows.
- mastererp-infrastructure/modules/api-gateways.yml owns the shared API definitions.
- Legacy exception: mastererp-infrastructure/modules/1.0-platform-base/1.1-tenant-onboarding/lambdas/*/resources.yml contains the three retained onboarding definitions pending explicit ownership transition. These paths are not the convention for new Lambdas.
- Current convention: each functional owner declares all its exclusive Lambdas and resources in its root resources.yml; shared resources belong to the nearest common functional parent. Backend lambdas/<name>/ directories contain code, not separate infrastructure templates.
- mastererp-platform owns the implementation code packaged for onboarding.

Region: us-west-1. Database migrator remains in the database repository.

## Deployment transition

These reorganized templates are NOT deployment-ready replacements for existing stacks. Preserve existing API routes, JWT authorizers, CORS, Lambda permissions, execution-role permissions, environment variables and resource IDs when preparing the migration change sets. The Admin API currently belongs to mastererp-dev-onboarding; client and agent APIs belong to mastererp-dev-http-apis. Move ownership using retention and resource import, reviewing change sets before execution. Do not deploy fresh stacks over existing names.

The old combined template was removed because it would recreate the five deleted functions. No AWS resource was changed by this repository reorganization.
