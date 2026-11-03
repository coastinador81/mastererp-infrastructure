# Mapa origen → destino de la jerarquía financiera DEV

Inventario actualizado: 2026-11-02T13:41:11.861380+00:00. Cuenta 277352717693; solo us-west-1. Ocho stacks MasterERP, 114 registros CFN y 13 funciones activas antes del lote. No se consultaron ni modificaron QA/PROD ni recursos de otras regiones.

Lote F1: importar el stack existente mastererp-dev-administration como hijo Administration de mastererp-dev-finance. No mover sus 48 recursos individualmente. Mantener sus IDs y el nombre del stack hijo. Capacidades: YAML funcional; Contabilidad y BI: reservas vacías.

Lote F2: actualizar desde Finanzas la composición publicada y las restricciones de parámetros, sin diferencias en las 48 declaraciones Resources.

| Región | Stack actual | ID lógico | Tipo / ID físico | Destino / lote |
| --- | --- | --- | --- | --- |
| us-west-1 | `mastererp-dev-administration` | `CarteraApiPermission` | `AWS::Lambda::Permission` · `mastererp-dev-administration-CarteraApiPermission-VtMxiAENVmel` | Mismo stack hijo bajo mastererp-dev-finance / F1; 48 recursos intactos |
| us-west-1 | `mastererp-dev-administration` | `CarteraFunction` | `AWS::Lambda::Function` · `mastererp-dev-adm-cartera` | Mismo stack hijo bajo mastererp-dev-finance / F1; 48 recursos intactos |
| us-west-1 | `mastererp-dev-administration` | `CarteraHealthRoute` | `AWS::ApiGatewayV2::Route` · `768ouce` | Mismo stack hijo bajo mastererp-dev-finance / F1; 48 recursos intactos |
| us-west-1 | `mastererp-dev-administration` | `CarteraIntegration` | `AWS::ApiGatewayV2::Integration` · `y2mekds` | Mismo stack hijo bajo mastererp-dev-finance / F1; 48 recursos intactos |
| us-west-1 | `mastererp-dev-administration` | `CarteraLogs` | `AWS::Logs::LogGroup` · `/aws/lambda/mastererp-dev-adm-cartera` | Mismo stack hijo bajo mastererp-dev-finance / F1; 48 recursos intactos |
| us-west-1 | `mastererp-dev-administration` | `CarteraRole` | `AWS::IAM::Role` · `mastererp-dev-administration-CarteraRole-XzBwjwJrdGwT` | Mismo stack hijo bajo mastererp-dev-finance / F1; 48 recursos intactos |
| us-west-1 | `mastererp-dev-administration` | `ClientesApiPermission` | `AWS::Lambda::Permission` · `mastererp-dev-administration-ClientesApiPermission-uKxxLrx3rgi7` | Mismo stack hijo bajo mastererp-dev-finance / F1; 48 recursos intactos |
| us-west-1 | `mastererp-dev-administration` | `ClientesFunction` | `AWS::Lambda::Function` · `mastererp-dev-adm-clientes` | Mismo stack hijo bajo mastererp-dev-finance / F1; 48 recursos intactos |
| us-west-1 | `mastererp-dev-administration` | `ClientesHealthRoute` | `AWS::ApiGatewayV2::Route` · `44p7w7h` | Mismo stack hijo bajo mastererp-dev-finance / F1; 48 recursos intactos |
| us-west-1 | `mastererp-dev-administration` | `ClientesIntegration` | `AWS::ApiGatewayV2::Integration` · `u40oikf` | Mismo stack hijo bajo mastererp-dev-finance / F1; 48 recursos intactos |
| us-west-1 | `mastererp-dev-administration` | `ClientesLogs` | `AWS::Logs::LogGroup` · `/aws/lambda/mastererp-dev-adm-clientes` | Mismo stack hijo bajo mastererp-dev-finance / F1; 48 recursos intactos |
| us-west-1 | `mastererp-dev-administration` | `ClientesRole` | `AWS::IAM::Role` · `mastererp-dev-administration-ClientesRole-l7p1SwfU55i8` | Mismo stack hijo bajo mastererp-dev-finance / F1; 48 recursos intactos |
| us-west-1 | `mastererp-dev-administration` | `ComprasApiPermission` | `AWS::Lambda::Permission` · `mastererp-dev-administration-ComprasApiPermission-uCe7Ual8XWYY` | Mismo stack hijo bajo mastererp-dev-finance / F1; 48 recursos intactos |
| us-west-1 | `mastererp-dev-administration` | `ComprasFunction` | `AWS::Lambda::Function` · `mastererp-dev-adm-compras` | Mismo stack hijo bajo mastererp-dev-finance / F1; 48 recursos intactos |
| us-west-1 | `mastererp-dev-administration` | `ComprasHealthRoute` | `AWS::ApiGatewayV2::Route` · `3vfcl09` | Mismo stack hijo bajo mastererp-dev-finance / F1; 48 recursos intactos |
| us-west-1 | `mastererp-dev-administration` | `ComprasIntegration` | `AWS::ApiGatewayV2::Integration` · `ifdz25r` | Mismo stack hijo bajo mastererp-dev-finance / F1; 48 recursos intactos |
| us-west-1 | `mastererp-dev-administration` | `ComprasLogs` | `AWS::Logs::LogGroup` · `/aws/lambda/mastererp-dev-adm-compras` | Mismo stack hijo bajo mastererp-dev-finance / F1; 48 recursos intactos |
| us-west-1 | `mastererp-dev-administration` | `ComprasRole` | `AWS::IAM::Role` · `mastererp-dev-administration-ComprasRole-uXVDtzn7MAXL` | Mismo stack hijo bajo mastererp-dev-finance / F1; 48 recursos intactos |
| us-west-1 | `mastererp-dev-administration` | `ConciliacionApiPermission` | `AWS::Lambda::Permission` · `mastererp-dev-administration-ConciliacionApiPermission-GyhnNm02XMdL` | Mismo stack hijo bajo mastererp-dev-finance / F1; 48 recursos intactos |
| us-west-1 | `mastererp-dev-administration` | `ConciliacionFunction` | `AWS::Lambda::Function` · `mastererp-dev-adm-conciliacion` | Mismo stack hijo bajo mastererp-dev-finance / F1; 48 recursos intactos |
| us-west-1 | `mastererp-dev-administration` | `ConciliacionHealthRoute` | `AWS::ApiGatewayV2::Route` · `1dk025g` | Mismo stack hijo bajo mastererp-dev-finance / F1; 48 recursos intactos |
| us-west-1 | `mastererp-dev-administration` | `ConciliacionIntegration` | `AWS::ApiGatewayV2::Integration` · `i5rkryr` | Mismo stack hijo bajo mastererp-dev-finance / F1; 48 recursos intactos |
| us-west-1 | `mastererp-dev-administration` | `ConciliacionLogs` | `AWS::Logs::LogGroup` · `/aws/lambda/mastererp-dev-adm-conciliacion` | Mismo stack hijo bajo mastererp-dev-finance / F1; 48 recursos intactos |
| us-west-1 | `mastererp-dev-administration` | `ConciliacionRole` | `AWS::IAM::Role` · `mastererp-dev-administration-ConciliacionRole-gaqrMlQev56e` | Mismo stack hijo bajo mastererp-dev-finance / F1; 48 recursos intactos |
| us-west-1 | `mastererp-dev-administration` | `GastosApiPermission` | `AWS::Lambda::Permission` · `mastererp-dev-administration-GastosApiPermission-yZrr87Ndkqdo` | Mismo stack hijo bajo mastererp-dev-finance / F1; 48 recursos intactos |
| us-west-1 | `mastererp-dev-administration` | `GastosFunction` | `AWS::Lambda::Function` · `mastererp-dev-adm-gastos` | Mismo stack hijo bajo mastererp-dev-finance / F1; 48 recursos intactos |
| us-west-1 | `mastererp-dev-administration` | `GastosHealthRoute` | `AWS::ApiGatewayV2::Route` · `b0wth89` | Mismo stack hijo bajo mastererp-dev-finance / F1; 48 recursos intactos |
| us-west-1 | `mastererp-dev-administration` | `GastosIntegration` | `AWS::ApiGatewayV2::Integration` · `ejajkug` | Mismo stack hijo bajo mastererp-dev-finance / F1; 48 recursos intactos |
| us-west-1 | `mastererp-dev-administration` | `GastosLogs` | `AWS::Logs::LogGroup` · `/aws/lambda/mastererp-dev-adm-gastos` | Mismo stack hijo bajo mastererp-dev-finance / F1; 48 recursos intactos |
| us-west-1 | `mastererp-dev-administration` | `GastosRole` | `AWS::IAM::Role` · `mastererp-dev-administration-GastosRole-40BwV3AQarii` | Mismo stack hijo bajo mastererp-dev-finance / F1; 48 recursos intactos |
| us-west-1 | `mastererp-dev-administration` | `ProveedoresApiPermission` | `AWS::Lambda::Permission` · `mastererp-dev-administration-ProveedoresApiPermission-5HXYou7FTIyI` | Mismo stack hijo bajo mastererp-dev-finance / F1; 48 recursos intactos |
| us-west-1 | `mastererp-dev-administration` | `ProveedoresFunction` | `AWS::Lambda::Function` · `mastererp-dev-adm-proveedores` | Mismo stack hijo bajo mastererp-dev-finance / F1; 48 recursos intactos |
| us-west-1 | `mastererp-dev-administration` | `ProveedoresHealthRoute` | `AWS::ApiGatewayV2::Route` · `onbcxbd` | Mismo stack hijo bajo mastererp-dev-finance / F1; 48 recursos intactos |
| us-west-1 | `mastererp-dev-administration` | `ProveedoresIntegration` | `AWS::ApiGatewayV2::Integration` · `nh5hkzl` | Mismo stack hijo bajo mastererp-dev-finance / F1; 48 recursos intactos |
| us-west-1 | `mastererp-dev-administration` | `ProveedoresLogs` | `AWS::Logs::LogGroup` · `/aws/lambda/mastererp-dev-adm-proveedores` | Mismo stack hijo bajo mastererp-dev-finance / F1; 48 recursos intactos |
| us-west-1 | `mastererp-dev-administration` | `ProveedoresRole` | `AWS::IAM::Role` · `mastererp-dev-administration-ProveedoresRole-787c8NMCZJWP` | Mismo stack hijo bajo mastererp-dev-finance / F1; 48 recursos intactos |
| us-west-1 | `mastererp-dev-administration` | `TesoreriaApiPermission` | `AWS::Lambda::Permission` · `mastererp-dev-administration-TesoreriaApiPermission-sP0iP2XOvkDd` | Mismo stack hijo bajo mastererp-dev-finance / F1; 48 recursos intactos |
| us-west-1 | `mastererp-dev-administration` | `TesoreriaFunction` | `AWS::Lambda::Function` · `mastererp-dev-adm-tesoreria` | Mismo stack hijo bajo mastererp-dev-finance / F1; 48 recursos intactos |
| us-west-1 | `mastererp-dev-administration` | `TesoreriaHealthRoute` | `AWS::ApiGatewayV2::Route` · `fgyn03m` | Mismo stack hijo bajo mastererp-dev-finance / F1; 48 recursos intactos |
| us-west-1 | `mastererp-dev-administration` | `TesoreriaIntegration` | `AWS::ApiGatewayV2::Integration` · `4kiq2xh` | Mismo stack hijo bajo mastererp-dev-finance / F1; 48 recursos intactos |
| us-west-1 | `mastererp-dev-administration` | `TesoreriaLogs` | `AWS::Logs::LogGroup` · `/aws/lambda/mastererp-dev-adm-tesoreria` | Mismo stack hijo bajo mastererp-dev-finance / F1; 48 recursos intactos |
| us-west-1 | `mastererp-dev-administration` | `TesoreriaRole` | `AWS::IAM::Role` · `mastererp-dev-administration-TesoreriaRole-IWfh5zauliih` | Mismo stack hijo bajo mastererp-dev-finance / F1; 48 recursos intactos |
| us-west-1 | `mastererp-dev-administration` | `VentasApiPermission` | `AWS::Lambda::Permission` · `mastererp-dev-administration-VentasApiPermission-qGLmKiTyTM8B` | Mismo stack hijo bajo mastererp-dev-finance / F1; 48 recursos intactos |
| us-west-1 | `mastererp-dev-administration` | `VentasFunction` | `AWS::Lambda::Function` · `mastererp-dev-adm-ventas` | Mismo stack hijo bajo mastererp-dev-finance / F1; 48 recursos intactos |
| us-west-1 | `mastererp-dev-administration` | `VentasHealthRoute` | `AWS::ApiGatewayV2::Route` · `ulap09o` | Mismo stack hijo bajo mastererp-dev-finance / F1; 48 recursos intactos |
| us-west-1 | `mastererp-dev-administration` | `VentasIntegration` | `AWS::ApiGatewayV2::Integration` · `8v281qs` | Mismo stack hijo bajo mastererp-dev-finance / F1; 48 recursos intactos |
| us-west-1 | `mastererp-dev-administration` | `VentasLogs` | `AWS::Logs::LogGroup` · `/aws/lambda/mastererp-dev-adm-ventas` | Mismo stack hijo bajo mastererp-dev-finance / F1; 48 recursos intactos |
| us-west-1 | `mastererp-dev-administration` | `VentasRole` | `AWS::IAM::Role` · `mastererp-dev-administration-VentasRole-dg694RhlPRH7` | Mismo stack hijo bajo mastererp-dev-finance / F1; 48 recursos intactos |
| us-west-1 | `mastererp-dev-application-data-access` | `ApplicationSecret` | `AWS::SecretsManager::Secret` · `arn:aws:secretsmanager:us-west-1:277352717693:secret:mastererp/dev/database/application-kXansa` | mastererp-dev-application-data-access (sin cambio; fuera de F1/F2) |
| us-west-1 | `mastererp-dev-application-data-access` | `ApplicationSecurityGroup` | `AWS::EC2::SecurityGroup` · `sg-00d5917aa994d3753` | mastererp-dev-application-data-access (sin cambio; fuera de F1/F2) |
| us-west-1 | `mastererp-dev-application-data-access` | `DatabaseIngress` | `AWS::EC2::SecurityGroupIngress` · `sgr-02e04d6e09aa5b6df` | mastererp-dev-application-data-access (sin cambio; fuera de F1/F2) |
| us-west-1 | `mastererp-dev-application-data-access` | `QaCredentialsSecret` | `AWS::SecretsManager::Secret` · `arn:aws:secretsmanager:us-west-1:277352717693:secret:mastererp/dev/qa/identity-validation-E1Hjye` | mastererp-dev-application-data-access (sin cambio; fuera de F1/F2) |
| us-west-1 | `mastererp-dev-application-data-access` | `SecretsEndpointIngress` | `AWS::EC2::SecurityGroupIngress` · `sgr-0631f2462482c0b2e` | mastererp-dev-application-data-access (sin cambio; fuera de F1/F2) |
| us-west-1 | `mastererp-dev-identity` | `AgentJwtAuthorizer` | `AWS::ApiGatewayV2::Authorizer` · `93tlzl` | mastererp-dev-identity (sin cambio; fuera de F1/F2) |
| us-west-1 | `mastererp-dev-identity` | `ApiResourceServer` | `AWS::Cognito::UserPoolResourceServer` · `mastererp-dev` | mastererp-dev-identity (sin cambio; fuera de F1/F2) |
| us-west-1 | `mastererp-dev-identity` | `Domain` | `AWS::Cognito::UserPoolDomain` · `mastererp-dev-uonify-277352717693` | mastererp-dev-identity (sin cambio; fuera de F1/F2) |
| us-west-1 | `mastererp-dev-identity` | `UserPool` | `AWS::Cognito::UserPool` · `us-west-1_oCn3VipDO` | mastererp-dev-identity (sin cambio; fuera de F1/F2) |
| us-west-1 | `mastererp-dev-identity` | `WebClient` | `AWS::Cognito::UserPoolClient` · `56psiha6rtmsu8qklace85k8m0` | mastererp-dev-identity (sin cambio; fuera de F1/F2) |
| us-west-1 | `mastererp-dev-uonify-google-connection` | `Function` | `AWS::Lambda::Function` · `mastererp-dev-uonify-google-connection-handler` | mastererp-dev-uonify-google-connection (sin cambio; fuera de F1/F2) |
| us-west-1 | `mastererp-dev-uonify-google-connection` | `Integration` | `AWS::ApiGatewayV2::Integration` · `nb6xd3c` | mastererp-dev-uonify-google-connection (sin cambio; fuera de F1/F2) |
| us-west-1 | `mastererp-dev-uonify-google-connection` | `Logs` | `AWS::Logs::LogGroup` · `/aws/lambda/mastererp-dev-uonify-google-connection-handler` | mastererp-dev-uonify-google-connection (sin cambio; fuera de F1/F2) |
| us-west-1 | `mastererp-dev-uonify-google-connection` | `Permission` | `AWS::Lambda::Permission` · `mastererp-dev-uonify-google-connection-Permission-VoEZ6L5IYXTd` | mastererp-dev-uonify-google-connection (sin cambio; fuera de F1/F2) |
| us-west-1 | `mastererp-dev-uonify-google-connection` | `Role` | `AWS::IAM::Role` · `mastererp-dev-uonify-google-connection-Role-Q1yWvhQwrV7F` | mastererp-dev-uonify-google-connection (sin cambio; fuera de F1/F2) |
| us-west-1 | `mastererp-dev-uonify-google-connection` | `Route` | `AWS::ApiGatewayV2::Route` · `w1gbd60` | mastererp-dev-uonify-google-connection (sin cambio; fuera de F1/F2) |
| us-west-1 | `mastererp-dev-uonify-google-connection` | `SpacesPermission` | `AWS::Lambda::Permission` · `mastererp-dev-uonify-google-connection-SpacesPermission-9CyYLRIgqqXy` | mastererp-dev-uonify-google-connection (sin cambio; fuera de F1/F2) |
| us-west-1 | `mastererp-dev-uonify-google-connection` | `SpacesRoute` | `AWS::ApiGatewayV2::Route` · `ik4w9vn` | mastererp-dev-uonify-google-connection (sin cambio; fuera de F1/F2) |
| us-west-1 | `mastererp-dev-uonify-hosting` | `Bucket` | `AWS::S3::Bucket` · `mastererp-dev-uonify-app-277352717693-us-west-1` | mastererp-dev-uonify-hosting (sin cambio; fuera de F1/F2) |
| us-west-1 | `mastererp-dev-uonify-hosting` | `BucketPolicy` | `AWS::S3::BucketPolicy` · `mastererp-dev-uonify-app-277352717693-us-west-1` | mastererp-dev-uonify-hosting (sin cambio; fuera de F1/F2) |
| us-west-1 | `mastererp-dev-uonify-hosting` | `Distribution` | `AWS::CloudFront::Distribution` · `E146MXYK3KTLSB` | mastererp-dev-uonify-hosting (sin cambio; fuera de F1/F2) |
| us-west-1 | `mastererp-dev-uonify-hosting` | `Dns` | `AWS::Route53::RecordSet` · `app-dev.uonify.com` | mastererp-dev-uonify-hosting (sin cambio; fuera de F1/F2) |
| us-west-1 | `mastererp-dev-uonify-hosting` | `OAC` | `AWS::CloudFront::OriginAccessControl` · `E1115W9ODC8XXF` | mastererp-dev-uonify-hosting (sin cambio; fuera de F1/F2) |
| us-west-1 | `mastererp-dev-data` | `Database` | `AWS::RDS::DBInstance` · `mastererp-dev-data` | mastererp-dev-data (sin cambio; fuera de F1/F2) |
| us-west-1 | `mastererp-dev-data` | `DatabaseSecurityGroup` | `AWS::EC2::SecurityGroup` · `sg-007e19fb5eb109b11` | mastererp-dev-data (sin cambio; fuera de F1/F2) |
| us-west-1 | `mastererp-dev-data` | `DatabaseSubnetGroup` | `AWS::RDS::DBSubnetGroup` · `mastererp-dev-data-databasesubnetgroup-2loxul94cdsd` | mastererp-dev-data (sin cambio; fuera de F1/F2) |
| us-west-1 | `mastererp-dev-onboarding` | `AdminApiLogGroup` | `AWS::Logs::LogGroup` · `/aws/apigateway/mastererp-dev-admin-api` | mastererp-dev-onboarding (sin cambio; fuera de F1/F2) |
| us-west-1 | `mastererp-dev-onboarding` | `AdminHttpApi` | `AWS::ApiGatewayV2::Api` · `qx8nmypdhi` | mastererp-dev-onboarding (sin cambio; fuera de F1/F2) |
| us-west-1 | `mastererp-dev-onboarding` | `AdminHttpApiApiGatewayDefaultStage` | `AWS::ApiGatewayV2::Stage` · `$default` | mastererp-dev-onboarding (sin cambio; fuera de F1/F2) |
| us-west-1 | `mastererp-dev-onboarding` | `DbMigratorFunction` | `AWS::Lambda::Function` · `mastererp-dev-db-migrator` | mastererp-dev-onboarding (sin cambio; fuera de F1/F2) |
| us-west-1 | `mastererp-dev-onboarding` | `DbMigratorFunctionRole` | `AWS::IAM::Role` · `mastererp-dev-onboarding-DbMigratorFunctionRole-nK4xcbsk0Obe` | mastererp-dev-onboarding (sin cambio; fuera de F1/F2) |
| us-west-1 | `mastererp-dev-onboarding` | `ModuleCatalogReaderFunction` | `AWS::Lambda::Function` · `mastererp-dev-module-catalog-reader` | mastererp-dev-onboarding (sin cambio; fuera de F1/F2) |
| us-west-1 | `mastererp-dev-onboarding` | `ModuleCatalogReaderFunctionGetModulesPermission` | `AWS::Lambda::Permission` · `mastererp-dev-onboarding-ModuleCatalogReaderFunctionGetModulesPermission-RMpNkGm9QKxq` | mastererp-dev-onboarding (sin cambio; fuera de F1/F2) |
| us-west-1 | `mastererp-dev-onboarding` | `ModuleCatalogReaderFunctionRole` | `AWS::IAM::Role` · `mastererp-dev-onboarding-ModuleCatalogReaderFunctio-6Zq8ATDUP3eE` | mastererp-dev-onboarding (sin cambio; fuera de F1/F2) |
| us-west-1 | `mastererp-dev-onboarding` | `OnboardingProgressTrackerFunction` | `AWS::Lambda::Function` · `mastererp-dev-onboarding-progress-tracker` | mastererp-dev-onboarding (sin cambio; fuera de F1/F2) |
| us-west-1 | `mastererp-dev-onboarding` | `OnboardingProgressTrackerFunctionGetProgressPermission` | `AWS::Lambda::Permission` · `mastererp-dev-onboarding-OnboardingProgressTrackerFunctionGetProgressPermission-RmNyVeAmSm9P` | mastererp-dev-onboarding (sin cambio; fuera de F1/F2) |
| us-west-1 | `mastererp-dev-onboarding` | `OnboardingProgressTrackerFunctionPutStepPermission` | `AWS::Lambda::Permission` · `mastererp-dev-onboarding-OnboardingProgressTrackerFunctionPutStepPermission-rbUpnH86PGl3` | mastererp-dev-onboarding (sin cambio; fuera de F1/F2) |
| us-west-1 | `mastererp-dev-onboarding` | `OnboardingProgressTrackerFunctionRole` | `AWS::IAM::Role` · `mastererp-dev-onboarding-OnboardingProgressTrackerF-64p7fBGwXcYG` | mastererp-dev-onboarding (sin cambio; fuera de F1/F2) |
| us-west-1 | `mastererp-dev-onboarding` | `OnboardingProvisionerFunction` | `AWS::Lambda::Function` · `mastererp-dev-onboarding-provisioner` | mastererp-dev-onboarding (sin cambio; fuera de F1/F2) |
| us-west-1 | `mastererp-dev-onboarding` | `OnboardingProvisionerFunctionRole` | `AWS::IAM::Role` · `mastererp-dev-onboarding-OnboardingProvisionerFunct-Bu7ez5LmiuTd` | mastererp-dev-onboarding (sin cambio; fuera de F1/F2) |
| us-west-1 | `mastererp-dev-onboarding` | `OnboardingSessionManagerFunction` | `AWS::Lambda::Function` · `mastererp-dev-onboarding-session-manager` | mastererp-dev-onboarding (sin cambio; fuera de F1/F2) |
| us-west-1 | `mastererp-dev-onboarding` | `OnboardingSessionManagerFunctionCompleteSessionPermission` | `AWS::Lambda::Permission` · `mastererp-dev-onboarding-OnboardingSessionManagerFunctionCompleteSessionPermission-0Av1FJUnH0xd` | mastererp-dev-onboarding (sin cambio; fuera de F1/F2) |
| us-west-1 | `mastererp-dev-onboarding` | `OnboardingSessionManagerFunctionGetSessionPermission` | `AWS::Lambda::Permission` · `mastererp-dev-onboarding-OnboardingSessionManagerFunctionGetSessionPermission-q0YxtcuSzivC` | mastererp-dev-onboarding (sin cambio; fuera de F1/F2) |
| us-west-1 | `mastererp-dev-onboarding` | `OnboardingSessionManagerFunctionPatchSessionPermission` | `AWS::Lambda::Permission` · `mastererp-dev-onboarding-OnboardingSessionManagerFunctionPatchSessionPermission-5Yf67n9f89gX` | mastererp-dev-onboarding (sin cambio; fuera de F1/F2) |
| us-west-1 | `mastererp-dev-onboarding` | `OnboardingSessionManagerFunctionPostSessionPermission` | `AWS::Lambda::Permission` · `mastererp-dev-onboarding-OnboardingSessionManagerFunctionPostSessionPermission-CFDwViVNBkJM` | mastererp-dev-onboarding (sin cambio; fuera de F1/F2) |
| us-west-1 | `mastererp-dev-onboarding` | `OnboardingSessionManagerFunctionRole` | `AWS::IAM::Role` · `mastererp-dev-onboarding-OnboardingSessionManagerFu-m4LMJNTPhLrB` | mastererp-dev-onboarding (sin cambio; fuera de F1/F2) |
| us-west-1 | `mastererp-dev-onboarding` | `SsmAdminApiId` | `AWS::SSM::Parameter` · `/mastererp/dev/gateways/admin-api-id` | mastererp-dev-onboarding (sin cambio; fuera de F1/F2) |
| us-west-1 | `mastererp-dev-onboarding` | `TenantConfigManagerFunction` | `AWS::Lambda::Function` · `mastererp-dev-tenant-config-manager` | mastererp-dev-onboarding (sin cambio; fuera de F1/F2) |
| us-west-1 | `mastererp-dev-onboarding` | `TenantConfigManagerFunctionGetConfigPermission` | `AWS::Lambda::Permission` · `mastererp-dev-onboarding-TenantConfigManagerFunctionGetConfigPermission-VsgaNgKTAWTF` | mastererp-dev-onboarding (sin cambio; fuera de F1/F2) |
| us-west-1 | `mastererp-dev-onboarding` | `TenantConfigManagerFunctionPatchConfigPermission` | `AWS::Lambda::Permission` · `mastererp-dev-onboarding-TenantConfigManagerFunctionPatchConfigPermission-OysTePGB0MhM` | mastererp-dev-onboarding (sin cambio; fuera de F1/F2) |
| us-west-1 | `mastererp-dev-onboarding` | `TenantConfigManagerFunctionRole` | `AWS::IAM::Role` · `mastererp-dev-onboarding-TenantConfigManagerFunctio-Ao7An0avp1Qe` | mastererp-dev-onboarding (sin cambio; fuera de F1/F2) |
| us-west-1 | `mastererp-dev-onboarding` | `TenantCreatorFunction` | `AWS::Lambda::Function` · `mastererp-dev-tenant-creator` | mastererp-dev-onboarding (sin cambio; fuera de F1/F2) |
| us-west-1 | `mastererp-dev-onboarding` | `TenantCreatorFunctionPostTenantPermission` | `AWS::Lambda::Permission` · `mastererp-dev-onboarding-TenantCreatorFunctionPostTenantPermission-9Du0WmzhjWPT` | mastererp-dev-onboarding (sin cambio; fuera de F1/F2) |
| us-west-1 | `mastererp-dev-onboarding` | `TenantCreatorFunctionRole` | `AWS::IAM::Role` · `mastererp-dev-onboarding-TenantCreatorFunctionRole-zvwmszL2v7g2` | mastererp-dev-onboarding (sin cambio; fuera de F1/F2) |
| us-west-1 | `mastererp-dev-onboarding` | `TenantModuleManagerFunction` | `AWS::Lambda::Function` · `mastererp-dev-tenant-module-manager` | mastererp-dev-onboarding (sin cambio; fuera de F1/F2) |
| us-west-1 | `mastererp-dev-onboarding` | `TenantModuleManagerFunctionGetTenantModulesPermission` | `AWS::Lambda::Permission` · `mastererp-dev-onboarding-TenantModuleManagerFunctionGetTenantModulesPermission-jMI1yGw6iVdV` | mastererp-dev-onboarding (sin cambio; fuera de F1/F2) |
| us-west-1 | `mastererp-dev-onboarding` | `TenantModuleManagerFunctionPutTenantModulePermission` | `AWS::Lambda::Permission` · `mastererp-dev-onboarding-TenantModuleManagerFunctionPutTenantModulePermission-2D8kzrov5fSy` | mastererp-dev-onboarding (sin cambio; fuera de F1/F2) |
| us-west-1 | `mastererp-dev-onboarding` | `TenantModuleManagerFunctionRole` | `AWS::IAM::Role` · `mastererp-dev-onboarding-TenantModuleManagerFunctio-Q4te6lbKThqT` | mastererp-dev-onboarding (sin cambio; fuera de F1/F2) |
| us-west-1 | `mastererp-dev-http-apis` | `AgentApiLogGroup` | `AWS::Logs::LogGroup` · `/aws/apigateway/mastererp-dev-api-agent` | mastererp-dev-http-apis (sin cambio; fuera de F1/F2) |
| us-west-1 | `mastererp-dev-http-apis` | `AgentHttpApi` | `AWS::ApiGatewayV2::Api` · `ebn01q74hh` | mastererp-dev-http-apis (sin cambio; fuera de F1/F2) |
| us-west-1 | `mastererp-dev-http-apis` | `AgentHttpApiApiGatewayDefaultStage` | `AWS::ApiGatewayV2::Stage` · `$default` | mastererp-dev-http-apis (sin cambio; fuera de F1/F2) |
| us-west-1 | `mastererp-dev-http-apis` | `ClientApiLogGroup` | `AWS::Logs::LogGroup` · `/aws/apigateway/mastererp-dev-client-api` | mastererp-dev-http-apis (sin cambio; fuera de F1/F2) |
| us-west-1 | `mastererp-dev-http-apis` | `ClientHttpApi` | `AWS::ApiGatewayV2::Api` · `btqqku792c` | mastererp-dev-http-apis (sin cambio; fuera de F1/F2) |
| us-west-1 | `mastererp-dev-http-apis` | `ClientHttpApiApiGatewayDefaultStage` | `AWS::ApiGatewayV2::Stage` · `$default` | mastererp-dev-http-apis (sin cambio; fuera de F1/F2) |
| us-west-1 | `mastererp-dev-http-apis` | `SsmAgentApiId` | `AWS::SSM::Parameter` · `/mastererp/dev/gateways/api-agent-id` | mastererp-dev-http-apis (sin cambio; fuera de F1/F2) |
| us-west-1 | `mastererp-dev-http-apis` | `SsmClientApiId` | `AWS::SSM::Parameter` · `/mastererp/dev/gateways/client-api-id` | mastererp-dev-http-apis (sin cambio; fuera de F1/F2) |

