# Tenant Onboarding

Objetivo específico: Guiar el alta de tenants, conservar su progreso y aprovisionar las capacidades autorizadas.

- **Responsabilidad funcional:** alta y configuración inicial de tenants.
- **Propietario del dato:** Plataforma Base.
- **Dependencias:** identidad y módulos.
- **APIs futuras:** alta y configuración de tenant.
- **Herramientas MCP futuras:** tenant.setup.
- **Estado:** tres Lambdas existentes en AWS; definición reorganizada en `lambdas.yml`, pendiente de completar equivalencia y migración de stack. Código en platform. API Gateway compartidos en `modules/api-gateways.yml`. RDS y migrador en database.

## Contrato y estado de esta capa

Código: 1.1. Nombre/ruta: `1.1-tenant-onboarding`. Objetivo y alcance: los descritos arriba; esta carpeta no amplía las responsabilidades de su módulo padre. Propietario funcional: dominio Plataforma Base; responsable nominal pendiente de asignación. Propietario de los datos: módulo que define sus entidades; no copiar datos de otros dominios.

Capa: infraestructura. Dependencias: contexto autenticado, tenant y contratos del padre cuando correspondan; contratos adicionales pendientes de definición. Exclusiones: lógica y recursos de otros módulos; conectores técnicos fuera de Digital Sales. APIs/eventos/MCP: no declarar disponibles por existir esta carpeta; revisar implementación y contrato antes de consumir. Propuestas sin contrato confirmado permanecen pendientes.

Estado verificable: parcial: plantillas individuales en lambdas; migración de stacks e integraciones pendiente.

Validaciones: estructura local mediante scripts/validate_structure.py. Pendientes: contratos específicos, responsable nominal y pruebas funcionales antes de habilitar esta capacidad.
