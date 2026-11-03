# Rutas

Objetivo específico: Planificar recorridos operativos sin poseer repartidores.

Responsabilidad: Rutas, dentro de Operaciones.
Estado: Lambda, rol, logs, integración y seis rutas JWT declarados; no desplegados.


## Contrato y estado de esta capa

Código: 2.3.3. Nombre/ruta: `2.3.3-routes`. Objetivo y alcance: los descritos arriba; esta carpeta no amplía las responsabilidades de su módulo padre. Propietario funcional: dominio Operaciones; responsable nominal pendiente de asignación. Propietario de los datos: módulo que define sus entidades; no copiar datos de otros dominios.

Capa: infraestructura. Dependencias: contexto autenticado, tenant y contratos del padre cuando correspondan; contratos adicionales pendientes de definición. Exclusiones: lógica y recursos de otros módulos; conectores técnicos fuera de Digital Sales. APIs/eventos/MCP: no declarar disponibles por existir esta carpeta; revisar implementación y contrato antes de consumir. Propuestas sin contrato confirmado permanecen pendientes.

Estado verificable: plantilla parseada y validador estructural aprobado. Change set y despliegue DEV pendientes.

Validaciones: estructura local mediante scripts/validate_structure.py. Pendientes: contratos específicos, responsable nominal y pruebas funcionales antes de habilitar esta capacidad.
