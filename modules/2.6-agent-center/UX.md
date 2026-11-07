# Centro de Agentes — guía de UI/UX

Esta entrada (**agentes-dev.uonify.com**) comparte criterios con **Finanzas** para que la experiencia sea reconocible dentro del ecosistema MasterERP/Uonify.

## Referencia principal

- **Tema y tokens:** [frontend/modules/2.2-finance/src/finance.css](https://github.com/eticayservicios/mastererp-platform/blob/dev/frontend/modules/2.2-finance/src/finance.css) en `mastererp-platform-frontend-wt`, ámbito `.finance-app` y variables `--finance-*`.
- **Acabado descrito en README:** sección *Acabado visual de Finanzas* en [frontend/modules/2.2-finance/README.md](https://github.com/eticayservicios/mastererp-platform/blob/dev/frontend/modules/2.2-finance/README.md) (menú blanco, fondo gris azulado `#F6F8FC`, acentos azules, sombras mínimas, Inter).

## Qué replica esta página estática

- Clase raíz **`finance-app`** en `<html>` y el mismo conjunto de tokens de color, radios y espaciado que Finanzas.
- Patrones de layout tipo shell: **cabecera** (`integrated-header`), **navegación lateral** (`integrated-nav`), **contenido** (`integrated-content`), **eyebrow**, **título** y **tarjetas** (`panel` / `module-card`), alineado con [Finance.jsx](https://github.com/eticayservicios/mastererp-platform/blob/dev/frontend/modules/2.2-finance/src/Finance.jsx) y estilos compartidos.
- Fuente **Inter** (400/500/600) vía Google Fonts en la landing estática; el producto Vite de Finanzas sirve Inter desde el bundle propio.

## Evolución

Cuando el Centro de Agentes tenga aplicación Vite propia (como Finanzas), debe importar el mismo `finance.css` o un tema compartido extraído a `frontend/shared`, manteniendo el ámbito por clase para no contaminar el shell Uonify.

Fuentes de verdad de dominio en Platform: [FRONTEND_ARCHITECTURE.md](https://github.com/eticayservicios/mastererp-platform/blob/dev/docs/FRONTEND_ARCHITECTURE.md) y [MODULE_REGISTRY.md](https://github.com/eticayservicios/mastererp-platform/blob/dev/docs/MODULE_REGISTRY.md) (2.6-agent-center).

## Lanzador común de aplicaciones

Los nueve puntos usan el Web Component oficial de Platform (`frontend/shared/module-launcher/module-launcher.mjs`), copiado como asset generado con manifiesto SHA-256. El encabezado identifica Agentes como sitio actual y ofrece Finanzas y Ecommerce por sus subdominios; los otros ocho módulos quedan pendientes. No es una nueva implementación ni contiene bypass de autenticación. Escape, foco, clic fuera y móvil se prueban en el mismo componente de los tres sitios. No editar `agents-static/shared/module-launcher.mjs` a mano: generar con `node scripts/sync_module_launcher.mjs` desde Platform y verificar `--check`.
