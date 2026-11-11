# Rutas

Objetivo específico: Planificar recorridos operativos sin poseer repartidores.

Responsabilidad: Rutas, dentro de Transporte.
Estado: Lambda, rol, logs, integración, seis rutas operativas y dos rutas JWT
del repartidor declarados; no desplegados.

Las rutas nuevas son `GET /driver-route` y `POST
/routes/{route_id}/driver-deliveries/{order_id}` bajo empresa. Ambas reutilizan
la Lambda de Rutas y el mismo authorizer; no crean lógica ni infraestructura
paralela. El Storefront agrega dos rutas JWT equivalentes bajo `/v1/storefront`;
resuelven la empresa por el dominio activo y reutilizan la misma Lambda.


## Contrato y estado de esta capa

Código: 2.10.5. Nombre/ruta: `2.10.5-routes`. Objetivo y alcance: los descritos arriba; esta carpeta no amplía las responsabilidades de su módulo padre. Propietario funcional: dominio Transporte; responsable nominal pendiente de asignación. Propietario de los datos: módulo que define sus entidades; no copiar datos de otros dominios.

Capa: infraestructura. Dependencias: contexto autenticado, tenant y contratos del padre cuando correspondan; contratos adicionales pendientes de definición. Exclusiones: lógica y recursos de otros módulos; conectores técnicos fuera de Digital Sales. APIs/eventos/MCP: no declarar disponibles por existir esta carpeta; revisar implementación y contrato antes de consumir. Propuestas sin contrato confirmado permanecen pendientes.

Estado verificable: plantilla parseada y validador estructural aprobado. Change set y despliegue DEV pendientes.

Validaciones: estructura local mediante scripts/validate_structure.py. Pendientes: contratos específicos, responsable nominal y pruebas funcionales antes de habilitar esta capacidad.
