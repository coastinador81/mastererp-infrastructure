# Architecture

MasterERP se organiza por módulos propietarios de datos. Plataforma Base aporta aislamiento por tenant, seguridad y capacidades compartidas. Uonify es el módulo 0: conversación, memoria, guardas, selección de modelos y orquestación controlada. Su ubicación funcional es modules/0-uonify; el Centro de Agentes lo consume.

Esta arquitectura es agnóstica de proveedor y no describe recursos desplegables.

## Contrato frontend

El [contrato frontend común](FRONTEND_ARCHITECTURE.md) define Uonify como front general y la navegación federada hacia frontends de módulos principales. MasterERP conserva el núcleo de negocio y autorización. Finanzas concentra Administración, Contabilidad y BI en su raíz objetivo; el documento distingue objetivos, DEV documentado y decisiones pendientes.
