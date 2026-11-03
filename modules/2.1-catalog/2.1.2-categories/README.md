# Categorías

Objetivo específico: Clasificar productos en categorías coherentes.

Responsabilidad: Categorías, dentro de Catálogo.
Estado: recursos candidatos declarados, no desplegados.


## Contrato y estado de esta capa

Código: 2.1.2. Nombre/ruta: `2.1.2-categories`. Objetivo y alcance: los descritos arriba; esta carpeta no amplía las responsabilidades de su módulo padre. Propietario funcional: dominio Catálogo; responsable nominal pendiente de asignación. Propietario de los datos: módulo que define sus entidades; no copiar datos de otros dominios.

Capa: infraestructura. Dependencias: contexto autenticado, tenant y contratos del padre cuando correspondan; contratos adicionales pendientes de definición. Exclusiones: lógica y recursos de otros módulos; conectores técnicos fuera de Digital Sales. APIs/eventos/MCP: no declarar disponibles por existir esta carpeta; revisar implementación y contrato antes de consumir. Propuestas sin contrato confirmado permanecen pendientes.

Estado verificable: Lambda privada y cuatro rutas JWT conectadas al Admin API mediante parámetros explícitos.

Validaciones: estructura local mediante scripts/validate_structure.py. Pendientes: contratos específicos, responsable nominal y pruebas funcionales antes de habilitar esta capacidad.
