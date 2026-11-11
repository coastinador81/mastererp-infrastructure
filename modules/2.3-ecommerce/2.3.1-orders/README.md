# Pedidos

Objetivo específico: Gestionar pedidos y sus transiciones autorizadas.

Responsabilidad: Pedidos, dentro de Ecommerce.
Estado: candidato CloudFormation no desplegado. `resources.yml` declara Lambda
privada, rol mínimo, secreto de credenciales de aplicación, logs y cinco rutas
JWT sobre el API Admin existente, incluida la escritura de notas internas.


## Contrato y estado de esta capa

Código: 2.3.1. Nombre/ruta: `2.3.1-orders`. Objetivo y alcance: los descritos arriba; esta carpeta no amplía las responsabilidades de su módulo padre. Propietario funcional: dominio Ecommerce; responsable nominal pendiente de asignación. Propietario de los datos: módulo que define sus entidades; no copiar datos de otros dominios.

Capa: infraestructura. Dependencias: contexto autenticado, tenant y contratos del padre cuando correspondan; contratos adicionales pendientes de definición. Exclusiones: lógica y recursos de otros módulos; conectores técnicos fuera de Digital Sales. APIs/eventos/MCP: no declarar disponibles por existir esta carpeta; revisar implementación y contrato antes de consumir. Propuestas sin contrato confirmado permanecen pendientes.

Estado verificable: `resources.yml` es JSON/CloudFormation válido localmente y
la estructura del repositorio pasa. No se ejecutó validación remota de AWS ni
se creó/modificó recurso alguno.

Validaciones: `python -m json.tool resources.yml`, `git diff --check` y
`python scripts/validate_structure.py`. Pendientes: composición en el stack,
parámetros DEV, carga del artefacto, change set y smoke test autorizados.


## Despliegue selectivo del adapter de Ventas — DEV

La descripción inicial de plantilla no desplegada es histórica: la inspección AWS del 7 noviembre 2026 confirmó OrdersFunction=mastererp-dev-orders en mastererp-dev-operations, con rutas nativas ya existentes en el API administrativo qx8nmypdhi. Esta tarea no reemplaza la propiedad de ese stack ni despliega de nuevo resources.yml.

`scripts/deploy_orders_sales.py --artifact <orders.zip> --source-commit <sha40> --plan <plan.json>` carga un artefacto Linux inmutable y prepara un change set usando la plantilla vigente y todos los parámetros anteriores salvo OrdersArtifactKey. Revisar el plan; ejecutar con `--plan <plan.json> --execute` solamente si la única modificación es OrdersFunction.Code, Replacement=False. El script comprueba esa condición y conserva IDs físicos y configuración de Lambda. Recuperación: preparar otro change set restaurando el valor old_artifact_key registrado en el plan; no eliminar stacks ni reimportar APIs con SAM/OpenAPI.

El artefacto procede del workflow Validate Orders backend candidate de Platform/dev. Depende de 046+047 de Database, sin SQL ni secretos en este repositorio. 047 acota la confirmación financiera al rol Administradores de Finanzas sin escritura operativa general. API, JWT, CORS, red, roles de ejecución, las otras funciones y sus parámetros permanecen sin cambios.

Estado de esta nota: procedimiento preparado; registrar resultado real del change set y pruebas HTTP antes de afirmar despliegue completado.


### Revisión del change set y arquitectura

La inspección real confirma Lambda Python 3.12 ARM64. El artefacto se construye para Linux ARM64 en CI y se comprueba ELF AArch64 de cada binario; el script rechaza un ZIP x86 antes de cargarlo. El primer change set no se ejecutó: incluía la reevaluación dinámica de OrdersIntegration.IntegrationUri por la referencia OrdersFunction.Arn. Se permite únicamente esa dependencia explícita, Modify sin reemplazo; el script bloquea cualquier otro recurso/cambio y compara después el valor real de integración, rutas completas, JWT, CORS, IDs y configuración de Lambda. No hay cambio funcional de la API por esa reevaluación.


## Resultado real — 7 noviembre 2026

Actualización final ejecutada en mastererp-dev-operations. Fuente Platform e2013ad; ZIP ARM64 SHA-256 61f69a11947e9fe16f0070f846f366c3d2d17a8801c2aa09d289e68c447aadc8. OrdersFunction Active/Successful. El script comprobó igualdad de IDs físicos, configuración, URI de integración, rutas, JWT y CORS, y el checksum real coincide con el ZIP. La única dependencia adicional fue la reevaluación dinámica de OrdersIntegration por el mismo ARN, sin reemplazo.

La primera actualización encontró typing_extensions.py ausente: se restauró por change set el paquete previo exacto 4b34522006c66161dfadc998839808761b1d52501ffefac8ee3a450511e75a5a, coincidente con Git d277dfe para el adapter. Después se desplegó el ZIP corregido y pasaron 14 casos HTTP reales, con tres ventas persistidas y concurrencia. Se conserva evidencia de la recuperación y del plan final en [docs/sales-deployment-evidence](../../../docs/sales-deployment-evidence). Las descripciones anteriores de candidato son históricas.

Sin cambios en Cognito, hosting, API compartida, JWT, CORS, otras Lambdas, IAM de ejecución o red. RDS se gestionó desde Database por su migrador oficial (046/047 y respaldos previos), no desde este script. Los datos de venta de fixture se conservan en tenant DEV suspendido para respetar inmutabilidad.


## Notas, historial y cancelación — 11 noviembre 2026

Se actualizó únicamente `OrdersFunction` en `mastererp-dev-operations` con el
artefacto validado de Platform `027710839c0fb1bce6f81397b9f601614cc2f192`
(SHA-256 `1b0f8b802ff6dea6a4717640ba9303449223144a06f3e51b42144ad158a58eb6`).
El mismo change set añadió la ruta JWT
`POST /v1/companies/{company_id}/orders/{order_id}/notes`, apuntando a la
integración existente de Orders. No se reemplazaron recursos ni cambiaron
Cognito, CORS, IAM, red, IDs físicos u otras Lambdas; Tesorería y sus rutas no
formaron parte del despliegue.

El script admite este caso con `--add-notes-route` al preparar el plan y permite
seleccionar explícitamente el perfil con `--profile`. Antes de ejecutar, valida
que el change set solo contenga `OrdersFunction`, la reevaluación dinámica de
`OrdersIntegration` y `OrdersNotesRoute`. Después comprueba los IDs, la
configuración de Lambda, todas las rutas previas, JWT y CORS.

Verificación DEV: la ruta de notas rechazó una solicitud sin JWT con HTTP 401 y
el smoke autenticado de solo lectura pasó Orders y el resto de capacidades
operativas, incluido el rechazo de un tenant ajeno y la eliminación de la
membresía QA temporal. No se mutaron pedidos ni pagos durante la prueba.
