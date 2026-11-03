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
