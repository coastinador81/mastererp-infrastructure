# Nodos

Objetivo específico: Gestionar nodos de operación y su contexto.

Responsabilidad: Nodos, dentro de Inventario.
Estado: candidato CloudFormation no desplegado: Lambda privada, cuatro rutas JWT,
rol mínimo, secreto de aplicación y VPC.


## Contrato y estado de esta capa

Código: 2.1.2. Nombre/ruta: `2.1.2-nodes`. Objetivo y alcance: los descritos arriba; esta carpeta no amplía las responsabilidades de su módulo padre. Propietario funcional: dominio Inventario; responsable nominal pendiente de asignación. Propietario de los datos: módulo que define sus entidades; no copiar datos de otros dominios.

Capa: infraestructura. Dependencias: contexto autenticado, tenant y contratos del padre cuando correspondan; contratos adicionales pendientes de definición. Exclusiones: lógica y recursos de otros módulos; conectores técnicos fuera de Digital Sales. APIs/eventos/MCP: no declarar disponibles por existir esta carpeta; revisar implementación y contrato antes de consumir. Propuestas sin contrato confirmado permanecen pendientes.

Estado verificable: JSON válido y estructura local; AWS no fue modificado.

Validaciones: estructura local mediante scripts/validate_structure.py. Pendientes: contratos específicos, responsable nominal y pruebas funcionales antes de habilitar esta capacidad.
