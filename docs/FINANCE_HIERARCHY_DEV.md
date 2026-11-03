# Jerarquía financiera DEV — despliegue y resultado

Estado comprobado el 2026-11-02, cuenta 277352717693, us-west-1. [Mapa por recurso](FINANCE_RESOURCE_MAP_DEV.md), [reglas de estructura](FOLDER_STANDARD.md), [evidencia de AWS y HTTP](finance-hierarchy-verification-dev.json).

## Jerarquía final

```text
modules/2.2-finance/
├── README.md
├── resources.yml                       # Padre Finanzas: un hijo Administration
├── 2.2.1-administration/
│   ├── README.md
│   ├── resources.yml                   # Plantilla de composición, ensamblar antes de desplegar
│   └── <área o capacidad numerada>/
│       ├── README.md
│       └── resources.yml               # Recursos exclusivos declarados una sola vez
├── 2.2.2-accounting/
│   ├── README.md
│   └── resources.yml                   # Vacío; excluido del despliegue
├── 2.2.3-bi/
│   ├── README.md
│   └── resources.yml                   # Vacío; excluido del despliegue
└── 2.2.4-masterpay/                     # Conservado; sin cambios
```

Stack raíz mastererp-dev-finance → hijo Administration = mastererp-dev-administration. Ambos UPDATE_COMPLETE e IN_SYNC. El hijo conserva su StackId y sus 48 recursos físicos: ocho funciones, ocho roles, ocho logs, ocho rutas, ocho integraciones y ocho permisos. Ninguna capacidad ni pantalla adicional se creó para justificar un stack.

El YAML de Administración declara Metadata.MasterERP.Composition con las ocho rutas de las plantillas propietarias. scripts/deploy_administration.py las ensambla en una plantilla temporal válida; no duplicar esas declaraciones en el padre ni subir el YAML fuente con Resources vacío como si fuera la plantilla ensamblada. El YAML de Finanzas es la plantilla CloudFormation del padre y consume la URL versionada de la hija. Los YAML vacíos de Contabilidad/BI no son plantillas desplegables ni crean stacks.

API ID, stage y artefactos se conectan por parámetros. El padre retransmite ocho ARN de función, AdministrationStackId y dos referencias de API mediante 11 outputs. Identidad y Database conservan sus propietarios y outputs vigentes; estos diagnósticos no consumen datos ni necesitan permisos de identidad o base de datos anticipados.

## Mecanismo elegido

Se evaluaron stack refactor e importación. describe-type confirma Stack FULLY_MUTABLE con StackId, y Lambda Permission IMMUTABLE. Refactorizar individualmente los permisos no es compatible; importar el stack existente completo como hijo a un nivel conserva sus IDs y evita fragmentarlo. No se usan stacks por Lambda o por YAML.

F1 importó una sola referencia AWS::CloudFormation::Stack con DeletionPolicy Retain y UpdateReplacePolicy Retain. La plantilla hija usada fue exactamente la desplegada, sin cambiar sus recursos. F2 publicó la plantilla del padre con outputs y referencias parametrizadas; su change set no contenía cambios de recursos. Ambos change sets se revisaron antes de ejecutarse.

Las fuentes permiten Environment dev/qa/prod para futura preparación; solo se ejecutó dev. El padre desplegado admite esos valores, mientras que el hijo DEV conserva su definición histórica AllowedValues dev porque F2 no requirió cambios del hijo. No se desplegaron QA/PROD. Cada futuro entorno necesita sus API, artefactos y referencias revisados; no reutilizar automáticamente endpoints o código identificador DEV para otro entorno.

## Incidencias y correcciones aplicadas

La primera preparación IMPORT rechazó nuevos outputs; se separaron a F2. Dos ejecuciones IMPORT fueron revertidas por validación de parámetros del hijo. Se conservaron sus recursos. Con autorización del propietario se eliminaron exclusivamente los padres fallidos en ROLLBACK_COMPLETE, tras verificar lista de recursos vacía y que Administración seguía independiente.

La adopción correcta usa exactamente los diez parámetros enviados originalmente al crear Administración. ExistingAdminApiId se añadió más tarde con valor por defecto y no debía aparecer como parámetro explícito del hijo durante IMPORT; el valor efectivo qx8nmypdhi no cambió. F2 restaura la interfaz parametrizada del padre sin cambiar recursos. No generalizar este bootstrap a otro stack sin inventariar sus parámetros reales.

## Comandos reproducibles y límites

