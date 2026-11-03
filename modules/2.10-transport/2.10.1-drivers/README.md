# Repartidores

Objetivo específico: Mantener repartidores y su disponibilidad autorizada.

Responsabilidad: Repartidores, dentro de Transporte.
Estado: recursos candidatos declarados, no desplegados.


## Contrato y estado de esta capa

Código: 2.10.1. Nombre/ruta: `2.10.1-drivers`. Objetivo y alcance: los descritos arriba; esta carpeta no amplía las responsabilidades de su módulo padre. Propietario funcional: dominio Transporte; responsable nominal pendiente de asignación. Propietario de los datos: módulo que define sus entidades; no copiar datos de otros dominios.

Capa: infraestructura. Dependencias: contexto autenticado, tenant y contratos del padre cuando correspondan; contratos adicionales pendientes de definición. Exclusiones: lógica y recursos de otros módulos; conectores técnicos fuera de Digital Sales. APIs/eventos/MCP: no declarar disponibles por existir esta carpeta; revisar implementación y contrato antes de consumir. Propuestas sin contrato confirmado permanecen pendientes.

Estado verificable: `resources.yml` declara una Lambda privada, integración al Admin API existente, cinco rutas JWT y permiso de invocación. Consume artefacto, API, authorizer, red y secreto mediante parámetros explícitos.

Validaciones: JSON/estructura local. Pendientes: empaquetado arm64, change set, despliegue DEV y smoke; la plantilla no se aplica implícitamente.
