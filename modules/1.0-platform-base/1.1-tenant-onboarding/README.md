# Tenant Onboarding

- **Responsabilidad funcional:** alta y configuración inicial de tenants.
- **Propietario del dato:** Plataforma Base.
- **Dependencias:** identidad y módulos.
- **APIs futuras:** alta y configuración de tenant.
- **Herramientas MCP futuras:** tenant.setup.
- **Estado:** tres Lambdas existentes en AWS; definición reorganizada en `lambdas.yml`, pendiente de completar equivalencia y migración de stack. Código en platform. API Gateway compartidos en `modules/api-gateways.yml`. RDS y migrador en database.
