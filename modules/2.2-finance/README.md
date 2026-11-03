# Finance

Objetivo específico: Coordinar los dominios financieros sin mezclar ejecución operativa.

- **Responsabilidad funcional:** administración, contabilidad, analítica y pagos.
- **Propietario del dato:** Finance.
- **Dependencias:** Plataforma Base.
- **APIs futuras:** finanzas.
- **Herramientas MCP futuras:** finance.query.
- **Estado:** planned.

## Contrato y estado de esta capa

Código: 2.2. Nombre/ruta: `2.2-finance`. Objetivo y alcance: los descritos arriba; esta carpeta no amplía las responsabilidades de su módulo padre. Propietario funcional: dominio Finanzas; responsable nominal pendiente de asignación. Propietario de los datos: módulo que define sus entidades; no copiar datos de otros dominios.

Capa: infraestructura. Dependencias: contexto autenticado, tenant y contratos del padre cuando correspondan; contratos adicionales pendientes de definición. Exclusiones: lógica y recursos de otros módulos; conectores técnicos fuera de Digital Sales. APIs/eventos/MCP: no declarar disponibles por existir esta carpeta; revisar implementación y contrato antes de consumir. Propuestas sin contrato confirmado permanecen pendientes.

Estado verificable: la reserva documental no acredita implementación; conservar cualquier código/plantilla existente y revisar evidencia específica antes de marcar implementado.

Validaciones: estructura local mediante scripts/validate_structure.py. Pendientes: contratos específicos, responsable nominal y pruebas funcionales antes de habilitar esta capacidad.

## Jerarquía de infraestructura

Se conserva la ruta y responsabilidad funcional. La composición Finanzas → Administración y las reservas de Contabilidad/BI se documentan en [docs/FINANCE_HIERARCHY.md](../../docs/FINANCE_HIERARCHY.md). En Infrastructure, cada recurso permanece en el YAML raíz de su carpeta propietaria; una carpeta no obliga a crear un stack. El resultado AWS se informa por separado en el mapa y evidencia de Infrastructure.

## Hosting del frontend financiero

[Procedimiento y evidencia DEV](HOSTING.md). Recursos exclusivos declarados una sola vez en `resources.yml`, IDs FinanceFrontend*. El script extrae esa composición explícita para el stack independiente mastererp-dev-finance-frontend; no despliega ni actualiza el padre backend mastererp-dev-finance. El certificado regional auxiliar está en certificate.yml y usa us-east-1. No hay un frontend propio de Administración ni nuevos recursos en sus carpetas.