## Nuevo recurso de composición

| Origen | Destino | Efecto |
| --- | --- | --- |
| Stack independiente mastererp-dev-administration (StackId real de la línea base) | mastererp-dev-finance → Administration (AWS::CloudFormation::Stack) | IMPORT del stack existente; no CREATE de otro hijo ni de sus funciones |

## Compatibilidad y secuencia

- AWS::CloudFormation::Stack: FULLY_MUTABLE, identificador /properties/StackId. AWS documenta importar un stack existente como hijo a un nivel. Se usa exactamente esa relación, sin anidar capacidades adicionales.
- Lambda Function, IAM Role, LogGroup, Integration y Route: FULLY_MUTABLE en describe-type. Lambda Permission: IMMUTABLE, identificadores FunctionName/Id. No se usará stack refactor para separar los permisos. La importación del hijo completo evita tocar estos tipos.
- Stack refactor no permite mezclar reorganización con cambios de parámetros/configuración, ni dejar vacío el origen; no es el mecanismo elegido para F1.
- F1 importa usando plantilla desplegada exacta, parámetros y tags del hijo existentes; root con Retain y UpdateReplacePolicy Retain. El change set debe contener un único Import de Administration.
- F2 cambia únicamente composición/parametrización mediante el padre: parámetros dev/qa/prod preparados, ejecución limitada explícitamente a dev y cuenta/región confirmadas. No crear recursos de QA o PROD.
- Recurso compartido consumido actualmente: API qx8nmypdhi por parámetro, stage $default. Cognito y Database conservan propietarios/outputs vigentes y no reciben permisos o conexiones ficticias: estos handlers no los utilizan.
- Dependencias: bucket de artefactos existente privado, plantilla hija publicada por hash, 11 parámetros actuales del hijo y 12 del padre (incluida URL). Outputs del padre retransmiten los ARN de las funciones y referencias de API.

