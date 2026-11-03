# Tenant Onboarding

Objetivo específico: Guiar el alta de tenants, conservar su progreso y aprovisionar las capacidades autorizadas.

- **Responsabilidad funcional:** alta y configuración inicial de tenants.
- **Propietario del dato:** Plataforma Base.
- **Dependencias:** identidad y módulos.
- **APIs futuras:** alta y configuración de tenant.
- **Herramientas MCP futuras:** tenant.setup.
- **Estado:** tres Lambdas reportadas en AWS; plantillas individuales enlazadas abajo, pendientes de completar equivalencia y transición de stacks. Código en platform. API Gateway compartidos en `modules/api-gateways.yml`. RDS y migrador en database.

Plantillas heredadas actuales (excepción pendiente de transición; no replicar este patrón para nuevas Lambdas):

- [Sesiones de onboarding](lambdas/onboarding-session-manager/resources.yml).
- [Progreso de onboarding](lambdas/onboarding-progress-tracker/resources.yml).
- [Aprovisionamiento de onboarding](lambdas/onboarding-provisioner/resources.yml).

Estas ubicaciones no acreditan un despliegue consolidado resuelto; la equivalencia e integración con los stacks existentes siguen pendientes.

## Contrato y estado de esta capa

Código: 1.1. Nombre/ruta: `1.1-tenant-onboarding`. Objetivo y alcance: los descritos arriba; esta carpeta no amplía las responsabilidades de su módulo padre. Propietario funcional: dominio Plataforma Base; responsable nominal pendiente de asignación. Propietario de los datos: módulo que define sus entidades; no copiar datos de otros dominios.

Capa: infraestructura. Dependencias: contexto autenticado, tenant y contratos del padre cuando correspondan; contratos adicionales pendientes de definición. Exclusiones: lógica y recursos de otros módulos; conectores técnicos fuera de Digital Sales. APIs/eventos/MCP: no declarar disponibles por existir esta carpeta; revisar implementación y contrato antes de consumir. Propuestas sin contrato confirmado permanecen pendientes.

Estado verificable: parcial: plantillas individuales en lambdas; migración de stacks e integraciones pendiente.

Validaciones: estructura local mediante scripts/validate_structure.py. Pendientes: contratos específicos, responsable nominal y pruebas funcionales antes de habilitar esta capacidad.

Convención vigente: las Lambdas exclusivas de onboarding deberán declararse en el resources.yml raíz del módulo cuando se prepare y autorice su transición. Los enlaces anteriores reflejan ubicaciones reales heredadas; esta corrección documental no mueve recursos ni cambia stacks.

## Reparación selectiva DEV de la base compartida (antecedente)

[resources.yml](resources.yml) es ahora el componente nativo de recursos exclusivos de Onboarding; se combina con el componente compartido de API mediante admin_api_model.py. La reparación de código se limita a sesiones y progreso. Conserva declaraciones históricas de cinco funciones físicamente ausentes para no cambiar otros recursos. NO usar como CREATE ni desplegar sin el guard de [repair_onboarding.py](../../../scripts/repair_onboarding.py). Este script solo permite Modify sin reemplazo de las dos funciones/roles; verifica el grafo completo y paginado del API y no permite volver a introducir SAM/Body.

No se declara completada la transición de stacks ni la reparación de las seis rutas hacia funciones retiradas. Las plantillas por Lambda enlazadas arriba siguen siendo históricas, excluidas de este despliegue. Aprovisionamiento interno y alta/configuración/módulos HTTP requieren reparación separada y evidencia funcional; no se recrean funciones.

Procedimiento y recuperación: [reparación de la base DEV](../../../docs/FOUNDATION_REPAIR_DEV.md).

## Routing nativo vigente

El Admin API se administra por recursos Route/Integration individuales y un ensamblado explícito de configuración compartida. Las referencias SAM/Body anteriores son históricas; no se usan para actualizar el API. Procedimiento y límites: docs/ADMIN_API_DEPLOYMENT.md en la raíz del repositorio. No desplegar directamente los fragmentos ni reimportar OpenAPI sobre rutas modulares.
