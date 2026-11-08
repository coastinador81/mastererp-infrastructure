# Agent Center

Objetivo específico: Configurar agentes y flujos que consumen Uonify.

- **Responsabilidad funcional:** agentes, flujos, aprobaciones, canales y auditoría de negocio.
- **Propietario del dato:** Agent Center.
- **Dependencias:** Uonify Core.
- **APIs futuras:** configuración de agentes.
- **Herramientas MCP futuras:** agent_center.manage_agent.
- **Estado:** planned.

## Contrato y estado de esta capa

Código: 2.6. Nombre/ruta: `2.6-agent-center`. Objetivo y alcance: los descritos arriba; esta carpeta no amplía las responsabilidades de su módulo padre. Propietario funcional: dominio Centro de Agentes; responsable nominal pendiente de asignación. Propietario de los datos: módulo que define sus entidades; no copiar datos de otros dominios.

Capa: infraestructura. Dependencias: contexto autenticado, tenant y contratos del padre cuando correspondan; contratos adicionales pendientes de definición. Exclusiones: lógica y recursos de otros módulos; conectores técnicos fuera de Digital Sales. APIs/eventos/MCP: no declarar disponibles por existir esta carpeta; revisar implementación y contrato antes de consumir. Propuestas sin contrato confirmado permanecen pendientes.

Estado verificable: la reserva documental no acredita implementación; conservar cualquier código/plantilla existente y revisar evidencia específica antes de marcar implementado.

Validaciones: estructura local mediante scripts/validate_structure.py. Pendientes: contratos específicos, responsable nominal y pruebas funcionales antes de habilitar esta capacidad.

## Alojamiento público (agentes-dev.uonify.com)

Infraestructura declarada para **S3 + CloudFront + ACM + Route53** y publicación desde este repo:

- Plantillas: `agents-frontend-certificate.json`, `agents-frontend-hosting.json`
- Workflow: `.github/workflows/publish-agents-uonify.yml`
- UI/UX: el código fuente pertenece a `mastererp-platform/frontend/modules/2.6-agent-center/`; Infrastructure no conserva una copia editable.
- Detalle operativo: [HOSTING.md](HOSTING.md)
