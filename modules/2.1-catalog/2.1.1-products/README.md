# Productos

Objetivo específico: Gestionar identidad y ficha maestra de productos.

Responsabilidad: Productos, dentro de Catálogo.
Estado: candidato CloudFormation no desplegado. Declara Lambda privada, rol
mínimo, secreto de aplicación y cuatro rutas JWT del API Admin.


## Contrato y estado de esta capa

Código: 2.1.1. Nombre/ruta: `2.1.1-products`. Objetivo y alcance: los descritos arriba; esta carpeta no amplía las responsabilidades de su módulo padre. Propietario funcional: dominio Catálogo; responsable nominal pendiente de asignación. Propietario de los datos: módulo que define sus entidades; no copiar datos de otros dominios.

Capa: infraestructura. Dependencias: contexto autenticado, tenant y contratos del padre cuando correspondan; contratos adicionales pendientes de definición. Exclusiones: lógica y recursos de otros módulos; conectores técnicos fuera de Digital Sales. APIs/eventos/MCP: no declarar disponibles por existir esta carpeta; revisar implementación y contrato antes de consumir. Propuestas sin contrato confirmado permanecen pendientes.

Estado verificable: `resources.yml` es JSON/CloudFormation válido localmente y
la estructura pasa. No se consultó ni modificó AWS.

Validaciones: `python -m json.tool resources.yml`, `git diff --check` y
`scripts/validate_structure.py`. Pendiente: composición, change set y despliegue.
