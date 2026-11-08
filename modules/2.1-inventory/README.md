# Inventario

Objetivo general: Administrar existencias, reservas, movimientos, recepciones, conteos y ajustes; Nodos y Preparación se referencian desde Ecommerce según la decisión del propietario.

Responsabilidad: Inventario, en la capa modules. Estado: estructura organizativa; capacidades existentes trasladadas conservando sus contratos.

Dependencias: identidad, autorización y contratos compartidos según el módulo; no crear datos ni recursos duplicados. Propietario funcional: Inventario; responsable nominal pendiente.

UX/UI: consultar el estándar común docs/UX_UI_STANDARD.md desde la raíz. No se implementan funciones por crear esta carpeta.

Hosting independiente de la base visual DEV en resources.yml raíz; ACM regional separado en certificate.yml. Ver [FRONTEND_HOSTING.md](FRONTEND_HOSTING.md) para propiedad, change sets, publicación y recuperación. No se modifican recursos de los submódulos históricos.
