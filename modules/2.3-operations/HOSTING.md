# E-commerce DEV hosting

`https://ecom-dev.uonify.com` es la aplicación administrativa independiente
del dominio Operaciones/E-commerce. No sustituye el Storefront comprador ni
`app-dev.uonify.com` y no comparte bucket o distribución con Finanzas.

Stack propietario: `mastererp-dev-ecommerce-frontend` en `us-west-1`.
Certificado propietario: `mastererp-dev-ecommerce-frontend-certificate` en
`us-east-1`. El hosting usa S3 privado con OAC, CloudFront, DNS A/AAAA y rol
GitHub OIDC limitado al repositorio Platform, rama `dev`, bucket y distribución
propios. Los proxys `/v1/uonify/*`, `/v1/companies/*`, `/v1/products*` y
`/v1/catalog/*` conservan Authorization y contexto; las APIs vuelven a
autorizar tenant, empresa y permisos.

Recursos DEV creados el 2026-11-06:

- Bucket: `mastererp-dev-ecommerce-web-277352717693-us-west-1`.
- CloudFront: `ESVCP7ME3HAFA`, `d9ftboa0o6m7y.cloudfront.net`.
- Rol: `mastererp-dev-ecommerce-frontend-github-role`.
- Certificado ACM: `81fb5def-189b-497f-b942-7bc7e1870ee9`.

La publicación manual inicial cargó el build validado y la entrada
`/auth/callback`. HTTPS respondió 200 y ambos proxys devolvieron 401 sin token.
La prueba visual pública aprobó la pantalla de acceso. Falta probar navegador
autenticado y aislamiento con dos tenants antes de considerar cerrado el
módulo.
