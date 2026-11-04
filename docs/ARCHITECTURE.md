# Architecture

MasterERP se organiza por módulos propietarios de datos. Plataforma Base aporta aislamiento por tenant, seguridad y capacidades compartidas. Uonify es el módulo 0: conversación, memoria, guardas, selección de modelos y orquestación controlada. Su ubicación funcional es modules/0-uonify; el Centro de Agentes lo consume.

Esta arquitectura es agnóstica de proveedor y no describe recursos desplegables.

## Contrato frontend

El [contrato frontend común](FRONTEND_ARCHITECTURE.md) define app-dev.uonify.com como entrada general DEV a un espacio con dashboard, chat y menú de módulos habilitados y autorizados. Las pantallas se presentan dentro de Uonify con identidad y contexto comunes; el primer recorrido integra Clientes/Proveedores por composición en build, con resultados reales en Platform/docs/FINANCE_UI_INTEGRATION.md. Finanzas agrupa Administración, Contabilidad y BI y mantiene entrega propia. Su hosting independiente DEV existe para desarrollo y pruebas, sin imponer una raíz productiva financiera. MasterERP conserva el núcleo de negocio y la autorización de cada API.
