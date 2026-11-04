# Publicación del recorrido integrado DEV

El hosting existente mastererp-dev-uonify-hosting conserva bucket privado, OAC, distribución E146MXYK3KTLSB, certificado y app-dev.uonify.com. resources.yml se concilió con la plantilla AWS verificada y añade solo FrontendPublisherRole para el workflow OIDC Platform/dev. No se publica código ajeno sin revisar. La identidad conserva pool/cliente y añade los dos callbacks/logout de Finanzas al cliente existente, mediante su plantilla propietaria.

`python scripts/deploy_integrated_frontend.py identity prepare --output build/integrated-finance` prepara un change set que solo puede modificar WebClient sin reemplazo; revisar antes de cambiar prepare por execute. Igual para hosting: solo se añade el rol de publicación. El ejecutor comprueba cuenta 277352717693, us-west-1 y preserva IDs. No modifica APIs ni reimporta SAM/OpenAPI.

Finanzas continúa en su stack mastererp-dev-finance-frontend. El ejecutor deploy_finance_frontend.py extrae resources.yml del padre funcional; revisar el change set (distribución y referencia DNS dinámica, sin reemplazo). Sus nuevos orígenes son APIs existentes, caché cero; no se despliegan stacks de APIs para habilitar el desarrollo independiente. El mismo JWT y servicios autorizan las peticiones.

Publicación de UI por workflows Platform Publish Uonify frontend DEV y Publish Finance frontend DEV. Tokens OIDC efímeros, scopes S3/CloudFront exclusivos de cada hosting, variables de repositorio no secretas. Build y rollback propios; componentes comunes compilados desde el mismo commit. El callback /auth/callback es un objeto HTML con no-cache. No configurar website público ni fallback SPA: las rutas internas usan hash.

Código backend mínimo mediante update_uonify_artifact.py, paquete revisado de Platform package_uonify.py. Se actualiza el parámetro de artefacto del propietario actual; se comparan código, runtime, red, variables, roles, rutas e integraciones después. La migración 015 pertenece a Database y se aplica solo mediante el migrador oficial. No hay un segundo migrador.

Resultados reales y capturas se registran en Platform/docs/FINANCE_UI_INTEGRATION.md. La integración no se certifica con build o estado CloudFormation únicamente. Restaurar el artefacto anterior y revisar change set inverso si falla; no borrar recursos o datos ni ampliar permisos.
