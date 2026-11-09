# Nexus infrastructure

Código: `0.3`.

Responsabilidad: alojar el frontend DEV independiente de Nexus en `https://nexus-dev.uonify.com`.

Recursos definidos: certificado ACM DNS-validado en `us-east-1`; bucket S3 privado, Origin Access Control, distribución CloudFront, política de acceso mínimo y alias Route 53 A/AAAA en la región de hosting.

Estado: definiciones listas para revisión, sin stack desplegado, sin DNS aplicado y sin artefactos publicados. El bucket no admite acceso público; solo CloudFront puede leer objetos mediante OAC.

Entradas: `Environment`, `FrontendDomainName`, `FrontendHostedZoneId` y el ARN del certificado. Salidas: bucket, distribución y URL. El despliegue debe crear primero el certificado en `us-east-1` y pasar su ARN al stack de hosting.

Correspondencia: `frontend/modules/0-uonify/0.3-nexus` y `backend/modules/0-uonify/0.3-nexus` en Platform; `modules/0-uonify/0.3-nexus` en Database.