Requisitos ya existentes: Python, boto3 y AWS CLI con mastererp-admin. No se instalaron herramientas. Ejecutar desde mastererp-infrastructure. En Windows usar py.

```powershell
py scripts/validate_structure.py
git diff --check
py scripts/verify_finance_preservation.py --output "$env:TEMP/mastererp-finance-hierarchy" --phase before
```

Los cuatro pasos de migración originales fueron prepare-import, execute-import, prepare-update y execute-update de scripts/finance_hierarchy.py, usando --output. Preparar no ejecuta el change set; ejecutar exige el registro revisado del mismo directorio. No repetir IMPORT: el script rechaza un hijo ya anidado. No incluir un borrado automático de stacks como recuperación.

Para revisar una actualización equivalente después de esta adopción:

```powershell
py scripts/finance_hierarchy.py --output "$env:TEMP/mastererp-finance-hierarchy" --action prepare-update
# Revisar finance-update-plan.json, outputs, parámetros y cualquier cambio antes de ejecutar.
py scripts/finance_hierarchy.py --output "$env:TEMP/mastererp-finance-hierarchy" --action execute-update
py scripts/verify_finance_preservation.py --output "$env:TEMP/mastererp-finance-hierarchy" --phase after-update
```

finance_hierarchy.py es una herramienta de adopción/equivalencia: exige las mismas 48 propiedades de recursos, no es un permiso para introducir nuevas operaciones. Una futura función o cambio de código necesita preparar artefactos y un change set nuevo desde el padre, con revisión del alcance. No actualizar directamente el hijo: deploy_administration.py --deploy rechaza esa operación cuando detecta ParentId. Su modo sin --deploy sigue disponible para empaquetado/validación local.

## Pruebas reales

Antes de F1, después de F1 y después de F2:

- Ocho HTTP GET health de Administración: 200, JSON exacto y nombre esperado.
- Dos rutas Uonify sin token: 401; su autenticación no se relajó.
- Tres API: configuración, CORS, rutas, integraciones y autorizadores idénticos por ID.
- Trece Lambdas: mismos ARN, hashes de código, roles, runtime, memoria, timeout y LastModified.
- Cuarenta y ocho recursos de Administración: mismos ID lógicos/físicos y tipos.
- Metadatos RDS: mismo ARN, endpoint, motor, clase y almacenamiento, sin conectar ni ejecutar SQL.

Drift antes: Administración, Identidad, APIs compartidas, application-data-access y Uonify IN_SYNC. Onboarding y Database DRIFTED previamente. Drift después: Finanzas y Administración IN_SYNC. Integration no ofrece cobertura de drift completa; se comparó su configuración directamente.

No se probaron login autorizado, operaciones de tenant, flujos funcionales ni restauración de RDS en esta tarea. Los diagnósticos públicos no acreditan operaciones de negocio. No se invocó el migrador ni se modificaron datos.

## Recuperación

Mantener las URLs de plantilla por hash y los registros de change sets. Ante un fallo de actualización revisar eventos y rollback del padre; no borrar el hijo. Si se decide retirar la relación anidada, preparar otra transición con Retain y comprobar su efecto antes de ejecutarla; no implica eliminar Administración o sus recursos. No reintentar un lote ampliando permisos ni volver a una versión antigua del script que actualice directamente el hijo.

## Pendientes fuera del lote financiero

Admin API sigue siendo propiedad de mastererp-dev-onboarding; JWT de agentes permanece en Identidad. La separación de rutas SAM embebidas exige su lote específico. Cinco funciones antiguas ausentes no se recrearon y seis rutas obsoletas no se borraron. Database, migrador, Cognito, hosting y certificado Uonify no se recrearon. El drift previo de Onboarding/Database queda al equipo DevOps, separado de esta adopción.

[Importar un stack existente como hijo](https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/resource-import-nested-stacks.html) y [limitaciones de stack refactor](https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/stack-refactoring.html): referencias del mecanismo, no sustituyen la evidencia real adjunta.

## Actualización Clientes/Proveedores 2026-11-03

El inventario anterior es histórico. El hijo conserva su StackId y contiene 64 recursos; ocho rutas JWT nuevas y ocho permisos, con dos funciones funcionales. Una reimportación SAM del API eliminó las ocho integraciones/rutas health externas: se recuperaron por su propietario con logical IDs *Recovered y nuevos IDs físicos. Lambdas, roles, logs y permisos originales conservan sus IDs; las otras seis Lambdas su código. Inventario vigente e incidencia: [evidencia](parties-deployment-verification.json) y [procedimiento](ADMINISTRATION_PARTIES.md).
