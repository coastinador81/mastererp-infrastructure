# Pedidos

Objetivo específico: Gestionar pedidos y sus transiciones autorizadas.

Responsabilidad: Pedidos, dentro de Operaciones.
Estado: candidato CloudFormation no desplegado. `resources.yml` declara Lambda
privada, rol mínimo, secreto de credenciales de aplicación, logs y cuatro rutas
JWT sobre el API Admin existente.


## Contrato y estado de esta capa

Código: 2.3.1. Nombre/ruta: `2.3.1-orders`. Objetivo y alcance: los descritos arriba; esta carpeta no amplía las responsabilidades de su módulo padre. Propietario funcional: dominio Operaciones; responsable nominal pendiente de asignación. Propietario de los datos: módulo que define sus entidades; no copiar datos de otros dominios.

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