## Recuperación por lote

F1 fallido: detener y revisar IMPORT_ROLLBACK; el hijo y recursos físicos deben conservarse. Si importó y se decide desanidar, preparar otra transición explícita con Retain, sin borrar el stack hijo o recrear sus recursos. No ejecutar una versión antigua del despliegue que trate el hijo como independiente.

F2 fallido: dejar que CloudFormation revierta la actualización del padre; conservar la URL anterior de la plantilla hija por hash y parámetros de F1 para un change set de recuperación. Ningún reemplazo o Remove se autoriza; no reintentar ampliando permisos.

Tras cada lote comparar IDs, hashes de código, roles/configuración, rutas/CORS/JWT y resultados HTTP con la línea base. Repetir drift donde esté soportado. Integration no cubre drift: comparar propiedades directamente.

## Drift previo (no corregir como efecto de esta reorganización)

| Stack | Estado de detección | Resultado |
| --- | --- | --- |
| `mastererp-dev-administration` | DETECTION_COMPLETE | IN_SYNC |
| `mastererp-dev-identity` | DETECTION_COMPLETE | IN_SYNC |
| `mastererp-dev-http-apis` | DETECTION_COMPLETE | IN_SYNC |
| `mastererp-dev-onboarding` | DETECTION_COMPLETE | DRIFTED |
| `mastererp-dev-data` | DETECTION_COMPLETE | DRIFTED |
| `mastererp-dev-application-data-access` | DETECTION_COMPLETE | IN_SYNC |
| `mastererp-dev-uonify-google-connection` | DETECTION_COMPLETE | IN_SYNC |

