# eCommerce

Objetivo específico: Gestionar venta online; catálogo y finanzas conservan sus datos propietarios.

Responsabilidad: eCommerce, dentro de Digital Sales.
Estado: Lambda, administración JWT y catálogo público de solo lectura declarados; no desplegados.


## Contrato y estado de esta capa

Código: 2.4.2. Nombre/ruta: `2.4.2-ecommerce`. Objetivo y alcance: los descritos arriba; esta carpeta no amplía las responsabilidades de su módulo padre. Propietario funcional: dominio Digital Sales; responsable nominal pendiente de asignación. Propietario de los datos: módulo que define sus entidades; no copiar datos de otros dominios.

Capa: infraestructura. Dependencias: contexto autenticado, tenant y contratos del padre cuando correspondan; contratos adicionales pendientes de definición. Exclusiones: lógica y recursos de otros módulos; conectores técnicos fuera de Digital Sales. APIs/eventos/MCP: no declarar disponibles por existir esta carpeta; revisar implementación y contrato antes de consumir. Propuestas sin contrato confirmado permanecen pendientes.

Estado verificable: plantilla parseada, permisos API acotados por ruta y validador estructural aprobado. Change set y despliegue DEV pendientes. Las operaciones administrativas reutilizan Admin API y su authorizer JWT; el catálogo público reutiliza Client API mediante una integración separada.

Validaciones: estructura local mediante scripts/validate_structure.py. Pendientes: contratos específicos, responsable nominal y pruebas funcionales antes de habilitar esta capacidad.