## Lotes que permanecen separados

- APIs compartidas: Admin API permanece en Onboarding; rutas SAM embebidas y recursos eliminados requieren su transición específica. No reemplazar Body ni borrar rutas obsoletas.
- JWT de agentes permanece en Identidad; no se migra por esta reorganización financiera.
- Database presenta drift previo. No actualizar RDS, su red, secretos, workflow ni migrador; no ejecutar SQL ni crear otro migrador.
- Cinco funciones antiguas ausentes no se recrean. Las seis rutas obsoletas documentadas por DevOps no se eliminan.
- Alojamiento y certificado Uonify permanecen sin cambios; el certificado de us-east-1 está fuera del alcance de ejecución.

## Evidencia y límites

Este mapa precede la ejecución de F1/F2. El resultado real se añadirá al informe FINANCE_HIERARCHY_DEV.md; no se declara migración completada por escribir este archivo. El inventario anterior de DevOps se conserva y esta lectura de us-west-1 lo complementa.

## Resultado posterior

F1 ejecutado: el mismo stack Administración quedó como hijo de mastererp-dev-finance, sin mover o recrear sus 48 recursos individualmente. F2 ejecutado: padre UPDATE_COMPLETE, 11 outputs, sin cambios de recursos. Drift posterior IN_SYNC en padre e hijo. Ver [informe y recuperación](FINANCE_HIERARCHY_DEV.md) y [evidencia](finance-hierarchy-verification-dev.json). Los registros anteriores describen el origen previo; las filas fuera de F1/F2 no cambiaron de propietario.

## Actualización Clientes/Proveedores 2026-11-03

El inventario anterior es histórico. El hijo conserva su StackId y contiene 64 recursos; ocho rutas JWT nuevas y ocho permisos, con dos funciones funcionales. Una reimportación SAM del API eliminó las ocho integraciones/rutas health externas: se recuperaron por su propietario con logical IDs *Recovered y nuevos IDs físicos. Lambdas, roles, logs y permisos originales conservan sus IDs; las otras seis Lambdas su código. Inventario vigente e incidencia: [evidencia](parties-deployment-verification.json) y [procedimiento](ADMINISTRATION_PARTIES.md).
